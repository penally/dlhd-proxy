import reflex as rx

from dlhd_proxy import backend
from dlhd_proxy.dlhd_proxy import app
from rxconfig import config


def test_app_configuration():
    assert isinstance(app, rx.App)
    assert app.api_transformer is backend.fastapi_app
    assert backend.update_channels in app.lifespan_tasks
    assert backend.auto_update_guide in app.lifespan_tasks


def test_rxconfig_plugins():
    plugin_types = {type(plugin) for plugin in config.plugins}
    assert config.app_name == "dlhd_proxy"
    assert any("SitemapPlugin" in cls.__name__ for cls in plugin_types)
    assert any("TailwindV4Plugin" in cls.__name__ for cls in plugin_types)
