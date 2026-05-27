"""
Configuration center — all settings loaded from .env file.

Usage:
    from config import get_config
    cfg = get_config()
    print(cfg.llm_api_key, cfg.papers_dir)
"""

import json
import os
import threading
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

SETTINGS_PATH = Path("data") / "settings.json"

# Thread-safe read/write for settings.json — prevents concurrent writes
# from UISettingsState, HomeState, and SettingsState from corrupting the file.
_settings_lock = threading.Lock()


def read_settings() -> dict:
    """Read settings.json with lock. Returns {} on any error."""
    with _settings_lock:
        if not SETTINGS_PATH.exists():
            return {}
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}


def write_settings(updates: dict) -> None:
    """Merge *updates* into settings.json atomically (read-modify-write under lock)."""
    with _settings_lock:
        existing: dict = {}
        if SETTINGS_PATH.exists():
            try:
                existing = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        if not isinstance(existing, dict):
            existing = {}
        existing.update(updates)
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_PATH.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def _safe_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class Config:
    """Global configuration, singleton pattern."""

    _instance: Optional["Config"] = None

    def __init__(self):
        # Load .env from project root (where this file lives)
        _project_root = Path(__file__).parent
        load_dotenv(_project_root / ".env")

        # --- AI Model (default) ---
        self.llm_api_key: str = os.getenv("LLM_API_KEY", "")
        self.llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.llm_temperature: float = _safe_float(os.getenv("LLM_TEMPERATURE"), 0.3)

        # --- NVIDIA NIM (optional) ---
        self.nvidia_api_key: str = os.getenv("NVIDIA_API_KEY", "")
        self.nvidia_base_url: str = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

        # --- Task-specific models (empty = use default) ---
        self.translate_api_key: str = os.getenv("TRANSLATE_API_KEY", "")
        self.translate_base_url: str = os.getenv("TRANSLATE_BASE_URL", "")
        self.translate_model: str = os.getenv("TRANSLATE_MODEL", "")
        self.translate_temperature: float = _safe_float(os.getenv("TRANSLATE_TEMPERATURE"), 0.2)
        self.qa_model: str = os.getenv("QA_MODEL", "")
        self.qa_temperature: float = _safe_float(os.getenv("QA_TEMPERATURE"), 0.3)
        self.summary_model: str = os.getenv("SUMMARY_MODEL", "")
        self.summary_temperature: float = _safe_float(os.getenv("SUMMARY_TEMPERATURE"), 0.3)

        # --- RAG ---
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        self.chunk_size: int = _safe_int(os.getenv("CHUNK_SIZE"), 500)
        self.chunk_overlap: int = _safe_int(os.getenv("CHUNK_OVERLAP"), 50)

        # --- Paths ---
        self.papers_dir: Path = Path(os.getenv("PAPERS_DIR", "./papers"))
        self.data_dir: Path = Path(os.getenv("DATA_DIR", "./data"))
        self.vector_db_dir: Path = self.data_dir / "vector_db"
        self.chat_history_dir: Path = self.data_dir / "chat_history"
        self.cache_dir: Path = self.data_dir / "cache"

        # --- App ---
        self.app_title: str = os.getenv("APP_TITLE", "Literature Assistant")
        self.debug: bool = os.getenv("DEBUG", "False").lower() == "true"

        # Overlay user overrides from settings.json (written by settings page)
        self._load_user_overrides()

        # Ensure data directories exist
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        for d in [self.papers_dir, self.vector_db_dir, self.chat_history_dir, self.cache_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _load_user_overrides(self) -> None:
        """Overlay values from data/settings.json (written by the settings page)."""
        if not SETTINGS_PATH.exists():
            return
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        if not isinstance(data, dict):
            return
        # Model overrides
        if data.get("default_model"):
            self.llm_model = data["default_model"]
        if data.get("translate_model"):
            self.translate_model = data["translate_model"]
        if data.get("qa_model"):
            self.qa_model = data["qa_model"]
        # Path overrides
        if data.get("papers_dir"):
            self.papers_dir = Path(data["papers_dir"])
        if data.get("data_dir"):
            self.data_dir = Path(data["data_dir"])
            self.vector_db_dir = self.data_dir / "vector_db"
            self.chat_history_dir = self.data_dir / "chat_history"
            self.cache_dir = self.data_dir / "cache"

    @classmethod
    def get(cls) -> "Config":
        """Get or create the global Config instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def reload(self) -> None:
        """Reload config from .env (useful after changing settings)."""
        Config._instance = None
        self.__class__.get()

    def get_model_for(self, task: str) -> tuple[str, float]:
        """Get model name and temperature for a specific task.

        Args:
            task: One of "translate", "qa", "summary".

        Returns:
            (model_name, temperature) — falls back to default if task-specific is empty.
        """
        task_map = {
            "translate": (self.translate_model, self.translate_temperature),
            "qa":        (self.qa_model,        self.qa_temperature),
            "summary":   (self.summary_model,   self.summary_temperature),
        }
        model, temp = task_map.get(task, ("", self.llm_temperature))
        return (model or self.llm_model, temp)


def get_config() -> Config:
    """Convenience function to get the global config."""
    return Config.get()
