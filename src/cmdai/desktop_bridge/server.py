"""Cross-platform FastAPI bridge for CMDAI CODE Desktop (Rust + Python).

This module lives in ``src/cmdai/desktop_bridge/`` and is marked immutable
against CLI GitHub updates in ``desktop/desktop_sync_manifest.json``. It
dynamically imports the shared Python core (``agent``, ``core``, ``indexer``,
``mcp``, ``editor.core``) so CLI updates land seamlessly in Desktop without
altering the desktop shell or UI.
"""

from __future__ import annotations

import argparse
import asyncio
import difflib
import json
import os
import platform
import queue as std_queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_THIS_FILE = Path(__file__).resolve()
_APP_ROOT = _THIS_FILE.parents[3]
_SRC_DIR = _APP_ROOT / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import uvicorn

from cmdai.core.capabilities import (
    clean_model_name,
    cycle_order,
    forget_uncached_capabilities,
    get_model_capability,
    normalize_level,
    note_reasoning_observed,
)
from cmdai.core.checkpoints import CheckpointManager
from cmdai.core.model_paths import list_gguf_files
from cmdai.core.providers import PROVIDERS_CATALOG, load_custom_providers
from cmdai.core.pty_terminal import get_pty_terminal
from cmdai.core.sessions import SessionManager, clean_title_from_prompt, format_relative_time
from cmdai.core.settings import SettingsManager
from cmdai.indexer.ast_indexer import extract_symbols_from_code
from cmdai.indexer.repo_map import build_repo_graph
from cmdai.mcp.client import MCPClient

try:
    from cmdai.editor.core.diagnostics import linter, scan_project
    from cmdai.editor.core.format import format_source, formatter_available
except ModuleNotFoundError:
    import types

    _ed_pkg = types.ModuleType("cmdai.editor")
    _ed_pkg.__path__ = [str(_SRC_DIR / "cmdai" / "editor")]
    sys.modules["cmdai.editor"] = _ed_pkg
    from cmdai.editor.core.diagnostics import linter, scan_project
    from cmdai.editor.core.format import format_source, formatter_available


def _rust_binary_path(app_root: Path) -> Optional[Path]:
    exe_name = "cmdai-desktop.exe" if os.name == "nt" else "cmdai-desktop"
    candidates = [
        app_root / "desktop" / "target" / "release" / exe_name,
        app_root / "desktop" / "target" / "debug" / exe_name,
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def _run_rust_cli(app_root: Path, args: List[str], timeout: int = 30) -> Optional[Dict[str, Any]]:
    bin_path = _rust_binary_path(app_root)
    if not bin_path:
        return None
    try:
        proc = subprocess.run(
            [str(bin_path)] + args,
            cwd=str(app_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except Exception:
        return None
    return None


def _python_fallback_platform(app_root: Path) -> Dict[str, Any]:
    sys_name = platform.system().lower()
    os_norm = "windows" if "windows" in sys_name else ("linux" if "linux" in sys_name else sys_name)
    shell = "powershell.exe" if os_norm == "windows" else os.environ.get("SHELL", "bash")
    return {
        "os": os_norm,
        "arch": platform.machine().lower() or "x86_64",
        "shell": shell,
        "shell_flag": "-NoProfile -Command" if os_norm == "windows" else "-lc",
        "app_root": str(app_root).replace("\\", "/"),
        "python_bin": sys.executable,
        "desktop_exe": str(_rust_binary_path(app_root) or "python-fallback"),
        "cross_platform": ["windows", "linux", "macos"],
        "rust_active": _rust_binary_path(app_root) is not None,
    }


def _resolve_git_root(workdir: Path, app_root: Optional[Path] = None) -> Optional[Path]:
    home_dir = Path.home().resolve()
    if (workdir / ".git").exists():
        return workdir
    for parent in workdir.parents:
        try:
            rp = parent.resolve()
            if rp == home_dir or rp.parent == rp:
                continue
        except Exception:
            pass
        if (parent / ".git").exists():
            return parent
    return None


def _human_git_status(code: str) -> str:
    c = (code or "").strip()
    mapping = {
        "??": "new",
        "M": "mod",
        "MM": "mod",
        "AM": "mod",
        "A": "add",
        "D": "del",
        "R": "ren",
        "C": "copy",
        "UU": "conflict",
    }
    return mapping.get(c, c or "mod")


def _git_status_summary(workdir: Path, app_root: Optional[Path] = None) -> Dict[str, Any]:
    git_target = _resolve_git_root(workdir, app_root)
    if not git_target:
        return {"is_repo": False, "branch": "no-git", "commit": "", "changed": [], "branches": []}
    out: Dict[str, Any] = {"is_repo": True, "branch": "main", "commit": "", "changed": [], "branches": ["main"]}
    try:
        br = subprocess.run(
            ["git", "-c", "safe.directory=*", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=str(git_target),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if br.returncode == 0 and br.stdout.strip():
            out["branch"] = br.stdout.strip()
        br_all = subprocess.run(
            ["git", "-c", "safe.directory=*", "branch", "--format=%(refname:short)"],
            cwd=str(git_target),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if br_all.returncode == 0 and br_all.stdout:
            branches = [b.strip() for b in br_all.stdout.splitlines() if b.strip()]
            if out["branch"] and out["branch"] not in branches:
                branches.insert(0, out["branch"])
            if branches:
                out["branches"] = branches
        cm = subprocess.run(
            ["git", "-c", "safe.directory=*", "rev-parse", "--short", "HEAD"],
            cwd=str(git_target),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if cm.returncode == 0 and cm.stdout.strip():
            val = cm.stdout.strip()
            out["commit"] = "" if val == "HEAD" else val
        st = subprocess.run(
            ["git", "-c", "safe.directory=*", "status", "--porcelain"],
            cwd=str(git_target),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if st.returncode == 0 and st.stdout:
            changed = []
            for raw in st.stdout.splitlines():
                if len(raw) >= 4:
                    code = _human_git_status(raw[:2])
                    path = raw[3:].strip().strip('"').replace("\\", "/")
                    changed.append({"status": code, "path": path})
            out["changed"] = changed[:100]
    except Exception:
        pass
    return out


def _mask_key(val: str) -> str:
    s = (val or "").strip()
    if not s:
        return ""
    if len(s) <= 8:
        return "•" * len(s)
    return f"{s[:4]}••••{s[-4:]}"


def _probe_local_api_models(base_url: str, api_key: str = "") -> List[str]:
    """Quick non-blocking check (<0.12s) for models served by a local OpenAI-compatible server."""
    if not base_url or not _is_local_api_reachable(base_url, timeout=0.08):
        return []
    import urllib.request

    url = base_url.rstrip("/") + "/models"
    req = urllib.request.Request(url, method="GET")
    if api_key.strip():
        req.add_header("Authorization", f"Bearer {api_key.strip()}")
    try:
        with urllib.request.urlopen(req, timeout=0.25) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            data = payload.get("data") or payload.get("models") or []
            out: List[str] = []
            for item in data:
                mid = item.get("id") or item.get("name") or item.get("model") if isinstance(item, dict) else str(item)
                if mid and mid not in out:
                    out.append(str(mid))
            return out
    except Exception:
        return []


def _is_local_api_reachable(base_url: str, timeout: float = 0.2) -> bool:
    if not base_url:
        return False
    import socket
    from urllib.parse import urlparse

    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def _normalize_mode(raw: Optional[str]) -> str:
    m = str(raw or "code").strip().lower()
    if m in ("auto", "code", "plan"):
        return m
    if m == "turbo":
        return "auto"
    return "code"


_PROVIDERS_CACHE: Dict[str, Any] = {"ts": 0.0, "sig": "", "payload": None}


def _invalidate_providers_cache() -> None:
    _PROVIDERS_CACHE["ts"] = 0.0
    _PROVIDERS_CACHE["payload"] = None


def _build_providers_payload(settings_mgr: SettingsManager, force_refresh: bool = False) -> Dict[str, Any]:
    cfg = settings_mgr.config or {}
    sig = json.dumps(
        {
            "dp": cfg.get("default_provider"),
            "dm": cfg.get("default_model"),
            "ak": sorted((cfg.get("api_keys") or {}).keys()),
            "cm": cfg.get("custom_models"),
            "cp": cfg.get("custom_providers"),
            "md": (cfg.get("agent") or {}).get("mode"),
            "rl": (cfg.get("generation") or {}).get("reasoning_level"),
        },
        sort_keys=True,
        default=str,
    )
    now = time.monotonic()
    if (
        not force_refresh
        and _PROVIDERS_CACHE["payload"] is not None
        and _PROVIDERS_CACHE["sig"] == sig
        and (now - float(_PROVIDERS_CACHE["ts"])) < 25.0
    ):
        return _PROVIDERS_CACHE["payload"]

    api_keys = cfg.get("api_keys") or {}
    custom_models = cfg.get("custom_models") or {}
    load_custom_providers()

    gguf_paths = list_gguf_files()
    gguf_files = [Path(p).name for p in gguf_paths]
    gguf_by_name = {Path(p).name: str(p) for p in gguf_paths}
    providers_list: List[Dict[str, Any]] = []
    cfg_active_provider = str(cfg.get("default_provider") or "openrouter")
    cfg_active_model = str(cfg.get("default_model") or "")

    for pid, pinfo in PROVIDERS_CATALOG.items():
        key_val = str(api_keys.get(pid) or "")
        raw_models: List[str] = []
        if pid == "local_gguf":
            raw_models = list(gguf_files) or ["(No .gguf weights found in models/)"]
        elif pid in ("localllmapi", "ollama", "lmstudio"):
            live_models = _probe_local_api_models(pinfo.base_url, key_val)
            for lm in live_models:
                if lm not in raw_models:
                    raw_models.append(lm)
            if pid == cfg_active_provider and cfg_active_model and cfg_active_model not in raw_models:
                raw_models.append(cfg_active_model)
            if pid == "localllmapi" and not raw_models and gguf_files:
                raw_models = list(gguf_files)
        else:
            try:
                from cmdai.core.model_catalog import models_for_provider
                cat_models = models_for_provider(pid) or []
                for cm in cat_models[:80]:
                    mid_c = str(cm.get("id") or "").strip() if isinstance(cm, dict) else str(cm).strip()
                    if mid_c and mid_c not in raw_models:
                        raw_models.append(mid_c)
            except Exception:
                pass
            if not raw_models and pid in ("opencode", "opencode_zen"):
                raw_models = list(pinfo.default_models or [])
            if pid == cfg_active_provider and cfg_active_model and cfg_active_model not in raw_models:
                raw_models.insert(0, cfg_active_model)
        extra = custom_models.get(pid) or []
        if isinstance(extra, list):
            for m in extra:
                if m and m not in raw_models:
                    raw_models.append(m)

        models_meta: List[Dict[str, Any]] = []
        for mid in raw_models:
            if mid.startswith("("):
                models_meta.append(
                    {
                        "id": mid,
                        "name": mid,
                        "raw_name": mid,
                        "thinking": False,
                        "vision": False,
                        "levels": [],
                        "default_level": "off",
                        "param_style": "none",
                        "max_budget": 0,
                        "context_limit": 0,
                        "source": "placeholder",
                        "is_placeholder": True,
                    }
                )
                continue
            try:
                m_path = gguf_by_name.get(mid, "")
                cap = get_model_capability(
                    mid,
                    pid,
                    api_key=key_val,
                    model_path=m_path,
                    timeout=0.35,
                )
                has_thinking = bool(cap.thinking)
                detected_levels = cycle_order(cap.levels) if has_thinking else []
                models_meta.append(
                    {
                        "id": mid,
                        "name": clean_model_name(mid),
                        "raw_name": mid,
                        "thinking": has_thinking,
                        "vision": bool(cap.vision),
                        "levels": detected_levels,
                        "default_level": cap.default_level or ("medium" if has_thinking else "off"),
                        "param_style": cap.param_style,
                        "max_budget": int(cap.max_budget or 0),
                        "context_limit": int(cap.context_limit or 0),
                        "source": cap.source,
                        "is_placeholder": False,
                    }
                )
            except Exception:
                models_meta.append(
                    {
                        "id": mid,
                        "name": clean_model_name(mid),
                        "raw_name": mid,
                        "thinking": False,
                        "vision": False,
                        "levels": [],
                        "default_level": "off",
                        "param_style": "none",
                        "max_budget": 0,
                        "context_limit": 0,
                        "source": "fallback",
                        "is_placeholder": False,
                    }
                )

        key_val = str(api_keys.get(pid) or "")
        providers_list.append(
            {
                "id": pid,
                "name": pinfo.name,
                "provider_type": pinfo.provider_type,
                "base_url": pinfo.base_url,
                "key_url": pinfo.key_url,
                "has_key": bool(key_val.strip()),
                "masked_key": _mask_key(key_val),
                "models": models_meta,
            }
        )

    active_provider = str(cfg.get("default_provider") or "openrouter")
    active_model = str(cfg.get("default_model") or "")
    if not active_model:
        for p in providers_list:
            if p["id"] == active_provider and p["models"]:
                active_model = p["models"][0]["id"]
                break
    if not active_model:
        active_model = "deepseek/deepseek-r1:free"

    payload = {
        "active_provider": active_provider,
        "active_model": active_model,
        "mode": _normalize_mode((cfg.get("agent") or {}).get("mode")),
        "reasoning_level": normalize_level((cfg.get("generation") or {}).get("reasoning_level") or "medium") or "medium",
        "providers": providers_list,
    }
    _PROVIDERS_CACHE["ts"] = time.monotonic()
    _PROVIDERS_CACHE["sig"] = sig
    _PROVIDERS_CACHE["payload"] = payload
    return payload


def _safe_resolve(workdir: Path, rel_path: str) -> Path:
    clean = (rel_path or "").strip().lstrip("/\\")
    target = (workdir / clean).resolve()
    root_res = workdir.resolve()
    try:
        target.relative_to(root_res)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Path outside workspace root") from exc
    return target


def _compute_hunks(old_text: str, new_text: str, rel_path: str) -> Dict[str, Any]:
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    hunks: List[Dict[str, Any]] = []
    added_total = 0
    removed_total = 0

    for idx, (tag, i1, i2, j1, j2) in enumerate(sm.get_opcodes()):
        if tag == "equal":
            continue
        ctx_before_start = max(0, i1 - 2)
        ctx_after_end = min(len(old_lines), i2 + 2)
        rows: List[Dict[str, Any]] = []
        for k in range(ctx_before_start, i1):
            rows.append(
                {
                    "type": "context",
                    "old_line": k + 1,
                    "new_line": j1 - (i1 - k) + 1,
                    "old_text": old_lines[k],
                    "new_text": old_lines[k],
                }
            )
        removed_chunk = old_lines[i1:i2]
        added_chunk = new_lines[j1:j2]
        removed_total += len(removed_chunk)
        added_total += len(added_chunk)
        max_len = max(len(removed_chunk), len(added_chunk))
        for k in range(max_len):
            o_line = (i1 + k + 1) if k < len(removed_chunk) else None
            n_line = (j1 + k + 1) if k < len(added_chunk) else None
            o_txt = removed_chunk[k] if k < len(removed_chunk) else None
            n_txt = added_chunk[k] if k < len(added_chunk) else None
            row_type = "modify" if (o_txt is not None and n_txt is not None) else ("remove" if o_txt is not None else "add")
            rows.append(
                {
                    "type": row_type,
                    "old_line": o_line,
                    "new_line": n_line,
                    "old_text": o_txt,
                    "new_text": n_txt,
                }
            )
        for k in range(i2, ctx_after_end):
            rows.append(
                {
                    "type": "context",
                    "old_line": k + 1,
                    "new_line": j2 + (k - i2) + 1,
                    "old_text": old_lines[k],
                    "new_text": old_lines[k],
                }
            )
        hunks.append(
            {
                "id": f"hunk_{idx}",
                "tag": tag,
                "old_start": i1 + 1,
                "old_count": i2 - i1,
                "new_start": j1 + 1,
                "new_count": j2 - j1,
                "new_lines": added_chunk,
                "rows": rows,
            }
        )

    unified = "".join(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
            lineterm="\n",
        )
    )
    return {
        "path": rel_path,
        "added": added_total,
        "removed": removed_total,
        "hunks": hunks,
        "unified": unified,
    }


_INTERNAL_TREE_SKIP_NAMES = {
    ".git", ".cmdai_code_project", ".cmdai", "__pycache__", "node_modules", ".venv", "venv",
    "target", ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build", "models",
    "cache", "logs", "cmdai_code.egg-info",
}


def _is_internal_tree_path(rel_path: str) -> bool:
    norm = (rel_path or "").replace("\\", "/").strip("/")
    if not norm:
        return False
    parts = norm.split("/")
    if any(
        p in _INTERNAL_TREE_SKIP_NAMES
        or p.startswith("node_modules")
        or p.endswith(".egg-info")
        or p.endswith(".npm-backup")
        for p in parts
    ):
        return True
    if norm == "app" or norm.startswith("app/sessions") or norm == "desktop/target" or norm.startswith("desktop/target/"):
        return True
    return False


def _filter_tree_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    entries = [e for e in (data.get("entries") or []) if not _is_internal_tree_path(e.get("path", ""))]
    return {
        **data,
        "count": len(entries),
        "entries": entries,
    }


def _python_tree_fallback(workdir: Path, limit: int = 1200) -> Dict[str, Any]:
    entries: List[Dict[str, Any]] = []

    def _walk(cur: Path, depth: int) -> None:
        if len(entries) >= limit or depth > 6:
            return
        try:
            items = sorted(cur.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for p in items:
            if len(entries) >= limit:
                break
            if p.is_dir():
                if (
                    p.name in _INTERNAL_TREE_SKIP_NAMES
                    or p.name.startswith("node_modules")
                    or p.name.endswith(".egg-info")
                    or p.name.endswith(".npm-backup")
                ):
                    continue
                rel = str(p.relative_to(workdir)).replace("\\", "/")
                if _is_internal_tree_path(rel):
                    continue
                entries.append({"path": rel, "name": p.name, "kind": "dir", "size": 0, "lang": "dir", "depth": depth})
                _walk(p, depth + 1)
            elif p.is_file():
                rel = str(p.relative_to(workdir)).replace("\\", "/")
                if _is_internal_tree_path(rel):
                    continue
                ext = p.suffix.lower()
                lang = {
                    ".py": "python", ".rs": "rust", ".js": "javascript", ".ts": "typescript",
                    ".json": "json", ".md": "markdown", ".html": "html", ".css": "css",
                    ".toml": "toml", ".sh": "shell", ".bat": "script",
                }.get(ext, "text")
                entries.append(
                    {
                        "path": rel,
                        "name": p.name,
                        "kind": "file",
                        "size": p.stat().st_size,
                        "lang": lang,
                        "depth": depth,
                    }
                )

    _walk(workdir, 0)
    return {"workdir": str(workdir).replace("\\", "/"), "count": len(entries), "entries": entries}


class ModelSettingsReq(BaseModel):
    provider: str
    model: str
    mode: Optional[str] = None
    reasoning_level: Optional[str] = None
    api_key: Optional[str] = None


class SaveFileReq(BaseModel):
    path: str
    content: str


class FormatFileReq(BaseModel):
    path: str
    content: str


class DiffPreviewReq(BaseModel):
    path: str
    old_content: str
    new_content: str


class ApplyHunkReq(BaseModel):
    path: str
    old_start: int
    old_count: int
    new_lines: List[str]


class TerminalRunReq(BaseModel):
    command: str
    cwd: Optional[str] = None


class AgentStreamReq(BaseModel):
    prompt: str
    session_id: Optional[str] = None
    workdir: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    mode: str = "auto"
    thinking_level: str = "medium"
    pinned_files: List[str] = Field(default_factory=list)
    use_live: bool = True


class SyncRunReq(BaseModel):
    dry_run: bool = False


class GitCheckoutReq(BaseModel):
    branch: str


class WorkspaceSwitchReq(BaseModel):
    workdir: str
    create_if_missing: bool = False


class CustomProviderReq(BaseModel):
    name: str
    base_url: str
    api_key: str = ""
    models: str = ""
    provider_id: str = ""


class CheckpointCreateReq(BaseModel):
    prompt: str = "Manual Desktop Snapshot"


class CheckpointRestoreReq(BaseModel):
    checkpoint_id: str


class McpAddReq(BaseModel):
    name: str
    command: str
    args: str = ""


class CliTransferReq(BaseModel):
    cli_root: str = ""
    paths: Optional[List[str]] = None


DEFAULT_VISIBLE_MODELS = [
    "localllmapi:gemma-4-12B-it-Q4_K_M.gguf",
    "openrouter:deepseek/deepseek-r1:free",
    "openrouter:anthropic/claude-3.7-sonnet",
    "openrouter:google/gemini-2.5-pro-preview",
    "openai:gpt-4o",
    "openai:o3-mini",
    "deepseek:deepseek-reasoner",
]


class GeneralSettingsReq(BaseModel):
    mode: Optional[str] = None
    reasoning_level: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    repetition_penalty: Optional[float] = None
    max_steps: Optional[int] = None
    subagent_model: Optional[str] = None
    auto_repo_map: Optional[bool] = None
    auto_approve_readonly: Optional[bool] = None
    browser_enabled: Optional[bool] = None
    perm_read: Optional[str] = None
    perm_write: Optional[str] = None
    perm_edit: Optional[str] = None
    perm_command: Optional[str] = None
    font_size: Optional[int] = None
    tab_size: Optional[int] = None
    format_on_save: Optional[bool] = None
    shell: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    confirm_exit: Optional[bool] = None
    auto_copy_selection: Optional[bool] = None
    enable_thinking_animation: Optional[bool] = None
    hide_context_on_type: Optional[bool] = None
    check_on_start: Optional[bool] = None
    auto_update: Optional[bool] = None
    cli_repo_path: Optional[str] = None
    server_port: Optional[int] = None
    active_loader: Optional[str] = None
    visible_models: Optional[List[str]] = None
    theme: Optional[str] = None


def _extract_general_settings(settings_mgr: SettingsManager, resolved_root: Path) -> Dict[str, Any]:
    cfg = settings_mgr.config or {}
    agent_cfg = cfg.get("agent") or {}
    gen_cfg = cfg.get("generation") or {}
    perm_cfg = cfg.get("permissions") or {}
    ed_cfg = cfg.get("editor") or {}
    term_cfg = cfg.get("terminal") or {}
    set_cfg = cfg.get("settings") or {}
    srv_cfg = cfg.get("server") or {}
    upd_cfg = cfg.get("updates") or {}
    plat = _python_fallback_platform(resolved_root)
    theme_raw = str(set_cfg.get("theme") or "light").strip().lower()
    if theme_raw not in ("light", "dark"):
        theme_raw = "light"
    vis_raw = set_cfg.get("visible_models")
    if isinstance(vis_raw, list):
        vis_models = [str(v).strip() for v in vis_raw if str(v).strip()]
    else:
        vis_models = list(DEFAULT_VISIBLE_MODELS)
    cmd_perm_raw = perm_cfg.get("command")
    cmd_perm = cmd_perm_raw.get("*", "ask") if isinstance(cmd_perm_raw, dict) else str(cmd_perm_raw or "ask")
    default_cli_path = str(set_cfg.get("cli_repo_path") or (resolved_root.parent / "CMDAI CODE")).replace("\\", "/")
    return {
        "mode": _normalize_mode(agent_cfg.get("mode")),
        "reasoning_level": str(gen_cfg.get("reasoning_level") or "medium"),
        "temperature": float(gen_cfg.get("temperature") if gen_cfg.get("temperature") is not None else 0.2),
        "top_p": float(gen_cfg.get("top_p") if gen_cfg.get("top_p") is not None else 0.95),
        "repetition_penalty": float(gen_cfg.get("repetition_penalty") if gen_cfg.get("repetition_penalty") is not None else 1.1),
        "max_steps": int(agent_cfg.get("max_steps") or agent_cfg.get("max_iterations") or 25),
        "subagent_model": str(cfg.get("subagent_model") or ""),
        "auto_repo_map": bool(agent_cfg.get("auto_repo_map", True)),
        "auto_approve_readonly": bool(agent_cfg.get("auto_approve_readonly", True)),
        "browser_enabled": bool((cfg.get("browser") or {}).get("enabled", False)),
        "perm_read": str(perm_cfg.get("read") or "allow"),
        "perm_write": str(perm_cfg.get("write") or "ask"),
        "perm_edit": str(perm_cfg.get("edit") or "ask"),
        "perm_command": str(cmd_perm or "ask"),
        "font_size": int(ed_cfg.get("font_size") or 13),
        "tab_size": int(ed_cfg.get("tab_size") or 4),
        "format_on_save": bool(ed_cfg.get("format_on_save", True)),
        "shell": str(term_cfg.get("shell") or plat.get("shell") or "powershell"),
        "confirm_exit": bool(set_cfg.get("confirm_exit", False)),
        "auto_copy_selection": bool(set_cfg.get("auto_copy_selection", True)),
        "enable_thinking_animation": bool(set_cfg.get("enable_thinking_animation", True)),
        "hide_context_on_type": bool(set_cfg.get("hide_context_on_type", True)),
        "check_on_start": bool(upd_cfg.get("check_on_start", True)),
        "auto_update": bool(upd_cfg.get("auto_update", False)),
        "cli_repo_path": default_cli_path,
        "server_port": int(srv_cfg.get("port") or 8080),
        "active_loader": str(cfg.get("active_loader") or "cpu").lower(),
        "theme": theme_raw,
        "visible_models": vis_models,
    }


def _load_merged_settings(workdir: Path, resolved_root: Path) -> SettingsManager:
    """Load global Desktop config while inheriting API keys & custom providers from CLI/project configs."""
    mgr = SettingsManager(str(resolved_root))
    cfg = mgr.config
    res_norm = resolved_root.resolve()
    candidates = [workdir, resolved_root.parent / "CMDAI CODE"]
    for src_root in candidates:
        try:
            if not src_root or src_root.resolve() == res_norm:
                continue
            cfg_file = src_root / "config.json"
            if not cfg_file.is_file():
                continue
            other = json.loads(cfg_file.read_text(encoding="utf-8-sig"))
            if not isinstance(other, dict):
                continue
            for section in ("api_keys", "custom_models", "custom_providers", "provider_urls"):
                other_sec = other.get(section)
                if not isinstance(other_sec, dict):
                    continue
                dst_sec = cfg.setdefault(section, {})
                for k, v in other_sec.items():
                    if k not in dst_sec or not dst_sec[k]:
                        dst_sec[k] = v
            if not cfg.get("default_model") and other.get("default_model"):
                cfg["default_model"] = other["default_model"]
            if not cfg.get("default_provider") and other.get("default_provider"):
                cfg["default_provider"] = other["default_provider"]
        except Exception:
            continue
    return mgr


def create_app(app_root: Optional[Path] = None, workdir: Optional[Path] = None) -> FastAPI:
    resolved_root = (app_root or _APP_ROOT).resolve()
    resolved_workdir = (workdir or resolved_root).resolve()

    app = FastAPI(title="CMDAI CODE Desktop Bridge", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _no_cache_ui(request, call_next):
        response = await call_next(request)
        p = request.url.path
        if p == "/" or p.endswith((".js", ".css", ".html")):
            response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response

    state: Dict[str, Any] = {
        "app_root": resolved_root,
        "workdir": resolved_workdir,
        "known_workspaces": [resolved_workdir, resolved_root, resolved_root.parent / "CMDAI CODE"],
        "subagents": [],
        "pending_approvals": {},
    }

    def _norm_ws_path(p_val: Any) -> str:
        s = str(p_val or "").strip()
        if not s:
            return ""
        s_slash = s.replace("\\", "/")
        if s_slash.startswith("//?/UNC/"):
            s_slash = "//" + s_slash[8:]
        elif s_slash.startswith("//?/"):
            s_slash = s_slash[4:]
        if len(s_slash) > 3:
            s_slash = s_slash.rstrip("/")
        return s_slash

    def _is_temp_ws_path(norm_path: str) -> bool:
        low = norm_path.lower()
        name_low = Path(norm_path).name.lower()
        return (
            "/appdata/local/temp/" in low
            or "/pytest-of-" in low
            or "/tmp/" in low
            or name_low.startswith("pytest-")
            or (name_low.startswith("tmp") and "/temp/" in low)
        )

    def _format_sessions_summary(raw_sessions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for s in raw_sessions:
            title = str(s.get("title") or "Untitled Session")
            if title == "Inspect repomap.py":
                continue
            dir_raw = _norm_ws_path(s.get("directory"))
            if dir_raw and _is_temp_ws_path(dir_raw):
                continue
            dir_name = str(s.get("dir_name") or (Path(dir_raw).name if dir_raw else ""))
            out.append(
                {
                    "id": s.get("id", ""),
                    "title": title,
                    "updated_at": s.get("relative_time") or format_relative_time(s.get("updated_ts") or s.get("updated_at")),
                    "model_id": s.get("model_id", ""),
                    "provider_id": s.get("provider_id", ""),
                    "mode": _normalize_mode(s.get("mode")),
                    "msg_count": int(s.get("message_count", s.get("msg_count", 0))),
                    "dir_name": dir_name,
                    "directory": dir_raw,
                }
            )
        return out

    def _discover_workspaces(wd: Path, raw_sessions: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        candidates_raw: List[Path] = list(state.get("known_workspaces") or [])
        candidates_raw.extend([wd, resolved_root, resolved_root.parent / "CMDAI CODE"])
        if raw_sessions:
            for s in raw_sessions:
                if str(s.get("title") or "") == "Inspect repomap.py":
                    continue
                d = _norm_ws_path(s.get("directory"))
                if d and not _is_temp_ws_path(d):
                    candidates_raw.append(Path(d))
        try:
            for child in sorted(resolved_root.parent.iterdir(), key=lambda x: x.name.lower()):
                if child.is_dir() and (
                    (child / ".git").exists()
                    or (child / "pyproject.toml").exists()
                    or (child / "package.json").exists()
                    or (child / "Cargo.toml").exists()
                ):
                    candidates_raw.append(child)
        except Exception:
            pass
        out: List[Dict[str, Any]] = []
        seen = set()
        wd_norm = _norm_ws_path(wd.resolve())
        for p in candidates_raw:
            try:
                p_clean = Path(_norm_ws_path(p) or str(p))
                rp = p_clean.resolve()
                rp_norm = _norm_ws_path(rp)
                if not rp_norm or _is_temp_ws_path(rp_norm):
                    continue
                key = rp_norm.lower()
                if rp.is_dir() and key not in seen:
                    seen.add(key)
                    out.append(
                        {
                            "name": rp.name or rp_norm,
                            "path": rp_norm,
                            "active": key == wd_norm.lower(),
                        }
                    )
            except Exception:
                pass
        return out

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        return {
            "ok": True,
            "app": "CMDAI CODE Desktop",
            "rust_binary": _rust_binary_path(resolved_root) is not None,
            "workdir": str(state["workdir"]),
        }

    @app.get("/assets/banner.png")
    def get_banner():
        banner = resolved_root / "assets" / "banner.png"
        if not banner.is_file():
            raise HTTPException(status_code=404, detail="banner.png not found")
        return FileResponse(str(banner), media_type="image/png")

    @app.get("/api/bootstrap")
    def bootstrap() -> Dict[str, Any]:
        wd: Path = state["workdir"]
        settings_mgr = _load_merged_settings(wd, resolved_root)
        plat = _run_rust_cli(resolved_root, ["--platform-info"]) or _python_fallback_platform(resolved_root)
        plat["rust_active"] = _rust_binary_path(resolved_root) is not None
        git_info = _git_status_summary(wd, resolved_root)
        providers_payload = _build_providers_payload(settings_mgr)

        sm = SessionManager(project_dir=str(wd))
        raw_sessions = sm.list_sessions(str(wd))[:60]
        sessions = _format_sessions_summary(raw_sessions)
        workspaces = _discover_workspaces(wd, raw_sessions)

        mcp_client = MCPClient()
        mcp_servers_raw = mcp_client.load_config(str(resolved_root)) or {}
        mcp_servers = [
            {
                "name": name,
                "type": entry.get("type") or ("http" if entry.get("url") else "stdio"),
                "target": entry.get("url") or f"{entry.get('command', '')} {' '.join(entry.get('args', []))}".strip(),
                "enabled": bool(entry.get("enabled", True)),
            }
            for name, entry in mcp_servers_raw.items()
        ]

        cp_mgr = CheckpointManager(str(wd))
        checkpoints = [
            {
                "id": c.id,
                "prompt": c.prompt,
                "timestamp": format_relative_time(c.timestamp),
                "files_changed": c.files_changed,
                "stats": c.stats,
                "is_active": c.is_active,
            }
            for c in cp_mgr.list_checkpoints()[:20]
        ]

        return {
            "app_name": "CMDAI CODE",
            "subtitle": "Rust + Python Desktop Studio",
            "workdir": str(wd).replace("\\", "/"),
            "platform": plat,
            "git": git_info,
            "models_state": providers_payload,
            "sessions": sessions,
            "workspaces": workspaces,
            "mcp_servers": mcp_servers,
            "checkpoints": checkpoints,
            "subagents": state["subagents"],
            "sync_summary": {},
            "general_settings": _extract_general_settings(settings_mgr, resolved_root),
            "formatter_available": formatter_available(),
        }

    @app.get("/api/capabilities")
    def get_capabilities_endpoint(model: str = Query(...), provider: str = Query("")) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        mgr = _load_merged_settings(wd, resolved_root)
        api_key = str((mgr.config.get("api_keys") or {}).get(provider) or "")
        cap = get_model_capability(model, provider, api_key=api_key, timeout=0.6)
        has_t = bool(cap.thinking)
        return {
            "model": model,
            "provider": provider,
            "name": clean_model_name(model),
            "thinking": has_t,
            "vision": bool(cap.vision),
            "levels": cycle_order(cap.levels) if has_t else [],
            "default_level": cap.default_level or ("medium" if has_t else "off"),
            "param_style": cap.param_style,
            "max_budget": int(cap.max_budget or 0),
            "context_limit": int(cap.context_limit or 0),
            "source": cap.source,
        }

    @app.get("/api/providers/{provider_id}/models")
    def fetch_provider_models_live(provider_id: str) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        mgr = _load_merged_settings(wd, resolved_root)
        cfg = mgr.config or {}
        api_key = str((cfg.get("api_keys") or {}).get(provider_id) or "")
        custom_models = (cfg.get("custom_models") or {}).get(provider_id) or []
        from cmdai.core.providers import fetch_remote_models

        fetched = fetch_remote_models(provider_id, api_key) or []
        seen = set()
        models_meta: List[Dict[str, Any]] = []
        raw_ids: List[str] = []
        for item in fetched:
            mid = str(item.get("id") or "").strip() if isinstance(item, dict) else str(item).strip()
            if mid and mid not in seen:
                seen.add(mid)
                raw_ids.append(mid)
        for cm in custom_models:
            if cm and cm not in seen:
                seen.add(cm)
                raw_ids.append(cm)

        for mid in raw_ids[:160]:
            try:
                cap = get_model_capability(mid, provider_id, api_key=api_key, timeout=0.35)
                has_t = bool(cap.thinking)
                models_meta.append(
                    {
                        "id": mid,
                        "name": clean_model_name(mid),
                        "raw_name": mid,
                        "thinking": has_t,
                        "vision": bool(cap.vision),
                        "levels": cycle_order(cap.levels) if has_t else [],
                        "default_level": cap.default_level or ("medium" if has_t else "off"),
                        "param_style": cap.param_style,
                        "max_budget": int(cap.max_budget or 0),
                        "context_limit": int(cap.context_limit or 0),
                        "source": cap.source,
                        "is_placeholder": False,
                    }
                )
            except Exception:
                models_meta.append(
                    {
                        "id": mid,
                        "name": clean_model_name(mid),
                        "raw_name": mid,
                        "thinking": False,
                        "vision": False,
                        "levels": [],
                        "default_level": "off",
                        "param_style": "none",
                        "max_budget": 0,
                        "context_limit": 0,
                        "source": "remote",
                        "is_placeholder": False,
                    }
                )
        return {"ok": True, "provider": provider_id, "models": models_meta}

    @app.post("/api/agent/respond")
    def agent_respond_approval(payload: Dict[str, Any]) -> Dict[str, Any]:
        req_id = str(payload.get("id") or "").strip()
        decision = payload.get("decision")
        entry = state["pending_approvals"].get(req_id)
        if not entry:
            return {"ok": False, "detail": "Approval request expired or not found"}
        entry["decision"] = decision
        entry["event"].set()
        return {"ok": True}

    @app.get("/api/sessions")
    def list_sessions_endpoint() -> Dict[str, Any]:
        wd: Path = state["workdir"]
        sm = SessionManager(project_dir=str(wd))
        return {"sessions": _format_sessions_summary(sm.list_sessions(str(wd))[:40])}

    @app.get("/api/sessions/{session_id}")
    def get_session(session_id: str) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        sm = SessionManager(project_dir=str(wd))
        loaded = sm.load_session(session_id)
        if not loaded:
            raise HTTPException(status_code=404, detail="Session not found")
        if not loaded.get("transcript") and loaded.get("messages"):
            try:
                from cmdai.core.sessions import transcript_from_messages
                loaded["transcript"] = transcript_from_messages(loaded["messages"])
            except Exception:
                loaded["transcript"] = []
        return loaded

    @app.delete("/api/sessions/{session_id}")
    def delete_session(session_id: str) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        sm = SessionManager(project_dir=str(wd))
        deleted = sm.delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"ok": True, "deleted": session_id}

    @app.post("/api/sessions/{session_id}/truncate")
    def truncate_session_turn(session_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        turn_index = int(body.get("turn_index", 0))
        wd: Path = state["workdir"]
        sm = SessionManager(project_dir=str(wd))
        loaded = sm.load_session(session_id)
        if not loaded:
            raise HTTPException(status_code=404, detail="Session not found")

        transcript = list(loaded.get("transcript") or [])
        messages = list(loaded.get("messages") or [])
        restored_prompt = ""

        # Truncate transcript at the turn_index-th user entry
        u_idx = 0
        t_cut = len(transcript)
        for i, ev in enumerate(transcript):
            if isinstance(ev, dict) and ev.get("kind") == "user":
                if u_idx == turn_index:
                    restored_prompt = str(ev.get("prompt") or ev.get("content") or ev.get("text") or "").strip()
                    t_cut = i
                    break
                u_idx += 1
        new_transcript = transcript[:t_cut]

        # Truncate messages at the turn_index-th real user prompt
        m_u_idx = 0
        m_cut = len(messages)
        for i, m in enumerate(messages):
            if isinstance(m, dict) and m.get("role") == "user":
                c = str(m.get("content") or "")
                if c.lstrip().startswith("<tool_result"):
                    continue
                if m_u_idx == turn_index:
                    if not restored_prompt:
                        restored_prompt = c.strip()
                    m_cut = i
                    break
                m_u_idx += 1
        new_messages = messages[:m_cut]

        sm.save_session(
            messages=new_messages,
            session_id=session_id,
            title=str(loaded.get("title") or "Conversation"),
            model_id=str(loaded.get("model_id") or ""),
            provider_id=str(loaded.get("provider_id") or ""),
            agent_mode=str(loaded.get("agent_mode") or "code"),
            transcript=new_transcript,
            bump_timestamp=False,
        )

        rt = state.get("runtimes", {}).get(session_id)
        if rt is not None:
            rt.messages = list(new_messages)
            rt.transcript = list(new_transcript)

        return {"ok": True, "prompt": restored_prompt, "remaining_messages": len(new_messages)}

    @app.get("/api/git/info")
    def git_info() -> Dict[str, Any]:
        wd: Path = state["workdir"]
        return _git_status_summary(wd, resolved_root)

    @app.post("/api/git/checkout")
    def git_checkout(req: GitCheckoutReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        git_target = _resolve_git_root(wd, resolved_root)
        if not git_target:
            raise HTTPException(status_code=400, detail="No Git repository detected in workspace")
        branch = req.branch.strip()
        if not branch:
            raise HTTPException(status_code=400, detail="Branch name is required")
        proc = subprocess.run(
            ["git", "-c", "safe.directory=*", "checkout", branch],
            cwd=str(git_target),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "Failed to checkout branch").strip()
            raise HTTPException(status_code=400, detail=err)
        return {"ok": True, "git": _git_status_summary(wd, resolved_root)}

    @app.post("/api/git/init")
    def git_init() -> Dict[str, Any]:
        wd: Path = state["workdir"]
        if not (wd / ".git").exists():
            proc = subprocess.run(["git", "init"], cwd=str(wd), capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                raise HTTPException(status_code=400, detail=(proc.stderr or proc.stdout or "git init failed").strip())
            subprocess.run(["git", "symbolic-ref", "HEAD", "refs/heads/main"], cwd=str(wd), capture_output=True, text=True, timeout=5)
        return {"ok": True, "git": _git_status_summary(wd, resolved_root)}

    @app.post("/api/git/create_branch")
    def git_create_branch(req: GitCheckoutReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        git_target = _resolve_git_root(wd, resolved_root)
        if not git_target:
            raise HTTPException(status_code=400, detail="No Git repository detected in workspace")
        branch = req.branch.strip()
        if not branch:
            raise HTTPException(status_code=400, detail="Branch name is required")
        proc = subprocess.run(
            ["git", "-c", "safe.directory=*", "checkout", "-b", branch],
            cwd=str(git_target),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "Failed to create branch").strip()
            raise HTTPException(status_code=400, detail=err)
        return {"ok": True, "git": _git_status_summary(wd, resolved_root)}

    @app.get("/api/git/diff")
    def git_diff(file_path: str = Query("")) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        summary = _git_status_summary(wd, resolved_root)
        git_target = _resolve_git_root(wd, resolved_root)
        if not git_target:
            return {"ok": True, **summary, "diff": ""}
        cmd = ["git", "-c", "safe.directory=*", "diff"]
        clean_fp = file_path.strip().replace("\\", "/")
        if clean_fp:
            cmd.extend(["--", clean_fp])
        proc = subprocess.run(
            cmd,
            cwd=str(git_target),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        diff_txt = proc.stdout or ""
        if not diff_txt.strip():
            cached_cmd = ["git", "-c", "safe.directory=*", "diff", "--cached"]
            if clean_fp:
                cached_cmd.extend(["--", clean_fp])
            proc2 = subprocess.run(
                cached_cmd,
                cwd=str(git_target),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            diff_txt = proc2.stdout or ""
        return {"ok": True, **summary, "diff": diff_txt[:120000]}

    @app.post("/api/git/stage")
    def git_stage(payload: Dict[str, Any]) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        git_target = _resolve_git_root(wd, resolved_root)
        if not git_target:
            raise HTTPException(status_code=400, detail="No Git repository in workspace")
        fp = str((payload or {}).get("file_path") or "").strip().replace("\\", "/")
        cmd = ["git", "-c", "safe.directory=*", "add", "--", fp] if fp else ["git", "-c", "safe.directory=*", "add", "-A"]
        proc = subprocess.run(cmd, cwd=str(git_target), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
        if proc.returncode != 0:
            raise HTTPException(status_code=400, detail=(proc.stderr or proc.stdout or "git add failed").strip())
        return {"ok": True, **_git_status_summary(wd, resolved_root)}

    @app.post("/api/git/discard")
    def git_discard(payload: Dict[str, Any]) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        git_target = _resolve_git_root(wd, resolved_root)
        if not git_target:
            raise HTTPException(status_code=400, detail="No Git repository in workspace")
        fp = str((payload or {}).get("file_path") or "").strip().replace("\\", "/")
        if not fp:
            raise HTTPException(status_code=400, detail="Specify file_path to discard")
        target_abs = (git_target / fp).resolve()
        if not str(target_abs).startswith(str(git_target.resolve())):
            raise HTTPException(status_code=400, detail="Path outside repository")
        # Check if tracked by git
        chk = subprocess.run(
            ["git", "-c", "safe.directory=*", "ls-files", "--error-unmatch", "--", fp],
            cwd=str(git_target), capture_output=True, text=True, timeout=10,
        )
        if chk.returncode == 0:
            subprocess.run(["git", "-c", "safe.directory=*", "reset", "HEAD", "--", fp], cwd=str(git_target), capture_output=True, timeout=10)
            proc = subprocess.run(
                ["git", "-c", "safe.directory=*", "checkout", "--", fp],
                cwd=str(git_target), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
            )
            if proc.returncode != 0:
                raise HTTPException(status_code=400, detail=(proc.stderr or proc.stdout or "git checkout failed").strip())
        else:
            if target_abs.is_file():
                target_abs.unlink()
        return {"ok": True, **_git_status_summary(wd, resolved_root)}

    @app.post("/api/git/commit")
    def git_commit(payload: Dict[str, Any]) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        git_target = _resolve_git_root(wd, resolved_root)
        if not git_target:
            raise HTTPException(status_code=400, detail="No Git repository in workspace")
        msg = str((payload or {}).get("message") or "").strip()
        if not msg:
            raise HTTPException(status_code=400, detail="Commit message is required")
        stage_all = bool((payload or {}).get("stage_all", True))
        if stage_all:
            subprocess.run(["git", "-c", "safe.directory=*", "add", "-A"], cwd=str(git_target), capture_output=True, timeout=15)
        proc = subprocess.run(
            ["git", "-c", "safe.directory=*", "commit", "-m", msg],
            cwd=str(git_target), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )
        if proc.returncode != 0:
            raise HTTPException(status_code=400, detail=(proc.stderr or proc.stdout or "git commit failed").strip())
        return {"ok": True, "output": (proc.stdout or "").strip(), **_git_status_summary(wd, resolved_root)}

    @app.get("/api/workspace/info")
    def workspace_info() -> Dict[str, Any]:
        wd: Path = state["workdir"]
        sm = SessionManager(project_dir=str(wd))
        raw_sessions = sm.list_sessions(str(wd))[:60]
        candidates = _discover_workspaces(wd, raw_sessions)
        return {
            "workdir": str(wd).replace("\\", "/"),
            "name": wd.name or str(wd),
            "workspaces": candidates,
        }

    @app.post("/api/workspace/switch")
    def workspace_switch(req: WorkspaceSwitchReq) -> Dict[str, Any]:
        target = Path(req.workdir).expanduser().resolve()
        if not target.exists() and req.create_if_missing:
            try:
                target.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Could not create directory {req.workdir}: {exc}")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail=f"Directory not found: {req.workdir}")
        state["workdir"] = target
        known = list(state.get("known_workspaces") or [])
        if target not in known:
            known.append(target)
            state["known_workspaces"] = known
        return {
            "ok": True,
            "workdir": str(target).replace("\\", "/"),
            "name": target.name or str(target),
            "git": _git_status_summary(target, resolved_root),
            "workspaces": _discover_workspaces(target),
        }

    @app.get("/api/project/details")
    def project_details(path: Optional[str] = None) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        target = Path(path).expanduser().resolve() if path else wd
        if not target.is_dir():
            target = wd

        customizations: List[Dict[str, str]] = []
        skills: List[Dict[str, str]] = []

        def _first_desc(md_path: Path, default_desc: str) -> str:
            try:
                for line in md_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    s = line.strip().lstrip("#").strip()
                    if s and not s.startswith("---"):
                        return s[:160]
            except Exception:
                pass
            return default_desc

        skills_dir = target / ".cmdai" / "skills"
        if skills_dir.is_dir():
            try:
                for item in sorted(skills_dir.iterdir(), key=lambda p: p.name.lower()):
                    if item.is_dir() and (item / "SKILL.md").is_file():
                        sm = item / "SKILL.md"
                        skills.append({
                            "name": item.name,
                            "scope": "Workspace",
                            "path": str(sm.relative_to(target)).replace("\\", "/"),
                            "desc": _first_desc(sm, "Workspace skill"),
                        })
                    elif item.is_file() and item.suffix.lower() == ".md":
                        skills.append({
                            "name": item.stem,
                            "scope": "Workspace",
                            "path": str(item.relative_to(target)).replace("\\", "/"),
                            "desc": _first_desc(item, "Workspace skill"),
                        })
            except Exception:
                pass

        for sub_name, label in (("rules", "Rule"), ("commands", "Command")):
            sub_dir = target / ".cmdai" / sub_name
            if sub_dir.is_dir():
                try:
                    for f in sorted(sub_dir.glob("*.md"), key=lambda p: p.name.lower()):
                        customizations.append({
                            "name": f.stem,
                            "kind": label,
                            "path": str(f.relative_to(target)).replace("\\", "/"),
                            "desc": _first_desc(f, f"{label} file"),
                        })
                except Exception:
                    pass

        for root_file in ("AGENTS.md", "CLAUDE.md", ".cursorrules", ".cmdai/memory.md"):
            rf = target / root_file
            if rf.is_file():
                customizations.append({
                    "name": rf.name,
                    "kind": "Rules",
                    "path": root_file,
                    "desc": _first_desc(rf, "Project instruction file"),
                })

        return {
            "ok": True,
            "path": _norm_ws_path(target),
            "name": target.name or str(target),
            "folders": [{"name": target.name or str(target), "path": _norm_ws_path(target)}],
            "customizations": customizations,
            "skills": skills,
        }

    @app.get("/api/settings/general")
    def get_general_settings() -> Dict[str, Any]:
        wd: Path = state["workdir"]
        mgr = _load_merged_settings(wd, resolved_root)
        return {
            "ok": True,
            "general_settings": _extract_general_settings(mgr, resolved_root),
            "models_state": _build_providers_payload(mgr),
        }

    @app.post("/api/settings/general")
    def save_general_settings(req: GeneralSettingsReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        mgr = _load_merged_settings(wd, resolved_root)
        if req.mode is not None:
            mgr.config.setdefault("agent", {})["mode"] = req.mode
        if req.max_steps is not None:
            steps_val = max(1, min(100, int(req.max_steps)))
            mgr.config.setdefault("agent", {})["max_steps"] = steps_val
            mgr.config.setdefault("agent", {})["max_iterations"] = steps_val
        if req.subagent_model is not None:
            mgr.config["subagent_model"] = req.subagent_model.strip()
        if req.auto_repo_map is not None:
            mgr.config.setdefault("agent", {})["auto_repo_map"] = bool(req.auto_repo_map)
        if req.auto_approve_readonly is not None:
            mgr.config.setdefault("agent", {})["auto_approve_readonly"] = bool(req.auto_approve_readonly)
        if req.browser_enabled is not None:
            mgr.config.setdefault("browser", {})["enabled"] = bool(req.browser_enabled)
        if req.reasoning_level is not None:
            mgr.config.setdefault("generation", {})["reasoning_level"] = req.reasoning_level
        if req.temperature is not None:
            mgr.config.setdefault("generation", {})["temperature"] = max(0.0, min(2.0, float(req.temperature)))
        if req.top_p is not None:
            mgr.config.setdefault("generation", {})["top_p"] = max(0.1, min(1.0, float(req.top_p)))
        if req.repetition_penalty is not None:
            mgr.config.setdefault("generation", {})["repetition_penalty"] = max(1.0, min(2.0, float(req.repetition_penalty)))
        perms = mgr.config.setdefault("permissions", {})
        if req.perm_read in ("allow", "ask", "deny"):
            perms["read"] = req.perm_read
            perms["search"] = req.perm_read
            perms["glob"] = req.perm_read
        if req.perm_write in ("allow", "ask", "deny"):
            perms["write"] = req.perm_write
        if req.perm_edit in ("allow", "ask", "deny"):
            perms["edit"] = req.perm_edit
        if req.perm_command in ("allow", "ask", "deny"):
            if isinstance(perms.get("command"), dict):
                perms["command"]["*"] = req.perm_command
            else:
                perms["command"] = {"*": req.perm_command}
        if req.font_size is not None:
            mgr.config.setdefault("editor", {})["font_size"] = max(10, min(24, int(req.font_size)))
        if req.tab_size is not None:
            mgr.config.setdefault("editor", {})["tab_size"] = max(2, min(8, int(req.tab_size)))
        if req.format_on_save is not None:
            mgr.config.setdefault("editor", {})["format_on_save"] = bool(req.format_on_save)
        if req.shell is not None and req.shell.strip():
            mgr.config.setdefault("terminal", {})["shell"] = req.shell.strip()
        if req.provider:
            mgr.config["default_provider"] = req.provider
            mgr.config.setdefault("settings", {})["default_provider"] = req.provider
        if req.model:
            mgr.config["default_model"] = req.model
        if req.api_key is not None and req.provider and req.api_key.strip():
            mgr.config.setdefault("api_keys", {})[req.provider] = req.api_key.strip()
        if req.base_url is not None and req.provider:
            mgr.set_provider_base_url(req.provider, req.base_url)
        if req.confirm_exit is not None:
            mgr.config.setdefault("settings", {})["confirm_exit"] = bool(req.confirm_exit)
        if req.auto_copy_selection is not None:
            mgr.config.setdefault("settings", {})["auto_copy_selection"] = bool(req.auto_copy_selection)
        if req.enable_thinking_animation is not None:
            mgr.config.setdefault("settings", {})["enable_thinking_animation"] = bool(req.enable_thinking_animation)
        if req.hide_context_on_type is not None:
            mgr.config.setdefault("settings", {})["hide_context_on_type"] = bool(req.hide_context_on_type)
        if req.cli_repo_path is not None:
            mgr.config.setdefault("settings", {})["cli_repo_path"] = req.cli_repo_path.strip()
        if req.check_on_start is not None:
            mgr.config.setdefault("updates", {})["check_on_start"] = bool(req.check_on_start)
        if req.auto_update is not None:
            mgr.config.setdefault("updates", {})["auto_update"] = bool(req.auto_update)
        if req.server_port is not None:
            mgr.config.setdefault("server", {})["port"] = max(1024, min(65535, int(req.server_port)))
        if req.active_loader is not None and req.active_loader.strip().lower() in ("cpu", "cuda", "vulkan"):
            mgr.config["active_loader"] = req.active_loader.strip().lower()
        if req.theme is not None and req.theme.strip().lower() in ("light", "dark"):
            mgr.config.setdefault("settings", {})["theme"] = req.theme.strip().lower()
        if req.visible_models is not None:
            mgr.config.setdefault("settings", {})["visible_models"] = [
                str(v).strip() for v in req.visible_models if str(v).strip()
            ]
        mgr.save_config()
        _invalidate_providers_cache()
        return {
            "ok": True,
            "general_settings": _extract_general_settings(mgr, resolved_root),
            "models_state": _build_providers_payload(mgr, force_refresh=True),
        }

    @app.post("/api/settings/model")
    def update_model_settings(req: ModelSettingsReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        mgr = _load_merged_settings(wd, resolved_root)
        mgr.config["default_provider"] = req.provider
        mgr.config["default_model"] = req.model
        mgr.config.setdefault("settings", {})["default_provider"] = req.provider
        if req.mode:
            mgr.config.setdefault("agent", {})["mode"] = req.mode
        if req.reasoning_level:
            mgr.config.setdefault("generation", {})["reasoning_level"] = req.reasoning_level
        if req.api_key is not None and req.api_key.strip():
            mgr.config.setdefault("api_keys", {})[req.provider] = req.api_key.strip()
        mgr.save_config()
        _invalidate_providers_cache()
        return {"ok": True, "models_state": _build_providers_payload(mgr, force_refresh=True)}

    @app.get("/api/editor/tree")
    def editor_tree(limit: int = 1200) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        data = _run_rust_cli(resolved_root, ["--tree", str(wd), "--limit", str(limit)])
        if data is None:
            data = _python_tree_fallback(wd, limit=limit)
        return _filter_tree_payload(data)

    @app.get("/api/editor/file")
    def editor_read_file(path: str = Query(...)) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        target = _safe_resolve(wd, path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        rel = str(target.relative_to(wd)).replace("\\", "/")
        binary_exts = {
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp",
            ".exe", ".dll", ".so", ".dylib", ".gguf", ".bin", ".zip", ".tar", ".gz", ".7z", ".pdf", ".woff", ".woff2",
        }
        if target.suffix.lower() in binary_exts:
            return {
                "path": rel,
                "name": target.name,
                "content": f"[Binary file: {target.name} ({target.stat().st_size:,} bytes) — preview not editable]",
                "is_binary": True,
                "lines": 0,
                "size": target.stat().st_size,
                "diagnostics": [],
                "symbols": [],
                "diff": {"path": rel, "added": 0, "removed": 0, "hunks": [], "unified": ""},
            }
        content = target.read_text(encoding="utf-8", errors="replace")

        diags_raw = linter.check(str(target), content)
        diagnostics = [
            {
                "row": int(d.row) + 1,
                "col": int(d.col) + 1,
                "end_col": int(d.end_col) + 1,
                "severity": d.severity,
                "code": d.code,
                "message": d.message,
                "source": d.source,
            }
            for d in diags_raw
        ]
        symbols = extract_symbols_from_code(str(target), content)

        head_text = content
        has_git_diff = False
        try:
            proc = subprocess.run(
                ["git", "-c", "safe.directory=*", "show", f"HEAD:{rel}"],
                cwd=str(wd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=4,
            )
            if proc.returncode == 0:
                head_text = proc.stdout
                has_git_diff = head_text != content
        except Exception:
            pass

        diff_info = _compute_hunks(head_text, content, rel) if has_git_diff else {
            "path": rel,
            "added": 0,
            "removed": 0,
            "hunks": [],
            "unified": "",
        }

        return {
            "path": rel,
            "name": target.name,
            "content": content,
            "lines": len(content.splitlines()),
            "size": target.stat().st_size,
            "diagnostics": diagnostics,
            "symbols": symbols,
            "diff": diff_info,
        }

    @app.post("/api/editor/save")
    def editor_save_file(req: SaveFileReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        target = _safe_resolve(wd, req.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(req.content, encoding="utf-8")
        diags_raw = linter.check(str(target), req.content)
        symbols = extract_symbols_from_code(str(target), req.content)
        return {
            "ok": True,
            "path": str(target.relative_to(wd)).replace("\\", "/"),
            "diagnostics": [
                {
                    "row": int(d.row) + 1,
                    "col": int(d.col) + 1,
                    "severity": d.severity,
                    "code": d.code,
                    "message": d.message,
                    "source": d.source,
                }
                for d in diags_raw
            ],
            "symbols": symbols,
        }

    @app.post("/api/editor/format")
    def editor_format_file(req: FormatFileReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        target = _safe_resolve(wd, req.path)
        res = format_source(req.content, str(target))
        return {
            "ok": res.ok,
            "changed": res.changed,
            "text": res.text,
            "tool": res.tool,
            "error": res.error,
        }

    @app.post("/api/editor/diff_preview")
    def editor_diff_preview(req: DiffPreviewReq) -> Dict[str, Any]:
        return _compute_hunks(req.old_content, req.new_content, req.path)

    @app.post("/api/editor/apply_hunk")
    def editor_apply_hunk(req: ApplyHunkReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        target = _safe_resolve(wd, req.path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        start_idx = max(0, req.old_start - 1)
        end_idx = min(len(lines), start_idx + max(0, req.old_count))
        updated = lines[:start_idx] + req.new_lines + lines[end_idx:]
        new_text = "\n".join(updated) + ("\n" if updated else "")
        target.write_text(new_text, encoding="utf-8")
        return {"ok": True, "path": req.path, "content": new_text}

    @app.get("/api/editor/search")
    def editor_search(q: str = Query("")) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        res = _run_rust_cli(resolved_root, ["--search", str(wd), q])
        if res is not None:
            return res
        hits: List[Dict[str, Any]] = []
        q_low = q.strip().lower()
        if not q_low:
            return {"query": q, "count": 0, "hits": []}
        for item in _python_tree_fallback(wd, limit=600)["entries"]:
            if item["kind"] != "file" or item["size"] > 600_000:
                continue
            p = wd / item["path"]
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for idx, line in enumerate(text.splitlines(), 1):
                pos = line.lower().find(q_low)
                if pos != -1:
                    hits.append(
                        {
                            "path": item["path"],
                            "line": idx,
                            "column": pos + 1,
                            "preview": line.strip()[:160],
                        }
                    )
                    if len(hits) >= 150:
                        return {"query": q, "count": len(hits), "hits": hits}
        return {"query": q, "count": len(hits), "hits": hits}

    @app.get("/api/editor/problems")
    def editor_problems() -> Dict[str, Any]:
        wd: Path = state["workdir"]
        scan = scan_project(str(wd), limit=200)
        items = []
        for d in scan.diagnostics[:150]:
            try:
                rel = str(Path(d.path).resolve().relative_to(wd.resolve())).replace("\\", "/")
            except Exception:
                rel = d.path.replace("\\", "/")
            items.append(
                {
                    "path": rel,
                    "row": int(d.row) + 1,
                    "col": int(d.col) + 1,
                    "severity": d.severity,
                    "code": d.code,
                    "message": d.message,
                    "source": d.source,
                }
            )
        return {
            "checked": scan.checked,
            "truncated": scan.truncated,
            "note": scan.note,
            "diagnostics": items,
        }

    @app.post("/api/terminal/run")
    def terminal_run(req: TerminalRunReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        cwd = _safe_resolve(wd, req.cwd) if req.cwd else wd
        cmd = (req.command or "").strip()
        if not cmd:
            return {"ok": True, "stdout": "", "stderr": "", "returncode": 0, "duration_ms": 0}
        t0 = time.perf_counter()
        if os.name == "nt":
            shell_exe = shutil.which("pwsh") or shutil.which("powershell") or "cmd"
            argv = [shell_exe, "/C", cmd] if shell_exe.endswith("cmd") else [shell_exe, "-NoProfile", "-Command", cmd]
        else:
            shell_exe = shutil.which("bash") or "sh"
            argv = [shell_exe, "-lc", cmd]
        try:
            proc = subprocess.run(
                argv,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            dt_ms = int((time.perf_counter() - t0) * 1000)
            return {
                "ok": proc.returncode == 0,
                "shell": Path(shell_exe).name,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode,
                "duration_ms": dt_ms,
            }
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "shell": Path(shell_exe).name,
                "stdout": "",
                "stderr": "Command timed out after 30s.",
                "returncode": -1,
                "duration_ms": 30000,
            }

    def _preferred_shell() -> str:
        try:
            sm_set = SettingsManager(state["workdir"])
            return str((sm_set.get("shell") or "")).strip()
        except Exception:
            return ""

    @app.get("/api/terminal/state")
    def terminal_pty_state() -> Dict[str, Any]:
        pty_sess = get_pty_terminal()
        return {"ok": True, **pty_sess.get_state()}

    @app.post("/api/terminal/input")
    def terminal_pty_input(payload: Dict[str, Any]) -> Dict[str, Any]:
        pty_sess = get_pty_terminal()
        data = str(payload.get("data", ""))
        if not pty_sess.get_state().get("running"):
            pty_sess.ensure_started(
                workdir=str(state["workdir"]),
                shell=_preferred_shell(),
                cols=int(payload.get("cols") or 100),
                rows=int(payload.get("rows") or 28),
            )
        ok = pty_sess.write(data)
        return {"ok": ok, **pty_sess.get_state()}

    @app.post("/api/terminal/resize")
    def terminal_pty_resize(payload: Dict[str, Any]) -> Dict[str, Any]:
        pty_sess = get_pty_terminal()
        cols = int(payload.get("cols") or 100)
        rows = int(payload.get("rows") or 28)
        ok = pty_sess.resize(cols, rows)
        return {"ok": ok, **pty_sess.get_state()}

    @app.post("/api/terminal/restart")
    def terminal_pty_restart(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = payload or {}
        pty_sess = get_pty_terminal()
        st = pty_sess.restart(
            workdir=str(state["workdir"]),
            shell=str(body.get("shell") or _preferred_shell()),
            cols=int(body.get("cols") or 100),
            rows=int(body.get("rows") or 28),
        )
        return {"ok": True, **st}

    @app.get("/api/terminal/stream")
    async def terminal_pty_stream(
        request: Request,
        cols: int = 100,
        rows: int = 28,
    ) -> StreamingResponse:
        pty_sess = get_pty_terminal()
        pty_sess.ensure_started(
            workdir=str(state["workdir"]),
            shell=_preferred_shell(),
            cols=cols,
            rows=rows,
        )
        sub_q, init_buf, init_state = pty_sess.subscribe()

        async def _gen():
            try:
                init_payload = json.dumps({"state": init_state, "buffer": init_buf})
                yield f"event: init\ndata: {init_payload}\n\n"
                last_ping = time.monotonic()
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        ev, pl = await asyncio.to_thread(sub_q.get, True, 0.4)
                        if ev == "data":
                            yield f"event: data\ndata: {json.dumps({'chunk': pl})}\n\n"
                        elif ev == "state":
                            yield f"event: state\ndata: {json.dumps(pl)}\n\n"
                        last_ping = time.monotonic()
                    except std_queue.Empty:
                        if time.monotonic() - last_ping >= 15.0:
                            yield ": keepalive\n\n"
                            last_ping = time.monotonic()
            finally:
                pty_sess.unsubscribe(sub_q)

        return StreamingResponse(
            _gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    @app.get("/api/map/graph")
    def map_graph(max_files: int = 65) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        graph = build_repo_graph(str(wd), max_files=max_files)
        raw_nodes = graph.get("nodes", [])
        raw_edges = graph.get("edges", [])

        enriched_nodes: List[Dict[str, Any]] = []
        for n in raw_nodes:
            node_copy = dict(n)
            if n.get("kind") == "file":
                fpath = wd / n.get("path", "")
                ast_details: List[Dict[str, Any]] = []
                line_count = 0
                if fpath.is_file():
                    try:
                        code = fpath.read_text(encoding="utf-8", errors="replace")
                        line_count = len(code.splitlines())
                        syms = extract_symbols_from_code(str(fpath), code)
                        ast_details = [
                            {
                                "name": s.get("name", ""),
                                "type": s.get("type", "symbol"),
                                "start_line": int(s.get("start_line", 1)),
                                "end_line": int(s.get("end_line", 1)),
                                "signature": s.get("signature", s.get("name", "")),
                            }
                            for s in syms[:30]
                        ]
                    except Exception:
                        pass
                node_copy["ast_symbols"] = ast_details
                node_copy["line_count"] = line_count
            else:
                node_copy["ast_symbols"] = []
                node_copy["line_count"] = 0
            enriched_nodes.append(node_copy)

        edges_out = [
            {"source": e[0], "target": e[1], "kind": e[2]}
            for e in raw_edges
            if isinstance(e, (list, tuple)) and len(e) >= 3
        ]

        import_count = sum(1 for e in edges_out if e["kind"] == "import")
        return {
            "workdir": str(wd).replace("\\", "/"),
            "nodes": enriched_nodes,
            "edges": edges_out,
            "stats": {
                "nodes": len(enriched_nodes),
                "edges": len(edges_out),
                "imports": import_count,
                "files": sum(1 for n in enriched_nodes if n.get("kind") == "file"),
                "dirs": sum(1 for n in enriched_nodes if n.get("kind") == "dir"),
            },
        }

    @app.get("/api/sync/status")
    def sync_status() -> Dict[str, Any]:
        res = _run_rust_cli(resolved_root, ["--sync-status"])
        if res is None:
            raise HTTPException(status_code=500, detail="Rust host binary unavailable for --sync-status")
        return res

    @app.post("/api/sync/run")
    def sync_run(req: SyncRunReq) -> Dict[str, Any]:
        args = ["--sync-run"] + (["--dry-run"] if req.dry_run else [])
        res = _run_rust_cli(resolved_root, args, timeout=60)
        if res is None:
            raise HTTPException(status_code=500, detail="Rust host binary unavailable for --sync-run")
        return res

    @app.post("/api/providers/custom")
    def add_custom_provider_endpoint(req: CustomProviderReq) -> Dict[str, Any]:
        name = req.name.strip()
        base_url = req.base_url.strip()
        if not name or not base_url:
            raise HTTPException(status_code=400, detail="Provider name and base URL are required.")
        wd: Path = state["workdir"]
        mgr = _load_merged_settings(wd, resolved_root)
        model_list = [m.strip() for m in str(req.models or "").split(",") if m.strip()]
        first_model = model_list[0] if model_list else ""
        pid = mgr.add_custom_provider(
            name=name,
            base_url=base_url,
            api_key=req.api_key.strip(),
            default_model=first_model,
            provider_id=req.provider_id.strip(),
        )
        for extra_m in model_list[1:]:
            mgr.add_custom_model(pid, extra_m)
        load_custom_providers()
        return {
            "ok": True,
            "provider_id": pid,
            "models_state": _build_providers_payload(mgr),
        }

    @app.get("/api/checkpoints/list")
    def list_checkpoints_endpoint() -> Dict[str, Any]:
        wd: Path = state["workdir"]
        cp_mgr = CheckpointManager(str(wd))
        cps = [
            {
                "id": c.id,
                "prompt": c.prompt,
                "timestamp": format_relative_time(c.timestamp),
                "files_changed": c.files_changed,
                "stats": c.stats,
                "is_active": c.is_active,
            }
            for c in cp_mgr.list_checkpoints()[:30]
        ]
        return {"ok": True, "checkpoints": cps}

    @app.post("/api/checkpoints/create")
    def create_checkpoint_endpoint(req: CheckpointCreateReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        cp_mgr = CheckpointManager(str(wd))
        cp = cp_mgr.create_checkpoint(req.prompt.strip() or "Manual Desktop Snapshot")
        return {
            "ok": True,
            "checkpoint": {
                "id": cp.id,
                "prompt": cp.prompt,
                "timestamp": format_relative_time(cp.timestamp),
                "files_changed": cp.files_changed,
                "stats": cp.stats,
                "is_active": cp.is_active,
            },
        }

    @app.post("/api/checkpoints/restore")
    def restore_checkpoint_endpoint(req: CheckpointRestoreReq) -> Dict[str, Any]:
        wd: Path = state["workdir"]
        cp_mgr = CheckpointManager(str(wd))
        ok = cp_mgr.revert_checkpoint(req.checkpoint_id.strip())
        if not ok:
            raise HTTPException(status_code=404, detail=f"Checkpoint not found or restore failed: {req.checkpoint_id}")
        cps = [
            {
                "id": c.id,
                "prompt": c.prompt,
                "timestamp": format_relative_time(c.timestamp),
                "files_changed": c.files_changed,
                "stats": c.stats,
                "is_active": c.is_active,
            }
            for c in cp_mgr.list_checkpoints()[:30]
        ]
        return {"ok": True, "restored": req.checkpoint_id.strip(), "checkpoints": cps}

    @app.post("/api/mcp/add")
    def add_mcp_server_endpoint(req: McpAddReq) -> Dict[str, Any]:
        name = req.name.strip()
        cmd = req.command.strip()
        if not name or not cmd:
            raise HTTPException(status_code=400, detail="MCP server name and command/URL are required.")
        mcp_client = MCPClient()
        cfg_path = Path(mcp_client.config_file(str(resolved_root)))
        existing: Dict[str, Any] = {}
        if cfg_path.is_file():
            try:
                existing = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
            except Exception:
                existing = {}
        if not isinstance(existing, dict):
            existing = {}
        servers_map = existing.get("mcpServers")
        if not isinstance(servers_map, dict):
            servers_map = {}
            existing["mcpServers"] = servers_map
        is_http = cmd.startswith("http://") or cmd.startswith("https://")
        if is_http:
            servers_map[name] = {"type": "http", "url": cmd, "enabled": True}
        else:
            args_list = [a for a in req.args.strip().split() if a]
            servers_map[name] = {"type": "stdio", "command": cmd, "args": args_list, "enabled": True}
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
        reloaded = mcp_client.load_config(str(resolved_root)) or {}
        mcp_servers = [
            {
                "name": sname,
                "type": entry.get("type") or ("http" if entry.get("url") else "stdio"),
                "target": entry.get("url") or f"{entry.get('command', '')} {' '.join(entry.get('args', []))}".strip(),
                "enabled": bool(entry.get("enabled", True)),
            }
            for sname, entry in reloaded.items()
        ]
        return {"ok": True, "mcp_servers": mcp_servers}

    @app.delete("/api/mcp/remove")
    def remove_mcp_server_endpoint(name: str = Query(...)) -> Dict[str, Any]:
        target_name = name.strip()
        mcp_client = MCPClient()
        cfg_path = Path(mcp_client.config_file(str(resolved_root)))
        if cfg_path.is_file():
            try:
                existing = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
                if isinstance(existing, dict):
                    servers_map = existing.get("mcpServers") or existing.get("mcp_servers") or existing
                    if isinstance(servers_map, dict) and target_name in servers_map:
                        servers_map.pop(target_name, None)
                        cfg_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to remove MCP server: {exc}") from exc
        reloaded = mcp_client.load_config(str(resolved_root)) or {}
        mcp_servers = [
            {
                "name": sname,
                "type": entry.get("type") or ("http" if entry.get("url") else "stdio"),
                "target": entry.get("url") or f"{entry.get('command', '')} {' '.join(entry.get('args', []))}".strip(),
                "enabled": bool(entry.get("enabled", True)),
            }
            for sname, entry in reloaded.items()
        ]
        return {"ok": True, "mcp_servers": mcp_servers}

    def _compute_cli_core_diff(cli_root_override: str = "") -> Dict[str, Any]:
        cli_dir = Path(cli_root_override).expanduser().resolve() if cli_root_override.strip() else (resolved_root.parent / "CMDAI CODE").resolve()
        shared_modules = ["src/cmdai/core", "src/cmdai/agent", "src/cmdai/indexer", "src/cmdai/mcp", "src/cmdai/editor/core"]
        protected_paths = ["desktop/", "src/cmdai/desktop_bridge/", "src/cmdai/tui/", "src/cmdai/cli.py"]

        if not cli_dir.is_dir():
            return {
                "ok": True,
                "cli_root": str(cli_dir).replace("\\", "/"),
                "cli_found": False,
                "protected_paths": protected_paths,
                "shared_modules": shared_modules,
                "modified_files": [],
                "synced_count": 0,
                "total_shared_files": 0,
            }

        modified_files: List[Dict[str, Any]] = []
        synced_count = 0
        total = 0

        for rel_mod in shared_modules:
            src_mod = cli_dir / rel_mod
            if not src_mod.is_dir():
                continue
            for fp in sorted(src_mod.rglob("*")):
                if not fp.is_file():
                    continue
                if "__pycache__" in fp.parts or fp.suffix.lower() in (".pyc", ".pyo"):
                    continue
                rel = str(fp.relative_to(cli_dir)).replace("\\", "/")
                if any(rel.startswith(p) for p in protected_paths):
                    continue
                total += 1
                dst = resolved_root / rel
                if not dst.is_file():
                    modified_files.append({"path": rel, "status": "new_from_cli", "size": fp.stat().st_size})
                else:
                    try:
                        if fp.read_bytes() != dst.read_bytes():
                            modified_files.append({"path": rel, "status": "updated_in_cli", "size": fp.stat().st_size})
                        else:
                            synced_count += 1
                    except Exception:
                        modified_files.append({"path": rel, "status": "updated_in_cli", "size": fp.stat().st_size})

        return {
            "ok": True,
            "cli_root": str(cli_dir).replace("\\", "/"),
            "cli_found": True,
            "protected_paths": protected_paths,
            "shared_modules": shared_modules,
            "modified_files": modified_files,
            "synced_count": synced_count,
            "total_shared_files": total,
        }

    @app.get("/api/sync/cli_diff")
    def sync_cli_diff(cli_root: str = "") -> Dict[str, Any]:
        return _compute_cli_core_diff(cli_root)

    @app.post("/api/sync/cli_transfer")
    def sync_cli_transfer(req: CliTransferReq) -> Dict[str, Any]:
        info = _compute_cli_core_diff(req.cli_root)
        if not info.get("cli_found"):
            raise HTTPException(status_code=404, detail=f"CLI repository not found at {info['cli_root']}")
        cli_dir = Path(info["cli_root"])
        allowed_rels = {item["path"] for item in info["modified_files"]}
        chosen = req.paths if req.paths else list(allowed_rels)

        copied: List[str] = []
        for rel in chosen:
            clean_rel = str(rel).replace("\\", "/").lstrip("/")
            if clean_rel not in allowed_rels:
                continue
            src = cli_dir / clean_rel
            dst = resolved_root / clean_rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            copied.append(clean_rel)

        forget_uncached_capabilities()
        load_custom_providers()
        after = _compute_cli_core_diff(req.cli_root)
        after["copied"] = copied
        return after

    @app.post("/api/agent/stream")
    async def agent_stream(req: AgentStreamReq, request: Request):
        if req.workdir and req.workdir.strip():
            cand_wd = Path(req.workdir.strip()).expanduser()
            if cand_wd.is_dir():
                state["workdir"] = cand_wd.resolve()
        wd: Path = state["workdir"]
        settings_mgr = _load_merged_settings(wd, resolved_root)
        cfg = settings_mgr.config or {}
        provider = req.provider or str(cfg.get("default_provider") or "openrouter")
        model = req.model or str(cfg.get("default_model") or "deepseek/deepseek-r1:free")
        api_key = str((cfg.get("api_keys") or {}).get(provider) or "")
        session_id = req.session_id or f"desktop_{uuid.uuid4().hex[:8]}"

        pinfo = PROVIDERS_CATALOG.get(provider)
        base_url_low = (pinfo.base_url if pinfo else "").lower()
        is_local_api = provider in ("localllmapi", "ollama", "lmstudio") or ("127.0.0.1" in base_url_low or "localhost" in base_url_low)
        is_keyless = provider in ("local_gguf", "opencode_zen") or (pinfo is not None and not getattr(pinfo, "requires_key", True))
        local_reachable = _is_local_api_reachable(pinfo.base_url if pinfo else "") if is_local_api else False
        has_live_cred = local_reachable if is_local_api else (True if is_keyless else bool(api_key.strip()))
        should_run_live = req.use_live and has_live_cred and not model.startswith("(")

        async def event_generator():
            def emit(ev_type: str, payload: Dict[str, Any]) -> str:
                return f"data: {json.dumps({'type': ev_type, **payload}, ensure_ascii=False)}\n\n"

            yield emit(
                "meta",
                {
                    "session_id": session_id,
                    "provider": provider,
                    "model": model,
                    "mode": req.mode,
                    "thinking_level": req.thinking_level,
                    "live": should_run_live,
                },
            )

            if should_run_live:
                q: asyncio.Queue = asyncio.Queue()
                loop = asyncio.get_running_loop()
                runtime_ref: Dict[str, Any] = {"obj": None}

                def _worker():
                    try:
                        from cmdai.core.session_runtime import SessionRuntime

                        def _ask_handler(question: str = "", options: Optional[List[str]] = None, details: Optional[Dict[str, Any]] = None) -> Any:
                            req_id = f"apr_{uuid.uuid4().hex[:8]}"
                            ev = threading.Event()
                            rec = {"event": ev, "decision": None}
                            state["pending_approvals"][req_id] = rec
                            merged_details = dict(details) if isinstance(details, dict) else {}
                            if question and "question" not in merged_details:
                                merged_details["question"] = question
                            if options and "options" not in merged_details:
                                merged_details["options"] = list(options)
                            if "action" not in merged_details:
                                merged_details["action"] = "ask" if options else "approve"
                            loop.call_soon_threadsafe(
                                q.put_nowait,
                                ("approval_request", {"id": req_id, "details": merged_details}),
                            )
                            ev.wait(timeout=300)
                            state["pending_approvals"].pop(req_id, None)
                            return rec.get("decision")

                        runtime = SessionRuntime(
                            workdir=str(wd),
                            provider=provider,
                            model=model,
                            mode=req.mode,
                            api_key=api_key,
                            settings_manager=settings_mgr,
                            ask_handler=_ask_handler,
                        )
                        runtime_ref["obj"] = runtime
                        if req.session_id:
                            try:
                                existing_sess = SessionManager(project_dir=str(wd)).load_session(req.session_id)
                                if existing_sess:
                                    if isinstance(existing_sess.get("messages"), list):
                                        runtime.messages = list(existing_sess["messages"])
                                    if isinstance(existing_sess.get("transcript"), list):
                                        runtime.transcript = list(existing_sess["transcript"])
                            except Exception:
                                pass
                        ctx_prefix = ""
                        if (req.mode or "").strip().lower() == "plan":
                            ctx_prefix += "[Active Mode: PLAN — read-only planning only; do NOT edit/write files or run commands]\n\n"
                        if req.pinned_files:
                            ctx_prefix += "Pinned context files: " + ", ".join(f"@{p}" for p in req.pinned_files) + "\n\n"
                        def _on_thinking(th: str):
                            note_reasoning_observed(model, provider)
                            loop.call_soon_threadsafe(q.put_nowait, ("thinking", {"text": th}))

                        def _parse_args_dict(a: Any) -> Optional[Dict[str, Any]]:
                            if isinstance(a, dict):
                                return a
                            if isinstance(a, str):
                                s = a.strip()
                                if s.startswith("{") and s.endswith("}"):
                                    try:
                                        import ast
                                        parsed = ast.literal_eval(s)
                                        if isinstance(parsed, dict):
                                            return parsed
                                    except Exception:
                                        pass
                            return None

                        def _fmt_tool_args(a: Any, tool_name: str = "") -> str:
                            if not a:
                                return ""
                            d = _parse_args_dict(a)
                            if d is not None:
                                tl = str(tool_name or "").lower()
                                p_val = d.get("path") or d.get("file_path") or d.get("target_file") or d.get("file") or d.get("dest")
                                if tl in ("write", "edit", "multi_edit", "patch", "read", "ls", "list") and p_val:
                                    return str(p_val)[:140]
                                skip_keys = {"content", "code", "old", "new", "old_str", "new_str", "old_content", "new_content", "replacement", "edits"}
                                parts = [f"{k}={v}" for k, v in d.items() if v not in ("", None) and str(k).lower() not in skip_keys]
                                if not parts and p_val:
                                    return str(p_val)[:140]
                                return ", ".join(parts)[:120]
                            s = str(a).strip()
                            if s in ("{}", "None", "null"):
                                return ""
                            import re as _re
                            pm = _re.search(r"""(?:path|file_path|target_file|file)\s*[:=]\s*["']?([^"',}\r\n]+)["']?""", s, _re.IGNORECASE)
                            if pm and str(tool_name or "").lower() in ("write", "edit", "patch", "read", "ls"):
                                return pm.group(1).strip()[:140]
                            return s[:120]

                        def _build_tool_diff(tool_name: str, args: Any, res: Any) -> Optional[Dict[str, Any]]:
                            tl = str(tool_name or "").lower()
                            if tl not in ("write", "edit", "patch"):
                                return None
                            d = _parse_args_dict(args) or {}
                            fpath = str(d.get("path") or d.get("file_path") or d.get("target_file") or d.get("file") or "").strip()
                            if not fpath:
                                return None
                            import difflib
                            old_txt = str(d.get("old") or d.get("old_str") or d.get("old_content") or "")
                            new_txt = str(d.get("new") or d.get("new_str") or d.get("new_content") or d.get("content") or d.get("code") or "")
                            if isinstance(res, dict) and res.get("diff"):
                                uni = str(res["diff"])
                            elif old_txt or new_txt:
                                uni = "\n".join(difflib.unified_diff(
                                    old_txt.splitlines(),
                                    new_txt.splitlines(),
                                    fromfile=f"a/{fpath}",
                                    tofile=f"b/{fpath}",
                                    lineterm="",
                                ))
                            else:
                                uni = ""
                            added = sum(1 for ln in uni.splitlines() if ln.startswith("+") and not ln.startswith("+++")) if uni else (len(new_txt.splitlines()) if new_txt else 1)
                            removed = sum(1 for ln in uni.splitlines() if ln.startswith("-") and not ln.startswith("---")) if uni else 0
                            return {"path": fpath, "added": max(0, added), "removed": max(0, removed), "unified": uni}

                        def _on_tool_start(name: str, args: Any):
                            loop.call_soon_threadsafe(
                                q.put_nowait,
                                ("tool_start", {"name": name, "args": _fmt_tool_args(args, name)}),
                            )

                        def _on_tool_finish(name: str, args: Any, res: Any):
                            ok = True
                            summary = "Completed"
                            preview = ""
                            if isinstance(res, dict):
                                ok = bool(res.get("success", True))
                                raw_out = str(res.get("content") or res.get("output") or res.get("error") or "").strip()
                                first_line = raw_out.splitlines()[0] if raw_out else ""
                                summary = first_line[:140] if first_line else ("Completed" if ok else "Failed")
                                preview = raw_out[:1200]
                                if name in ("todo", "scratch") and isinstance(getattr(runtime.agent_ctx, "todo_list", None), list):
                                    loop.call_soon_threadsafe(
                                        q.put_nowait,
                                        ("todo_update", {"todos": list(runtime.agent_ctx.todo_list)}),
                                    )
                            elif res:
                                summary = str(res)[:140]
                            diff_obj = _build_tool_diff(name, args, res) if ok else None
                            if diff_obj and diff_obj.get("unified") and not preview:
                                preview = diff_obj["unified"][:2400]
                            payload: Dict[str, Any] = {
                                "name": name,
                                "args": _fmt_tool_args(args, name),
                                "ok": ok,
                                "summary": summary,
                                "preview": preview,
                            }
                            if diff_obj:
                                payload["diff"] = diff_obj
                            loop.call_soon_threadsafe(
                                q.put_nowait,
                                ("tool_finish", payload),
                            )

                        def _on_tool_stream(name: str, target: str, lines: int, preview: str):
                            loop.call_soon_threadsafe(
                                q.put_nowait,
                                ("tool_streaming", {"name": name, "args": target, "lines": lines, "preview": preview}),
                            )

                        def _on_subagent_event(ev: Dict[str, Any]):
                            sid_sub = str(ev.get("id") or ev.get("name") or "subagent")
                            entry = {
                                "id": sid_sub,
                                "name": str(ev.get("name") or ev.get("role") or "Subagent"),
                                "role": str(ev.get("role") or ev.get("name") or "Subagent"),
                                "status": str(ev.get("status") or "running"),
                                "tool": str(ev.get("tool") or ""),
                                "arg": str(ev.get("arg") or ""),
                                "summary": str(ev.get("summary") or ""),
                                "output": str(ev.get("output") or ""),
                                "goal": str(ev.get("goal") or ""),
                                "events": list(ev.get("events") or []),
                                "elapsed": float(ev.get("elapsed") or 0.0),
                                "updated_at": time.time(),
                            }
                            subs_list = state["subagents"]
                            updated = False
                            for idx_s, existing_s in enumerate(subs_list):
                                if str(existing_s.get("id") or "") == sid_sub:
                                    if not entry["goal"] and existing_s.get("goal"):
                                        entry["goal"] = existing_s["goal"]
                                    if not entry["output"] and existing_s.get("output"):
                                        entry["output"] = existing_s["output"]
                                    if not entry["events"] and existing_s.get("events"):
                                        entry["events"] = existing_s["events"]
                                    subs_list[idx_s] = entry
                                    updated = True
                                    break
                            if not updated:
                                subs_list.insert(0, entry)
                                del subs_list[30:]
                            loop.call_soon_threadsafe(
                                q.put_nowait,
                                ("subagent_event", {**entry, "phase": str(ev.get("phase") or "progress")}),
                            )

                        from cmdai.browser import get_browser_engine as _get_b_eng
                        _b_eng = _get_b_eng()

                        def _on_browser_ev(bev: Dict[str, Any]):
                            loop.call_soon_threadsafe(q.put_nowait, ("browser_event", bev))

                        _b_eng.add_listener(_on_browser_ev)
                        try:
                            max_steps_cfg = int((cfg.get("agent") or {}).get("max_iterations") or 50)
                            final = runtime.run_turn(
                                ctx_prefix + req.prompt,
                                on_token=lambda tok: loop.call_soon_threadsafe(q.put_nowait, ("token", {"text": tok})),
                                on_thinking=_on_thinking,
                                on_tool_start=_on_tool_start,
                                on_tool_finish=_on_tool_finish,
                                on_tool_stream=_on_tool_stream,
                                on_subagent_event=_on_subagent_event,
                                max_steps=max(15, max_steps_cfg),
                            )
                        finally:
                            _b_eng.remove_listener(_on_browser_ev)
                        if req.prompt.strip() != "Inspect repomap.py":
                            try:
                                sm = SessionManager(project_dir=str(wd))
                                existing = sm.load_session(session_id)
                                title = (existing or {}).get("title") or clean_title_from_prompt(req.prompt)
                                saved_msgs = list(runtime.messages) if runtime.messages else (
                                    list((existing or {}).get("messages") or [])
                                    + [{"role": "user", "content": req.prompt}, {"role": "assistant", "content": final or ""}]
                                )
                                sm.save_session(
                                    session_id=session_id,
                                    title=title,
                                    messages=saved_msgs,
                                    model_id=model,
                                    provider_id=provider,
                                    agent_mode=req.mode,
                                    transcript=list(runtime.transcript),
                                    todo_list=list(getattr(runtime.agent_ctx, "todo_list", None) or []),
                                    workdir=str(wd),
                                )
                            except Exception:
                                pass
                        loop.call_soon_threadsafe(q.put_nowait, ("done", {"text": final, "session_id": session_id}))
                    except Exception as exc:
                        loop.call_soon_threadsafe(q.put_nowait, ("error", {"message": str(exc)}))

                threading.Thread(target=_worker, daemon=True).start()
                while True:
                    if await request.is_disconnected():
                        if runtime_ref.get("obj") is not None:
                            runtime_ref["obj"].abort_requested = True
                        break
                    try:
                        ev_type, payload = await asyncio.wait_for(q.get(), timeout=10.0)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    yield emit(ev_type, payload)
                    if ev_type in ("done", "error"):
                        break
                return

            if req.use_live:
                hint = (
                    f"Brak aktywnego klucza API dla dostawcy `{provider}` "
                    + ("oraz lokalny serwer modeli nie odpowiada pod skonfigurowanym adresem." if is_local_api else f"(model `{model}`).")
                    + "\n\nOtwórz **Models & Engine** w lewym panelu, wklej klucz API dla dostawcy "
                    "lub uruchom **LocalLLMAPI / Ollama** i wybierz model lokalny."
                )
                yield emit("token", {"text": hint})
                yield emit("done", {"text": hint, "session_id": session_id})
                return

            # Deterministic workspace-grounded offline inspection stream (used by automated tests with use_live=False)
            target_rel = req.pinned_files[0] if req.pinned_files else "src/cmdai/indexer/repo_map.py"
            target_file = wd / target_rel
            if not target_file.is_file():
                target_rel = "src/cmdai/core/updater.py"
                target_file = wd / target_rel

            think_steps = [
                f"Analyzing request in **{req.mode.upper()}** mode (`thinking={req.thinking_level}`)...",
                f"Inspecting workspace architecture at `{target_rel}` and dependency graph via Rust + AST indexer...",
                "Preparing concrete code insights, inline diff preview, and cross-platform verification plan.",
            ]
            for chunk in think_steps:
                yield emit("thinking", {"text": chunk + "\n"})
                await asyncio.sleep(0.16)

            # Tool 1: read_file (real file read)
            yield emit("tool_start", {"id": "t1", "name": "read_file", "args": f"path='{target_rel}', lines=1..45"})
            await asyncio.sleep(0.18)
            snippet = ""
            if target_file.is_file():
                lines = target_file.read_text(encoding="utf-8", errors="replace").splitlines()
                snippet = "\n".join(lines[:14])
            yield emit(
                "tool_finish",
                {
                    "id": "t1",
                    "name": "read_file",
                    "ok": True,
                    "summary": f"Read {target_rel} ({len(snippet.splitlines())} preview lines)",
                    "preview": snippet,
                },
            )

            # Tool 2: ast_graph (real repo map stats)
            yield emit("tool_start", {"id": "t2", "name": "ast_repo_map", "args": f"workdir='{wd.name}'"})
            await asyncio.sleep(0.18)
            graph = build_repo_graph(str(wd), max_files=40)
            yield emit(
                "tool_finish",
                {
                    "id": "t2",
                    "name": "ast_repo_map",
                    "ok": True,
                    "summary": f"Mapped {len(graph.get('nodes', []))} nodes & {len(graph.get('edges', []))} AST edges",
                    "preview": "",
                },
            )

            # Tool 3: propose inline diff preview grounded on a real file
            sample_rel = "src/cmdai/core/server.py"
            sample_path = wd / sample_rel
            diff_payload = None
            if sample_path.is_file():
                old_txt = sample_path.read_text(encoding="utf-8", errors="replace")
                if "active_model" in old_txt:
                    new_txt = old_txt.replace(
                        '"status": "CMDAI CODE background server online",',
                        '"status": "CMDAI CODE Desktop & Background Server online",',
                        1,
                    )
                    if new_txt != old_txt:
                        diff_payload = _compute_hunks(old_txt, new_txt, sample_rel)
                        yield emit("diff_proposal", {"diff": diff_payload})
                        await asyncio.sleep(0.12)

            answer_md = (
                f"### Workspace Analysis Complete (`{model}`)\n\n"
                f"Przeanalizowałem strukturę projektu **{wd.name}** w trybie **{req.mode.upper()}** "
                f"(poziom rozumowania: `{req.thinking_level}`).\n\n"
                f"- **Sprawdzony moduł**: `{target_rel}`\n"
                f"- **Graf AST (`/map`)**: wykryto `{len(graph.get('nodes', []))}` węzłów oraz `{len(graph.get('edges', []))}` powiązań importów.\n"
                f"- **Rdzeń Pythona + Rust**: warstwa `agent/`, `core/`, `indexer/`, `mcp/`, `editor/core/` obsługuje podpowiedzi `@` i `/` bezpośrednio w czacie.\n\n"
                f"Możesz otworzyć **Open in Editor** na podglądzie diffa lub wybrać z menu **Overview** w prawym górnym rogu (`Files`, `Review`, `Mind Map`, `Terminal`)."
            )

            words = answer_md.split(" ")
            acc = []
            for idx in range(0, len(words), 4):
                piece = " ".join(words[idx : idx + 4]) + (" " if idx + 4 < len(words) else "")
                acc.append(piece)
                yield emit("token", {"text": piece})
                await asyncio.sleep(0.03)

            # Save or append thread via SessionManager (skip synthetic pytest smoke prompt)
            if req.prompt.strip() != "Inspect repomap.py":
                try:
                    sm = SessionManager(project_dir=str(wd))
                    existing = sm.load_session(session_id)
                    prior_msgs = list((existing or {}).get("messages") or [])
                    prior_msgs.extend(
                        [
                            {"role": "user", "content": req.prompt},
                            {"role": "assistant", "content": answer_md},
                        ]
                    )
                    title = (existing or {}).get("title") or clean_title_from_prompt(req.prompt)
                    sm.save_session(
                        session_id=session_id,
                        title=title,
                        messages=prior_msgs,
                        model_id=model,
                        provider_id=provider,
                        agent_mode=req.mode,
                        workdir=str(wd),
                    )
                except Exception:
                    pass

            yield emit("done", {"text": answer_md, "session_id": session_id})

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    @app.post("/api/voice/transcribe")
    async def api_voice_transcribe(request: Request):
        body = await request.json()
        wav_b64 = str((body or {}).get("audio_wav_base64") or "")
        from cmdai.core.web_overview import transcribe_web_voice_wav
        res = await asyncio.to_thread(transcribe_web_voice_wav, wav_b64)
        return JSONResponse(res, status_code=200 if res.get("ok") else 400)

    @app.get("/api/voice/status")
    async def api_voice_status():
        from cmdai.core.voice import is_voice_model_ready
        from cmdai.core.web_overview import get_settings_payload
        ready, detail = await asyncio.to_thread(is_voice_model_ready)
        cfg_data = get_settings_payload()
        return {
            "ready": ready,
            "detail": detail,
            "provider": cfg_data.get("voice_provider", "local"),
            "model": cfg_data.get("voice_model", "large-v3-turbo"),
            "language": cfg_data.get("voice_language", "auto"),
        }

    @app.post("/api/voice/config")
    async def api_voice_config(request: Request):
        body = await request.json()
        from cmdai.core.web_overview import update_settings_payload
        from cmdai.core.voice import is_voice_model_ready
        updated = update_settings_payload(body if isinstance(body, dict) else {})
        ready, detail = await asyncio.to_thread(is_voice_model_ready)
        return {"ok": True, "ready": ready, "detail": detail, "settings": updated}

    @app.get("/api/settings/cli")
    async def api_settings_cli_get():
        from cmdai.core.web_overview import get_settings_payload
        return get_settings_payload()

    @app.post("/api/settings/cli")
    async def api_settings_cli_post(request: Request):
        body = await request.json()
        from cmdai.core.web_overview import update_settings_payload
        updated = update_settings_payload(body if isinstance(body, dict) else {})
        return {"ok": True, "settings": updated}

    @app.get("/api/hf/search")
    async def api_hf_search(q: str = Query("qwen coder")):
        try:
            from cmdai.core.hf_hub import search_hf_models
            items = await asyncio.to_thread(search_hf_models, q, 14)
            return {"ok": True, "items": items or []}
        except Exception as exc:
            return {"ok": False, "items": [], "error": str(exc)}

    @app.get("/api/subagents")
    def list_subagents_api() -> Dict[str, Any]:
        return {"ok": True, "subagents": list(state["subagents"])}

    @app.post("/api/subagents/cancel")
    def cancel_subagent_api(payload: Dict[str, Any]) -> Dict[str, Any]:
        sid = str(payload.get("id") or "").strip()
        if not sid:
            return {"ok": False, "error": "Missing subagent id"}
        try:
            from cmdai.agent.tasks import BackgroundTaskManager
            BackgroundTaskManager.get_instance().cancel_subagent(sid)
        except Exception:
            pass
        for item in state["subagents"]:
            if str(item.get("id") or "") == sid:
                item["status"] = "cancelled"
                item["summary"] = "Cancelled by user"
                break
        return {"ok": True, "subagents": list(state["subagents"])}

    @app.get("/api/browser/state")
    def browser_state_api() -> Dict[str, Any]:
        from cmdai.browser import get_browser_engine
        return {"ok": True, **get_browser_engine().get_state()}

    @app.get("/api/browser/frame")
    def browser_frame_api():
        from fastapi.responses import Response
        from cmdai.browser import get_browser_engine
        eng = get_browser_engine()
        if not eng.latest_frame:
            return Response(status_code=204)
        return Response(
            content=eng.latest_frame,
            media_type="image/jpeg",
            headers={"Cache-Control": "no-store"},
        )

    @app.post("/api/browser/open")
    async def browser_open_api(payload: Dict[str, Any]) -> Dict[str, Any]:
        from cmdai.browser import get_browser_engine
        url = str(payload.get("url") or "").strip()
        if not url:
            return {"ok": False, "error": "URL is required"}
        res = await asyncio.to_thread(get_browser_engine().open_url, url)
        return {"ok": bool(res.get("success")), **res, "state": get_browser_engine().get_state()}

    @app.post("/api/browser/interact")
    async def browser_interact_api(payload: Dict[str, Any]) -> Dict[str, Any]:
        from cmdai.browser import get_browser_engine
        eng = get_browser_engine()
        act = str(payload.get("action") or "click").lower()
        if act == "click":
            res = await asyncio.to_thread(
                eng.click,
                x=int(payload.get("x", 0)),
                y=int(payload.get("y", 0)),
                from_user=True,
            )
        elif act == "type":
            res = await asyncio.to_thread(
                eng.type_text,
                text=str(payload.get("text") or ""),
                submit=bool(payload.get("submit", False)),
                from_user=True,
            )
        elif act == "scroll":
            res = await asyncio.to_thread(
                eng.scroll,
                direction=str(payload.get("direction") or "down"),
                amount=int(payload.get("amount") or 420),
            )
        else:
            res = {"success": False, "error": f"Unknown action: {act}"}
        return {"ok": bool(res.get("success")), **res, "state": eng.get_state()}

    @app.post("/api/browser/take-control")
    def browser_take_control_api(payload: Dict[str, Any]) -> Dict[str, Any]:
        from cmdai.browser import get_browser_engine
        st = get_browser_engine().set_take_control(bool(payload.get("enabled", False)))
        return {"ok": True, **st}

    @app.post("/api/browser/close")
    def browser_close_api() -> Dict[str, Any]:
        from cmdai.browser import get_browser_engine
        return {"ok": True, **get_browser_engine().close()}

    ui_dir = resolved_root / "web" / "ui"
    if not ui_dir.is_dir():
        ui_dir = resolved_root / "desktop" / "ui"
    if ui_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(ui_dir), html=True), name="desktop_ui")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="CMDAI CODE Desktop Bridge Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    parser.add_argument("--workdir", default=str(_APP_ROOT))
    parser.add_argument("--open", action="store_true", help="Open desktop window when ready")
    args = parser.parse_args()

    app = create_app(app_root=_APP_ROOT, workdir=Path(args.workdir))
    if args.open:
        url = f"http://{args.host}:{args.port}"

        def _open_later():
            time.sleep(1.1)
            import webbrowser

            webbrowser.open(url)

        threading.Thread(target=_open_later, daemon=True).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
