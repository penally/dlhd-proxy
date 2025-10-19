import asyncio

from dlhd_proxy.step_daddy import Channel, StepDaddy
from dlhd_proxy.utils import urlsafe_base64
from rxconfig import config


def test_enumerate_duplicate_names():
    channels = [
        Channel(id="1", name="MLB League Pass", tags=[], logo="logo1"),
        Channel(id="2", name="MLB League Pass", tags=[], logo="logo2"),
        Channel(id="3", name="Other", tags=[], logo="logo3"),
        Channel(id="4", name="MLB League Pass", tags=[], logo="logo4"),
    ]

    StepDaddy._enumerate_duplicate_names(channels)

    assert [channel.name for channel in channels] == [
        "MLB League Pass (1)",
        "MLB League Pass (2)",
        "Other",
        "MLB League Pass (3)",
    ]


def test_load_channels_parses_stream_list(monkeypatch):
    html = """
    <div class="grid">
        <a class="card" href="/watch.php?id=149" data-title="espn sur">
            <div class="card__title">ESPN SUR</div>
            <div class="">ID: 149</div>
        </a>
        <a class="card" href="/watch.php?id=150" data-title="18+ (player-01)">
            <div class="card__title">18+ (Player-01)</div>
            <div class="">ID: 150</div>
        </a>
    </div>
    """

    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

    class FakeSession:
        async def get(self, *_args, **_kwargs):
            return FakeResponse(html)

    step_daddy = StepDaddy()
    monkeypatch.setattr(step_daddy, "_session", FakeSession(), raising=False)

    step_daddy._meta = {
        "ESPN SUR": {"logo": "https://cdn.example.com/espn-sur.png", "tags": ["sports"]},
        "18+": {"logo": "https://cdn.example.com/adult.png", "tags": ["adult"]},
    }

    asyncio.run(step_daddy.load_channels())

    assert [channel.id for channel in step_daddy.channels] == ["149", "150"]

    channel_one = step_daddy.channels[0]
    assert channel_one.name == "ESPN SUR"
    assert channel_one.tags == ["sports"]
    assert channel_one.logo == (
        f"{config.api_url}/logo/{urlsafe_base64('https://cdn.example.com/espn-sur.png')}"
    )

    channel_two = step_daddy.channels[1]
    assert channel_two.name == "18+ (Player-01)"
    assert channel_two.tags == ["adult"]
    assert channel_two.logo == (
        f"{config.api_url}/logo/{urlsafe_base64('https://cdn.example.com/adult.png')}"
    )


def test_load_channels_logs_request_status(monkeypatch, caplog):
    html = """
    <div class="grid">
        <a class="card" href="/watch.php?id=149">
            <div class="card__title">ESPN SUR</div>
        </a>
    </div>
    """

    class FakeResponse:
        def __init__(self, text: str, status_code: int = 200):
            self.text = text
            self.status_code = status_code

    class FakeSession:
        async def get(self, *_args, **_kwargs):
            return FakeResponse(html)

    step_daddy = StepDaddy()
    monkeypatch.setattr(step_daddy, "_session", FakeSession(), raising=False)

    caplog.set_level("INFO")
    asyncio.run(step_daddy.load_channels())

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "Request to https://daddylivestream.com/24-7-channels.php succeeded with HTTP 200"
        in message
        for message in messages
    )
