"""Bulk-normalize Marker citation brackets in saved Markdown files."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.core.markdown_links import normalize_escaped_brackets_in_link_labels


def migrate(root: Path, *, dry_run: bool = False) -> tuple[int, int]:
    """Normalize every Markdown file below *root* and return scan/change counts."""
    scanned = 0
    changed = 0
    for path in root.rglob("*.md"):
        scanned += 1
        source = path.read_text(encoding="utf-8")
        normalized = normalize_escaped_brackets_in_link_labels(source)
        if normalized == source:
            continue
        changed += 1
        print(f"{'WOULD UPDATE' if dry_run else 'UPDATED'} {path}")
        if not dry_run:
            path.write_text(normalized, encoding="utf-8")
    return scanned, changed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=Path("paper_translation"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    scanned, changed = migrate(args.root, dry_run=args.dry_run)
    print(f"Scanned {scanned} Markdown files; changed {changed}.")


if __name__ == "__main__":
    main()
