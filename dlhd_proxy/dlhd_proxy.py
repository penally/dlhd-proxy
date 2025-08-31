import reflex as rx
import dlhd_proxy.pages
from typing import List
from dlhd_proxy import backend
from dlhd_proxy.components import navbar, card
from dlhd_proxy.step_daddy import Channel


class State(rx.State):
    channels: List[Channel] = []
    search_query: str = ""
    is_loading: bool = False

    @rx.var
    def filtered_channels(self) -> List[Channel]:
        if not self.search_query:
            return self.channels
        return [ch for ch in self.channels if self.search_query.lower() in ch.name.lower()]

    async def load_channels(self):
        # Avoid reloading if channels are already fetched.
        if self.channels:
            return
        self.is_loading = True
        self.channels = backend.get_enabled_channels()
        self.is_loading = False


@rx.page("/")
def index() -> rx.Component:
    channel_grid = rx.grid(
        rx.foreach(
            State.filtered_channels,
            lambda channel: card(channel),
        ),
        grid_template_columns="repeat(auto-fill, minmax(250px, 1fr))",
        spacing=rx.breakpoints(
            initial="4",
            sm="6",
            lg="9"
        ),
        width="100%",
    )

    return rx.box(
        navbar(
            rx.box(
                rx.input(
                    rx.input.slot(
                        rx.icon("search"),
                    ),
                    placeholder="Search channels...",
                    on_change=State.set_search_query,
                    value=State.search_query,
                    width="100%",
                    max_width="25rem",
                    size="3",
                ),
            ),
        ),
        rx.center(
            rx.vstack(
                rx.desktop_only(
                    rx.box(
                        rx.cond(
                            State.channels,
                            channel_grid,
                            rx.center(rx.spinner(), height="50vh"),
                        ),
                    ),
                    on_mount=State.load_channels,
                ),
                rx.mobile_and_tablet(
                    rx.cond(
                        State.channels,
                        channel_grid,
                        rx.button(
                            "Load channels...",
                            on_click=State.load_channels,
                            loading=State.is_loading,
                            size="3",
                        ),
                    ),
                ),
            ),
            padding="1rem",
            padding_top="10rem",
        ),
    )


app = rx.App(
    theme=rx.theme(
        appearance="dark",
        accent_color="red",
    ),
    api_transformer=backend.fastapi_app,
)

app.register_lifespan_task(backend.update_channels)
app.register_lifespan_task(backend.auto_update_guide)
