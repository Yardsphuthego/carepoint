import reflex as rx

config = rx.Config(
    app_name="carepoint",
    frontend_port=3000,
    backend_port=8001,
    disable_plugins=[rx.plugins.SitemapPlugin],
    plugins=[rx.plugins.RadixThemesPlugin(theme=rx.theme(appearance="light", accent_color="blue", font_family="Arial"))],
)
