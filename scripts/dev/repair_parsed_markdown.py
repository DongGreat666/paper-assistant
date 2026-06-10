"""Repair common structural issues in parsed paper Markdown.

This is a deterministic, conservative pre-translation repair step. It does not
call an LLM and does not overwrite the input file unless an explicit output path
is provided.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.markdown_repair import collect_stats, repair_file


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Parsed Markdown file to repair.")
    parser.add_argument(
        "-o",
        "--output",
        default="",
        help="Output Markdown path. Defaults to *_rule_repaired.md next to input.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else None

    before_text = input_path.read_text(encoding="utf-8")
    output_path, report_path, report = repair_file(input_path, output_path)
    after_text = output_path.read_text(encoding="utf-8")

    print(f"input:  {input_path}")
    print(f"output: {output_path}")
    print(f"report: {report_path}")
    print("before:", collect_stats(before_text))
    print("after: ", collect_stats(after_text))
    print("changes:", report.to_dict())


if __name__ == "__main__":
    main()
