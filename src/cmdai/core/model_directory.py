"""Structured model directory for the Web UI and TUI Model Selector.

Provides a unified, ranked view of providers and models with:
- Pinned and recently used models persisted in settings
- Live readiness status (`ready`, `local`, `needs_key`)
- Normalized capability tags (`tools`, `vision`, `thinking`, context length)
- Non-blocking cached remote model lists + local GGUF discovery
"""

import os
import time
from typing import Any, Dict, List, Optional, Tuple

from . import model_catalog as MC
from .providers import (
    PROVIDERS_CATALOG,
    fetch_remote_models,
    has_reasoning,
    load_custom_providers,
)
from .settings import get_settings

LOCAL_PROVIDER_IDS = ("local_gguf", "localllmapi", "ollama", "lmstudio", "vllm")
KEYLESS_PROVIDER_IDS = ("local_gguf", "ollama", "lmstudio", "opencode_zen", "openrouter")

# Short in-memory cache so rapid Web UI polls don't re-hit local servers every second
_MODEL_LIST_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_CACHE_TTL = 20.0


def _all_providers() -> Dict[str, Any]:
    merged = dict(PROVIDERS_CATALOG)
    try:
        custom = load_custom_providers()
        if isinstance(custom, dict):
            merged.update(custom)
    except Exception:
        pass
    return merged


def _get_selector_prefs(settings: Any) -> Dict[str, Any]:
    prefs = settings.config.setdefault("model_selector", {})
    if not isinstance(prefs.get("pinned"), list):
        prefs["pinned"] = []
    if not isinstance(prefs.get("recent"), list):
        prefs["recent"] = []
    return prefs


def make_model_key(provider_id: str, model_id: str) -> str:
    return f"{provider_id}::{model_id}"


def record_recent_model(provider_id: str, model_id: str, max_items: int = 8) -> None:
    if not provider_id or not model_id:
        return
    settings = get_settings()
    prefs = _get_selector_prefs(settings)
    key = make_model_key(provider_id, model_id)
    recent = [k for k in prefs["recent"] if k != key]
    recent.insert(0, key)
    prefs["recent"] = recent[:max_items]
    try:
        settings.save_config()
    except Exception:
        pass


def toggle_pin_model(provider_id: str, model_id: str) -> bool:
    """Toggle pin state for a provider::model pair. Returns new pinned state."""
    settings = get_settings()
    prefs = _get_selector_prefs(settings)
    key = make_model_key(provider_id, model_id)
    pinned = list(prefs["pinned"])
    if key in pinned:
        pinned.remove(key)
        is_pinned = False
    else:
        pinned.insert(0, key)
        is_pinned = True
    prefs["pinned"] = pinned[:20]
    try:
        settings.save_config()
    except Exception:
        pass
    return is_pinned


def _discover_local_gguf_models() -> List[Dict[str, Any]]:
    """Scan local models/ folder for .gguf files."""
    app_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    models_dir = os.path.join(app_root, "models")
    results: List[Dict[str, Any]] = []
    if not os.path.isdir(models_dir):
        return results
    for root, _, files in os.walk(models_dir):
        # Skip whisper voice models subdirectory
        rel_root = os.path.relpath(root, models_dir)
        if rel_root.lower().startswith("whisper"):
            continue
        for fname in sorted(files):
            if not fname.lower().endswith(".gguf"):
                continue
            full_path = os.path.join(root, fname)
            try:
                size_gb = os.path.getsize(full_path) / (1024 ** 3)
            except Exception:
                size_gb = 0.0
            rel_id = fname if rel_root == "." else os.path.join(rel_root, fname).replace("\\", "/")
            results.append({
                "id": rel_id,
                "name": fname,
                "size_gb": round(size_gb, 2),
                "context_length": 0,
                "vision": any(tok in fname.lower() for tok in ("vl", "vision", "llava", "gemma-4", "pixtral")),
                "thinking": has_reasoning("local_gguf", fname),
                "tools": True,
            })
    return results


def _normalize_model_entry(
    provider_id: str,
    provider_name: str,
    raw: Dict[str, Any],
    is_local: bool,
    status: str,
    pinned_set: set,
    recent_rank: Dict[str, int],
    active_key: str,
) -> Dict[str, Any]:
    mid = str(raw.get("id") or raw.get("name") or "").strip()
    name = str(raw.get("name") or mid).strip()
    key = make_model_key(provider_id, mid)

    # Enrich with cached models.dev facts (zero network calls)
    ctx_len = int(raw.get("context_length") or raw.get("context_window") or 0)
    thinking = bool(raw.get("thinking") or raw.get("reasoning") or has_reasoning(provider_id, mid))
    vision = bool(raw.get("vision") or any(t in mid.lower() for t in ("vision", "-vl", "4o", "gemini", "claude-3", "claude-4", "gemma-4")))
    tools = raw.get("tools", True)
    try:
        facts = MC.lookup(provider_id, mid)
        if facts:
            if getattr(facts, "reasoning", None) is not None:
                thinking = bool(facts.reasoning)
            if getattr(facts, "context_limit", 0) and not ctx_len:
                ctx_len = int(facts.context_limit)
            if getattr(facts, "tool_call", None) is not None:
                tools = bool(facts.tool_call)
    except Exception:
        pass

    size_gb = raw.get("size_gb")
    return {
        "key": key,
        "provider_id": provider_id,
        "provider_name": provider_name,
        "model_id": mid,
        "display_name": name,
        "is_local": is_local,
        "status": status,
        "is_active": key == active_key,
        "is_pinned": key in pinned_set,
        "is_recent": key in recent_rank,
        "recent_rank": recent_rank.get(key, 999),
        "context_length": ctx_len,
        "size_gb": size_gb,
        "capabilities": {
            "tools": bool(tools),
            "vision": bool(vision),
            "thinking": bool(thinking),
        },
    }


def _fetch_provider_models_cached(provider_id: str, settings: Any, force_refresh: bool = False) -> List[Dict[str, Any]]:
    now = time.time()
    if not force_refresh and provider_id in _MODEL_LIST_CACHE:
        ts, cached = _MODEL_LIST_CACHE[provider_id]
        if now - ts < _CACHE_TTL:
            return cached

    if provider_id == "local_gguf":
        items = _discover_local_gguf_models()
        _MODEL_LIST_CACHE[provider_id] = (now, items)
        return items

    items: List[Dict[str, Any]] = []
    try:
        api_key = settings.get_api_key(provider_id) or ""
        raw_list = fetch_remote_models(provider_id, api_key=api_key, timeout=4.0)
        if isinstance(raw_list, list):
            for entry in raw_list:
                if isinstance(entry, dict) and entry.get("id"):
                    items.append(entry)
                elif isinstance(entry, str) and entry.strip():
                    items.append({"id": entry.strip(), "name": entry.strip()})
    except Exception:
        pass

    # Fallback to models.dev offline catalog if provider doesn't support live fetch
    if not items:
        try:
            cat_models = MC.list_provider_models(provider_id)
            if isinstance(cat_models, list):
                for m in cat_models[:60]:
                    if isinstance(m, dict) and m.get("id"):
                        items.append(m)
                    elif isinstance(m, str):
                        items.append({"id": m, "name": m})
        except Exception:
            pass

    _MODEL_LIST_CACHE[provider_id] = (now, items)
    return items


def get_structured_directory(
    active_provider: str = "",
    active_model: str = "",
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Return a clean, categorized provider + model payload for Web UI and TUI."""
    settings = get_settings()
    prefs = _get_selector_prefs(settings)
    pinned_list: List[str] = list(prefs.get("pinned") or [])
    recent_list: List[str] = list(prefs.get("recent") or [])
    pinned_set = set(pinned_list)
    recent_rank = {k: i for i, k in enumerate(recent_list)}

    active_provider = active_provider or settings.config.get("default_provider") or "local_gguf"
    active_model = active_model or settings.config.get("default_model") or ""
    active_key = make_model_key(active_provider, active_model)

    providers_map = _all_providers()
    providers_out: List[Dict[str, Any]] = []
    models_out: List[Dict[str, Any]] = []
    seen_keys = set()

    for pid, pinfo in providers_map.items():
        pname = getattr(pinfo, "name", None) or (pinfo.get("name") if isinstance(pinfo, dict) else pid)
        requires_key = getattr(pinfo, "requires_key", True) if not isinstance(pinfo, dict) else pinfo.get("requires_key", True)
        is_local = pid in LOCAL_PROVIDER_IDS
        has_key = bool(settings.get_api_key(pid))
        keyless = (not requires_key) or (pid in KEYLESS_PROVIDER_IDS)

        if is_local:
            status = "local"
        elif has_key:
            status = "ready"
        elif keyless:
            status = "keyless"
        else:
            status = "needs_key"

        # Fetch live/cached models only for ready, local, keyless, or active provider
        p_models: List[Dict[str, Any]] = []
        if status in ("local", "ready", "keyless") or pid == active_provider:
            raw_models = _fetch_provider_models_cached(pid, settings, force_refresh=force_refresh)
            for raw in raw_models[:80]:
                entry = _normalize_model_entry(
                    provider_id=pid,
                    provider_name=pname,
                    raw=raw,
                    is_local=is_local,
                    status=status,
                    pinned_set=pinned_set,
                    recent_rank=recent_rank,
                    active_key=active_key,
                )
                if entry["model_id"] and entry["key"] not in seen_keys:
                    seen_keys.add(entry["key"])
                    p_models.append(entry)
                    models_out.append(entry)

        providers_out.append({
            "id": pid,
            "name": pname,
            "status": status,
            "is_local": is_local,
            "has_key": has_key,
            "model_count": len(p_models),
            "is_active": pid == active_provider,
        })

    # Ensure active model is always represented even if server is offline
    if active_provider and active_model and active_key not in seen_keys:
        pinfo = providers_map.get(active_provider)
        pname = getattr(pinfo, "name", None) or active_provider
        models_out.insert(
            0,
            _normalize_model_entry(
                provider_id=active_provider,
                provider_name=pname,
                raw={"id": active_model, "name": active_model},
                is_local=active_provider in LOCAL_PROVIDER_IDS,
                status="local" if active_provider in LOCAL_PROVIDER_IDS else "ready",
                pinned_set=pinned_set,
                recent_rank=recent_rank,
                active_key=active_key,
            ),
        )

    # Sort providers: active -> local -> ready -> keyless -> needs_key
    status_order = {"local": 0, "ready": 1, "keyless": 2, "needs_key": 3}
    providers_out.sort(key=lambda p: (0 if p["is_active"] else 1, status_order.get(p["status"], 9), p["name"].lower()))

    # Sort models: active -> pinned -> recent -> local -> ready -> name
    models_out.sort(
        key=lambda m: (
            0 if m["is_active"] else 1,
            0 if m["is_pinned"] else 1,
            m["recent_rank"] if m["is_recent"] else 999,
            status_order.get(m["status"], 9),
            m["display_name"].lower(),
        )
    )

    return {
        "active_provider": active_provider,
        "active_model": active_model,
        "providers": providers_out,
        "models": models_out,
        "pinned_count": sum(1 for m in models_out if m["is_pinned"]),
        "ready_providers": sum(1 for p in providers_out if p["status"] in ("local", "ready", "keyless")),
        "total_providers": len(providers_out),
    }
