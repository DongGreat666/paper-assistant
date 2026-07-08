import os

import paths  # noqa: F401 — sets MODEL_CACHE_DIR before any ML imports

os.environ.setdefault("REFLEX_UPLOADED_FILES_DIR", "data/reflex_uploads")

import reflex as rx

os.environ.setdefault(
    "REFLEX_HOT_RELOAD_EXCLUDE_PATHS",
    "paper_translation:data/reflex_uploads:data:logs:MyPapers",
)

config = rx.Config(
    app_name="paper_assistant",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
        rx.plugins.RadixThemesPlugin(),
    ],
)





