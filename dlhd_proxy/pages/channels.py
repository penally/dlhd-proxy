import reflex as rx
from typing import List, Optional, TypedDict
from dlhd_proxy import backend
from dlhd_proxy.components import navbar
import re


class ChannelItem(TypedDict):
    id: str
    name: str
    enabled: bool
    country: Optional[str]


COUNTRY_SUFFIXES = ["US", "UK", "Israel", "Spain"]


def get_country(name: str) -> Optional[str]:
    parts = name.split()
    if not parts:
        return None
    last = parts[-1]
    if last in COUNTRY_SUFFIXES:
        return last
    if len(parts) >= 2 and parts[-2] in COUNTRY_SUFFIXES and re.fullmatch(r"HD|FHD|4K", last):
        return parts[-2]
    return None


class ChannelState(rx.State):
    channels: List[ChannelItem] = []
    countries: List[str] = []
    country_states: dict[str, bool] = {}

    async def on_load(self):
        selected = backend.get_selected_channel_ids()
        self.channels = []
        found_countries = set()
        for ch in backend.get_channels():
            country = get_country(ch.name)
            self.channels.append(
                ChannelItem(id=ch.id, name=ch.name, enabled=(ch.id in selected), country=country)
            )
            if country:
                found_countries.add(country)
        self.countries = sorted(found_countries)
        self.country_states = {
            c: all(ch["enabled"] for ch in self.channels if ch["country"] == c)
            for c in self.countries
        }

    def set_channel(self, channel_id: str, value: bool):
        for ch in self.channels:
            if ch["id"] == channel_id:
                ch["enabled"] = value
                if ch.get("country"):
                    country = ch["country"]
                    self.country_states[country] = all(
                        c["enabled"] for c in self.channels if c["country"] == country
                    )
                break

    def select_all(self):
        for ch in self.channels:
            ch["enabled"] = True
        for c in self.country_states:
            self.country_states[c] = True

    def select_none(self):
        for ch in self.channels:
            ch["enabled"] = False
        for c in self.country_states:
            self.country_states[c] = False

    def set_country(self, country: str, value: bool):
        self.country_states[country] = value
        for ch in self.channels:
            if ch["country"] == country:
                ch["enabled"] = value

    async def save(self):
        ids = [ch["id"] for ch in self.channels if ch["enabled"]]
        backend.set_selected_channel_ids(ids)
        try:
            await backend.generate_guide()
        except Exception:
            pass
        return rx.toast("Channel selection saved")


@rx.page("/channels", on_load=ChannelState.on_load)
def channels() -> rx.Component:
    return rx.box(
        navbar(),
        rx.container(
            rx.center(
                rx.card(
                    rx.vstack(
                        rx.hstack(
                            rx.button(
                                "Select All",
                                on_click=ChannelState.select_all,
                            ),
                            rx.button(
                                "Select None",
                                on_click=ChannelState.select_none,
                                color_scheme="gray",
                            ),
                            rx.spacer(),
                            rx.button(
                                "Save",
                                on_click=ChannelState.save,
                                color_scheme="green",
                            ),
                            width="100%",
                        ),
                        rx.divider(margin_y="1rem"),
                        rx.hstack(
                            rx.foreach(
                                ChannelState.countries,
                                lambda c: rx.checkbox(
                                    c,
                                    checked=ChannelState.country_states[c],
                                    on_change=lambda v, country=c: ChannelState.set_country(country, v),
                                ),
                            ),
                            spacing="2",
                            wrap="wrap",
                            width="100%",
                        ),
                        rx.divider(margin_y="1rem"),
                        rx.scroll_area(
                            rx.vstack(
                                rx.foreach(
                                    ChannelState.channels,
                                    lambda ch: rx.checkbox(
                                        ch["name"],
                                        checked=ch["enabled"],
                                        on_change=lambda v, cid=ch["id"]: ChannelState.set_channel(cid, v),
                                        width="100%",
                                    ),
                                ),
                                spacing="2",
                                width="100%",
                            ),
                            height="60vh",
                            width="100%",
                        ),
                    ),
                    padding="2rem",
                    width="100%",
                    max_width="800px",
                    border_radius="xl",
                    box_shadow="lg",
                ),
                padding_y="3rem",
            ),
            padding_top="7rem",
        ),
    )
