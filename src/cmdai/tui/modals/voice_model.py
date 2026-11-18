import threading
from typing import Dict, List, Optional

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from ...core.settings import get_settings
from ...core.voice import (
    VOICE_MODEL_CATALOG,
    install_local_whisper_model,
    is_local_whisper_installed,
)

VOICE_LANGUAGES = [
    "auto", "pl", "en", "de", "uk", "fr", "es", "it",
    "cs", "sk", "pt", "nl", "sv", "no", "da", "fi",
    "tr", "ja", "ko", "zh",
]


class VoiceLanguageModal(ModalScreen[Optional[str]]):
    """Prompt for entering any ISO language code (or 'auto') for voice dictation."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("enter", "save", "Save"),
    ]

    def __init__(self, current_lang: str = "auto", **kwargs):
        super().__init__(**kwargs)
        self.current_lang = current_lang

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            with Horizontal(id="modal-header"):
                yield Static("Voice Language Code", id="modal-title")
                yield Static("[dim]esc[/]", id="modal-esc")
            yield Static(
                "[dim]Enter 'auto' or any Whisper ISO code (e.g. pl, en, de, uk, fr, es, it, cs, ja, zh):[/dim]\n"
            )
            yield Input(value=self.current_lang, placeholder="auto", id="voice-lang-input")
            with Horizontal(id="modal-footer"):
                yield Static("[b #58a6ff]Save[/] enter   [dim]Cancel[/] esc")

    def on_mount(self) -> None:
        self.query_one("#voice-lang-input", Input).focus()

    @on(Input.Submitted, "#voice-lang-input")
    def on_submitted(self, event: Input.Submitted) -> None:
        self.action_save()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_save(self) -> None:
        val = self.query_one("#voice-lang-input", Input).value.strip().lower()
        self.dismiss(val or "auto")


class VoiceModelModal(ModalScreen[Optional[Dict[str, str]]]):
    """Modal for selecting and installing local or API speech-to-text models (/voicemodel)."""

    BINDINGS = [
        Binding("escape", "cancel", "Close"),
        Binding("enter", "select_item", "Select"),
        Binding("ctrl+d", "configure_key", "Set API Key"),
        Binding("ctrl+l", "cycle_language", "Language"),
    ]

    DEFAULT_CSS = """
    VoiceModelModal #voice-install-status {
        color: #8b949e;
        height: auto;
        margin: 0 0 1 0;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings = get_settings()
        self._row_entries: List[Dict[str, str]] = []
        self._installing = False

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-dialog"):
            with Horizontal(id="modal-header"):
                yield Static("Voice Model (Speech-to-Text)", id="modal-title")
                yield Static("[dim]esc[/]", id="modal-esc")

            yield Static(
                "[dim]Select an installed model or press Enter on any local model to download it.[/dim]",
                id="voice-install-status",
                markup=True,
            )
            yield OptionList(id="modal-list")

            with Horizontal(id="modal-footer"):
                yield Static("enter: Select / Install  ·  ctrl+l: Cycle Lang  ·  ctrl+d: API Key  ·  esc: Close")
                yield Static("", id="modal-footer-right")

    def on_mount(self) -> None:
        self.rebuild()
        self.query_one("#modal-list", OptionList).focus()

    def _voice_cfg(self) -> Dict[str, str]:
        cfg = self.settings.config.setdefault("voice", {})
        if not isinstance(cfg, dict):
            cfg = {}
            self.settings.config["voice"] = cfg
        return cfg

    def rebuild(self) -> None:
        ol = self.query_one("#modal-list", OptionList)
        prev = ol.highlighted
        ol.clear_options()
        self._row_entries = []

        vcfg = self._voice_cfg()
        cur_prov = str(vcfg.get("provider", "local") or "local").lower()
        cur_mod = str(vcfg.get("model", "small") or "small")
        cur_lang = str(vcfg.get("language", "auto") or "auto")

        lang_row = Text()
        lang_row.append("  Language: ", style="dim")
        lang_row.append(cur_lang, style="bold #58a6ff")
        lang_row.append("  (ctrl+l: cycle · enter: type any ISO code)", style="dim")
        ol.add_option(Option(lang_row, id="voice_lang"))
        self._row_entries.append({"kind": "language"})

        for item in VOICE_MODEL_CATALOG:
            prov = item["provider"]
            mid = item["id"]
            name = item["name"]
            note = item["note"]
            is_active = (prov == cur_prov and mid == cur_mod)

            row = Text()
            row.append("* " if is_active else "  ", style="bold #58a6ff" if is_active else "")
            row.append(name, style="bold white" if is_active else "white")
            row.append(f"  [{note}]", style="dim")

            if prov == "local":
                if is_local_whisper_installed(mid):
                    row.append("  installed", style="#3fb950")
                else:
                    row.append("  not installed", style="#d29922")
            else:
                has_key = bool(self.settings.get_api_key(prov))
                if has_key:
                    row.append("  ready", style="#3fb950")
                else:
                    row.append("  no key", style="#d29922")

            ol.add_option(Option(row, id=f"voice_{prov}_{mid}"))
            self._row_entries.append({"kind": "model", "provider": prov, "model": mid})

        if prev is not None and 0 <= prev < len(self._row_entries):
            ol.highlighted = prev
        else:
            ol.highlighted = 1 if len(self._row_entries) > 1 else 0

    def action_cancel(self) -> None:
        if self._installing:
            self.app.notify("Please wait for the voice model download to finish.", title="Voice", timeout=2.5)
            return
        self.dismiss(None)

    def action_cycle_language(self) -> None:
        if self._installing:
            return
        vcfg = self._voice_cfg()
        cur = str(vcfg.get("language", "auto") or "auto").lower()
        nxt = VOICE_LANGUAGES[(VOICE_LANGUAGES.index(cur) + 1) % len(VOICE_LANGUAGES)] if cur in VOICE_LANGUAGES else "auto"
        vcfg["language"] = nxt
        self.settings.save_config()
        self.rebuild()

    def _edit_language(self) -> None:
        vcfg = self._voice_cfg()
        cur = str(vcfg.get("language", "auto") or "auto").lower()

        def _on_saved(val: Optional[str]) -> None:
            if val:
                vcfg["language"] = val
                self.settings.save_config()
                self.rebuild()

        self.app.push_screen(VoiceLanguageModal(cur), _on_saved)

    def action_configure_key(self) -> None:
        if self._installing:
            return
        ol = self.query_one("#modal-list", OptionList)
        idx = ol.highlighted
        if idx is None or not (0 <= idx < len(self._row_entries)):
            return
        entry = self._row_entries[idx]
        prov = entry.get("provider", "")
        if not prov or prov == "local":
            self.app.notify("Local Whisper does not require an API key.", title="Voice", timeout=2.5)
            return

        from .api_key import ApiKeyModal

        def _on_saved(saved: Optional[bool]) -> None:
            if saved:
                self.rebuild()

        self.app.push_screen(ApiKeyModal(prov), _on_saved)

    def _install_and_select_local(self, mid: str) -> None:
        self._installing = True
        self.query_one("#voice-install-status", Static).update(
            f"[b #58a6ff]Downloading[/] local Whisper [b white]{mid}[/] into models/whisper/..."
        )

        def _worker() -> None:
            err = ""
            try:
                install_local_whisper_model(mid)
            except Exception as exc:
                err = str(exc)
            self.app.call_from_thread(self._finish_local_install, mid, err)

        threading.Thread(target=_worker, daemon=True).start()

    def _finish_local_install(self, mid: str, err: str) -> None:
        self._installing = False
        if err:
            self.query_one("#voice-install-status", Static).update(f"[#f85149]Install failed: {err}[/]")
            self.app.notify(err, title="Voice Install Failed", severity="error", timeout=5.0)
            return

        vcfg = self._voice_cfg()
        vcfg["provider"] = "local"
        vcfg["model"] = mid
        self.settings.save_config()
        self.rebuild()
        self.query_one("#voice-install-status", Static).update(
            f"[b #3fb950]Installed[/] Whisper [b white]{mid}[/]."
        )
        self.dismiss({"provider": "local", "model": mid, "language": str(vcfg.get("language", "auto"))})

    def action_select_item(self) -> None:
        if self._installing:
            return
        ol = self.query_one("#modal-list", OptionList)
        idx = ol.highlighted
        if idx is None or not (0 <= idx < len(self._row_entries)):
            return
        entry = self._row_entries[idx]
        if entry.get("kind") == "language":
            self._edit_language()
            return

        prov = entry["provider"]
        mid = entry["model"]
        if prov == "local":
            if not is_local_whisper_installed(mid):
                self._install_and_select_local(mid)
                return
        elif not self.settings.get_api_key(prov):
            self.action_configure_key()
            return

        vcfg = self._voice_cfg()
        vcfg["provider"] = prov
        vcfg["model"] = mid
        self.settings.save_config()
        self.dismiss({"provider": prov, "model": mid, "language": str(vcfg.get("language", "auto"))})

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.action_select_item()
