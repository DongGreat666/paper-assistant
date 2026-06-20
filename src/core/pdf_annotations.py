"""PDF annotation read/write using PyMuPDF.

Uses real PDF annotations (Highlight, Underline, StrikeOut, Text, FreeText)
that are embedded in the PDF binary. Visible in any PDF reader (Adobe, WPS,
Chrome, Foxit, etc.) and persist across sessions.

Thread-safe: all write operations acquire a per-file lock to prevent
concurrent saveIncr() calls from corrupting the PDF.
"""

import logging
import re
import threading
import weakref
from contextlib import contextmanager

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

# Per-file locks — prevents concurrent writes to the same PDF
# Uses WeakValueDictionary to auto-cleanup locks when no longer referenced
_pdf_locks: weakref.WeakValueDictionary[str, threading.Lock] = weakref.WeakValueDictionary()
_locks_lock = threading.Lock()


def _get_pdf_lock(path: str) -> threading.Lock:
    """Get or create a lock for the given PDF path.

    Uses WeakValueDictionary so locks are automatically cleaned up
    when no longer in use, preventing memory leaks.
    """
    key = str(path)
    with _locks_lock:
        lock = _pdf_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _pdf_locks[key] = lock
        return lock


def _cleanup_pdf_lock(path: str) -> None:
    """Explicitly remove a lock for the given PDF path.

    Call this when a PDF is deleted or no longer needs locking.
    """
    key = str(path)
    with _locks_lock:
        _pdf_locks.pop(key, None)


def _clean_annotation_text(text: str) -> str:
    """Normalize text read back from PDF annotations for sidebar display."""
    if not text:
        return ""
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=[A-Za-z0-9,.;:!?%])-\s*\n\s*(?=[A-Za-z])", "", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _same_annotation_text(a: str, b: str) -> bool:
    """Return true when PDF annotation content is just another copy of selected text."""
    a_norm = _clean_annotation_text(a)
    b_norm = _clean_annotation_text(b)
    if not a_norm or not b_norm:
        return False
    if a_norm == b_norm:
        return True
    compact_a = re.sub(r"\W+", "", a_norm.casefold())
    compact_b = re.sub(r"\W+", "", b_norm.casefold())
    return bool(compact_a and compact_b and compact_a == compact_b)


def _text_from_annotation_words(page, annot) -> str:
    """Rebuild annotation text from PDF words inside the annotation quads."""
    try:
        words = page.get_text("words")
    except Exception:
        return ""
    if not words:
        return ""

    vertices = getattr(annot, "vertices", None) or []
    quad_rects = []
    for i in range(0, len(vertices), 4):
        quad = vertices[i:i + 4]
        if len(quad) != 4:
            continue
        xs = [p[0] for p in quad]
        ys = [p[1] for p in quad]
        rect = fitz.Rect(min(xs), min(ys), max(xs), max(ys))
        rect.x0 -= 1
        rect.x1 += 1
        rect.y0 -= 1
        rect.y1 += 1
        quad_rects.append(rect)
    if not quad_rects:
        quad_rects = [annot.rect]

    selected: list[tuple[float, float, float, str]] = []
    seen: set[tuple[float, float, float, float, str]] = set()
    for rect in quad_rects:
        line_words = []
        for word in words:
            x0, y0, x1, y1, value = word[:5]
            word_rect = fitz.Rect(x0, y0, x1, y1)
            if not rect.intersects(word_rect):
                continue
            key = (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2), value)
            if key in seen:
                continue
            seen.add(key)
            line_words.append((x0, y0, x1, value))
        selected.extend(sorted(line_words, key=lambda item: (item[1], item[0])))

    lines: list[list[tuple[float, float, float, str]]] = []
    for item in sorted(selected, key=lambda item: (item[1], item[0])):
        if not lines or abs(lines[-1][0][1] - item[1]) > 3:
            lines.append([item])
        else:
            lines[-1].append(item)

    parts = [" ".join(word for *_coords, word in sorted(line, key=lambda item: item[0])) for line in lines]
    return _clean_annotation_text("\n".join(parts))


@contextmanager
def _open_pdf_for_write(pdf_path: str):
    """Open a PDF with per-file lock. Caller must call _save(doc) explicitly.

    Acquires the per-file lock, opens the document, and yields doc.
    Lock is released and doc closed automatically on exit.
    """
    lock = _get_pdf_lock(pdf_path)
    lock.acquire()
    doc = None
    try:
        doc = fitz.open(pdf_path)
        yield doc
    finally:
        if doc is not None:
            try:
                doc.close()
            except Exception:
                pass
        lock.release()


def read_highlights(pdf_path: str) -> list[dict]:
    """Read all highlight annotations from a PDF file.

    Returns a list of dicts in react-pdf-highlighter IHighlight format.
    Acquires a shared read on the per-file lock to avoid reading during writes.
    """
    lock = _get_pdf_lock(pdf_path)
    lock.acquire()
    try:
        try:
            doc = fitz.open(pdf_path)
        except Exception:
            return []

        try:
            highlights = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_rect = page.rect
                w = page_rect.width
                h = page_rect.height
                x0_offset = page_rect.x0
                y0_offset = page_rect.y0

                for annot in page.annots():
                    atype = annot.type[0]
                    if atype not in (0, 2, 8, 9, 10):
                        continue

                    ar = annot.rect
                    scaled_rect = {
                        "x1": ar.x0 - x0_offset,
                        "y1": ar.y0 - y0_offset,
                        "x2": ar.x1 - x0_offset,
                        "y2": ar.y1 - y0_offset,
                        "width": w,
                        "height": h,
                        "pageNumber": page_num + 1,
                    }

                    annot_id = annot.info.get("title", "") or f"ann-{page_num}-{annot.xref}"
                    info = annot.info or {}
                    comment_text = _clean_annotation_text(info.get("content", "") or "")

                    # Text annotation (sticky note)
                    if atype == 0:
                        highlights.append({
                            "id": annot_id,
                            "position": {
                                "boundingRect": dict(scaled_rect),
                                "rects": [dict(scaled_rect)],
                                "pageNumber": page_num + 1,
                            },
                            "content": {"text": ""},
                            "comment": {"text": comment_text, "emoji": ""},
                            "_color": "#FFD700",
                            "_type": "comment",
                        })
                        continue

                    # FreeText annotation (inline translation)
                    if atype == 2:
                        text_content = ""
                        try:
                            text_content = _clean_annotation_text(annot.get_text("text"))
                        except Exception:
                            logger.debug("Failed to extract FreeText content, falling back to comment")
                            text_content = comment_text
                        highlights.append({
                            "id": annot_id,
                            "position": {
                                "boundingRect": dict(scaled_rect),
                                "rects": [dict(scaled_rect)],
                                "pageNumber": page_num + 1,
                            },
                            "content": {"text": ""},
                            "comment": {"text": "", "emoji": "", "translation": text_content},
                            "_color": "#E8D5F5",
                            "_type": "translation",
                        })
                        continue

                    # Highlight / Underline / StrikeOut
                    colors = annot.colors
                    stroke_color = colors.get("stroke", (1, 1, 0))
                    color_hex = "#{:02x}{:02x}{:02x}".format(
                        int(stroke_color[0] * 255),
                        int(stroke_color[1] * 255),
                        int(stroke_color[2] * 255),
                    )

                    text = _text_from_annotation_words(page, annot)
                    try:
                        if not text:
                            text = _clean_annotation_text(annot.get_text("text"))
                    except Exception:
                        logger.debug("Failed to extract text from annotation xref=%d", annot.xref)
                    note_text = comment_text if comment_text and not _same_annotation_text(comment_text, text) else ""

                    # Detect annotation type: check subject field first, then fallback to PDF type
                    subject = info.get("subject", "") or ""
                    if subject == "translation" or annot_id.startswith("trans-"):
                        ann_type = "translation"
                    elif atype == 9:
                        ann_type = "underline"
                    elif atype == 10:
                        ann_type = "strikethrough"
                    else:
                        ann_type = "highlight"

                    highlights.append({
                        "id": annot_id,
                        "position": {
                            "boundingRect": dict(scaled_rect),
                            "rects": [dict(scaled_rect)],
                            "pageNumber": page_num + 1,
                        },
                        "content": {"text": text},
                        "comment": {"text": note_text, "emoji": ""},
                        "_color": color_hex,
                        "_type": ann_type,
                    })

            return highlights
        finally:
            doc.close()
    finally:
        lock.release()


def _convert_rects(rects: list[dict], page) -> list[fitz.Quad]:
    """Convert relative 0-1 rects to fitz Quad objects for a page."""
    page_rect = page.rect
    x0_offset = page_rect.x0
    y0_offset = page_rect.y0
    w = page_rect.width
    h = page_rect.height

    quads = []
    for rect in rects:
        x1 = rect["x1"] * w + x0_offset
        y1 = rect["y1"] * h + y0_offset
        x2 = rect["x2"] * w + x0_offset
        y2 = rect["y2"] * h + y0_offset
        quad = fitz.Quad(
            fitz.Point(x1, y1),
            fitz.Point(x2, y1),
            fitz.Point(x1, y2),
            fitz.Point(x2, y2),
        )
        quads.append(quad)
    return quads


def _merge_rects_by_line(rects: list[dict]) -> list[dict]:
    """Merge fragmented text-selection rects into line-level rects.

    PDF.js selections often return one rect per word/character run. Underline
    annotations look broken if those fragments are written as-is, so merge
    nearby fragments on the same visual line while keeping large column gaps.
    """
    if not rects:
        return []

    normalized = [
        {
            "x1": min(float(rect["x1"]), float(rect["x2"])),
            "y1": min(float(rect["y1"]), float(rect["y2"])),
            "x2": max(float(rect["x1"]), float(rect["x2"])),
            "y2": max(float(rect["y1"]), float(rect["y2"])),
        }
        for rect in rects
    ]
    normalized.sort(key=lambda r: ((r["y1"] + r["y2"]) / 2, r["x1"]))

    line_groups: list[list[dict]] = []
    for rect in normalized:
        center_y = (rect["y1"] + rect["y2"]) / 2
        height = max(rect["y2"] - rect["y1"], 0.0001)
        for group in line_groups:
            group_center = sum((r["y1"] + r["y2"]) / 2 for r in group) / len(group)
            group_height = max(max(r["y2"] - r["y1"] for r in group), 0.0001)
            if abs(center_y - group_center) <= max(height, group_height) * 0.65:
                group.append(rect)
                break
        else:
            line_groups.append([rect])

    merged: list[dict] = []
    for group in line_groups:
        group.sort(key=lambda r: r["x1"])
        line_height = max(max(r["y2"] - r["y1"] for r in group), 0.0001)
        max_gap = max(0.015, line_height * 2.5)
        current = dict(group[0])
        for rect in group[1:]:
            gap = rect["x1"] - current["x2"]
            if gap <= max_gap:
                current["x1"] = min(current["x1"], rect["x1"])
                current["y1"] = min(current["y1"], rect["y1"])
                current["x2"] = max(current["x2"], rect["x2"])
                current["y2"] = max(current["y2"], rect["y2"])
            else:
                merged.append(current)
                current = dict(rect)
        merged.append(current)

    return merged


def _line_rects_for_text_marks(rects: list[dict]) -> list[dict]:
    """Build tighter line rects for underline/strikeout annotations."""
    merged = _merge_rects_by_line(rects)
    adjusted: list[dict] = []
    for rect in merged:
        height = max(rect["y2"] - rect["y1"], 0.0001)
        adjusted.append({
            **rect,
            "y1": rect["y2"] - height * 0.72,
            "y2": rect["y2"] + height * 0.08,
        })
    return adjusted


def _save(doc, pdf_path: str):
    """Save PDF incrementally."""
    try:
        doc.saveIncr()
    except Exception:
        doc.save(pdf_path, incremental=True, encryption=0)


def _parse_color(color_hex: str) -> tuple[float, float, float]:
    r = int(color_hex[1:3], 16) / 255.0
    g = int(color_hex[3:5], 16) / 255.0
    b = int(color_hex[5:7], 16) / 255.0
    return r, g, b


def add_highlight(
    pdf_path: str,
    page_num: int,
    rects: list[dict],
    color_hex: str = "#FFD700",
    highlight_id: str = "",
    text: str = "",
    subject: str = "",
) -> bool:
    """Add a real PDF Highlight annotation."""
    with _open_pdf_for_write(pdf_path) as doc:
        if page_num < 1 or page_num > len(doc):
            return False
        page = doc[page_num - 1]
        r, g, b = _parse_color(color_hex)
        quads = _convert_rects(_merge_rects_by_line(rects), page)
        annot = page.add_highlight_annot(quads)
        annot.set_colors(stroke=(r, g, b))
        annot.set_opacity(0.4)
        info = {"title": highlight_id, "content": text}
        if subject:
            info["subject"] = subject
        annot.set_info(info)
        annot.update()
        _save(doc, pdf_path)
    return True


def add_underline(
    pdf_path: str,
    page_num: int,
    rects: list[dict],
    color_hex: str = "#FFD700",
    highlight_id: str = "",
    text: str = "",
) -> bool:
    """Add a real PDF Underline annotation."""
    with _open_pdf_for_write(pdf_path) as doc:
        if page_num < 1 or page_num > len(doc):
            return False
        page = doc[page_num - 1]
        r, g, b = _parse_color(color_hex)
        quads = _convert_rects(_line_rects_for_text_marks(rects), page)
        annot = page.add_underline_annot(quads)
        annot.set_colors(stroke=(r, g, b))
        annot.set_info(title=highlight_id, content=text)
        annot.update()
        _save(doc, pdf_path)
    return True


def add_strikethrough(
    pdf_path: str,
    page_num: int,
    rects: list[dict],
    color_hex: str = "#EF4444",
    highlight_id: str = "",
    text: str = "",
) -> bool:
    """Add a real PDF StrikeOut annotation."""
    with _open_pdf_for_write(pdf_path) as doc:
        if page_num < 1 or page_num > len(doc):
            return False
        page = doc[page_num - 1]
        r, g, b = _parse_color(color_hex)
        quads = _convert_rects(_line_rects_for_text_marks(rects), page)
        annot = page.add_strikeout_annot(quads)
        annot.set_colors(stroke=(r, g, b))
        annot.set_info(title=highlight_id, content=text)
        annot.update()
        _save(doc, pdf_path)
    return True


def _annotation_matches_id(annot, page_index: int, annot_id: str) -> bool:
    """Match annotations with stored IDs or the fallback ID used while reading PDFs."""
    stored_id = annot.info.get("title", "") or ""
    return stored_id == annot_id or (
        not stored_id and annot_id == f"ann-{page_index}-{annot.xref}"
    )


def delete_highlight(pdf_path: str, highlight_id: str) -> bool:
    """Delete a PDF annotation by its stored or read-time fallback ID."""
    with _open_pdf_for_write(pdf_path) as doc:
        deleted = False
        for page_index, page in enumerate(doc):
            for annot in page.annots():
                if _annotation_matches_id(annot, page_index, highlight_id):
                    page.delete_annot(annot)
                    deleted = True
                    break
            if deleted:
                break
        if deleted:
            _save(doc, pdf_path)
    return deleted


def update_annotation_comment(pdf_path: str, annot_id: str, comment: str) -> bool:
    """Update the stored popup/comment text on an existing PDF annotation."""
    if not annot_id:
        return False
    with _open_pdf_for_write(pdf_path) as doc:
        updated = False
        for page_index, page in enumerate(doc):
            for annot in page.annots():
                if not _annotation_matches_id(annot, page_index, annot_id):
                    continue
                annot.set_info(content=comment)
                annot.update()
                updated = True
                break
            if updated:
                break
        if updated:
            _save(doc, pdf_path)
    return updated


def add_text_annot(
    pdf_path: str,
    page_num: int,
    point: dict,
    comment: str,
    annot_id: str = "",
    text: str = "",
) -> bool:
    """Add a sticky note (Text annotation) to a PDF file."""
    with _open_pdf_for_write(pdf_path) as doc:
        if page_num < 1 or page_num > len(doc):
            return False
        page = doc[page_num - 1]
        page_rect = page.rect
        w = page_rect.width
        h = page_rect.height

        px = point["x"] * w + page_rect.x0
        py = point["y"] * h + page_rect.y0

        annot = page.add_text_annot(fitz.Point(px, py), comment)
        annot.set_colors(stroke=(1, 0.85, 0))
        annot.set_info(title=annot_id, content=comment)
        annot.update()
        _save(doc, pdf_path)
    return True


def add_freetext_annot(
    pdf_path: str,
    page_num: int,
    rects: list[dict],
    translation: str,
    annot_id: str = "",
) -> bool:
    """Add a FreeText annotation with translation text below the selection."""
    if not rects:
        return False

    with _open_pdf_for_write(pdf_path) as doc:
        if page_num < 1 or page_num > len(doc):
            return False
        page = doc[page_num - 1]
        page_rect = page.rect
        w = page_rect.width
        h = page_rect.height

        last = rects[-1]
        if last.get("placement"):
            rect = fitz.Rect(
                last["x1"] * w + page_rect.x0,
                last["y1"] * h + page_rect.y0,
                last["x2"] * w + page_rect.x0,
                last["y2"] * h + page_rect.y0,
            )
        else:
            x1 = last["x1"] * w + page_rect.x0
            y2 = last["y2"] * h + page_rect.y0
            x2 = last["x2"] * w + page_rect.x0
            box_width = max(220, (x2 - x1) + 80)
            line_count = max(1, len(translation) // 24 + 1)
            box_height = min(160, max(30, line_count * 16 + 10))
            rect = fitz.Rect(
                x1,
                y2 + 2,
                min(page_rect.x1 - 8, x1 + box_width),
                min(page_rect.y1 - 8, y2 + 2 + box_height),
            )

        annot = page.add_freetext_annot(
            rect,
            translation,
            fontsize=12,
            text_color=(1, 0, 0),
            fill_color=None,
            border_color=None,
            border_width=0,
        )
        annot.set_info(title=annot_id, content=translation)
        annot.update()
        _save(doc, pdf_path)
    return True


def move_freetext_annot(
    pdf_path: str,
    annot_id: str,
    page_num: int,
    rects: list[dict],
    text: str,
) -> bool:
    """Move an existing FreeText annotation by replacing it at a new rect."""
    if not annot_id or not rects:
        return False
    delete_highlight(pdf_path, annot_id)
    return add_freetext_annot(
        pdf_path,
        page_num=page_num,
        rects=rects,
        translation=text,
        annot_id=annot_id,
    )
