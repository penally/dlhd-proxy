import asyncio
from pathlib import Path

from xml.etree import ElementTree

from dlhd_proxy import backend
from dlhd_proxy.step_daddy import Channel


def test_generate_guide_uses_enumerated_names(tmp_path, monkeypatch):
    guide_path = tmp_path / "guide.xml"
    monkeypatch.setattr(backend, "GUIDE_FILE", guide_path)

    channels = [
        Channel(id="1", name="MLB League Pass (1)", tags=[], logo=""),
        Channel(id="2", name="MLB League Pass (2)", tags=[], logo=""),
    ]
    monkeypatch.setattr(backend.step_daddy, "channels", channels, raising=False)

    async def fake_get_schedule():
        return {
            "01-01-2024 - Monday": {
                "Sports": [
                    {
                        "time": "12:00",
                        "event": "Game",
                        "channels": [
                            {"channel_id": "1", "channel_name": "MLB League Pass"},
                            {"channel_id": "2", "channel_name": "MLB League Pass"},
                        ],
                    }
                ]
            }
        }

    monkeypatch.setattr(backend, "get_schedule", fake_get_schedule)
    monkeypatch.setattr(backend, "get_selected_channel_ids", lambda: {"1", "2"})

    asyncio.run(backend.generate_guide())

    tree = ElementTree.parse(Path(guide_path))
    channel_names = [
        channel.findtext("display-name") for channel in tree.findall("channel")
    ]

    assert channel_names == ["MLB League Pass (1)", "MLB League Pass (2)"]


def test_get_schedule_keeps_events_with_duplicate_channel_names(monkeypatch):
    channels = [
        Channel(id="1", name="MLB League Pass (1)", tags=[], logo=""),
        Channel(id="2", name="MLB League Pass (2)", tags=[], logo=""),
    ]
    monkeypatch.setattr(backend.step_daddy, "channels", channels, raising=False)

    async def fake_schedule():
        return {
            "01-02-2024 - Tuesday": {
                "Sports": [
                    {
                        "time": "15:00",
                        "event": "Afternoon Game",
                        "channels": [
                            {"channel_id": "999", "channel_name": "MLB League Pass"},
                            {"channel_id": "2", "channel_name": "MLB League Pass (2)"},
                        ],
                    }
                ]
            }
        }

    monkeypatch.setattr(backend.step_daddy, "schedule", fake_schedule, raising=False)
    monkeypatch.setattr(backend, "get_selected_channel_ids", lambda: {"1"})

    schedule = asyncio.run(backend.get_schedule())

    day = "01-02-2024 - Tuesday"
    assert day in schedule
    events = schedule[day]["Sports"]
    assert len(events) == 1
    channels_out = events[0]["channels"]
    assert channels_out == [
        {"channel_id": "1", "channel_name": "MLB League Pass"}
    ]
