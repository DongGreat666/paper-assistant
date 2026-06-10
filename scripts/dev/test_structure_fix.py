"""Experiment: ask an LLM to repair parsed paper Markdown structure.

This script is intentionally separate from the app flow. It writes sibling
`*_structure_fixed_test.md` output and a JSON report without modifying the
source Markdown. Chunk outputs are saved as checkpoints so a long model call can
be resumed after a timeout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.engine import get_default_translation_engine
from src.core.translator import split_markdown_into_sections
from src.utils.http_client import chat_completions_url, chat_message_content


DEFAULT_INPUT = Path(
    "uploaded_files/YOLOv1_2016_You_Only/YOLOv1_2016_You_Only.md"
)


SYSTEM_PROMPT = """你是论文 Markdown 结构修复助手。目标不是重写论文，而是把 PDF 解析造成的结构问题修到更适合阅读和后续翻译。

总原则：内容不动。保留原文语言、事实、实验结果、数字、引用编号、专有名词和作者表达。不要翻译，不要总结，不要润色成另一种写法。

你可以灵活判断并做最小必要修复：
1. 修复明显的 Markdown、LaTeX、表格、标题层级、换页断句问题。
2. 普通句子尽量保留原词序和全部信息。只有当 PDF 换页、page anchor、表格或图片把一句话拆开时，才把断开的续句接回去。
3. 续接断句时，寻找附近的句子碎片。常见信号是前一句停在 its/their/and/with/which/of/to 等未完成成分，后面出现小写词、指标名或普通名词开头的半句。接回时保留全部数字、百分比、单位、引用和专有名词。
4. 公式优先修 begin/end 环境匹配、公式块边界、明显缺失的换行或拼写 OCR 错误；不要改变公式含义。
5. 表格优先修 Markdown 分隔和列对齐；不要改动单元格数值。复杂表格宁可保守保留，也不要为了漂亮丢数据。
6. 标题层级只修明显错层级的章节标题；不要删除标题文字。
7. 图注、表注、图片路径、page anchor 尽量保持与相邻图片/表格/段落的相对位置。只有明显插断句子时才做小范围调整。
8. 引用和参考文献保留编号、作者、年份和链接文本。不要把图/表/公式编号当成参考文献改写。
9. 高置信 OCR 错词可以修，例如公式里的 clusses 在上下文表示类别集合时可修成 classes；不确定的拼写保持原样。
10. 如果某处可能是作者原意而不是解析错误，保留原样。

只输出修复后的 Markdown，不要输出解释、说明、diff 或代码块围栏。"""


@dataclass
class Metrics:
    chars: int
    image_count: int
    table_rows: int
    display_math_delims: int
    begin_envs: list[str]
    end_envs: list[str]


def metrics(text: str) -> Metrics:
    return Metrics(
        chars=len(text),
        image_count=len(re.findall(r"!\[[^\]]*]\([^)]+\)", text)),
        table_rows=sum(1 for line in text.splitlines() if line.strip().startswith("|")),
        display_math_delims=text.count("$$"),
        begin_envs=re.findall(r"\\begin\{([^}]+)\}", text),
        end_envs=re.findall(r"\\end\{([^}]+)\}", text),
    )


def number_tokens(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?(?![A-Za-z])", text)


def link_targets(text: str) -> list[str]:
    return re.findall(r"\[[^\]]+]\(([^)]+)\)", text)


def heading_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if re.match(r"^#{1,6}\s+", line.strip())]


def table_col_counts(text: str) -> list[int]:
    return [line.count("|") - 1 for line in text.splitlines() if line.strip().startswith("|")]


def dangling_sentence_lines(text: str) -> list[str]:
    endings = re.compile(
        r"\b(?:its|their|his|her|our|and|or|but|with|for|that|which|whose|of|to|in|on|at|by|from)$",
        re.IGNORECASE,
    )
    result: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "|", "!", "<span")):
            continue
        if stripped.endswith((".", "!", "?", ":", ";")):
            continue
        if endings.search(stripped):
            result.append(stripped)
    return result


def suspicious_changes(before: str, after: str) -> list[str]:
    before_m = metrics(before)
    after_m = metrics(after)
    warnings: list[str] = []

    if after_m.chars < before_m.chars * 0.65:
        warnings.append("输出长度明显变短")
    if before_m.image_count != after_m.image_count:
        warnings.append(f"图片数量变化: {before_m.image_count} -> {after_m.image_count}")
    if before_m.display_math_delims % 2 != after_m.display_math_delims % 2:
        warnings.append("公式块 $$ 奇偶性变化")
    if sorted(after_m.begin_envs) != sorted(after_m.end_envs):
        warnings.append("LaTeX 环境可能不匹配")
    if before_m.table_rows and after_m.table_rows < before_m.table_rows * 0.6:
        warnings.append(f"表格行数明显减少: {before_m.table_rows} -> {after_m.table_rows}")
    if number_tokens(before) != number_tokens(after):
        warnings.append("数字/百分比序列发生变化")
    if link_targets(before) != link_targets(after):
        warnings.append("Markdown 链接目标序列发生变化")
    if heading_lines(before) != heading_lines(after):
        warnings.append("标题序列或标题层级发生变化")
    if table_col_counts(before) != table_col_counts(after):
        warnings.append("表格列数序列发生变化")
    dangling = dangling_sentence_lines(after)
    if dangling:
        warnings.append(f"仍存在疑似断句: {dangling[:3]}")

    return warnings


def clean_model_output(text: str) -> str:
    result = text.strip()
    result = re.sub(r"^```(?:markdown|md)?\s*", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\s*```$", "", result)
    return result.strip()


def split_long_section(section: str, max_chars: int) -> list[str]:
    if len(section) <= max_chars:
        return [section]

    blocks = re.split(r"(\n\s*\n)", section)
    chunks: list[str] = []
    current = ""
    for block in blocks:
        if not block:
            continue
        if current and len(current) + len(block) > max_chars:
            chunks.append(current.strip())
            current = block
        else:
            current += block

        # Keep an oversized table or paragraph intact rather than splitting
        # inside Markdown syntax. It is safer than losing table cells.
        if len(current) > max_chars * 1.8:
            chunks.append(current.strip())
            current = ""

    if current.strip():
        chunks.append(current.strip())
    return chunks


def chunk_sections(text: str, max_chars: int) -> list[str]:
    sections = split_markdown_into_sections(text)
    expanded_sections: list[str] = []
    for section in sections:
        expanded_sections.extend(split_long_section(section, max_chars))

    chunks: list[str] = []
    current = ""
    for section in expanded_sections:
        if current and len(current) + len(section) + 2 > max_chars:
            chunks.append(current.strip())
            current = section
        else:
            current = f"{current}\n\n{section}" if current else section
    if current.strip():
        chunks.append(current.strip())
    return chunks


async def repair_section(
    client: httpx.AsyncClient,
    section: str,
    section_index: int,
    total: int,
    *,
    api_key: str,
    base_url: str,
    model: str,
) -> str:
    response = await client.post(
        chat_completions_url(base_url),
        headers={"Authorization": f"Bearer {api_key.strip()}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"下面是第 {section_index}/{total} 个 Markdown 片段。"
                        "只修格式和明确解析错误，内容不动。输出修复后的片段：\n\n"
                        f"{section}"
                    ),
                },
            ],
            "temperature": 0,
        },
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"LLM request failed: {response.status_code} {response.text[:1000]}"
        )
    return clean_model_output(chat_message_content(response.json()))


def paths_for(input_path: Path, suffix: str) -> tuple[Path, Path, Path]:
    output_path = input_path.with_name(f"{input_path.stem}_{suffix}.md")
    report_path = input_path.with_name(f"{input_path.stem}_{suffix}_report.json")
    checkpoint_path = input_path.with_name(f"{input_path.stem}_{suffix}_checkpoint.json")
    return output_path, report_path, checkpoint_path


def load_checkpoint(checkpoint_path: Path) -> dict[int, str]:
    if not checkpoint_path.exists():
        return {}
    data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    return {int(item["chunk"]): item["text"] for item in data.get("chunks", [])}


def save_progress(
    *,
    output_path: Path,
    report_path: Path,
    checkpoint_path: Path,
    chunks: list[str],
    fixed_by_index: dict[int, str],
    report_by_index: dict[int, dict],
) -> None:
    ordered_fixed = [fixed_by_index.get(i + 1, "") for i in range(len(chunks))]
    output_path.write_text("\n\n".join(part for part in ordered_fixed if part), encoding="utf-8")
    report = [report_by_index[i + 1] for i in range(len(chunks)) if i + 1 in report_by_index]
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    checkpoint_path.write_text(
        json.dumps(
            {
                "chunks": [
                    {"chunk": index, "text": fixed_by_index[index]}
                    for index in sorted(fixed_by_index)
                ]
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", nargs="?", default=str(DEFAULT_INPUT))
    parser.add_argument("--max-chars", type=int, default=5000)
    parser.add_argument("--start", type=int, default=1, help="1-based chunk index to start from.")
    parser.add_argument("--limit", type=int, default=0, help="Only repair first N chunks for quick tests.")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--read-timeout", type=float, default=240)
    parser.add_argument("--suffix", default="structure_fixed_test")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    engine = get_default_translation_engine()
    api_key = args.api_key or engine.api_key
    base_url = args.base_url or engine.base_url
    model = args.model or engine.model
    print(f"Using model={model} base_url={base_url}")

    input_path = Path(args.input)
    source = input_path.read_text(encoding="utf-8")
    all_chunks = chunk_sections(source, args.max_chars)
    selected_indices = list(range(max(1, args.start), len(all_chunks) + 1))
    if args.limit > 0:
        selected_indices = selected_indices[: args.limit]

    if args.limit > 0 or args.start > 1:
        suffix = f"{args.suffix}_chunks_{selected_indices[0]}_{selected_indices[-1]}"
    else:
        suffix = args.suffix
    output_path, report_path, checkpoint_path = paths_for(input_path, suffix)

    fixed_by_index = load_checkpoint(checkpoint_path) if args.resume else {}
    report_by_index: dict[int, dict] = {}
    if args.resume and report_path.exists():
        for item in json.loads(report_path.read_text(encoding="utf-8")):
            report_by_index[int(item["chunk"])] = item

    timeout = httpx.Timeout(connect=20, read=args.read_timeout, write=60, pool=20)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for idx in selected_indices:
            if idx in fixed_by_index:
                print(f"Skipping chunk {idx}/{len(all_chunks)} from checkpoint.")
                continue

            chunk = all_chunks[idx - 1]
            print(f"Repairing chunk {idx}/{len(all_chunks)} ({len(chunk)} chars)...")
            fixed = await repair_section(
                client,
                chunk,
                idx,
                len(all_chunks),
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
            warnings = suspicious_changes(chunk, fixed)
            fixed_by_index[idx] = fixed
            report_by_index[idx] = {
                "chunk": idx,
                "input_chars": len(chunk),
                "output_chars": len(fixed),
                "warnings": warnings,
            }
            save_progress(
                output_path=output_path,
                report_path=report_path,
                checkpoint_path=checkpoint_path,
                chunks=all_chunks,
                fixed_by_index=fixed_by_index,
                report_by_index=report_by_index,
            )

    save_progress(
        output_path=output_path,
        report_path=report_path,
        checkpoint_path=checkpoint_path,
        chunks=all_chunks,
        fixed_by_index=fixed_by_index,
        report_by_index=report_by_index,
    )
    print(f"Wrote: {output_path}")
    print(f"Wrote: {report_path}")
    print(f"Wrote: {checkpoint_path}")


if __name__ == "__main__":
    asyncio.run(main())
