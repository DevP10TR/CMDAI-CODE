"""Plugin discovery and lifecycle for CMDAI CODE (.cmdai/plugins & ~/.cmdai/plugins)."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def _safe_plugin_slug(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", (name or "").strip()).strip("-").lower()
    return clean or "my-plugin"


def get_plugins_dirs(
    workdir: str = ".",
    global_plugins_dir: Optional[str] = None,
) -> List[tuple[str, Path]]:
    """Return (scope, directory) pairs for global and project plugin roots."""
    if global_plugins_dir:
        g_dir = Path(global_plugins_dir)
    else:
        env_g = os.environ.get("CMDAI_GLOBAL_PLUGINS_DIR", "").strip()
        g_dir = Path(env_g) if env_g else (Path.home() / ".cmdai" / "plugins")
    p_dir = Path(workdir or ".") / ".cmdai" / "plugins"
    return [("global", g_dir), ("project", p_dir)]


def _read_json_dict(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_disabled_from_settings() -> Set[str]:
    try:
        from .settings import SettingsManager

        cfg = SettingsManager().config
        raw = cfg.get("disabled_plugins", [])
        if isinstance(raw, list):
            return {str(x).strip().lower() for x in raw if str(x).strip()}
    except Exception:
        pass
    return set()


def set_plugin_enabled(plugin_id: str, enabled: bool) -> bool:
    """Persist enabled/disabled state of `plugin_id` in SettingsManager."""
    pid = (plugin_id or "").strip().lower()
    if not pid:
        return False
    try:
        from .settings import SettingsManager

        sm = SettingsManager()
        raw = sm.config.get("disabled_plugins", [])
        disabled = {str(x).strip().lower() for x in (raw if isinstance(raw, list) else []) if str(x).strip()}
        if enabled:
            disabled.discard(pid)
        else:
            disabled.add(pid)
        sm.config["disabled_plugins"] = sorted(disabled)
        sm.save()
        return True
    except Exception:
        return False


def _load_plugin_dir(plugin_dir: Path, scope: str, disabled_set: Set[str]) -> Optional[Dict[str, Any]]:
    if not plugin_dir.is_dir():
        return None
    slug = plugin_dir.name.lower()
    manifest = _read_json_dict(plugin_dir / "plugin.json")
    name = str(manifest.get("name") or plugin_dir.name).strip()
    version = str(manifest.get("version") or "1.0.0").strip()
    description = str(manifest.get("description") or "").strip()
    author = str(manifest.get("author") or "").strip()

    # Commands: commands/*.md
    commands: List[Dict[str, str]] = []
    cmd_dir = plugin_dir / "commands"
    if cmd_dir.is_dir():
        for md in sorted(cmd_dir.glob("*.md")):
            try:
                body = md.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            first = next((ln.strip().lstrip("#").strip() for ln in body.splitlines() if ln.strip()), "")
            commands.append({
                "name": "/" + md.stem.lower(),
                "slug": md.stem.lower(),
                "path": str(md),
                "description": (first[:80] or f"Plugin command ({name})"),
                "body": body,
                "plugin": name,
            })

    # Rules: rules/*.md
    rules: List[Dict[str, str]] = []
    rules_dir = plugin_dir / "rules"
    if rules_dir.is_dir():
        for md in sorted(rules_dir.glob("*.md")):
            try:
                body = md.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                continue
            if body:
                rules.append({"name": md.stem, "path": str(md), "body": body, "plugin": name})

    # Hooks: hooks.json
    hooks_data = _read_json_dict(plugin_dir / "hooks.json")
    post_hooks = hooks_data.get("PostToolUse") if isinstance(hooks_data.get("PostToolUse"), list) else []

    # MCP servers: mcp.json
    mcp_data = _read_json_dict(plugin_dir / "mcp.json")
    mcp_servers = mcp_data.get("mcpServers") if isinstance(mcp_data.get("mcpServers"), dict) else {}

    manifest_enabled = manifest.get("enabled")
    is_enabled = (slug not in disabled_set) and (manifest_enabled is not False)

    return {
        "id": slug,
        "name": name,
        "version": version,
        "description": description or "Local CMDAI plugin",
        "author": author,
        "scope": scope,
        "path": str(plugin_dir),
        "enabled": is_enabled,
        "commands": commands,
        "rules": rules,
        "hooks": post_hooks,
        "mcp_servers": mcp_servers,
        "commands_count": len(commands),
        "rules_count": len(rules),
        "hooks_count": len(post_hooks),
        "mcp_count": len(mcp_servers),
    }


def discover_plugins(
    workdir: str = ".",
    disabled_plugins: Optional[Set[str]] = None,
    global_plugins_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Discover all global and project-local plugins (project overrides global on same id)."""
    disabled_set = disabled_plugins if disabled_plugins is not None else _load_disabled_from_settings()
    by_id: Dict[str, Dict[str, Any]] = {}
    for scope, root in get_plugins_dirs(workdir, global_plugins_dir=global_plugins_dir):
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir(), key=lambda p: p.name.lower()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            info = _load_plugin_dir(entry, scope, disabled_set)
            if info is not None:
                by_id[info["id"]] = info
    return sorted(by_id.values(), key=lambda p: p["name"].lower())


def get_enabled_plugin_commands(
    workdir: str = ".",
    disabled_plugins: Optional[Set[str]] = None,
    global_plugins_dir: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Return slash commands from all enabled plugins."""
    cmds: List[Dict[str, str]] = []
    for p in discover_plugins(workdir, disabled_plugins=disabled_plugins, global_plugins_dir=global_plugins_dir):
        if p.get("enabled"):
            cmds.extend(p.get("commands") or [])
    return cmds


def get_enabled_plugin_rules(
    workdir: str = ".",
    max_chars: int = 4000,
    disabled_plugins: Optional[Set[str]] = None,
    global_plugins_dir: Optional[str] = None,
) -> str:
    """Return formatted rules markdown from all enabled plugins."""
    blocks: List[str] = []
    for p in discover_plugins(workdir, disabled_plugins=disabled_plugins, global_plugins_dir=global_plugins_dir):
        if not p.get("enabled"):
            continue
        for r in p.get("rules") or []:
            blocks.append(f"[PLUGIN RULE: {p['name']} / {r['name']}]\n{r['body']}")
    if not blocks:
        return ""
    joined = "\n\n".join(blocks)
    if len(joined) > max_chars:
        joined = joined[: max_chars - 30].rstrip() + "\n... [plugin rules truncated]"
    return joined


def get_enabled_plugin_hooks(
    workdir: str = ".",
    disabled_plugins: Optional[Set[str]] = None,
    global_plugins_dir: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return PostToolUse hook entries from all enabled plugins."""
    out: List[Dict[str, Any]] = []
    for p in discover_plugins(workdir, disabled_plugins=disabled_plugins, global_plugins_dir=global_plugins_dir):
        if p.get("enabled"):
            out.extend(p.get("hooks") or [])
    return out


def get_enabled_plugin_mcp_servers(
    workdir: str = ".",
    disabled_plugins: Optional[Set[str]] = None,
    global_plugins_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Return merged MCP server definitions from all enabled plugins."""
    merged: Dict[str, Any] = {}
    for p in discover_plugins(workdir, disabled_plugins=disabled_plugins, global_plugins_dir=global_plugins_dir):
        if p.get("enabled") and isinstance(p.get("mcp_servers"), dict):
            merged.update(p["mcp_servers"])
    return merged


def create_sample_plugin(
    workdir: str,
    name: str,
    description: str = "",
    scope: str = "project",
    global_plugins_dir: Optional[str] = None,
) -> str:
    """Scaffold a sample plugin with manifest, command, and rule."""
    slug = _safe_plugin_slug(name)
    dirs = dict(get_plugins_dirs(workdir, global_plugins_dir=global_plugins_dir))
    root = dirs.get("global" if scope == "global" else "project", Path(workdir or ".") / ".cmdai" / "plugins")
    plugin_dir = root / slug
    (plugin_dir / "commands").mkdir(parents=True, exist_ok=True)
    (plugin_dir / "rules").mkdir(parents=True, exist_ok=True)

    manifest = {
        "name": (name or slug).strip(),
        "version": "1.0.0",
        "description": (description or f"Custom plugin {slug}").strip(),
    }
    (plugin_dir / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (plugin_dir / "commands" / f"{slug}-hello.md").write_text(
        f"# Sample command from plugin {manifest['name']}\n"
        "Summarize the current task and any arguments: $ARGUMENTS\n",
        encoding="utf-8",
    )
    (plugin_dir / "rules" / "guidelines.md").write_text(
        f"# {manifest['name']} guidelines\n"
        "- Follow the plugin conventions when working in this workspace.\n",
        encoding="utf-8",
    )
    return str(plugin_dir)


def delete_plugin(plugin_path: str) -> bool:
    """Safely delete a plugin directory inside `.cmdai/plugins`."""
    p = Path(plugin_path)
    if not p.is_dir():
        return False
    if p.parent.name != "plugins" or p.parent.parent.name != ".cmdai":
        return False
    shutil.rmtree(p, ignore_errors=False)
    return True
