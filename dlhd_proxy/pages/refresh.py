import reflex as rx
from dlhd_proxy import backend
from dlhd_proxy.components import navbar


class RefreshState(rx.State):
    async def refresh(self):
        try:
            await backend.refresh_all()
            return rx.toast("Data refreshed")
        except Exception as e:
            return rx.toast(f"Refresh failed: {e}", color_scheme="red")


@rx.page("/refresh")
def refresh() -> rx.Component:
    return rx.box(
        navbar(),
        rx.container(
            rx.center(
                rx.button("Refresh data", on_click=RefreshState.refresh, size="3"),
                padding_y="3rem",
            ),
            padding_top="7rem",
        ),
    )
