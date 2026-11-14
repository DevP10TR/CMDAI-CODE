"""`/mode`: pick an agent execution mode, styled like `/thinking` and `/models`."""

from __future__ import annotations

from typing import Optional

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option


_MODES = [
    ("auto", "#7ee787", "Full autonomy — runs tools and commands without asking"),
    ("code", "#d29922", "Auto-edits files, asks confirmation for terminal commands"),
    ("plan", "#58a6ff", "Read-only planning — inspects codebase without editing"),
]


class ModeSelectModal(ModalScreen[Optional[str]]):
    """Choose an agent execution mode. Returns canonical mode name or None."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close"),
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("enter", "select", "Select", show=False),
    ]

    DEFAULT_CSS = """
    ModeSelectModal {
        align: center middle;
        background: rgba(0, 0, 0, 0.72);
    }
    #mode-list {
        width: 100%;
        height: auto;
        max-height: 12;
        background: #0d1117;
        border: none;
        padding: 0;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, current_mode: str = "code") -> None:
        super().__init__()
        self.current_mode = (current_mode or "code").lower()

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            with Horizontal(id="modal-header"):
                yield Static("Agent Mode", id="modal-title")
                yield Static("[dim]Esc[/]", id="modal-esc")
            ol = OptionList(id="mode-list")
            for mode_id, color, desc in _MODES:
                active = mode_id == self.current_mode
                t = Text()
                t.append("● " if active else "  ", style=f"bold {color}" if active else "#484f58")
                t.append(f"{mode_id:<8}", style=f"bold {color}" if active else "#e6edf3")
                t.append(desc, style="#8b949e")
                ol.add_option(Option(t, id=mode_id))
            yield ol
            with Horizontal(id="modal-footer"):
                yield Static("[dim]Enter select  •  Shift+Tab cycle[/dim]", id="modal-footer-left")
                yield Static("[dim]Esc close[/dim]", id="modal-footer-right")

    def on_mount(self) -> None:
        ol = self.query_one("#mode-list", OptionList)
        for idx, (mode_id, _, _) in enumerate(_MODES):
            if mode_id == self.current_mode:
                ol.highlighted = idx
                break
        else:
            ol.highlighted = 0
        ol.focus()

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def action_cursor_up(self) -> None:
        self.query_one("#mode-list", OptionList).action_cursor_up()

    def action_cursor_down(self) -> None:
        self.query_one("#mode-list", OptionList).action_cursor_down()

    def action_select(self) -> None:
        ol = self.query_one("#mode-list", OptionList)
        if ol.highlighted is not None:
            opt = ol.get_option_at_index(ol.highlighted)
            if opt and opt.id:
                self.dismiss(str(opt.id))
                return
        self.dismiss(None)

    @on(OptionList.OptionSelected, "#mode-list")
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option and event.option.id:
            self.dismiss(str(event.option.id))

    def on_click(self, event) -> None:
        if getattr(getattr(event, "widget", None), "id", "") == "modal-esc":
            self.dismiss(None)
