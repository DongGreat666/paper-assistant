"""Persisted conversation storage.

Each conversation is a JSON file in data/chat_history/<id>.json.
Schema:
{
    "id": "uuid",
    "title": "首条用户消息摘要",
    "paper": "论文文件名或空串",
    "messages": [{"role": "user/assistant", "content": "..."}],
    "created_at": "ISO timestamp",
    "updated_at": "ISO timestamp"
}
"""

import json
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from config import get_config

HISTORY_DIR: Path = get_config().chat_history_dir
_CONVERSATION_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")


def _conversation_path(conv_id: str) -> Path | None:
    """Return the bounded history path for a valid conversation ID."""
    if not isinstance(conv_id, str) or not _CONVERSATION_ID_PATTERN.fullmatch(conv_id):
        return None
    history_root = HISTORY_DIR.resolve()
    path = (history_root / f"{conv_id}.json").resolve()
    return path if path.parent == history_root else None


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _make_title(first_user_msg: str) -> str:
    text = first_user_msg.strip().replace("\n", " ")
    return text[:40] + ("..." if len(text) > 40 else "")


def clean_generated_title(title: str) -> str:
    """Clean an LLM-generated chat title for sidebar display."""
    text = str(title or "").strip()
    text = re.sub(r"^(标题|对话标题|聊天标题)\s*[:：]\s*", "", text, flags=re.IGNORECASE)
    text = text.strip(" \t\r\n\"'“”‘’`#*-：:。.!！?？")
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    text = text[:24] + ("..." if len(text) > 24 else "")
    return text.strip(" \t\r\n\"'“”‘’`#*-：:。.!！?？")


def _paper_title(paper: str) -> str:
    """Return a readable title from an attached paper filename."""
    if not paper:
        return ""
    text = Path(paper).stem.strip() or paper.strip()
    return _make_title(text)


def _is_upload_status_message(message: dict) -> bool:
    """Return whether a message is an internal upload/progress notice."""
    content = str(message.get("content", "")).strip()
    return (
        message.get("role") == "assistant"
        and content.startswith("已上传 ")
        and "正在准备问答上下文" in content
    )


def conversation_title(messages: list[dict] | None = None, paper: str = "") -> str:
    """Derive a stable sidebar title.

    Prefer the first real user question.  Upload-only chats fall back to the
    paper name instead of the internal "已上传 xxx" progress message.
    """
    for message in messages or []:
        if message.get("role") != "user":
            continue
        content = str(message.get("content", "")).strip()
        if content:
            return _make_title(content)
    if any(_is_upload_status_message(message) for message in messages or []):
        return _paper_title(paper)
    return _paper_title(paper)


def _is_bad_auto_title(title: str) -> bool:
    """Return whether an old title was generated from an upload notice."""
    return title.strip().startswith("已上传 ")


def new_conversation(paper: str = "", messages: list[dict] | None = None, engine: str = "") -> dict:
    """Create a conversation dict (not yet saved)."""
    initial_messages = messages or []
    conv = {
        "id": uuid.uuid4().hex[:12],
        "title": conversation_title(initial_messages, paper),
        "paper": paper,
        "engine": engine,
        "messages": initial_messages,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    return conv


def save(conv: dict) -> None:
    """Write conversation to disk."""
    path = _conversation_path(conv.get("id", ""))
    if path is None:
        raise ValueError("Invalid conversation ID")
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    conv["updated_at"] = _now_iso()
    path.write_text(json.dumps(conv, ensure_ascii=False, indent=2), encoding="utf-8")


def load(conv_id: str) -> dict | None:
    """Load a conversation by id."""
    path = _conversation_path(conv_id)
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def delete(conv_id: str) -> bool:
    """Delete a conversation file."""
    path = _conversation_path(conv_id)
    if path is None or not path.exists():
        return False
    try:
        path.unlink()
        return True
    except OSError:
        return False


def list_conversations() -> list[dict]:
    """Return all conversations as summary dicts, newest first.

    Each summary: {"id", "title", "paper", "time_label", "updated_at"}
    """
    if not HISTORY_DIR.exists():
        return []

    summaries: list[dict] = []
    now = datetime.now()
    today = now.date()
    yesterday = today - timedelta(days=1)

    for path in HISTORY_DIR.glob("*.json"):
        if not _CONVERSATION_ID_PATTERN.fullmatch(path.stem):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        updated = data.get("updated_at", "")
        try:
            dt = datetime.fromisoformat(updated)
            d = dt.date()
            if d == today:
                time_label = "今天"
            elif d == yesterday:
                time_label = "昨天"
            else:
                time_label = f"{d.month}/{d.day}"
        except (ValueError, TypeError):
            time_label = ""

        stored_title = str(data.get("title", "") or "")
        title = stored_title
        if not title or _is_bad_auto_title(title):
            title = conversation_title(data.get("messages", []), data.get("paper", ""))
        if not title:
            title = "未命名对话"

        paper = data.get("paper", "")
        paper_label = paper
        if paper and (title == paper or title == _paper_title(paper) or stored_title == _paper_title(paper)):
            paper_label = ""

        summaries.append({
            "id": path.stem,
            "title": title,
            "paper": paper,
            "paper_label": paper_label,
            "engine": data.get("engine", ""),
            "time_label": time_label,
            "updated_at": updated,
        })

    # Sort by updated_at descending
    summaries.sort(key=lambda s: s["updated_at"], reverse=True)
    return summaries


def update_title(conv: dict, messages: list[dict] | None = None, paper: str = "") -> None:
    """Set or repair auto-generated titles."""
    current = str(conv.get("title", "") or "")
    if not current or _is_bad_auto_title(current):
        conv["title"] = conversation_title(messages or conv.get("messages", []), paper or conv.get("paper", ""))
