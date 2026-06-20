"""Patch generated Vite config to ignore runtime data directories."""

from __future__ import annotations

from pathlib import Path


VITE_CONFIG = Path(".web") / "vite.config.js"
IGNORED_DIRS = [
    "**/paper_translation/**",
    "**/uploaded_files/**",
    "**/MyPapers/**",
    "**/logs/**",
    "**/data/**",
]


def main() -> None:
    if not VITE_CONFIG.exists():
        return

    text = VITE_CONFIG.read_text(encoding="utf-8")
    if "watch: {" not in text or all(entry in text for entry in IGNORED_DIRS):
        return

    marker = '        "**/.web/reflex.install_frontend_packages.cached",\n'
    if marker not in text:
        return

    additions = "".join(f'        "{entry}",\n' for entry in IGNORED_DIRS if entry not in text)
    VITE_CONFIG.write_text(text.replace(marker, marker + additions), encoding="utf-8")


if __name__ == "__main__":
    main()
