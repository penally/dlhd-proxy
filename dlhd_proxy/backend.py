import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re

import httpx
from dateutil import parser
from xml.etree.ElementTree import Element, SubElement, tostring

from dlhd_proxy.step_daddy import StepDaddy, Channel
from fastapi import Response, status, FastAPI
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from rxconfig import config
from .utils import urlsafe_base64_decode

GUIDE_FILE = Path("guide.xml")
CHANNEL_FILE = Path("channels.json")


fastapi_app = FastAPI()
step_daddy = StepDaddy()
client = httpx.AsyncClient(http2=True, timeout=None)


def get_selected_channel_ids() -> set[str]:
    """Return the set of enabled channel IDs."""
    if CHANNEL_FILE.exists():
        try:
            return set(json.loads(CHANNEL_FILE.read_text()))
        except Exception:
            pass
    return {ch.id for ch in step_daddy.channels}


def set_selected_channel_ids(ids: list[str]) -> None:
    """Persist the selected channel IDs to disk."""
    CHANNEL_FILE.write_text(json.dumps(ids))


@fastapi_app.get("/stream/{channel_id}.m3u8")
async def stream(channel_id: str):
    try:
        return Response(
            content=await step_daddy.stream(channel_id),
            media_type="application/vnd.apple.mpegurl",
            headers={f"Content-Disposition": f"attachment; filename={channel_id}.m3u8"}
        )
    except IndexError:
        return JSONResponse(content={"error": "Stream not found"}, status_code=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@fastapi_app.get("/key/{url}/{host}")
async def key(url: str, host: str):
    try:
        return Response(
            content=await step_daddy.key(url, host),
            media_type="application/octet-stream",
            headers={"Content-Disposition": "attachment; filename=key"}
        )
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@fastapi_app.get("/content/{path}")
async def content(path: str):
    try:
        async def proxy_stream():
            async with client.stream("GET", step_daddy.content_url(path), timeout=60) as response:
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    yield chunk
        return StreamingResponse(proxy_stream(), media_type="application/octet-stream")
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def update_channels():
    while True:
        try:
            await step_daddy.load_channels()
            await asyncio.sleep(300)
        except asyncio.CancelledError:
            continue


def get_channels():
    return step_daddy.channels


def get_enabled_channels():
    selected = get_selected_channel_ids()
    return [ch for ch in step_daddy.channels if ch.id in selected]


def get_channel(channel_id) -> Channel | None:
    if not channel_id or channel_id == "":
        return None
    return next((channel for channel in step_daddy.channels if channel.id == channel_id), None)


@fastapi_app.get("/playlist.m3u8")
def playlist():
    selected = get_selected_channel_ids()
    channels = [ch for ch in step_daddy.channels if ch.id in selected]
    return Response(
        content=step_daddy.playlist(channels),
        media_type="application/vnd.apple.mpegurl",
        headers={"Content-Disposition": "attachment; filename=playlist.m3u8"},
    )


async def get_schedule():
    schedule = await step_daddy.schedule()
    selected = get_selected_channel_ids()

    # Build lookup maps for resolving channel name/id mismatches.
    id_to_name = {ch.id: ch.name for ch in step_daddy.channels}

    def norm(name: str) -> str:
        """Return a simplified version of a channel name."""
        return re.sub(r"\W+", "", name or "").lower()

    name_to_id: dict[str, str] = {}
    for ch in step_daddy.channels:
        key = norm(ch.name)
        # Prefer selected channels when multiple share the same name.
        if key not in name_to_id or ch.id in selected:
            name_to_id[key] = ch.id

    def filter_channels(data):
        def resolve(chan: dict):
            cid = str(chan.get("channel_id", ""))
            name = chan.get("channel_name", "")
            mapped = name_to_id.get(norm(name))
            if id_to_name.get(cid) != name:
                if mapped:
                    cid = mapped
                else:
                    return None
            if cid in selected:
                chan = chan.copy()
                chan["channel_id"] = cid
                return chan
            return None

        if isinstance(data, list):
            return [c for c in (resolve(x) for x in data) if c]
        if isinstance(data, dict):
            return {k: v for k, v in ((k, resolve(v)) for k, v in data.items()) if v}
        return []

    filtered = {}
    for day, categories in schedule.items():
        for category, events in categories.items():
            new_events = []
            for event in events:
                ch1 = filter_channels(event.get("channels"))
                ch2 = filter_channels(event.get("channels2"))
                if not ch1 and not ch2:
                    continue
                e = event.copy()
                if ch1:
                    e["channels"] = ch1
                else:
                    e.pop("channels", None)
                if ch2:
                    e["channels2"] = ch2
                else:
                    e.pop("channels2", None)
                new_events.append(e)
            if new_events:
                filtered.setdefault(day, {})[category] = new_events
    return filtered


@fastapi_app.get("/logo/{logo}")
async def logo(logo: str):
    url = urlsafe_base64_decode(logo)
    file = url.split("/")[-1]
    if not os.path.exists("./logo-cache"):
        os.makedirs("./logo-cache")
    if os.path.exists(f"./logo-cache/{file}"):
        return FileResponse(f"./logo-cache/{file}")
    try:
        response = await client.get(url, headers={"user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0"})
        if response.status_code == 200:
            with open(f"./logo-cache/{file}", "wb") as f:
                f.write(response.content)
            return FileResponse(f"./logo-cache/{file}")
        else:
            return JSONResponse(content={"error": "Logo not found"}, status_code=status.HTTP_404_NOT_FOUND)
    except httpx.ConnectTimeout:
        return JSONResponse(content={"error": "Request timed out"}, status_code=status.HTTP_504_GATEWAY_TIMEOUT)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


async def generate_guide():
    """Fetch schedule and write an updated guide.xml file."""
    schedule = await get_schedule()
    selected = get_selected_channel_ids()

    root = Element("tv", attrib={"generator-info-name": "dlhd-proxy"})
    added_channels = set()

    # Known channels with logos
    for ch in step_daddy.channels:
        if ch.id not in selected:
            continue
        channel_elem = SubElement(root, "channel", id=ch.id)
        SubElement(channel_elem, "display-name").text = ch.name
        if ch.logo:
            SubElement(channel_elem, "icon", src=ch.logo)
        added_channels.add(ch.id)

    def ensure_channel(channel: dict):
        cid = channel.get("channel_id")
        if cid and cid in selected and cid not in added_channels:
            elem = SubElement(root, "channel", id=cid)
            SubElement(elem, "display-name").text = channel.get("channel_name", cid)
            added_channels.add(cid)

    def iter_channels(data):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return list(data.values())
        return []

    local_tz = ZoneInfo(config.timezone)
    utc = ZoneInfo("UTC")

    for day, categories in schedule.items():
        date = parser.parse(day.split(" - ")[0], dayfirst=True)
        for category, events in categories.items():
            for event in events:
                hour, minute = map(int, event["time"].split(":"))
                start_local = date.replace(hour=hour, minute=minute, tzinfo=local_tz)
                start = start_local.astimezone(utc)
                stop = start + timedelta(hours=1)
                for channel in iter_channels(event.get("channels")) + iter_channels(event.get("channels2")):
                    ensure_channel(channel)
                    programme = SubElement(
                        root,
                        "programme",
                        start=start.strftime("%Y%m%d%H%M%S +0000"),
                        stop=stop.strftime("%Y%m%d%H%M%S +0000"),
                        channel=channel.get("channel_id"),
                    )
                    SubElement(programme, "title", lang="en").text = event.get("event")
                    SubElement(programme, "category").text = category

    xml_data = tostring(root, encoding="utf-8", xml_declaration=True)
    GUIDE_FILE.write_bytes(xml_data)


@fastapi_app.get("/guide.xml")
async def guide():
    """Return the cached XMLTV guide, generating it if needed."""
    if not GUIDE_FILE.exists():
        await generate_guide()
    return FileResponse(GUIDE_FILE)


async def auto_update_guide():
    """Update guide.xml once per day at the configured time."""
    hour, minute = map(int, config.guide_update.split(":"))
    tz = ZoneInfo(config.timezone)
    if not GUIDE_FILE.exists():
        try:
            await generate_guide()
        except Exception:
            pass
    while True:
        now = datetime.now(tz)
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await asyncio.sleep((target - now).total_seconds())
        try:
            await generate_guide()
        except asyncio.CancelledError:
            break
        except Exception:
            continue

