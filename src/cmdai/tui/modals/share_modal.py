"""TUI modals for `/share` (Session Picker with remembered selection) and `cloudflared` auto-install.

Styled with the native CMDAI CODE `#modal-dialog` / `#modal-header` / `#modal-list` / `#modal-footer`
layout so they match UpdateNoticeModal, SessionsModal, and SettingsModal seamlessly.
"""

from typing import Any, Dict, List, Optional

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from ...core.sessions import format_relative_time
from ...core.settings import get_settings
from ...core.tunnel import find_cloudflared, install_cloudflared


class CloudflaredInstallModal(ModalScreen[bool]):
    """Native CMDAI CODE confirmation modal to download `cloudflared.exe` into `bin/`."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    CloudflaredInstallModal #cf-desc {
        color: #8b949e;
        padding: 0 1 1 1;
        height: auto;
    }
    CloudflaredInstallModal #cf-status {
        color: #58a6ff;
        padding: 0 1 1 1;
        height: auto;
    }
    CloudflaredInstallModal #modal-list {
        height: auto;
        max-height: 6;
    }
    """

    def __init__(self, feature_name: str = "/tunnel"):
        super().__init__()
        self.feature_name = feature_name
        self._installing = False

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            with Horizontal(id="modal-header"):
                yield Static(
                    f"Install Cloudflare Tunnel for {self.feature_name}",
                    id="modal-title",
                )
                yield Static("[dim]esc[/]", id="modal-esc")
            yield Static(
                "Cloudflare Quick Tunnel creates a free temporary HTTPS link with a QR code\n"
                "(no account or API key required). Official cloudflared.exe (~35 MB) will be\n"
                "saved into bin/cloudflared.exe.",
                id="cf-desc",
            )
            yield Static("[dim]Ready to install.[/dim]", id="cf-status")
            yield OptionList(id="modal-list")
            with Horizontal(id="modal-footer"):
                yield Static(
                    "[b #58a6ff]Confirm[/] enter / click   [dim]esc cancel[/dim]",
                    id="modal-footer-left",
                )
                yield Static("", id="modal-footer-right")

    def on_mount(self) -> None:
        ol = self.query_one("#modal-list", OptionList)
        ol.clear_options()

        opt_install = Text(no_wrap=True, overflow="ellipsis")
        opt_install.append("● ", style="#3fb950")
        opt_install.append("Install cloudflared.exe & Continue", style="bold #e6edf3")
        opt_install.append("  · GitHub Releases", style="#6e7681")
        ol.add_option(Option(opt_install, id="install"))

        opt_cancel = Text(no_wrap=True, overflow="ellipsis")
        opt_cancel.append("○ ", style="#6e7681")
        opt_cancel.append("Cancel", style="#8b949e")
        ol.add_option(Option(opt_cancel, id="cancel"))

        ol.highlighted = 0
        ol.focus()

    def action_cursor_up(self) -> None:
        if not self._installing:
            self.query_one("#modal-list", OptionList).action_cursor_up()

    def action_cursor_down(self) -> None:
        if not self._installing:
            self.query_one("#modal-list", OptionList).action_cursor_down()

    def action_cancel(self) -> None:
        if not self._installing:
            self.dismiss(False)

    @on(OptionList.OptionSelected, "#modal-list")
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if self._installing:
            return
        opt_id = event.option.id
        if opt_id == "install":
            self._installing = True
            self.query_one("#modal-list", OptionList).disabled = True
            self._set_status("Starting download...")
            self._run_download()
        else:
            self.dismiss(False)

    @work(thread=True)
    def _run_download(self) -> None:
        def _status(msg: str) -> None:
            self.app.call_from_thread(self._set_status, msg)

        ok, detail = install_cloudflared(on_status=_status)
        if ok:
            self.app.call_from_thread(self.dismiss, True)
        else:
            self.app.call_from_thread(self._on_fail, detail)

    def _set_status(self, msg: str) -> None:
        self.query_one("#cf-status", Static).update(f"[#58a6ff]{msg}[/]")

    def _on_fail(self, err: str) -> None:
        self._installing = False
        self.query_one("#modal-list", OptionList).disabled = False
        self.query_one("#cf-status", Static).update(f"[#f85149]{err}[/]")


class ShareSessionModal(ModalScreen[Optional[Dict[str, Any]]]):
    """Native CMDAI CODE session picker for `/share` that remembers the last selected session."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ShareSessionModal #share-sub {
        color: #8b949e;
        padding: 0 1 1 1;
        height: auto;
    }
    """

    def __init__(self, sessions: List[Dict[str, Any]], current_session_id: str):
        super().__init__()
        self.sessions = sessions
        self.current_session_id = current_session_id
        self.settings = get_settings()
        self.last_shared_id = str(
            (self.settings.config.get("share") or {}).get("last_session_id") or ""
        )

    def compose(self) -> ComposeResult:
        cf_ready = bool(find_cloudflared())
        footer_note = (
            "opens Share terminal with QR code · close window to stop"
            if cf_ready
            else "will prompt to install cloudflared.exe first"
        )
        with Vertical(id="modal-dialog"):
            with Horizontal(id="modal-header"):
                yield Static("Share Session", id="modal-title")
                yield Static("[dim]esc[/]", id="modal-esc")
            yield Static(
                "Pick a session to publish (read-only HTML · API keys redacted · remembers last choice)",
                id="share-sub",
            )
            yield OptionList(id="modal-list")
            with Horizontal(id="modal-footer"):
                yield Static(
                    f"[b #58a6ff]Share[/] enter / click   [dim]{footer_note}[/dim]",
                    id="modal-footer-left",
                )
                yield Static("", id="modal-footer-right")

    def on_mount(self) -> None:
        ol = self.query_one("#modal-list", OptionList)
        ol.clear_options()
        highlight_idx = 0

        for idx, sess in enumerate(self.sessions):
            sid = str(sess.get("id") or "")
            title = str(sess.get("title") or sid or "Session")
            is_cur = bool(sess.get("is_current"))
            is_last = bool(self.last_shared_id and sid == self.last_shared_id)
            if is_last:
                highlight_idx = idx

            rel = sess.get("updated_rel") or format_relative_time(sess.get("updated_at"))
            turn_count = sess.get("turn_count")
            tool_count = sess.get("tool_count")
            msgs = int(sess.get("msg_count") or 0)
            if turn_count is not None:
                t_lbl = "1 msg" if turn_count == 1 else f"{turn_count} msgs"
                count_str = f"{t_lbl} · {tool_count} tools" if tool_count else t_lbl
            else:
                count_str = f"{msgs} msgs"
            label = Text(no_wrap=True, overflow="ellipsis")
            if is_cur:
                label.append("● ", style="#3fb950")
                label.append(f"{title} ", style="bold #e6edf3")
                label.append("[Current]", style="#58a6ff")
            else:
                label.append("○ ", style="#8b949e")
                label.append(f"{title} ", style="#c9d1d9")
            if is_last:
                label.append("  ★ Last", style="#e3b341")
            dir_name = str(sess.get("dir_name") or "").strip()
            if dir_name and not sess.get("is_current_dir", True):
                label.append(f"  [{dir_name}]", style="#58a6ff")
            meta = f"  · {count_str}" + (f" · {rel}" if rel else "")
            label.append(meta, style="#6e7681")
            ol.add_option(Option(label, id=sid))

        if self.sessions:
            ol.highlighted = highlight_idx
        ol.focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(OptionList.OptionSelected, "#modal-list")
    def _on_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not self.sessions:
            self.dismiss(None)
            return
        chosen: Optional[Dict[str, Any]] = None
        opt_id = str(event.option.id or "") if event.option is not None else ""
        if opt_id:
            for sess in self.sessions:
                if str(sess.get("id") or "") == opt_id:
                    chosen = sess
                    break
        if chosen is None and event.option_index is not None:
            idx = int(event.option_index)
            if 0 <= idx < len(self.sessions):
                chosen = self.sessions[idx]
        if chosen is not None:
            share_cfg = self.settings.config.setdefault("share", {})
            share_cfg["last_session_id"] = str(chosen.get("id") or "")
            try:
                self.settings.save_config()
            except Exception:
                pass
            self.dismiss(chosen)
