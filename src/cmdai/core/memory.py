"""Cross-session persistent memory (.cmdai/memory.md & ~/.cmdai/memory.md)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


_MAX_ENTRY_CHARS = 500


def get_memory_file_path(
    workdir: str = ".",
    scope: str = "project",
    global_path: Optional[str] = None,
) -> Path:
    """Return the path to the project or global memory markdown file."""
    sc = (scope or "project").strip().lower()
    if sc == "global":
        if global_path:
            return Path(global_path)
        env_override = os.environ.get("CMDAI_GLOBAL_MEMORY_PATH", "").strip()
        if env_override:
            return Path(env_override)
        return Path.home() / ".cmdai" / "memory.md"
    return Path(workdir or ".") / ".cmdai" / "memory.md"


def _read_entries(path: Path) -> List[str]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return []
    out: List[str] = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("- "):
            s = s[2:].strip()
        elif s.startswith("* "):
            s = s[2:].strip()
        if s:
            out.append(s)
    return out


def _write_entries(path: Path, entries: List[str], header: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not entries:
        path.write_text(f"# {header}\n", encoding="utf-8")
        return
    body = "\n".join(f"- {e}" for e in entries)
    path.write_text(f"# {header}\n\n{body}\n", encoding="utf-8")


def list_memory_entries(
    workdir: str = ".",
    scope: str = "all",
    global_path: Optional[str] = None,
) -> Dict[str, List[str]]:
    """Return memory entries for `project`, `global`, or `all`."""
    sc = (scope or "all").strip().lower()
    result: Dict[str, List[str]] = {}
    if sc in ("all", "global"):
        result["global"] = _read_entries(get_memory_file_path(workdir, "global", global_path))
    if sc in ("all", "project"):
        result["project"] = _read_entries(get_memory_file_path(workdir, "project", global_path))
    return result


def add_memory_entry(
    workdir: str,
    content: str,
    scope: str = "project",
    global_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a concise, deduplicated memory entry to project or global memory."""
    sc = (scope or "project").strip().lower()
    if sc not in ("project", "global"):
        sc = "project"
    cleaned = " ".join(str(content or "").strip().split())
    if not cleaned:
        return {"success": False, "error": "Memory content cannot be empty."}
    if len(cleaned) > _MAX_ENTRY_CHARS:
        cleaned = cleaned[: _MAX_ENTRY_CHARS - 3].rstrip() + "..."

    path = get_memory_file_path(workdir, sc, global_path)
    entries = _read_entries(path)
    low = cleaned.lower()
    if any(e.lower() == low for e in entries):
        return {
            "success": True,
            "scope": sc,
            "path": str(path),
            "entry": cleaned,
            "duplicate": True,
            "count": len(entries),
        }
    entries.append(cleaned)
    header = "Global User Memory" if sc == "global" else "Project Memory"
    _write_entries(path, entries, header)
    return {
        "success": True,
        "scope": sc,
        "path": str(path),
        "entry": cleaned,
        "duplicate": False,
        "count": len(entries),
    }


def remove_memory_entry(
    workdir: str,
    index: int = 0,
    query: str = "",
    scope: str = "project",
    global_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Remove a memory entry by 1-based `index` or substring `query`."""
    sc = (scope or "project").strip().lower()
    if sc not in ("project", "global"):
        sc = "project"
    path = get_memory_file_path(workdir, sc, global_path)
    entries = _read_entries(path)
    if not entries:
        return {"success": False, "scope": sc, "error": "No memory entries found."}

    removed: List[str] = []
    if index and int(index) >= 1:
        idx0 = int(index) - 1
        if idx0 >= len(entries):
            return {"success": False, "scope": sc, "error": f"Index {index} out of range (1..{len(entries)})."}
        removed.append(entries.pop(idx0))
    elif (query or "").strip():
        q_low = query.strip().lower()
        kept: List[str] = []
        for e in entries:
            if q_low in e.lower():
                removed.append(e)
            else:
                kept.append(e)
        entries = kept
        if not removed:
            return {"success": False, "scope": sc, "error": f"No memory entry matching '{query}'."}
    else:
        return {"success": False, "scope": sc, "error": "Provide either 1-based index or query."}

    header = "Global User Memory" if sc == "global" else "Project Memory"
    _write_entries(path, entries, header)
    return {"success": True, "scope": sc, "path": str(path), "removed": removed, "count": len(entries)}


def clear_memory(
    workdir: str,
    scope: str = "project",
    global_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Clear all entries from `project`, `global`, or `all` memory."""
    sc = (scope or "project").strip().lower()
    cleared: List[str] = []
    targets = ["global", "project"] if sc == "all" else [sc if sc in ("global", "project") else "project"]
    for t in targets:
        path = get_memory_file_path(workdir, t, global_path)
        header = "Global User Memory" if t == "global" else "Project Memory"
        if path.is_file():
            _write_entries(path, [], header)
        cleared.append(t)
    return {"success": True, "cleared": cleared}


def format_memory_hint(
    workdir: str = ".",
    global_path: Optional[str] = None,
) -> str:
    """Return a lightweight hint when persistent memory exists, without dumping entries."""
    data = list_memory_entries(workdir, scope="all", global_path=global_path)
    g_cnt = len(data.get("global", []))
    p_cnt = len(data.get("project", []))
    if g_cnt == 0 and p_cnt == 0:
        return ""
    return (
        f"Persistent memory is available ({p_cnt} project, {g_cnt} global). "
        'Call <tool:memory action="list" scope="all" /> only when prior project facts or user preferences are needed.'
    )


def format_memory_for_prompt(
    workdir: str = ".",
    max_chars: int = 4000,
    global_path: Optional[str] = None,
) -> str:
    """Format global and project memory entries for inclusion in the system prompt."""
    data = list_memory_entries(workdir, scope="all", global_path=global_path)
    g_entries = data.get("global", [])
    p_entries = data.get("project", [])
    if not g_entries and not p_entries:
        return ""

    parts: List[str] = []
    if g_entries:
        parts.append("[GLOBAL USER MEMORY (~/.cmdai/memory.md)]")
        parts.extend(f"- {e}" for e in g_entries)
    if p_entries:
        if parts:
            parts.append("")
        parts.append("[PROJECT MEMORY (.cmdai/memory.md)]")
        parts.extend(f"- {e}" for e in p_entries)

    text = "\n".join(parts)
    if len(text) > max_chars:
        text = text[: max_chars - 30].rstrip() + "\n... [memory truncated]"
    return text
