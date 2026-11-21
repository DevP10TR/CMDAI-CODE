"""Backend helpers for CMDAI CODE Web UI Overview panels (AST Map, Git Diff, Files),
Settings management, and Voice WAV transcription."""

import ast
import base64
import os
import re
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from .providers import PROVIDERS_CATALOG
from .settings import get_settings

_IGNORE_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "__pycache__",
    "target", "dist", "build", ".pytest_cache", ".ruff_cache",
    "models", "logs", "cache", "bin", ".cmdai_code_project",
}
_CODE_EXTS = {".py", ".rs", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".json", ".toml", ".md"}


def _safe_join(workdir: str, rel_path: str) -> Optional[str]:
    base = os.path.abspath(workdir)
    target = os.path.abspath(os.path.join(base, rel_path))
    if target == base or target.startswith(base + os.sep):
        return target
    return None


def get_git_overview(workdir: str) -> Dict[str, Any]:
    wd = os.path.abspath(workdir)
    safe_arg = wd.replace("\\", "/")

    def _run(args: List[str]) -> str:
        try:
            proc = subprocess.run(
                ["git", "-c", f"safe.directory={safe_arg}"] + args,
                cwd=wd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=6,
            )
            return proc.stdout if proc.returncode == 0 else ""
        except Exception:
            return ""

    branch = _run(["branch", "--show-current"]).strip()
    status_raw = _run(["status", "--short"])
    files: List[Dict[str, str]] = []
    for line in status_raw.splitlines():
        if len(line) >= 4:
            code = line[:2].strip() or "M"
            path = line[3:].strip()
            files.append({"status": code, "path": path})

    diff_text = _run(["diff", "--no-color"])
    if len(diff_text) > 120_000:
        diff_text = diff_text[:120_000] + "\n... (diff truncated for preview)"

    return {
        "is_git": bool(branch or status_raw or os.path.isdir(os.path.join(wd, ".git"))),
        "branch": branch or "detached",
        "changed_files": files,
        "diff": diff_text,
    }


def list_workspace_files(workdir: str, limit: int = 220) -> List[Dict[str, Any]]:
    wd = os.path.abspath(workdir)
    out: List[Dict[str, Any]] = []
    for root, dirs, files in os.walk(wd):
        dirs[:] = sorted(d for d in dirs if d not in _IGNORE_DIRS and not d.startswith("."))
        for fname in sorted(files):
            if len(out) >= limit:
                return out
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, wd).replace("\\", "/")
            ext = os.path.splitext(fname)[1].lower()
            try:
                size = os.path.getsize(full)
            except Exception:
                size = 0
            out.append({
                "path": rel,
                "name": fname,
                "ext": ext,
                "size": size,
            })
    return out


def read_workspace_file(workdir: str, rel_path: str, max_bytes: int = 120_000) -> Dict[str, Any]:
    target = _safe_join(workdir, rel_path)
    if not target or not os.path.isfile(target):
        return {"ok": False, "error": "File not found"}
    try:
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(max_bytes)
        return {"ok": True, "path": rel_path.replace("\\", "/"), "content": content}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def build_ast_overview(workdir: str, max_files: int = 90) -> Dict[str, Any]:
    """Build a structured AST symbol & module dependency overview for the workspace."""
    wd = os.path.abspath(workdir)
    files_info: List[Dict[str, Any]] = []
    edges: List[Dict[str, str]] = []
    module_to_path: Dict[str, str] = {}

    collected_paths: List[Tuple[str, str]] = []
    for root, dirs, files in os.walk(wd):
        dirs[:] = sorted(d for d in dirs if d not in _IGNORE_DIRS and not d.startswith("."))
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in (".py", ".rs", ".js", ".ts"):
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, wd).replace("\\", "/")
            collected_paths.append((rel, full))
            if ext == ".py":
                stem = os.path.splitext(fname)[0]
                module_to_path[stem] = rel
            if len(collected_paths) >= max_files:
                break
        if len(collected_paths) >= max_files:
            break

    total_symbols = 0
    for rel, full in collected_paths:
        ext = os.path.splitext(rel)[1].lower()
        symbols: List[Dict[str, Any]] = []
        imports: List[str] = []
        lines_count = 0

        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                src = f.read(200_000)
            lines_count = src.count("\n") + 1

            if ext == ".py":
                try:
                    tree = ast.parse(src)
                    for node in tree.body:
                        if isinstance(node, ast.ClassDef):
                            methods = [
                                n.name for n in node.body
                                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                            ][:12]
                            symbols.append({
                                "kind": "class",
                                "name": node.name,
                                "line": node.lineno,
                                "children": methods,
                            })
                        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            symbols.append({
                                "kind": "fn",
                                "name": node.name,
                                "line": node.lineno,
                            })
                        elif isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.append(alias.name.split(".")[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.append(node.module.split(".")[-1])
                except SyntaxError:
                    pass
            elif ext == ".rs":
                for m in re.finditer(r"^\s*(?:pub\s+)?(?:async\s+)?(fn|struct|enum|trait)\s+([A-Za-z0-9_]+)", src, re.M):
                    line_no = src[:m.start()].count("\n") + 1
                    symbols.append({"kind": m.group(1), "name": m.group(2), "line": line_no})
            elif ext in (".js", ".ts"):
                for m in re.finditer(r"^\s*(?:export\s+)?(?:async\s+)?(function|class)\s+([A-Za-z0-9_]+)", src, re.M):
                    line_no = src[:m.start()].count("\n") + 1
                    symbols.append({"kind": "fn" if m.group(1) == "function" else "class", "name": m.group(2), "line": line_no})
        except Exception:
            pass

        total_symbols += len(symbols)
        uniq_imports = sorted(set(imports))
        for imp in uniq_imports:
            target = module_to_path.get(imp)
            if target and target != rel:
                edges.append({"from": rel, "to": target})

        folder = os.path.dirname(rel) or "."
        files_info.append({
            "path": rel,
            "name": os.path.basename(rel),
            "folder": folder,
            "ext": ext,
            "lines": lines_count,
            "symbols": symbols[:40],
            "symbol_count": len(symbols),
            "imports": uniq_imports[:12],
        })

    return {
        "workdir": wd,
        "file_count": len(files_info),
        "symbol_count": total_symbols,
        "edge_count": len(edges),
        "files": files_info,
        "edges": edges[:120],
    }


def get_settings_payload() -> Dict[str, Any]:
    s = get_settings()
    cfg = s.config
    gguf = cfg.get("gguf") or {}
    voice = cfg.get("voice") or {}

    providers_keys = []
    for pid, pinfo in PROVIDERS_CATALOG.items():
        if not getattr(pinfo, "requires_key", True):
            continue
        key_val = s.get_api_key(pid) or ""
        src = ""
        try:
            src = s.get_api_key_source(pid) or ""
        except Exception:
            pass
        masked = ""
        if key_val:
            masked = f"{key_val[:4]}...{key_val[-3:]}" if len(key_val) > 10 else "***"
        providers_keys.append({
            "id": pid,
            "name": getattr(pinfo, "name", pid),
            "configured": bool(key_val),
            "masked": masked,
            "source": src,
        })

    return {
        "loader": str(cfg.get("loader") or gguf.get("loader") or "VULKAN").upper(),
        "flash_attn": bool(gguf.get("flash_attn", True)),
        "kv_cache_type": str(gguf.get("kv_cache_type") or "auto"),
        "use_system_keyring": bool(cfg.get("use_system_keyring", False)),
        "voice_provider": str(voice.get("provider") or "local"),
        "voice_model": str(voice.get("model") or "large-v3-turbo"),
        "voice_language": str(voice.get("language") or "auto"),
        "providers_keys": providers_keys,
    }


def update_settings_payload(updates: Dict[str, Any]) -> Dict[str, Any]:
    s = get_settings()
    cfg = s.config
    gguf = cfg.setdefault("gguf", {})
    voice = cfg.setdefault("voice", {})

    if "loader" in updates and str(updates["loader"]).upper() in ("VULKAN", "CUDA", "CPU"):
        val = str(updates["loader"]).upper()
        cfg["loader"] = val
        gguf["loader"] = val
    if "flash_attn" in updates:
        gguf["flash_attn"] = bool(updates["flash_attn"])
    if "kv_cache_type" in updates and str(updates["kv_cache_type"]) in ("auto", "f16", "q8_0", "q4_0"):
        gguf["kv_cache_type"] = str(updates["kv_cache_type"])
    if "use_system_keyring" in updates:
        cfg["use_system_keyring"] = bool(updates["use_system_keyring"])
    if "voice_provider" in updates:
        voice["provider"] = str(updates["voice_provider"])
    if "voice_model" in updates:
        voice["model"] = str(updates["voice_model"])
    if "voice_language" in updates:
        voice["language"] = str(updates["voice_language"])

    if "set_api_key" in updates and isinstance(updates["set_api_key"], dict):
        pid = str(updates["set_api_key"].get("provider_id") or "").strip()
        key = str(updates["set_api_key"].get("api_key") or "").strip()
        if pid:
            try:
                s.set_api_key(pid, key)
            except Exception:
                cfg.setdefault("api_keys", {})[pid] = key

    s.save_config()
    return get_settings_payload()


def transcribe_web_voice_wav(wav_base64: str) -> Dict[str, Any]:
    """Decode base64 WAV audio from browser mic and transcribe via CMDAI CODE voice engine."""
    if not wav_base64:
        return {"ok": False, "error": "Empty audio payload"}
    try:
        raw = base64.b64decode(wav_base64)
    except Exception as exc:
        return {"ok": False, "error": f"Invalid base64 audio: {exc}"}

    fd, tmp_wav = tempfile.mkstemp(prefix="cmdai_web_voice_", suffix=".wav")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        from .voice import transcribe_audio
        text = transcribe_audio(tmp_wav)
        return {"ok": True, "text": (text or "").strip()}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            if os.path.isfile(tmp_wav):
                os.remove(tmp_wav)
        except Exception:
            pass
