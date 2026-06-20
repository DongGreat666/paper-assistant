import paths  # noqa: F401 — sets MODEL_CACHE_DIR before any ML imports

import os

import reflex as rx

os.environ.setdefault(
    "REFLEX_HOT_RELOAD_EXCLUDE_PATHS",
    "paper_translation:uploaded_files:data:logs:MyPapers",
)

config = rx.Config(
    app_name="paper_assistant",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ],
)





