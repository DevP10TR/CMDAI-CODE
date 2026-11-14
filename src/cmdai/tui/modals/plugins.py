"""Modal for /plugins: manage .cmdai/plugins and ~/.cmdai/plugins (SessionsModal parity)."""

from __future__ import annotations

from rich.markup import escape
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from ...core.plugins import (
    create_sample_plugin,
    delete_plugin,
    discover_plugins,
    set_plugin_enabled,
)


class _PluginSearchInput(Input):
    """Search input that forwards navigation and Enter to PluginsModal."""

    def _on_key(self, event: events.Key) -> None:
        modal = self.screen
        if not isinstance(modal, PluginsModal):
            return
        if modal.query_one("#plugins-new-row").has_class("visible"):
            return
        if event.key in ("down", "up"):
            ol = modal.query_one("#modal-list", OptionList)
            if event.key == "down":
                ol.action_cursor_down()
            else:
                ol.action_cursor_up()
            event.prevent_default()
            event.stop()
        elif event.key == "enter":
            modal.action_toggle_selected()
            event.prevent_default()
            event.stop()


class PluginsModal(ModalScreen):
    """Modal for browsing, toggling, creating, and deleting plugins with live search."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("enter", "toggle_selected", "Toggle"),
        Binding("space", "toggle_selected", "Toggle", show=False),
        Binding("ctrl+n", "new_plugin", "New sample"),
        Binding("delete", "delete_selected", "Delete"),
        Binding("ctrl+r", "refresh_plugins", "Refresh", show=False),
    ]

    DEFAULT_CSS = """
    #plugins-new-row {
        width: 100%;
        height: auto;
        display: none;
        margin: 0 0 1 0;
    }
    #plugins-new-row.visible {
        display: block;
    }
    """

    def __init__(self, workdir: str = ".", **kwargs):
        super().__init__(**kwargs)
        self.workdir = workdir
        self._all_plugins = []
        self._filtered_plugins = []

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog", classes="sessions-dialog"):
            with Horizontal(id="modal-header"):
                yield Static("Plugins (.cmdai/plugins)", id="modal-title")
                yield Static("[dim]esc[/]", id="modal-esc")

            yield _PluginSearchInput(placeholder="Type to filter plugins...", id="modal-search")

            with Vertical(id="plugins-new-row"):
                yield Input(placeholder="New plugin name (Enter to create, Esc to cancel)...", id="plugins-name-input")

            yield OptionList(id="modal-list")

            with Horizontal(id="modal-footer"):
                yield Static("enter: Toggle  ·  ctrl+n: New sample  ·  delete: Delete  ·  esc: Close", id="plugins-footer-text")

    def on_mount(self) -> None:
        self._reload_plugins()
        self.query_one("#modal-search", _PluginSearchInput).focus()

    def _reload_plugins(self) -> None:
        self._all_plugins = discover_plugins(self.workdir)
        q = self.query_one("#modal-search", _PluginSearchInput).value.strip().lower()
        if not q:
            self._filtered_plugins = list(self._all_plugins)
        else:
            self._filtered_plugins = [
                p for p in self._all_plugins
                if q in str(p.get("name", "")).lower()
                or q in str(p.get("description", "")).lower()
                or q in str(p.get("scope", "")).lower()
            ]
        self._refresh_list()

    def _refresh_list(self) -> None:
        ol = self.query_one("#modal-list", OptionList)
        ol.clear_options()
        if not self._filtered_plugins:
            ol.add_option(Option(Text.from_markup("  [dim]No plugins found — press ctrl+n to create a sample plugin[/]"), disabled=True))
            return
        for p in self._filtered_plugins:
            badge = "[b #3fb950]●  [/]" if p.get("enabled") else "[dim]○  [/]"
            scope_lbl = "proj" if p.get("scope") == "project" else "glob"
            counts = f"cmd:{p['commands_count']} rule:{p['rules_count']} hook:{p['hooks_count']} mcp:{p['mcp_count']}"
            right_plain = f"{counts}  ({scope_lbl})"
            name_disp = str(p.get("name") or p["id"])[:24]
            max_desc = max(0, 86 - 3 - len(name_disp) - 2 - len(right_plain) - 2)
            raw_desc = str(p.get("description") or "").replace("\n", " ").strip()
            if max_desc <= 3:
                desc = ""
                left_plain = name_disp
                desc_markup = ""
            else:
                desc = (raw_desc[: max_desc - 2] + "..") if len(raw_desc) > max_desc else raw_desc
                left_plain = f"{name_disp}  {desc}" if desc else name_disp
                desc_markup = f"[dim]  {escape(desc)}[/]" if desc else ""
            pad = " " * max(2, 86 - 3 - len(left_plain) - len(right_plain))
            line = (
                f"{badge}[bold white]{escape(name_disp)}[/]"
                f"{desc_markup}{pad}"
                f"[#7ee787]{escape(counts)}[/]  [dim]({scope_lbl})[/]"
            )
            t_row = Text.from_markup(line)
            t_row.no_wrap = True
            t_row.overflow = "ellipsis"
            ol.add_option(Option(t_row, id=p["id"]))
        if ol.option_count > 0:
            ol.highlighted = 0

    def _selected_plugin(self):
        ol = self.query_one("#modal-list", OptionList)
        if ol.highlighted is None or not self._filtered_plugins:
            return None
        try:
            opt = ol.get_option_at_index(ol.highlighted)
            pid = getattr(opt, "id", None)
            return next((p for p in self._filtered_plugins if p["id"] == pid), None)
        except Exception:
            return None

    @on(Input.Changed, "#modal-search")
    def _on_search_changed(self) -> None:
        self._reload_plugins()

    def action_dismiss_modal(self) -> None:
        row = self.query_one("#plugins-new-row")
        if row.has_class("visible"):
            row.remove_class("visible")
            self.query_one("#modal-search", _PluginSearchInput).focus()
            return
        self.dismiss(None)

    def action_toggle_selected(self) -> None:
        p = self._selected_plugin()
        if not p:
            return
        new_state = not bool(p.get("enabled"))
        if set_plugin_enabled(p["id"], new_state):
            self._reload_plugins()

    def action_new_plugin(self) -> None:
        row = self.query_one("#plugins-new-row")
        row.add_class("visible")
        self.query_one("#plugins-name-input", Input).focus()

    def action_delete_selected(self) -> None:
        p = self._selected_plugin()
        if not p:
            return
        if delete_plugin(p["path"]):
            self._reload_plugins()

    def action_refresh_plugins(self) -> None:
        self._reload_plugins()

    @on(OptionList.OptionSelected, "#modal-list")
    def _on_option_selected(self) -> None:
        self.action_toggle_selected()

    @on(Input.Submitted, "#plugins-name-input")
    def _on_create_submitted(self, event: Input.Submitted) -> None:
        name = (event.value or "").strip()
        if not name:
            return
        create_sample_plugin(self.workdir, name=name)
        event.input.value = ""
        self.query_one("#plugins-new-row").remove_class("visible")
        self._reload_plugins()
        self.query_one("#modal-search", _PluginSearchInput).focus()
