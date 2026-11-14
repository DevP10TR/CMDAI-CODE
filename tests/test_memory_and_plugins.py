"""Tests for cross-session memory (<tool:memory>) and plugins (/plugins)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmdai.agent.runner import AgentRunner, load_project_instructions
from cmdai.agent.tools import AgentContext, tool_memory
from cmdai.core.custom_extensions import get_custom_command_body, list_custom_commands, load_hooks
from cmdai.core.memory import format_memory_for_prompt
from cmdai.core.plugins import (
    create_sample_plugin,
    delete_plugin,
    discover_plugins,
    get_enabled_plugin_rules,
)
from cmdai.tui.app import CMDAICodeTUI


def test_tool_memory_crud_and_prompt_loading(tmp_path: Path, monkeypatch) -> None:
    global_mem = tmp_path / "global_mem.md"
    monkeypatch.setenv("CMDAI_GLOBAL_MEMORY_PATH", str(global_mem))

    workdir = tmp_path / "proj"
    workdir.mkdir()
    ctx = AgentContext(workdir=str(workdir))

    res_add_p = tool_memory(ctx, action="add", content="Use pytest -q for fast tests", scope="project")
    assert res_add_p["success"] is True
    assert res_add_p["duplicate"] is False

    # Deduplication
    res_dup = tool_memory(ctx, action="add", content="use pytest -q for fast tests", scope="project")
    assert res_dup["success"] is True
    assert res_dup["duplicate"] is True

    res_add_g = tool_memory(ctx, action="add", content="Reply concisely in Polish", scope="global")
    assert res_add_g["success"] is True

    listed = tool_memory(ctx, action="list", scope="all")
    assert listed["entries"]["project"] == ["Use pytest -q for fast tests"]
    assert listed["entries"]["global"] == ["Reply concisely in Polish"]

    prompt_mem = format_memory_for_prompt(str(workdir))
    assert "Reply concisely in Polish" in prompt_mem
    assert "Use pytest -q for fast tests" in prompt_mem

    full_inst = load_project_instructions(str(workdir))
    assert "PERSISTENT MEMORY" in full_inst
    assert "1 project, 1 global" in full_inst
    assert "Use pytest -q for fast tests" not in full_inst

    rem = tool_memory(ctx, action="remove", index=1, scope="project")
    assert rem["success"] is True
    assert tool_memory(ctx, action="list", scope="project")["entries"]["project"] == []


def test_memory_permissions_in_plan_vs_auto_and_code(tmp_path: Path) -> None:
    runner = AgentRunner(AgentContext(workdir=str(tmp_path)))
    assert runner.check_tool_permission("memory", {"action": "list"}, "plan") == "allow"
    assert runner.check_tool_permission("memory", {"action": "add", "content": "x"}, "plan") == "deny"
    assert runner.check_tool_permission("memory", {"action": "remove", "index": 1}, "plan") == "deny"
    assert runner.check_tool_permission("memory", {"action": "add", "content": "x"}, "auto") == "allow"
    assert runner.check_tool_permission("memory", {"action": "add", "content": "x"}, "code") == "allow"


def test_plugins_discovery_toggle_and_extensions(tmp_path: Path, monkeypatch) -> None:
    global_plugs = tmp_path / "global_plugins"
    global_plugs.mkdir()
    monkeypatch.setenv("CMDAI_GLOBAL_PLUGINS_DIR", str(global_plugs))

    workdir = tmp_path / "proj"
    workdir.mkdir()

    p_dir = Path(create_sample_plugin(str(workdir), name="My Helper", description="Test helper plugin"))
    assert (p_dir / "plugin.json").is_file()

    # Add a PostToolUse hook to the plugin
    (p_dir / "hooks.json").write_text(
        json.dumps({"PostToolUse": [{"matcher": "write", "command": "echo ok"}]}),
        encoding="utf-8",
    )

    found = discover_plugins(str(workdir), disabled_plugins=set())
    assert len(found) == 1
    assert found[0]["id"] == "my-helper"
    assert found[0]["enabled"] is True
    assert found[0]["commands_count"] == 1
    assert found[0]["rules_count"] == 1
    assert found[0]["hooks_count"] == 1

    cmds = list_custom_commands(str(workdir))
    assert any(c["name"] == "/my-helper-hello" for c in cmds)
    body = get_custom_command_body(str(workdir), "/my-helper-hello", "foo")
    assert body is not None and "foo" in body

    rules_txt = get_enabled_plugin_rules(str(workdir), disabled_plugins=set())
    assert "My Helper" in rules_txt

    hooks = load_hooks(str(workdir))
    assert len(hooks["PostToolUse"]) == 1

    # Disabled plugin contributes no rules/commands
    assert get_enabled_plugin_rules(str(workdir), disabled_plugins={"my-helper"}) == ""

    assert delete_plugin(str(p_dir)) is True
    assert discover_plugins(str(workdir), disabled_plugins=set()) == []


@pytest.mark.asyncio
async def test_tui_plugins_and_memory_modals(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("CMDAI_GLOBAL_MEMORY_PATH", str(tmp_path / "g_mem.md"))
    monkeypatch.setenv("CMDAI_GLOBAL_PLUGINS_DIR", str(tmp_path / "g_plugs"))
    app = CMDAICodeTUI(workdir=str(tmp_path))
    async with app.run_test() as pilot:
        app._dispatch_command("/plugins")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "PluginsModal"
        await pilot.press("escape")
        await pilot.pause()

        app._dispatch_command("/memory")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "MemoryModal"
        await pilot.press("escape")
        await pilot.pause()
