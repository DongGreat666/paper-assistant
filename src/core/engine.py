"""Translation/chat engine config, profile CRUD, and local secret references."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from config import get_config


ENGINE_PROFILES_PATH = Path("data") / "translation_engines.json"
CHAT_ENGINE_PROFILES_PATH = Path("data") / "chat_engines.json"
SECRETS_PATH = Path("data") / "secrets.json"


@dataclass
class TranslationEngine:
    """OpenAI-compatible engine settings."""

    api_key: str
    base_url: str
    model: str
    temperature: float = 0.2


def _safe_float(value: float | str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_json(path: Path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default
    return data if isinstance(data, type(default)) else default


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip().lower()).strip("-")
    return slug or "profile"


def load_api_secrets() -> dict[str, str]:
    """Load API keys from data/secrets.json."""
    data = _read_json(SECRETS_PATH, {})
    if isinstance(data.get("api_keys"), dict):
        data = data["api_keys"]
    return {
        str(key): value.strip()
        for key, value in data.items()
        if isinstance(value, str) and value.strip()
    }


def save_api_secrets(secrets: dict[str, str]) -> None:
    """Persist API keys in one ignored local file."""
    SECRETS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SECRETS_PATH.write_text(
        json.dumps(secrets, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def make_api_key_ref(profile: dict, namespace: str = "engine") -> str:
    """Create a stable reference name for a profile's API key."""
    existing = (profile.get("api_key_ref") or "").strip()
    if existing:
        return existing
    raw = profile.get("id") or profile.get("name") or namespace
    return f"{namespace}:{_slug(str(raw))}"


def api_key_display(profile: dict) -> str:
    """Return a non-secret value for password fields."""
    ref = (profile.get("api_key_ref") or "").strip()
    return f"ref:{ref}" if ref else ""


def resolve_api_key(profile: dict) -> str:
    """Resolve a real API key from a profile, secret ref, or env defaults."""
    key = (profile.get("api_key") or "").strip()
    if key and not key.startswith("ref:"):
        return key

    ref = key[4:] if key.startswith("ref:") else (profile.get("api_key_ref") or "").strip()
    if ref:
        secret_key = load_api_secrets().get(ref, "").strip()
        if secret_key:
            return secret_key

    cfg = get_config()
    profile_id = profile.get("id", "")
    if profile_id == "env-default":
        return cfg.translate_api_key or cfg.llm_api_key
    if str(profile_id).startswith("nvidia-"):
        return cfg.nvidia_api_key
    if profile_id == "deepseek-direct":
        return cfg.translate_api_key or cfg.llm_api_key
    return ""


def profile_has_api_key(profile: dict) -> bool:
    """Whether a profile can resolve a usable key."""
    return has_usable_api_key(resolve_api_key(profile))


def externalize_profile_api_key(profile: dict, namespace: str = "engine") -> dict:
    """Move inline api_key into data/secrets.json and store api_key_ref."""
    profile = dict(profile)
    key = (profile.get("api_key") or "").strip()

    if key.startswith("ref:"):
        profile["api_key_ref"] = key[4:].strip()
        profile.pop("api_key", None)
        return profile

    if key:
        ref = make_api_key_ref(profile, namespace)
        secrets = load_api_secrets()
        secrets[ref] = key
        save_api_secrets(secrets)
        profile["api_key_ref"] = ref

    profile.pop("api_key", None)
    profile.pop("has_api_key", None)
    return profile


def externalize_profiles(profiles: list[dict], namespace: str = "engine") -> list[dict]:
    """Externalize inline keys for all profiles."""
    return [
        externalize_profile_api_key(profile, namespace)
        for profile in profiles
        if isinstance(profile, dict)
    ]


def prepare_profile_for_ui(profile: dict) -> dict:
    """Add non-secret UI metadata to a profile."""
    profile = dict(profile)
    profile["has_api_key"] = profile_has_api_key(profile)
    profile["api_key"] = api_key_display(profile)
    return profile


def get_default_translation_engine() -> TranslationEngine:
    """Read translation settings from .env with sane fallbacks."""
    cfg = get_config()
    model, temperature = cfg.get_model_for("translate")
    return TranslationEngine(
        api_key=cfg.translate_api_key or cfg.llm_api_key,
        base_url=cfg.translate_base_url or cfg.llm_base_url,
        model=model,
        temperature=temperature,
    )


def build_engine(
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    temperature: float | str | None = None,
    default_profile: str = "translate",
) -> TranslationEngine:
    """Build a TranslationEngine from overrides, refs, and .env defaults."""
    cfg = get_config()
    default_model, default_temp = cfg.get_model_for(default_profile)
    defaults = get_default_translation_engine()
    resolved_key = api_key.strip()
    if resolved_key.startswith("ref:"):
        resolved_key = resolve_api_key({"api_key_ref": resolved_key[4:]})
    return TranslationEngine(
        api_key=resolved_key or defaults.api_key,
        base_url=(base_url or "").strip() or defaults.base_url,
        model=(model or "").strip() or default_model,
        temperature=_safe_float(temperature, default_temp),
    )


def build_engine_from_profile(profile: dict, default_profile: str = "translate") -> TranslationEngine:
    """Build an engine and resolve api_key_ref at call time."""
    return build_engine(
        api_key=resolve_api_key(profile),
        base_url=profile.get("base_url", ""),
        model=profile.get("model", ""),
        temperature=profile.get("temperature"),
        default_profile=default_profile,
    )


def has_usable_api_key(api_key: str) -> bool:
    """Check whether an API key looks usable enough to attempt a request."""
    key = (api_key or "").strip()
    return bool(
        key
        and not key.startswith("sk-your-api-key")
        and key.lower() not in {"none", "null"}
    )


def _default_engine_profiles() -> list[dict]:
    cfg = get_config()
    default = get_default_translation_engine()
    profiles = [
        {
            "id": "env-default",
            "name": "Default .env",
            "api_key_ref": "",
            "base_url": default.base_url,
            "model": default.model,
            "temperature": str(default.temperature),
            "status": "",
        },
        {
            "id": "deepseek-direct",
            "name": "DeepSeek V4 Flash",
            "api_key_ref": "",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-v4-flash",
            "temperature": "0.2",
            "status": "",
        },
    ]
    if cfg.nvidia_api_key:
        profiles.extend(
            [
                {
                    "id": "nvidia-llama",
                    "name": "NVIDIA Llama 3.1 8B",
                    "api_key_ref": "",
                    "base_url": cfg.nvidia_base_url,
                    "model": "meta/llama-3.1-8b-instruct",
                    "temperature": "0.2",
                    "status": "",
                },
                {
                    "id": "nvidia-deepseek-flash",
                    "name": "NVIDIA DeepSeek V4 Flash",
                    "api_key_ref": "",
                    "base_url": cfg.nvidia_base_url,
                    "model": "deepseek-ai/deepseek-v4-flash",
                    "temperature": "0.3",
                    "status": "",
                },
                {
                    "id": "nvidia-llama-small",
                    "name": "NVIDIA Llama 3.2 3B (Fast)",
                    "api_key_ref": "",
                    "base_url": cfg.nvidia_base_url,
                    "model": "meta/llama-3.2-3b-instruct",
                    "temperature": "0.2",
                    "status": "",
                },
            ]
        )
    return [prepare_profile_for_ui(profile) for profile in profiles]


def load_engine_profiles() -> list[dict]:
    """Load saved local translation engine profiles."""
    defaults = _default_engine_profiles()
    if not ENGINE_PROFILES_PATH.exists():
        return defaults

    data = _read_json(ENGINE_PROFILES_PATH, [])
    profiles = externalize_profiles(data, "engine")

    default_by_id = {p["id"]: p for p in defaults}
    for profile in profiles:
        if profile.get("id") in default_by_id:
            preset = default_by_id[profile["id"]]
            profile["base_url"] = preset["base_url"]
            profile["model"] = preset["model"]
            profile["temperature"] = preset["temperature"]

    existing_ids = {p.get("id") for p in profiles}
    profiles.extend(p for p in defaults if p["id"] not in existing_ids)
    profiles = [
        p
        for p in profiles
        if p.get("id") not in {"nvidia-kimi-k2", "nvidia-glm4"}
    ]
    for profile in profiles:
        profile.setdefault("status", "")
        profile.pop("api_key", None)

    save_engine_profiles(profiles)
    return [prepare_profile_for_ui(profile) for profile in profiles]


def save_engine_profiles(profiles: list[dict]) -> None:
    """Persist translation engine profiles without inline API keys."""
    ENGINE_PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    profiles = externalize_profiles(profiles, "engine")
    ENGINE_PROFILES_PATH.write_text(
        json.dumps(profiles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _default_chat_profiles() -> list[dict]:
    default = get_default_translation_engine()
    return [
        {
            "id": "env-default",
            "name": "Default .env",
            "api_key_ref": "",
            "base_url": default.base_url,
            "model": default.model,
            "temperature": "0.3",
        }
    ]


def load_chat_engine_profiles() -> list[dict]:
    """Load saved chat engine profiles."""
    defaults = _default_chat_profiles()
    if not CHAT_ENGINE_PROFILES_PATH.exists():
        return defaults

    data = _read_json(CHAT_ENGINE_PROFILES_PATH, [])
    if not data:
        return defaults

    profiles = externalize_profiles(data, "chat")
    if not any(profile.get("id") == "env-default" for profile in profiles):
        profiles.insert(0, defaults[0])
    for profile in profiles:
        profile.pop("api_key", None)

    save_chat_engine_profiles(profiles)
    return profiles


def save_chat_engine_profiles(profiles: list[dict]) -> None:
    """Persist chat engine profiles without inline API keys."""
    CHAT_ENGINE_PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
    profiles = externalize_profiles(profiles, "chat")
    CHAT_ENGINE_PROFILES_PATH.write_text(
        json.dumps(profiles, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
