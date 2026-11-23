"""Autonomous Isolated Shots Subagent for multi-capture & interactive screenshots.

Runs in its own isolated headless BrowserEngine (never touches `get_browser_engine()`),
can click controls, navigate links, switch desktop/mobile/tablet viewports, and capture
multiple crisp 2x Retina PNG screenshots into ONE clickable `● Shots` tree card.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from .agent import _build_vision_user_msg, _extract_json_obj, _resolve_browser_model
from .engine import get_browser_engine


_SHOTS_SUBAGENT_SYS = (
    "You are an autonomous Screenshot Subagent operating an isolated headless browser.\n"
    "On each step you receive the task, current URL, interactive elements `[1]..[N]`, "
    "captures collected so far, and the current page screenshot.\n"
    "Respond ONLY with ONE raw JSON object (no markdown fences, no extra prose):\n"
    '{"thought": "2-5 word status", '
    '"action": "capture|click|type|open|scroll|back|set_viewport|shots_done", '
    '"label": "short capture caption (required for capture)", '
    '"selector": "", "full_page": false, '
    '"index": 3, "text": "", "submit": false, "url": "", '
    '"direction": "down", "device": "desktop|mobile|tablet", '
    '"summary": "short summary of captured screenshots (required for shots_done)"}\n'
    "Rules:\n"
    "- Use `capture` with a crisp short `label` whenever you reach a requested page, modal, tab state, or viewport.\n"
    "- Keep `full_page=false` by default for crisp readable viewport shots; ONLY set `full_page=true` if the user explicitly asks for the entire scrollable page.\n"
    "- Use `click` / `open` / `type` / `set_viewport` between captures to reach each requested state or subpage.\n"
    "- Never capture duplicate unchanged views.\n"
    "- Call `shots_done` with `summary` once all requested screenshots have been captured."
)


def run_shots_agent(
    task: str,
    url: str,
    display_target: str = "",
    workdir: str = ".",
    device: str = "desktop",
    max_steps: int = 16,
    max_captures: int = 10,
    on_step: Optional[Callable[[str], None]] = None,
    on_capture: Optional[Callable[[Dict[str, Any]], None]] = None,
    is_aborted: Optional[Callable[[], bool]] = None,
    model_call_override: Optional[Callable[[List[Dict[str, Any]]], str]] = None,
) -> Dict[str, Any]:
    """Run an isolated autonomous subagent that navigates/clicks and collects multiple PNG captures."""
    from ..agent.tools import (
        _SUBPAGE_LINKS_JS,
        _apply_crisp_viewport,
        _capture_from_engine,
        _resolve_browser_url,
        _screenshot_dir,
        _viewport_spec,
    )
    from ..core.capabilities import get_model_capability
    from ..core.providers import stream_chat_completion
    from ..core.settings import get_settings

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

    if url and not str(url).lower().startswith(("http://", "https://", "file://")):
        url = _resolve_browser_url(url, workdir)
    if not url or not str(url).lower().startswith(("http://", "https://", "file://")):
        return {"success": False, "error": f"Provide a valid URL or workspace HTML file (got '{url}')."}

    eng = get_browser_engine()
    eng.last_session = None
    eng.viewer_mode = "shots"
    eng.set_viewport(device=device or "desktop")
    t0 = time.monotonic()
    captures: List[Dict[str, Any]] = []
    steps_log: List[str] = []
    recent_actions: List[Dict[str, str]] = []
    final_summary = ""
    last_sig: Optional[Tuple[Any, ...]] = None
    repeat_count = 0
    stall_nudge = ""

    def _check_abort() -> bool:
        if eng.stopped_by_user or not eng.running:
            return True
        if is_aborted and is_aborted():
            return True
        return False

    try:
        if on_step:
            on_step(f"{display_target or url} · opening")
        r_open = eng.open_url(url)
        if not r_open.get("success"):
            return {"success": False, "error": r_open.get("error") or f"Failed to open {url}"}
        initial_title = (eng.title or "").strip()
        initial_favicon = (eng.favicon or "").strip()
        _apply_crisp_viewport(eng, eng.width, eng.height, eng.is_mobile)
        time.sleep(0.35)
        steps_log.append(f"Opened {eng.url}")

        step_idx = 0
        while step_idx < max_steps and len(captures) < max_captures and not _check_abort():
            step_idx += 1
            eng.set_cursor(state="thinking", label="Thinking")
            els_lines = [
                f"  [{e['index']}] <{e['tag']}{e.get('id', '')}> {e.get('text', '')}"
                for e in (eng.elements or [])[:35]
            ]
            nav_lines: List[str] = []
            try:
                sub_links = eng._run_coro(eng._eval_js_async(_SUBPAGE_LINKS_JS), timeout=6.0) or []
                for lnk in list(sub_links)[:15]:
                    if isinstance(lnk, dict) and lnk.get("url"):
                        nav_lines.append(f"  - {lnk.get('label', 'link')} -> {lnk['url']}")
            except Exception:
                pass
            cap_labels = ", ".join(c["label"] for c in captures) or "none"
            obs_text = (
                f"Task: {task}\n"
                f"Step {step_idx}/{max_steps} | Viewport: {eng.device} ({eng.width}x{eng.height})\n"
                f"Current URL: {eng.url} | Title: {eng.title}\n"
                f"Captures collected ({len(captures)}/{max_captures}): {cap_labels}\n"
                + ("Navigation links:\n" + "\n".join(nav_lines) + "\n" if nav_lines else "")
                + f"Interactive elements:\n" + ("\n".join(els_lines) or "  (none)") + "\n"
                + (f"\nWARNING: {stall_nudge}\n" if stall_nudge else "")
                + "Return ONE JSON action (`capture`, `click`, `type`, `open`, `scroll`, `back`, `set_viewport`, or `shots_done`)."
            )
            stall_nudge = ""

            call_msgs: List[Dict[str, Any]] = (
                [{"role": "system", "content": _SHOTS_SUBAGENT_SYS}]
                + recent_actions[-6:]
                + [_build_vision_user_msg(obs_text, eng.latest_frame, allow_vision)]
            )

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
                    is_aborted=_check_abort,
                )

            if _check_abort():
                break

            act_obj = _extract_json_obj(resp_txt or "")
            if not act_obj:
                break

            thought = str(act_obj.get("thought") or "").strip()[:34]
            action = str(act_obj.get("action") or "shots_done").strip().lower()
            if thought:
                eng.set_cursor(state="thinking", label=thought)

            if action in ("shots_done", "done", "stop", "finish"):
                final_summary = str(act_obj.get("summary") or thought or "Screenshots captured.").strip()
                break

            sig = (
                action,
                act_obj.get("index"),
                act_obj.get("selector"),
                act_obj.get("url"),
                act_obj.get("device"),
                eng.url,
                len(captures),
            )
            if sig == last_sig:
                repeat_count += 1
            else:
                last_sig = sig
                repeat_count = 1
            if repeat_count >= 3:
                stall_nudge = "Action repeated 3 times without progress. Pick another action or call `shots_done`."
                repeat_count = 0
                continue

            if action == "capture":
                raw_lbl = str(act_obj.get("label") or thought or eng.title or f"View {len(captures) + 1}").strip()
                cap_lbl = raw_lbl[:60]
                sel_val = str(act_obj.get("selector") or "").strip()
                full_val = bool(act_obj.get("full_page", False))
                out_p = os.path.join(_screenshot_dir(), f"{uuid.uuid4().hex}.png")
                cap_res = _capture_from_engine(eng, out_p, selector=sel_val, full_page=full_val)
                if cap_res.get("success"):
                    cap_entry = {
                        "label": cap_lbl,
                        "path": cap_res["path"],
                        "target": display_target or eng.url,
                        "device": eng.device,
                        "width": cap_res.get("width", 0),
                        "height": cap_res.get("height", 0),
                        "size_bytes": cap_res.get("size_bytes", 0),
                        "selector": cap_res.get("selector", ""),
                        "full_page": cap_res.get("full_page", False),
                    }
                    captures.append(cap_entry)
                    eng.emit_capture_flash(cap_lbl)
                    if on_capture:
                        try:
                            on_capture(cap_entry)
                        except Exception:
                            pass
                    steps_log.append(f"Captured '{cap_lbl}'")
                    if on_step:
                        on_step(f"captured: {cap_lbl}")
            elif action == "open":
                next_url = str(act_obj.get("url") or "").strip()
                if next_url:
                    full_next = urllib.parse.urljoin(eng.url, next_url) if not next_url.lower().startswith(("http://", "https://")) else next_url
                    eng.open_url(full_next)
                    _apply_crisp_viewport(eng, eng.width, eng.height, eng.is_mobile)
                    time.sleep(0.35)
                    steps_log.append(f"Opened {full_next}")
                    if on_step:
                        on_step(f"open: {full_next}")
            elif action == "click":
                idx_val = act_obj.get("index")
                sel_val = str(act_obj.get("selector") or "").strip()
                r_c = eng.click(
                    index=int(idx_val) if idx_val not in (None, "") else None,
                    selector=sel_val,
                )
                if (not r_c.get("success")) and sel_val and idx_val in (None, ""):
                    txt_clk_js = f"""
                    (() => {{
                      const q = {json.dumps(sel_val.lower())};
                      const isVis = (n) => {{
                        if (!n || (n.offsetParent === null && getComputedStyle(n).position !== 'fixed')) return false;
                        const r = n.getBoundingClientRect();
                        return r.width > 4 && r.height > 4;
                      }};
                      const cands = Array.from(document.querySelectorAll(
                        "button, a, [role='tab'], [role='button'], summary, label, input[type='submit'], input[type='button'], [onclick], li"
                      )).filter(isVis);
                      const txtOf = (n) => ((n.innerText || n.textContent || n.getAttribute('aria-label') || n.getAttribute('title') || n.value || '').trim().replace(/\\s+/g, ' ').toLowerCase());
                      const el = cands.find(n => txtOf(n) === q) || cands.find(n => txtOf(n).includes(q));
                      if (!el) return false;
                      try {{ el.scrollIntoView({{block: 'center', inline: 'center'}}); }} catch (e) {{}}
                      el.click();
                      return true;
                    }})()
                    """
                    try:
                        if eng._run_coro(eng._eval_js_async(txt_clk_js), timeout=6.0):
                            time.sleep(0.25)
                            eng.snapshot()
                    except Exception:
                        pass
                time.sleep(0.25)
                steps_log.append(f"Clicked {sel_val or f'#{idx_val}'}")
                if on_step:
                    on_step(thought or f"click {sel_val or f'#{idx_val}'}")
            elif action == "type":
                idx_val = act_obj.get("index")
                sel_val = str(act_obj.get("selector") or "")
                txt_val = str(act_obj.get("text") or "")
                eng.type_text(
                    text=txt_val,
                    index=int(idx_val) if idx_val not in (None, "") else None,
                    selector=sel_val,
                    submit=bool(act_obj.get("submit", False)),
                )
                steps_log.append(f"Typed '{txt_val[:20]}'")
            elif action == "scroll":
                direction = str(act_obj.get("direction") or "down")
                eng.scroll(direction=direction)
                steps_log.append(f"Scrolled {direction}")
            elif action == "back":
                eng.go_back()
                steps_log.append("Back")
            elif action in ("set_viewport", "viewport", "device"):
                dev_val = str(act_obj.get("device") or "mobile").strip().lower()
                eng.set_viewport(device=dev_val)
                _apply_crisp_viewport(eng, eng.width, eng.height, eng.is_mobile)
                time.sleep(0.25)
                steps_log.append(f"Viewport {eng.device}")
                if on_step:
                    on_step(f"viewport: {eng.device}")

            recent_actions.append({"role": "assistant", "content": json.dumps(act_obj, ensure_ascii=False)})

        # Guarantee at least 1 crisp capture if agent exited early without calling `capture`
        if not captures:
            out_p = os.path.join(_screenshot_dir(), f"{uuid.uuid4().hex}.png")
            fb = _capture_from_engine(eng, out_p)
            if fb.get("success"):
                fb_lbl = (eng.title or display_target or "Home").strip()[:60]
                fb_entry = {
                    "label": fb_lbl,
                    "path": fb["path"],
                    "target": display_target or eng.url,
                    "device": eng.device,
                    "width": fb.get("width", 0),
                    "height": fb.get("height", 0),
                    "size_bytes": fb.get("size_bytes", 0),
                    "selector": "",
                    "full_page": False,
                }
                captures.append(fb_entry)
                eng.emit_capture_flash(fb_lbl)
                if on_capture:
                    try:
                        on_capture(fb_entry)
                    except Exception:
                        pass

        if not captures:
            return {"success": False, "error": "Shots subagent failed to capture any screenshots."}

        elapsed_sec = round(time.monotonic() - t0, 1)
        summary_txt = final_summary or f"Captured {len(captures)} screenshots."
        eng.last_session = {
            "mode": "shots",
            "model": model_id or provider,
            "url": display_target or url,
            "title": initial_title or display_target or url,
            "favicon": initial_favicon or eng.favicon,
            "elapsed": elapsed_sec,
            "count": len(captures),
            "steps_count": len(steps_log),
            "summary": summary_txt,
            "captures": [
                {
                    "label": c.get("label", ""),
                    "path": c.get("path", ""),
                    "device": c.get("device", ""),
                    "width": c.get("width", 0),
                    "height": c.get("height", 0),
                    "size_bytes": c.get("size_bytes", 0),
                }
                for c in captures
            ],
        }

        return {
            "success": True,
            "path": captures[0]["path"],
            "size_bytes": sum(int(c.get("size_bytes", 0) or 0) for c in captures),
            "width": captures[0].get("width", 0),
            "height": captures[0].get("height", 0),
            "target": display_target or url,
            "captures": captures,
            "count": len(captures),
            "steps_count": len(steps_log),
            "elapsed": elapsed_sec,
            "summary": summary_txt,
            "source": "shots_agent",
        }
    except Exception as exc:
        return {"success": False, "error": f"shots agent failed: {exc}"}
    finally:
        eng.viewer_mode = "browser"
        if eng.running and not eng.take_control:
            eng.close()
