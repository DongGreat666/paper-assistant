"""Model profile helpers for the home chat page."""

from typing import Any

import httpx

from config import get_config, read_settings, write_settings
from src.core.engine import (
    TranslationEngine,
    api_key_display,
    build_engine,
    build_engine_from_profile,
    delete_api_secret_refs,
    externalize_profile_api_key,
    get_default_translation_engine,
    has_usable_api_key,
    load_engine_profiles,
    profile_has_api_key,
    save_engine_profiles,
)
from src.utils.http_client import chat_completions_url, chat_message_content, get_client


def resolve_model_defaults() -> dict:
    defaults = dict(read_settings())
    existing_key = str(defaults.get("home_engine_api_key", "") or "").strip()
    if existing_key and not existing_key.startswith("ref:"):
        profile = externalize_profile_api_key(
            {
                "id": defaults.get("home_selected_engine_id") or "home-model",
                "name": defaults.get("home_engine_name") or "Home model",
                "api_key": existing_key,
            },
            "home",
        )
        defaults["home_engine_api_key"] = api_key_display(profile)
        write_settings({"home_engine_api_key": defaults["home_engine_api_key"]})
    if not defaults.get("home_model_auto", True):
        return defaults

    cfg = get_config()
    key = cfg.translate_api_key or cfg.llm_api_key
    if has_usable_api_key(key):
        return defaults

    for profile in load_engine_profiles():
        if profile_has_api_key(profile):
            defaults["home_model_auto"] = False
            defaults["home_selected_engine_id"] = profile.get("id", "env-default")
            defaults["home_engine_name"] = profile.get("name", "")
            defaults["home_engine_api_key"] = api_key_display(profile)
            defaults["home_engine_base_url"] = profile.get("base_url", "")
            defaults["home_engine_model"] = profile.get("model", "")
            defaults["home_engine_temperature"] = profile.get("temperature", "0.3")
            break

    return defaults


def persist_home_model(
    *,
    model_auto: bool,
    selected_engine_id: str,
    engine_api_key: str,
    engine_base_url: str,
    engine_model: str,
    engine_temperature: str,
    engine_name: str,
) -> None:
    # Externalize API key to secrets.json — never write plaintext keys to settings
    key_to_store = ""
    stripped = engine_api_key.strip()
    if stripped:
        if stripped.startswith("ref:"):
            key_to_store = stripped
        else:
            profile = externalize_profile_api_key(
                {"id": selected_engine_id or "home-model", "api_key": stripped},
                "home",
            )
            key_to_store = api_key_display(profile)
    write_settings({
        "home_model_auto": model_auto,
        "home_selected_engine_id": selected_engine_id,
        "home_engine_api_key": key_to_store,
        "home_engine_base_url": engine_base_url,
        "home_engine_model": engine_model,
        "home_engine_temperature": engine_temperature,
        "home_engine_name": engine_name,
    })


def find_profile(profiles: list[dict], profile_id: str) -> dict | None:
    return next((profile for profile in profiles if profile.get("id") == profile_id), None)


def profile_form_values(
    profile: dict,
    fallback_base_url: str,
    fallback_model: str,
    fallback_temperature: str,
) -> dict:
    return {
        "engine_name": profile.get("name", "QA model"),
        "engine_api_key": api_key_display(profile),
        "engine_base_url": profile.get("base_url", fallback_base_url),
        "engine_model": profile.get("model", fallback_model),
        "engine_temperature": profile.get("temperature", fallback_temperature),
    }


def new_engine_form_values() -> dict:
    defaults = get_default_translation_engine()
    qa_model, qa_temp = get_config().get_model_for("qa")
    return {
        "engine_name": "",
        "engine_api_key": "",
        "engine_base_url": defaults.base_url,
        "engine_model": qa_model,
        "engine_temperature": str(qa_temp),
    }


def make_profile(
    *,
    engine_name: str,
    engine_api_key: str,
    engine_base_url: str,
    engine_model: str,
    engine_temperature: str,
) -> dict:
    profile_id = engine_name.strip().lower().replace(" ", "-") or "qa-model"
    profile = {
        "id": profile_id,
        "name": engine_name.strip() or "QA model",
        "base_url": engine_base_url.strip(),
        "model": engine_model.strip(),
        "temperature": engine_temperature.strip() or "0.3",
        "status": "",
    }
    if engine_api_key.strip():
        if engine_api_key.strip().startswith("ref:"):
            profile["api_key_ref"] = engine_api_key.strip()[4:]
        else:
            profile["api_key"] = engine_api_key.strip()
    return profile


def upsert_profile(profiles: list[dict], profile: dict, editing_engine_id: str) -> list[dict]:
    old_id = editing_engine_id if editing_engine_id not in {"", "__new__"} else ""
    existing = [
        item
        for item in profiles
        if item.get("id") not in {profile.get("id"), old_id}
    ]
    updated = [profile, *existing]
    save_engine_profiles(updated)
    return load_engine_profiles()


def remove_profile(profiles: list[dict], profile_id: str) -> list[dict]:
    removed = [item for item in profiles if item.get("id") == profile_id]
    refs = [
        ref
        for item in removed
        for ref in [
            item.get("api_key_ref", ""),
            f"engine:{profile_id}",
            f"chat:{profile_id}",
            f"home:{profile_id}",
        ]
    ]
    delete_api_secret_refs(refs)
    updated = [item for item in profiles if item.get("id") != profile_id]
    save_engine_profiles(updated)
    return load_engine_profiles()


def current_engine_label(model_auto: bool, engine_name: str, engine_model: str) -> str:
    if model_auto:
        return "Auto"
    return engine_name or engine_model or "Unknown"


def build_home_engine(
    *,
    model_auto: bool,
    engine_api_key: str,
    engine_base_url: str,
    engine_model: str,
    engine_temperature: str,
) -> TranslationEngine:
    if model_auto:
        return build_engine(default_profile="qa")
    return build_engine(
        api_key=engine_api_key,
        base_url=engine_base_url,
        model=engine_model,
        temperature=engine_temperature,
        default_profile="qa",
    )


async def chat_completion(
    messages: list[dict[str, Any]],
    engine: TranslationEngine,
    max_tokens: int = 1800,
) -> str:
    client = get_client()
    response = await client.post(
        chat_completions_url(engine.base_url),
        headers={"Authorization": f"Bearer {engine.api_key.strip()}"},
        json={
            "model": engine.model,
            "messages": messages,
            "temperature": engine.temperature,
            "max_tokens": max_tokens,
        },
    )
    response.raise_for_status()
    return chat_message_content(response.json())


async def test_profile(profile: dict) -> None:
    engine = build_engine_from_profile(profile, default_profile="qa")
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=10, read=45, write=10, pool=5),
        limits=httpx.Limits(max_connections=2, max_keepalive_connections=0),
    ) as client:
        response = await client.post(
            chat_completions_url(engine.base_url),
            headers={"Authorization": f"Bearer {engine.api_key.strip()}"},
            json={
                "model": engine.model,
                "messages": [{"role": "user", "content": "Reply briefly: OK"}],
                "temperature": engine.temperature,
                "max_tokens": 200,
            },
        )
        response.raise_for_status()
        chat_message_content(response.json())


def select_engine_action(profiles: list[dict], profile_id: str) -> dict | None:
    """Return state updates for selecting an engine profile, or None if not found."""
    profile = find_profile(profiles, profile_id)
    if profile is None:
        return None
    return {
        "model_auto": False,
        "selected_engine_id": profile_id,
        "engine_name": profile.get("name", "QA model"),
        "engine_api_key": api_key_display(profile),
        "engine_base_url": profile.get("base_url", ""),
        "engine_model": profile.get("model", ""),
        "engine_temperature": profile.get("temperature", ""),
        "status_message": f"Selected model: {profile.get('name', 'QA model')}.",
    }


def start_edit_engine_action(profiles: list[dict], profile_id: str) -> dict | None:
    """Return state updates for starting engine edit, or None if not found."""
    profile = find_profile(profiles, profile_id)
    if profile is None:
        return None
    return {
        "editing_engine_id": profile_id,
        "engine_name": profile.get("name", "QA model"),
        "engine_api_key": api_key_display(profile),
        "engine_base_url": profile.get("base_url", ""),
        "engine_model": profile.get("model", ""),
        "engine_temperature": profile.get("temperature", ""),
    }


def save_engine_action(
    profiles: list[dict],
    *,
    engine_name: str,
    engine_api_key: str,
    engine_base_url: str,
    engine_model: str,
    engine_temperature: str,
    editing_engine_id: str,
) -> tuple[list[dict], str]:
    """Build profile, upsert, return (updated_profiles, profile_id)."""
    profile = make_profile(
        engine_name=engine_name,
        engine_api_key=engine_api_key,
        engine_base_url=engine_base_url,
        engine_model=engine_model,
        engine_temperature=engine_temperature,
    )
    updated = upsert_profile(profiles, profile, editing_engine_id)
    return updated, profile["id"]


def delete_engine_action(profiles: list[dict], profile_id: str) -> list[dict]:
    """Remove a profile and return updated list."""
    return remove_profile(profiles, profile_id)
