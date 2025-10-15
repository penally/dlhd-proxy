import json
import html
import re
from importlib import resources
from typing import Iterable, List
from urllib.parse import quote, urlparse

import reflex as rx
from curl_cffi import AsyncSession

from .utils import decode_bundle, decrypt, encrypt, urlsafe_base64
from rxconfig import config


class Channel(rx.Base):
    id: str
    name: str
    tags: List[str]
    logo: str | None


class StepDaddy:
    def __init__(self):
        socks5 = config.socks5
        if socks5 != "":
            self._session = AsyncSession(proxy="socks5://" + socks5)
        else:
            self._session = AsyncSession()
        self._base_url = "https://daddylivestream.com"
        self.channels: list[Channel] = []
        try:
            meta_data = resources.files(__package__).joinpath("meta.json").read_text()
            self._meta = json.loads(meta_data)
        except Exception:
            self._meta = {}

    def _headers(self, referer: str = None, origin: str = None):
        if referer is None:
            referer = self._base_url
        headers = {
            "Referer": referer,
            "user-agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:137.0) Gecko/20100101 Firefox/137.0",
        }
        if origin:
            headers["Origin"] = origin
        return headers

    async def load_channels(self):
        channels = []
        try:
            response = await self._session.get(
                f"{self._base_url}/24-7-channels.php", headers=self._headers()
            )
            if response.status_code >= 400:
                raise ValueError(
                    f"Failed to load channels: HTTP {response.status_code}"
                )
            matches = re.findall(
                r'href="/stream/stream-(\d+)\.php"[^>]*>.*?<strong>(.*?)</strong>',
                response.text,
                re.DOTALL,
            )
            seen_ids = set()
            for channel_id, channel_name in matches:
                if channel_id in seen_ids:
                    continue
                seen_ids.add(channel_id)
                channel_name = html.unescape(channel_name.strip()).replace("#", "")
                meta = self._meta.get("18+" if channel_name.startswith("18+") else channel_name, {})
                logo = meta.get("logo", "")
                if logo:
                    logo = f"{config.api_url}/logo/{urlsafe_base64(logo)}"
                channels.append(Channel(id=channel_id, name=channel_name, tags=meta.get("tags", []), logo=logo))
        finally:
            self._enumerate_duplicate_names(channels)
            self.channels = sorted(
                channels,
                key=lambda channel: (channel.name.startswith("18"), channel.name),
            )

    async def stream(self, channel_id: str):
        key = "CHANNEL_KEY"
        url = f"{self._base_url}/stream/stream-{channel_id}.php"
        response = await self._session.get(url, headers=self._headers())
        matches = re.compile("iframe src=\"(.*)\" width").findall(response.text)
        if matches:
            source_url = matches[0]
            source_response = await self._session.get(source_url, headers=self._headers(url))
        else:
            raise ValueError("Failed to find source URL for channel")

        channel_key = re.compile(rf"const\s+{re.escape(key)}\s*=\s*\"(.*?)\";").findall(source_response.text)[-1]

        data = decode_bundle(source_response.text)
        auth_ts = data.get("b_ts", "")
        auth_sig = data.get("b_sig", "")
        auth_rnd = data.get("b_rnd", "")
        auth_url = data.get("b_host", "")
        auth_request_url = f"{auth_url}auth.php?channel_id={channel_key}&ts={auth_ts}&rnd={auth_rnd}&sig={auth_sig}"
        auth_response = await self._session.get(
            auth_request_url, headers=self._headers(source_url)
        )
        if auth_response.status_code != 200:
            raise ValueError("Failed to get auth response")
        key_url = urlparse(source_url)
        key_url = f"{key_url.scheme}://{key_url.netloc}/server_lookup.php?channel_id={channel_key}"
        key_response = await self._session.get(key_url, headers=self._headers(source_url))
        server_key = key_response.json().get("server_key")
        if not server_key:
            raise ValueError("No server key found in response")
        if server_key == "top1/cdn":
            server_url = f"https://top1.newkso.ru/top1/cdn/{channel_key}/mono.m3u8"
        else:
            server_url = f"https://{server_key}new.newkso.ru/{server_key}/{channel_key}/mono.m3u8"
        m3u8 = await self._session.get(
            server_url, headers=self._headers(quote(str(source_url)))
        )
        m3u8_data = ""
        for line in m3u8.text.split("\n"):
            if line.startswith("#EXT-X-KEY:"):
                original_url = re.search(r'URI="(.*?)"', line).group(1)
                line = line.replace(original_url, f"{config.api_url}/key/{encrypt(original_url)}/{encrypt(urlparse(source_url).netloc)}")
            elif line.startswith("http") and config.proxy_content:
                line = f"{config.api_url}/content/{encrypt(line)}"
            m3u8_data += line + "\n"
        return m3u8_data

    async def key(self, url: str, host: str):
        url = decrypt(url)
        host = decrypt(host)
        response = await self._session.get(url, headers=self._headers(f"{host}/", host), timeout=60)
        if response.status_code != 200:
            raise Exception(f"Failed to get key")
        return response.content

    @staticmethod
    def content_url(path: str):
        return decrypt(path)

    def playlist(self, channels: Iterable[Channel] | None = None):
        data = "#EXTM3U\n"
        channels = list(channels) if channels is not None else self.channels
        for channel in channels:
            entry = f" tvg-logo=\"{channel.logo}\",{channel.name}" if channel.logo else f",{channel.name}"
            data += f"#EXTINF:-1{entry}\n{config.api_url}/stream/{channel.id}.m3u8\n"
        return data

    async def schedule(self):
        response = await self._session.get(
            f"{self._base_url}/schedule/schedule-generated.php",
            headers=self._headers(),
        )
        if response.status_code >= 400:
            raise ValueError(
                f"Failed to fetch schedule: HTTP {response.status_code}"
            )
        return response.json()

    async def aclose(self) -> None:
        await self._session.aclose()

    @staticmethod
    def _enumerate_duplicate_names(channels: Iterable[Channel]) -> None:
        channel_list = list(channels)
        counts: dict[str, int] = {}
        for channel in channel_list:
            counts[channel.name] = counts.get(channel.name, 0) + 1

        seen: dict[str, int] = {}
        for channel in channel_list:
            if counts[channel.name] > 1:
                seen[channel.name] = seen.get(channel.name, 0) + 1
                channel.name = f"{channel.name} ({seen[channel.name]})"
