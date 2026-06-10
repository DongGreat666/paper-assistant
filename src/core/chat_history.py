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


def new_conversation(paper: str = "", messages: list[dict] | None = None, engine: str = "") -> dict:
    """Create a conversation dict (not yet saved)."""
    conv = {
        "id": uuid.uuid4().hex[:12],
        "title": "",
        "paper": paper,
        "engine": engine,
        "messages": messages or [],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    # Auto-title from first user message
    for m in conv["messages"]:
        if m.get("role") == "user" and m.get("content", "").strip():
            conv["title"] = _make_title(m["content"])
            break
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

        summaries.append({
            "id": path.stem,
            "title": data.get("title", "未命名对话"),
            "paper": data.get("paper", ""),
            "engine": data.get("engine", ""),
            "time_label": time_label,
            "updated_at": updated,
        })

    # Sort by updated_at descending
    summaries.sort(key=lambda s: s["updated_at"], reverse=True)
    return summaries


def update_title(conv: dict, first_user_msg: str) -> None:
    """Set title from first user message if not already set."""
    if not conv.get("title") and first_user_msg.strip():
        conv["title"] = _make_title(first_user_msg)
