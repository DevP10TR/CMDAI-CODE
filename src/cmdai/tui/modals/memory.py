"""Modal for /memory: read-only/delete view of what the model remembered for this directory."""

from __future__ import annotations

import os

from rich.markup import escape
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from ...core.memory import (
    clear_memory,
    list_memory_entries,
    remove_memory_entry,
)


class MemoryModal(ModalScreen):
    """Modal displaying memory entries saved by the model for the current directory."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("delete", "delete_selected", "Delete"),
        Binding("ctrl+delete", "clear_project", "Clear directory"),
    ]

    def __init__(self, workdir: str = ".", **kwargs):
        super().__init__(**kwargs)
        self.workdir = workdir
        self._items: list[tuple[str, int, str]] = []

    def compose(self) -> ComposeResult:
        dir_name = os.path.basename(os.path.abspath(self.workdir or ".")) or self.workdir
        with Vertical(id="modal-dialog", classes="sessions-dialog"):
            with Horizontal(id="modal-header"):
                yield Static(f"Memory — {dir_name}", id="modal-title")
                yield Static("[dim]esc[/]", id="modal-esc")

            yield OptionList(id="modal-list")

            with Horizontal(id="modal-footer"):
                yield Static("delete: Delete  ·  ctrl+del: Clear directory  ·  esc: Close")

    def on_mount(self) -> None:
        self._reload_list()
        self.query_one("#modal-list", OptionList).focus()

    def _reload_list(self) -> None:
        data = list_memory_entries(self.workdir, scope="all")
        ol = self.query_one("#modal-list", OptionList)
        ol.clear_options()
        self._items = []
        dir_name = os.path.basename(os.path.abspath(self.workdir or ".")) or self.workdir
        p_list = data.get("project", [])
        g_list = data.get("global", [])

        if p_list:
            ol.add_option(Option(Text.from_markup(f"[bold #58a6ff]  ── Directory: {escape(dir_name)} (.cmdai/memory.md)[/]"), disabled=True))
            for idx, text in enumerate(p_list, 1):
                oid = f"project:{idx}"
                self._items.append(("project", idx, text))
                t_row = Text.from_markup(f"   [#58a6ff]#{idx}[/]  [white]{escape(text)}[/]")
                t_row.no_wrap = True
                t_row.overflow = "ellipsis"
                ol.add_option(Option(t_row, id=oid))

        if g_list:
            if p_list:
                ol.add_option(Option(Text(""), disabled=True))
            ol.add_option(Option(Text.from_markup("[bold #a371f7]  ── Global (~/.cmdai/memory.md)[/]"), disabled=True))
            for idx, text in enumerate(g_list, 1):
                oid = f"global:{idx}"
                self._items.append(("global", idx, text))
                t_row = Text.from_markup(f"   [#a371f7]#{idx}[/]  [white]{escape(text)}[/]")
                t_row.no_wrap = True
                t_row.overflow = "ellipsis"
                ol.add_option(Option(t_row, id=oid))

        if not self._items:
            ol.add_option(
                Option(
                    Text.from_markup(f"  [dim]No memories recorded for '{escape(dir_name)}' yet.[/]"),
                    disabled=True,
                )
            )

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def action_delete_selected(self) -> None:
        ol = self.query_one("#modal-list", OptionList)
        if ol.highlighted is None or not self._items:
            return
        try:
            opt = ol.get_option_at_index(ol.highlighted)
            oid = str(getattr(opt, "id", "") or "")
            if ":" not in oid:
                return
            scope, idx_str = oid.split(":", 1)
            res = remove_memory_entry(self.workdir, index=int(idx_str), scope=scope)
            if res.get("success"):
                self._reload_list()
        except Exception:
            pass

    def action_clear_project(self) -> None:
        clear_memory(self.workdir, scope="project")
        self._reload_list()
