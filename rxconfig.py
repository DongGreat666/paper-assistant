import paths  # noqa: F401 — sets MODEL_CACHE_DIR before any ML imports

import reflex as rx

config = rx.Config(
    app_name="paper_assistant",
    backend_port=8000,
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ],
)





