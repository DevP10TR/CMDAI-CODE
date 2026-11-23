"""Modal for `/rules` (alias `/agents`): view and edit `<workdir>/AGENTS.md`."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from rich.markup import escape
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, TextArea

from ...agent.runner import _estimate_rule_tokens, inspect_project_rules


class RulesModal(ModalScreen[Optional[str]]):
    """Single-screen AGENTS.md editor modal matching SystemPromptEditScreen (`/system`)."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close", priority=True),
        Binding("ctrl+s", "save_rules", "Save", priority=True),
    ]

    DEFAULT_CSS = """
    RulesModal #modal-dialog {
        width: 86;
        max-width: 95%;
        height: 74%;
        max-height: 85%;
    }
    RulesModal #rules-edit-meta {
        height: 1;
        color: #8b949e;
        margin: 0 0 1 0;
    }
    RulesModal #sp-text {
        height: 1fr;
        min-height: 10;
        background: #161b22;
        border: none;
    }
    """

    def __init__(self, workdir: str = ".", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.workdir = os.path.abspath(workdir or ".")
        self.target_path = os.path.join(self.workdir, "AGENTS.md")

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            with Horizontal(id="modal-header"):
                yield Static("[bold white]AGENTS.md[/]", id="modal-title")
                yield Static("[dim]esc[/]", id="modal-esc")
            yield Static("", id="rules-edit-meta")
            yield TextArea(
                "",
                language="markdown",
                soft_wrap=True,
                id="sp-text",
                placeholder="Write project instructions for AGENTS.md... Press Ctrl+S to save.",
            )
            with Horizontal(id="modal-footer"):
                yield Static("[b #58a6ff]Save[/] ctrl+s", id="modal-footer-left")
                yield Static("[dim]esc close[/]", id="modal-footer-right")

    def _update_meta(self, content: str) -> None:
        tok = _estimate_rule_tokens(content)
        exists = os.path.isfile(self.target_path)
        tag = "" if exists else " (new)"
        try:
            self.query_one("#rules-edit-meta", Static).update(
                f"[dim]{escape(self.target_path)}{tag}[/]  ·  [#58a6ff]~{tok} tok · {len(content)} chars[/]"
            )
        except Exception:
            pass

    def on_mount(self) -> None:
        info = inspect_project_rules(self.workdir)
        self.target_path = str(info.get("path") or self.target_path)
        content = str(info.get("content") or "")
        ta = self.query_one("#sp-text", TextArea)
        ta.text = content
        self._update_meta(content)
        ta.focus()

    @on(TextArea.Changed, "#sp-text")
    def _on_text_changed(self, event: TextArea.Changed) -> None:
        self._update_meta(event.text_area.text)

    def action_save_rules(self) -> None:
        content = self.query_one("#sp-text", TextArea).text.replace("\r\n", "\n")
        try:
            p = Path(self.target_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            self._update_meta(content)
            self.query_one("#modal-footer-right", Static).update("[b #3fb950]Saved AGENTS.md[/]")
        except Exception as exc:
            self.query_one("#modal-footer-right", Static).update(
                f"[b #f85149]Save failed: {escape(str(exc))}[/]"
            )

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
