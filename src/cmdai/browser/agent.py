"""Autonomous Isolated Browser Subagent for CMDAI CODE (1:1 Antigravity pattern).

Runs in a completely separate, clean context from the lead agent inside ONE single
`Browser` tool block:
- Unbounded step loop (no artificial 8-step cap) — exits cleanly when the subagent
  explicitly calls `action: "browser_stop"` (or `"done"`).
- Rolling Vision Context: sends ONLY the 1 latest screenshot + compact text step log
  so 30–50+ steps never overflow VRAM or the main conversation context.
- Stall Guard: detects 3 identical consecutive actions with no DOM/URL change and nudges
  (then exits cleanly on repeated stalls) so an unbounded loop can never hang forever.
- Instant User Abort: clicking `Stop` in the browser viewer or aborting the turn stops
  the loop immediately and returns all findings collected so far.
"""

from __future__ import annotations

import base64
import json
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .engine import get_browser_engine


_PHASE_KEYWORDS = [
    (("console", "error", "bug", "exception", "warning", "fail"), "Checking console"),
    (("model", "models"), "Checking Models"),
    (("log", "logs", "history", "request"), "Checking logs"),
    (("setting", "config", "theme", "dark", "light"), "Checking settings"),
    (("layout", "design", "ui", "style", "visual", "look", "wygl"), "Inspecting UI"),
    (("button", "click", "link", "tab", "menu", "nav"), "Finding element"),
    (("type", "input", "form", "search", "field"), "Preparing input"),
    (("scroll", "bottom", "below", "down"), "Scanning page"),
    (("done", "finish", "summary", "complete", "koniec", "podsum"), "Wrapping up"),
]


def _infer_phase_label(chunk_tail: str) -> str:
    low = (chunk_tail or "").lower()
    for keys, lbl in _PHASE_KEYWORDS:
        if any(k in low for k in keys):
            return lbl
    return "Thinking"


def _clean_whisper_label(raw: str) -> str:
    return (raw or "").strip().rstrip(".… ").strip()[:34]


_BROWSER_SUBAGENT_SYS = (
    "You are an isolated autonomous Browser Subagent operating a headless browser.\n"
    "On each step you receive the current URL, interactive elements `[1]..[N]`, "
    "console errors, your previous step log, and the current page screenshot.\n"
    "Respond ONLY with ONE raw JSON object (no markdown fences, no extra prose):\n"
    '{"thought": "short 2-5 word status for cursor pill", '
    '"action": "click|type|scroll|open|back|wait|browser_stop", '
    '"index": 3, "selector": "", "text": "", "submit": false, "url": "", '
    '"direction": "down", "seconds": 1.5, '
    '"summary": "complete final report (required when action is browser_stop)"}\n'
    "Rules:\n"
    "- Keep `thought` ultra-short (max 34 chars, e.g. 'Opening Models tab', 'Checking API Logs').\n"
    "- You have NO step limit: thoroughly test every requested tab, button, and feature.\n"
    "- When you have finished everything requested (or verified all views), call "
    '`"action": "browser_stop"` with a detailed `"summary"` in the same language as the task.\n'
    "- Never repeat the exact same click if the page did not change."
)


def _extract_json_obj(raw: str) -> Optional[Dict[str, Any]]:
    txt = (raw or "").strip()
    if not txt:
        return None
    txt = re.sub(r"^```(?:json)?\s*", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\s*```$", "", txt)
    try:
        obj = json.loads(txt, strict=False)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", txt)
    if m:
        try:
            obj = json.loads(m.group(0), strict=False)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None


def _build_vision_user_msg(text_body: str, jpeg_bytes: bytes, allow_vision: bool) -> Dict[str, Any]:
    if allow_vision and jpeg_bytes:
        b64 = base64.b64encode(jpeg_bytes).decode("ascii")
        return {
            "role": "user",
            "content": [
                {"type": "text", "text": text_body},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }
    return {"role": "user", "content": text_body}


def _resolve_browser_model(settings: Any) -> Tuple[str, str, str]:
    cfg = settings.config or {}
    default_prov = str(cfg.get("default_provider") or "openrouter")
    default_mod = str(cfg.get("default_model") or "")
    sub_raw = str(cfg.get("subagent_model") or "").strip()
    if sub_raw:
        if ":" in sub_raw:
            p, m = sub_raw.split(":", 1)
            if p.strip() and m.strip():
                return p.strip(), m.strip(), (settings.get_api_key(p.strip()) or "")
        return default_prov, sub_raw, (settings.get_api_key(default_prov) or "")
    return default_prov, default_mod, (settings.get_api_key(default_prov) or "")


def run_browser_agent(
    task: str,
    url: str = "",
    workdir: str = ".",
    device: str = "desktop",
    on_step: Optional[Callable[[str], None]] = None,
    is_aborted: Optional[Callable[[], bool]] = None,
    model_call_override: Optional[Callable[[List[Dict[str, Any]]], str]] = None,
) -> Dict[str, Any]:
    """Run an unbounded isolated Browser Subagent inside a single tool call until `browser_stop`."""
    from ..core.capabilities import get_model_capability
    from ..core.providers import stream_chat_completion
    from ..core.settings import get_settings

    eng = get_browser_engine()
    settings = get_settings()
    cfg = settings.config or {}
    provider, model_id, api_key = _resolve_browser_model(settings)
    gen_params = dict(cfg.get("generation") or {})
    gen_params["max_tokens"] = min(int(gen_params.get("max_tokens") or 1024), 1024)

    allow_vision = False
    try:
        cap = get_model_capability(model_id, provider, api_key=api_key, timeout=0.6)
        allow_vision = bool(cap.vision) and provider != "local_gguf"
    except Exception:
        allow_vision = provider != "local_gguf"

    t0 = time.monotonic()
    eng.last_session = None
    steps_log: List[str] = []
    eng.set_viewport(device=device or "desktop")
    if url:
        if on_step:
            on_step(f"{url} · opening")
        r_open = eng.open_url(url)
        if not r_open.get("success"):
            return {"success": False, "error": r_open.get("error") or "Failed to open URL"}
        steps_log.append(f"Opened {eng.url} ({eng.title})")
    elif not eng.running:
        return {"success": False, "error": "Provide a `url` to open in the browser."}

    # Isolated rolling text history (never holds old screenshots -> constant low token usage!)
    recent_actions: List[Dict[str, str]] = []
    final_summary = ""
    step_idx = 0
    last_sig: Optional[Tuple[Any, ...]] = None
    repeat_count = 0
    stall_warnings = 0
    stall_nudge = ""

    def _check_abort() -> bool:
        if eng.stopped_by_user or not eng.running:
            return True
        if is_aborted and is_aborted():
            return True
        return False

    try:
        while not _check_abort():
            step_idx += 1
            els_lines = [
                f"  [{e['index']}] <{e['tag']}{e.get('id', '')}> {e.get('text', '')}"
                for e in (eng.elements or [])[:35]
            ]
            errs = [c for c in eng.console_logs if c.get("level") in ("error", "exception")][-6:]
            err_txt = "\n".join(f"  - [{c['level']}] {c['text']}" for c in errs) if errs else "  (none)"
            obs_text = (
                f"Task: {task}\n"
                f"Step #{step_idx} (unbounded — call `browser_stop` when finished)\n"
                f"Current URL: {eng.url} | Title: {eng.title}\n"
                f"Completed steps ({len(steps_log)}): {'; '.join(steps_log[-10:]) or 'none'}\n"
                f"Interactive elements:\n" + ("\n".join(els_lines) or "  (none)") + "\n"
                f"Console errors:\n{err_txt}\n"
                + (f"\nWARNING: {stall_nudge}\n" if stall_nudge else "")
                + "Return ONE JSON action (`click`, `type`, `scroll`, `open`, `back`, `wait`, or `browser_stop`)."
            )
            stall_nudge = ""

            eng.set_cursor(state="thinking", label="Thinking")
            # Rolling Vision Context: system prompt + last 6 compact JSON actions + ONLY 1 current screenshot
            call_msgs: List[Dict[str, Any]] = (
                [{"role": "system", "content": _BROWSER_SUBAGENT_SYS}]
                + recent_actions[-6:]
                + [_build_vision_user_msg(obs_text, eng.latest_frame, allow_vision)]
            )

            # Calm phase-label updater (min 1.2s dwell time so 100-200 tok/s models never flicker)
            _th_buf: List[str] = []
            _last_lbl = ["Thinking"]
            _last_lbl_ts = [time.monotonic()]

            def _on_sub_thinking(chunk: str) -> None:
                if not chunk:
                    return
                _th_buf.append(chunk)
                now_m = time.monotonic()
                if now_m - _last_lbl_ts[0] < 1.2:
                    return
                tail = "".join(_th_buf)[-140:]
                nxt = _infer_phase_label(tail)
                if nxt != _last_lbl[0]:
                    _last_lbl[0] = nxt
                    _last_lbl_ts[0] = now_m
                    eng.set_cursor(state="thinking", label=nxt)

            if model_call_override is not None:
                resp_txt = model_call_override(call_msgs)
            elif provider == "local_gguf":
                from ..core.engine import SimpleGGUFLoader
                loader = SimpleGGUFLoader()
                ok_l, err_l = loader.ensure_loaded(model_id)
                if not ok_l:
                    return {"success": False, "error": err_l or "Local model failed to load"}
                resp_txt = "".join(loader.stream_chat(call_msgs, max_tokens=768))
            else:
                resp_txt, _ = stream_chat_completion(
                    provider_id=provider,
                    model_id=model_id,
                    messages=call_msgs,
                    api_key=api_key,
                    generation_params=gen_params,
                    on_thinking=_on_sub_thinking,
                    is_aborted=_check_abort,
                )

            if _check_abort():
                final_summary = "Browser session stopped by user. Steps completed: " + ("; ".join(steps_log) or "none")
                break

            act_obj = _extract_json_obj(resp_txt or "")
            if not act_obj:
                final_summary = (resp_txt or "").strip() or "Browser inspection finished."
                break

            thought = _clean_whisper_label(str(act_obj.get("thought") or ""))
            action = str(act_obj.get("action") or "browser_stop").strip().lower()
            if thought:
                eng.set_cursor(state="thinking", label=thought)

            if action in ("browser_stop", "stop", "done", "finish"):
                final_summary = str(act_obj.get("summary") or thought or "Browser task completed.").strip()
                break

            # Stall Guard: detect identical repeated action with unchanged page state
            sig = (action, act_obj.get("index"), act_obj.get("selector"), act_obj.get("url"), eng.url, len(eng.elements))
            if sig == last_sig:
                repeat_count += 1
            else:
                last_sig = sig
                repeat_count = 1

            if repeat_count >= 3:
                stall_warnings += 1
                if stall_warnings >= 2:
                    final_summary = (
                        f"Stopped automatically after repeated no-op action on {eng.url}. "
                        f"Completed {len(steps_log)} steps: " + "; ".join(steps_log)
                    )
                    break
                stall_nudge = "That exact action repeated 3 times with no page change. Try a different element or call `browser_stop` with your summary."
                repeat_count = 0
                continue

            if action == "open":
                next_url = str(act_obj.get("url") or "").strip()
                if next_url:
                    if on_step:
                        on_step(f"step {step_idx}: open {next_url}")
                    eng.open_url(next_url)
                    steps_log.append(f"Opened {next_url}")
            elif action == "click":
                idx_val = act_obj.get("index")
                sel_val = str(act_obj.get("selector") or "")
                lbl_step = thought or (f"click #{idx_val}" if idx_val else f"click {sel_val}")
                if on_step:
                    on_step(f"step {step_idx}: {lbl_step}")
                r_c = eng.click(
                    index=int(idx_val) if idx_val not in (None, "") else None,
                    selector=sel_val,
                )
                clicked_lbl = (r_c.get("clicked") or {}).get("label") or lbl_step
                steps_log.append(f"Clicked {clicked_lbl}" if r_c.get("success") else f"Click failed: {r_c.get('error')}")
            elif action == "type":
                idx_val = act_obj.get("index")
                sel_val = str(act_obj.get("selector") or "")
                txt_val = str(act_obj.get("text") or "")
                if on_step:
                    on_step(f"step {step_idx}: {thought or 'typing…'}")
                r_t = eng.type_text(
                    text=txt_val,
                    index=int(idx_val) if idx_val not in (None, "") else None,
                    selector=sel_val,
                    submit=bool(act_obj.get("submit", False)),
                )
                steps_log.append(f"Typed '{txt_val[:24]}'" if r_t.get("success") else f"Type failed: {r_t.get('error')}")
            elif action == "scroll":
                direction = str(act_obj.get("direction") or "down")
                if on_step:
                    on_step(f"step {step_idx}: {thought or f'scroll {direction}'}")
                eng.scroll(direction=direction)
                steps_log.append(f"Scrolled {direction}")
            elif action == "back":
                if on_step:
                    on_step(f"step {step_idx}: back")
                eng.go_back()
                steps_log.append(f"Back to {eng.url}")
            elif action == "wait":
                secs = float(act_obj.get("seconds") or 1.5)
                if on_step:
                    on_step(f"step {step_idx}: waiting {secs:.1f}s")
                eng.wait_seconds(secs)
                steps_log.append(f"Waited {secs:.1f}s")
            elif action in ("set_viewport", "viewport", "device"):
                dev_val = str(act_obj.get("device") or "mobile").strip().lower()
                if on_step:
                    on_step(f"step {step_idx}: viewport {dev_val}")
                eng.set_viewport(device=dev_val)
                steps_log.append(f"Switched viewport to {dev_val} ({eng.width}x{eng.height})")
            else:
                final_summary = str(act_obj.get("summary") or "Browser inspection finished.")
                break

            recent_actions.append({"role": "assistant", "content": json.dumps(act_obj, ensure_ascii=False)})

        if not final_summary:
            final_summary = f"Completed {len(steps_log)} browser steps on {eng.url}: " + "; ".join(steps_log)

        console_errs = [c for c in eng.console_logs if c.get("level") in ("error", "exception")]
        elapsed_sec = round(time.monotonic() - t0, 1)
        eng.last_session = {
            "model": model_id or provider,
            "url": eng.url,
            "title": eng.title,
            "favicon": eng.favicon,
            "elapsed": elapsed_sec,
            "steps": list(steps_log),
            "steps_count": len(steps_log),
            "console_errors": len(console_errs),
            "summary": final_summary,
        }
        return {
            "success": True,
            "url": eng.url,
            "title": eng.title,
            "steps": steps_log,
            "steps_count": len(steps_log),
            "elapsed": elapsed_sec,
            "console_errors": console_errs[-10:],
            "summary": final_summary,
        }
    finally:
        if eng.running and not eng.take_control:
            eng.close()
