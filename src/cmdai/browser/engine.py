"""Zero-Playwright Headless Chromium/Edge CDP Engine for CMDAI CODE.

Runs an isolated headless Edge/Chrome instance via Chrome DevTools Protocol (CDP)
over `websockets` — never touches the user's physical mouse, keyboard, or personal
browser profile. Streams live virtual cursor coordinates, Frosted Whisper status,
Tap Burst click events, JPEG frames, and JS console errors to both CLI and Web UI.
"""

from __future__ import annotations

import asyncio
import atexit
import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple


_BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

_SNAPSHOT_JS = r"""
(() => {
  const sel = 'a[href], button, input, textarea, select, [role="button"], [onclick]';
  const els = Array.from(document.querySelectorAll(sel));
  const out = [];
  let idx = 1;
  for (const el of els) {
    const r = el.getBoundingClientRect();
    if (r.width < 4 || r.height < 4) continue;
    const st = window.getComputedStyle(el);
    if (st.visibility === 'hidden' || st.display === 'none' || parseFloat(st.opacity) === 0) continue;
    if (r.bottom < 0 || r.top > window.innerHeight * 2.5) continue;
    const tag = el.tagName.toLowerCase();
    const text = (el.innerText || el.value || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.getAttribute('title') || '').trim().replace(/\s+/g, ' ').slice(0, 72);
    const idAttr = el.id ? ('#' + el.id) : '';
    const typeAttr = el.getAttribute('type') || '';
    out.push({
      index: idx++,
      tag,
      type: typeAttr,
      id: idAttr,
      text,
      x: Math.round(r.left + r.width / 2),
      y: Math.round(r.top + r.height / 2),
      w: Math.round(r.width),
      h: Math.round(r.height),
    });
    if (out.length >= 60) break;
  }
  const iconEl = document.querySelector('link[rel~="icon"], link[rel="shortcut icon"], link[rel="apple-touch-icon"]');
  const favicon = (iconEl && iconEl.href) ? iconEl.href : (location.protocol.startsWith('http') ? (location.origin + '/favicon.ico') : '');
  return {
    url: location.href,
    title: document.title || '',
    favicon,
    elements: out,
  };
})()
"""


def find_chromium_binary() -> Optional[str]:
    for p in _BROWSER_CANDIDATES:
        if os.path.isfile(p):
            return p
    for name in ("msedge", "chrome", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class BrowserEngine:
    """Thread-safe Headless CDP browser controller with live virtual cursor & frame capture."""

    def __init__(self, width: int = 1280, height: int = 800, mobile: bool = False):
        self.width = width
        self.height = height
        self.is_mobile: bool = bool(mobile)
        self.device: str = "mobile" if mobile else "desktop"
        self._proc: Optional[subprocess.Popen] = None
        self._profile_dir: Optional[str] = None
        self._port: int = 0
        self._ws_url: str = ""
        self._ws: Any = None
        self._msg_id: int = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="cmdai-cdp-loop")
        self._thread.start()

        self._lock = threading.Lock()
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []

        self.running: bool = False
        self.take_control: bool = False
        self.stopped_by_user: bool = False
        self.url: str = "about:blank"
        self.title: str = ""
        self.favicon: str = ""
        self.last_session: Optional[Dict[str, Any]] = None
        self.elements: List[Dict[str, Any]] = []
        self.console_logs: List[Dict[str, Any]] = []
        self.latest_frame: bytes = b""
        self.frame_seq: int = 0
        self.cursor: Dict[str, Any] = {
            "x": width // 2,
            "y": height // 2,
            "state": "idle",
            "label": "",
            "click_seq": 0,
        }

        atexit.register(self.close)

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_coro(self, coro: Any, timeout: float = 25.0) -> Any:
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout)

    def add_listener(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            if fn not in self._listeners:
                self._listeners.append(fn)

    def remove_listener(self, fn: Callable[[Dict[str, Any]], None]) -> None:
        with self._lock:
            if fn in self._listeners:
                self._listeners.remove(fn)

    def _emit_state(self, event_type: str = "update") -> None:
        payload = self.get_state()
        payload["event"] = event_type
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(payload)
            except Exception:
                pass

    def get_state(self) -> Dict[str, Any]:
        err_count = sum(1 for c in self.console_logs if c.get("level") in ("error", "exception"))
        return {
            "running": self.running,
            "take_control": self.take_control,
            "url": self.url,
            "title": self.title,
            "favicon": self.favicon,
            "last_session": self.last_session,
            "width": self.width,
            "height": self.height,
            "mobile": self.is_mobile,
            "device": self.device,
            "cursor": dict(self.cursor),
            "frame_seq": self.frame_seq,
            "has_frame": bool(self.latest_frame),
            "console_count": len(self.console_logs),
            "console_errors": err_count,
            "console_logs": self.console_logs[-25:],
        }

    def set_cursor(self, x: Optional[int] = None, y: Optional[int] = None, state: str = "thinking", label: str = "", clicked: bool = False) -> None:
        if x is not None:
            self.cursor["x"] = max(0, min(self.width, int(x)))
        if y is not None:
            self.cursor["y"] = max(0, min(self.height, int(y)))
        self.cursor["state"] = state
        self.cursor["label"] = label
        if clicked:
            self.cursor["click_seq"] = int(self.cursor.get("click_seq", 0)) + 1
        self._emit_state("cursor")

    def set_take_control(self, enabled: bool) -> Dict[str, Any]:
        self.take_control = bool(enabled)
        if self.take_control:
            self.cursor["state"] = "idle"
            self.cursor["label"] = "User control"
        self._emit_state("take_control")
        return self.get_state()

    def ensure_started(self) -> Tuple[bool, str]:
        if self.running and self._ws is not None and self._proc and self._proc.poll() is None:
            return True, ""
        binary = find_chromium_binary()
        if not binary:
            return False, "No Chromium/Edge/Chrome browser found on this system."

        self.close()
        self._port = _pick_free_port()
        self._profile_dir = tempfile.mkdtemp(prefix="cmdai_browser_profile_")
        args = [
            binary,
            "--headless=new",
            f"--remote-debugging-port={self._port}",
            f"--user-data-dir={self._profile_dir}",
            f"--window-size={self.width},{self.height}",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-extensions",
            "--mute-audio",
            "about:blank",
        ]
        creation_flags = 0x08000000 if os.name == "nt" else 0
        try:
            self._proc = subprocess.Popen(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
        except Exception as exc:
            return False, f"Failed to launch headless browser: {exc}"

        ws_url = ""
        deadline = time.time() + 10.0
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self._port}/json/list", timeout=1.0) as resp:
                    tabs = json.loads(resp.read().decode("utf-8"))
                    for t in tabs:
                        if t.get("type") == "page" and t.get("webSocketDebuggerUrl"):
                            ws_url = t["webSocketDebuggerUrl"]
                            break
                if ws_url:
                    break
            except Exception:
                time.sleep(0.18)

        if not ws_url:
            self.close()
            return False, "Timed out waiting for headless browser CDP port."

        self._ws_url = ws_url
        try:
            self._run_coro(self._connect_cdp(ws_url), timeout=10.0)
        except Exception as exc:
            self.close()
            return False, f"CDP WebSocket connection failed: {exc}"

        self.running = True
        self.stopped_by_user = False
        self.console_logs = []
        self._emit_state("started")
        return True, ""

    async def _connect_cdp(self, ws_url: str) -> None:
        import websockets
        self._ws = await websockets.connect(ws_url, max_size=20 * 1024 * 1024)
        self._reader_task = asyncio.create_task(self._cdp_reader())
        await self._send_cdp("Page.enable")
        await self._send_cdp("Runtime.enable")
        await self._send_cdp("Emulation.setDeviceMetricsOverride", {
            "width": self.width,
            "height": self.height,
            "deviceScaleFactor": 2 if self.is_mobile else 1,
            "mobile": self.is_mobile,
        })
        await self._send_cdp("Emulation.setTouchEmulationEnabled", {
            "enabled": self.is_mobile,
            "maxTouchPoints": 5 if self.is_mobile else 1,
        })
        if self.is_mobile:
            await self._send_cdp("Emulation.setUserAgentOverride", {
                "userAgent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                ),
                "platform": "iPhone",
            })

    def set_viewport(
        self,
        device: str = "desktop",
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Switch viewport between desktop (1280x800), mobile (390x844 touch), or tablet (768x1024)."""
        dev = str(device or "desktop").strip().lower()
        if dev in ("mobile", "phone", "iphone", "smartphone"):
            w, h, mob, norm_dev = int(width or 390), int(height or 844), True, "mobile"
        elif dev in ("tablet", "ipad"):
            w, h, mob, norm_dev = int(width or 768), int(height or 1024), True, "tablet"
        else:
            w, h, mob, norm_dev = int(width or 1280), int(height or 800), False, "desktop"

        self.width = max(280, min(2560, w))
        self.height = max(400, min(1600, h))
        self.is_mobile = mob
        self.device = norm_dev
        self.cursor["x"] = min(self.cursor.get("x", self.width // 2), self.width - 10)
        self.cursor["y"] = min(self.cursor.get("y", self.height // 2), self.height - 10)

        if self.running and self._ws is not None:
            async def _apply():
                await self._send_cdp("Emulation.setDeviceMetricsOverride", {
                    "width": self.width,
                    "height": self.height,
                    "deviceScaleFactor": 2 if self.is_mobile else 1,
                    "mobile": self.is_mobile,
                })
                await self._send_cdp("Emulation.setTouchEmulationEnabled", {
                    "enabled": self.is_mobile,
                    "maxTouchPoints": 5 if self.is_mobile else 1,
                })
                if self.is_mobile:
                    await self._send_cdp("Emulation.setUserAgentOverride", {
                        "userAgent": (
                            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
                        ),
                        "platform": "iPhone",
                    })
                else:
                    await self._send_cdp("Emulation.setUserAgentOverride", {"userAgent": ""})
                await asyncio.sleep(0.18)
                await self._capture_frame_async()

            try:
                self._run_coro(_apply(), timeout=10.0)
                self._emit_state("frame")
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        return {"success": True, "device": dev, "width": self.width, "height": self.height, "mobile": self.is_mobile}

    async def _cdp_reader(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                if "id" in msg:
                    fut = self._pending.pop(msg["id"], None)
                    if fut and not fut.done():
                        if "error" in msg:
                            fut.set_exception(RuntimeError(str(msg["error"])))
                        else:
                            fut.set_result(msg.get("result", {}))
                else:
                    method = msg.get("method", "")
                    params = msg.get("params") or {}
                    if method == "Runtime.consoleAPICalled":
                        lvl = str(params.get("type") or "log")
                        args_txt = " ".join(
                            str(a.get("value") if a.get("value") is not None else a.get("description") or "")
                            for a in (params.get("args") or [])
                        ).strip()
                        if args_txt:
                            self.console_logs.append({"level": lvl, "text": args_txt[:400], "ts": time.time()})
                            del self.console_logs[:-80]
                    elif method == "Runtime.exceptionThrown":
                        det = params.get("exceptionDetails") or {}
                        exc_obj = det.get("exception") or {}
                        txt = str(exc_obj.get("description") or det.get("text") or "Uncaught JS exception")
                        self.console_logs.append({"level": "exception", "text": txt[:400], "ts": time.time()})
                        del self.console_logs[:-80]
        except Exception:
            pass

    async def _send_cdp(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if self._ws is None:
            raise RuntimeError("Browser CDP is not connected.")
        self._msg_id += 1
        cid = self._msg_id
        fut = self._loop.create_future()
        self._pending[cid] = fut
        await self._ws.send(json.dumps({"id": cid, "method": method, "params": params or {}}))
        return await asyncio.wait_for(fut, timeout=20.0)

    async def _capture_frame_async(self) -> bytes:
        res = await self._send_cdp("Page.captureScreenshot", {"format": "jpeg", "quality": 74})
        b64 = res.get("data") or ""
        if b64:
            self.latest_frame = base64.b64decode(b64)
            self.frame_seq += 1
        return self.latest_frame

    async def _eval_js_async(self, expression: str) -> Any:
        res = await self._send_cdp("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })
        return (res.get("result") or {}).get("value")

    def open_url(self, url: str) -> Dict[str, Any]:
        ok, err = self.ensure_started()
        if not ok:
            return {"success": False, "error": err}
        target = url.strip()
        if target and not target.startswith(("http://", "https://", "file://", "about:")):
            target = "http://" + target
        self.set_cursor(state="thinking", label=f"Opening {target[:32]}")
        self.console_logs = []

        async def _do():
            await self._send_cdp("Page.navigate", {"url": target})
            await asyncio.sleep(1.0)
            snap = await self._eval_js_async(_SNAPSHOT_JS)
            await self._capture_frame_async()
            return snap

        try:
            snap = self._run_coro(_do(), timeout=22.0) or {}
            self.url = str(snap.get("url") or target)
            self.title = str(snap.get("title") or "")
            self.favicon = str(snap.get("favicon") or "")
            self.elements = list(snap.get("elements") or [])
            self.set_cursor(state="thinking", label="Thinking")
            self._emit_state("frame")
            return {
                "success": True,
                "url": self.url,
                "title": self.title,
                "elements_count": len(self.elements),
                "elements": self.elements[:25],
                "console_errors": [c for c in self.console_logs if c.get("level") in ("error", "exception")][-10:],
            }
        except Exception as exc:
            self.set_cursor(state="idle", label="")
            return {"success": False, "error": str(exc)}

    def snapshot(self) -> Dict[str, Any]:
        ok, err = self.ensure_started()
        if not ok:
            return {"success": False, "error": err}
        self.set_cursor(state="thinking", label="Reading page")

        async def _do():
            snap = await self._eval_js_async(_SNAPSHOT_JS)
            await self._capture_frame_async()
            return snap

        try:
            snap = self._run_coro(_do(), timeout=15.0) or {}
            self.url = str(snap.get("url") or self.url)
            self.title = str(snap.get("title") or "")
            self.elements = list(snap.get("elements") or [])
            self.set_cursor(state="thinking", label="Thinking")
            self._emit_state("frame")
            return {
                "success": True,
                "url": self.url,
                "title": self.title,
                "elements": self.elements[:35],
                "console_errors": [c for c in self.console_logs if c.get("level") in ("error", "exception")][-10:],
            }
        except Exception as exc:
            self.set_cursor(state="idle", label="")
            return {"success": False, "error": str(exc)}

    def _resolve_target_xy(self, index: Optional[int] = None, selector: str = "", x: Optional[int] = None, y: Optional[int] = None) -> Tuple[Optional[int], Optional[int], str]:
        if x is not None and y is not None:
            return int(x), int(y), f"({x}, {y})"
        if index is not None:
            for el in self.elements:
                if int(el.get("index", -1)) == int(index):
                    lbl = el.get("text") or el.get("id") or el.get("tag") or f"#{index}"
                    return int(el["x"]), int(el["y"]), str(lbl)[:28]
        if selector:
            js = f"""
            (() => {{
              const el = document.querySelector({json.dumps(selector)});
              if (!el) return null;
              el.scrollIntoView({{block: 'center', inline: 'center'}});
              const r = el.getBoundingClientRect();
              return {{x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2), label: (el.innerText || el.id || {json.dumps(selector)}).slice(0, 28)}};
            }})()
            """
            res = self._run_coro(self._eval_js_async(js), timeout=8.0)
            if isinstance(res, dict):
                return int(res["x"]), int(res["y"]), str(res.get("label") or selector)[:28]
        return None, None, ""

    def click(self, index: Optional[int] = None, selector: str = "", x: Optional[int] = None, y: Optional[int] = None, from_user: bool = False) -> Dict[str, Any]:
        ok, err = self.ensure_started()
        if not ok:
            return {"success": False, "error": err}
        tx, ty, lbl = self._resolve_target_xy(index=index, selector=selector, x=x, y=y)
        if tx is None or ty is None:
            return {"success": False, "error": "Target element not found. Call browser snapshot first or provide valid index/selector/x,y."}

        if not from_user:
            self.set_cursor(x=tx, y=ty, state="clicking", label=f"Clicking {lbl}" if lbl else "Clicking", clicked=True)
            time.sleep(0.28)

        async def _do():
            await self._send_cdp("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": tx, "y": ty})
            await self._send_cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": tx, "y": ty, "button": "left", "clickCount": 1})
            await self._send_cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": tx, "y": ty, "button": "left", "clickCount": 1})
            await asyncio.sleep(0.45)
            snap = await self._eval_js_async(_SNAPSHOT_JS)
            await self._capture_frame_async()
            return snap

        try:
            snap = self._run_coro(_do(), timeout=15.0) or {}
            self.url = str(snap.get("url") or self.url)
            self.title = str(snap.get("title") or self.title)
            self.elements = list(snap.get("elements") or [])
            if not from_user:
                self.set_cursor(x=tx, y=ty, state="thinking", label="Thinking")
            self._emit_state("frame")
            return {
                "success": True,
                "clicked": {"x": tx, "y": ty, "label": lbl},
                "url": self.url,
                "title": self.title,
                "console_errors": [c for c in self.console_logs if c.get("level") in ("error", "exception")][-10:],
            }
        except Exception as exc:
            self.set_cursor(state="idle", label="")
            return {"success": False, "error": str(exc)}

    def type_text(self, text: str, index: Optional[int] = None, selector: str = "", submit: bool = False, from_user: bool = False) -> Dict[str, Any]:
        ok, err = self.ensure_started()
        if not ok:
            return {"success": False, "error": err}
        tx, ty, lbl = self._resolve_target_xy(index=index, selector=selector)
        if not from_user:
            self.set_cursor(x=tx, y=ty, state="typing", label="Typing", clicked=(tx is not None))
            if tx is not None:
                time.sleep(0.22)

        async def _do():
            if tx is not None and ty is not None:
                await self._send_cdp("Input.dispatchMouseEvent", {"type": "mousePressed", "x": tx, "y": ty, "button": "left", "clickCount": 1})
                await self._send_cdp("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": tx, "y": ty, "button": "left", "clickCount": 1})
                await asyncio.sleep(0.1)
            await self._send_cdp("Input.insertText", {"text": text})
            if submit:
                await self._send_cdp("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
                await self._send_cdp("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13})
            await asyncio.sleep(0.35)
            snap = await self._eval_js_async(_SNAPSHOT_JS)
            await self._capture_frame_async()
            return snap

        try:
            snap = self._run_coro(_do(), timeout=15.0) or {}
            self.url = str(snap.get("url") or self.url)
            self.elements = list(snap.get("elements") or [])
            if not from_user:
                self.set_cursor(state="thinking", label="Thinking")
            self._emit_state("frame")
            return {
                "success": True,
                "typed": text[:80],
                "url": self.url,
                "console_errors": [c for c in self.console_logs if c.get("level") in ("error", "exception")][-10:],
            }
        except Exception as exc:
            self.set_cursor(state="idle", label="")
            return {"success": False, "error": str(exc)}

    def scroll(self, direction: str = "down", amount: int = 480) -> Dict[str, Any]:
        ok, err = self.ensure_started()
        if not ok:
            return {"success": False, "error": err}
        dy = abs(int(amount or 480))
        if str(direction).lower() == "up":
            dy = -dy
        self.set_cursor(state="thinking", label=f"Scrolling {direction}")

        async def _do():
            await self._send_cdp("Input.dispatchMouseEvent", {
                "type": "mouseWheel",
                "x": self.width // 2,
                "y": self.height // 2,
                "deltaX": 0,
                "deltaY": dy,
            })
            await asyncio.sleep(0.3)
            snap = await self._eval_js_async(_SNAPSHOT_JS)
            await self._capture_frame_async()
            return snap

        try:
            snap = self._run_coro(_do(), timeout=12.0) or {}
            self.elements = list(snap.get("elements") or [])
            self.set_cursor(state="thinking", label="Thinking")
            self._emit_state("frame")
            return {"success": True, "direction": direction, "amount": abs(dy)}
        except Exception as exc:
            self.set_cursor(state="idle", label="")
            return {"success": False, "error": str(exc)}

    def screenshot(self, save_dir: str = "") -> Dict[str, Any]:
        ok, err = self.ensure_started()
        if not ok:
            return {"success": False, "error": err}
        try:
            frame = self._run_coro(self._capture_frame_async(), timeout=12.0)
            out_dir = save_dir or os.path.join(tempfile.gettempdir(), "cmdai_browser_shots")
            os.makedirs(out_dir, exist_ok=True)
            path = os.path.join(out_dir, f"browser_{int(time.time() * 1000)}.jpg")
            with open(path, "wb") as f:
                f.write(frame)
            self._emit_state("frame")
            return {"success": True, "path": path, "bytes": len(frame), "url": self.url}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def get_console(self) -> Dict[str, Any]:
        return {
            "success": True,
            "url": self.url,
            "logs": self.console_logs[-40:],
            "error_count": sum(1 for c in self.console_logs if c.get("level") in ("error", "exception")),
        }

    def go_back(self) -> Dict[str, Any]:
        ok, err = self.ensure_started()
        if not ok:
            return {"success": False, "error": err}
        self.set_cursor(state="thinking", label="Going back")

        async def _do():
            hist = await self._send_cdp("Page.getNavigationHistory")
            idx = int(hist.get("currentIndex", 0))
            entries = hist.get("entries") or []
            if idx > 0 and idx - 1 < len(entries):
                entry_id = entries[idx - 1]["id"]
                await self._send_cdp("Page.navigateToHistoryEntry", {"entryId": entry_id})
                await asyncio.sleep(0.75)
            snap = await self._eval_js_async(_SNAPSHOT_JS)
            await self._capture_frame_async()
            return snap

        try:
            snap = self._run_coro(_do(), timeout=12.0) or {}
            self.url = str(snap.get("url") or self.url)
            self.title = str(snap.get("title") or "")
            self.elements = list(snap.get("elements") or [])
            self.set_cursor(state="thinking", label="Thinking")
            self._emit_state("frame")
            return {"success": True, "url": self.url, "title": self.title}
        except Exception as exc:
            self.set_cursor(state="thinking", label="Thinking")
            return {"success": False, "error": str(exc)}

    def wait_seconds(self, seconds: float = 1.5) -> Dict[str, Any]:
        ok, err = self.ensure_started()
        if not ok:
            return {"success": False, "error": err}
        secs = max(0.2, min(8.0, float(seconds or 1.5)))
        self.set_cursor(state="thinking", label=f"Waiting {secs:.1f}s")
        time.sleep(secs)
        try:
            snap = self._run_coro(self._eval_js_async(_SNAPSHOT_JS), timeout=10.0) or {}
            self._run_coro(self._capture_frame_async(), timeout=10.0)
            self.url = str(snap.get("url") or self.url)
            self.title = str(snap.get("title") or self.title)
            self.elements = list(snap.get("elements") or [])
            self.set_cursor(state="thinking", label="Thinking")
            self._emit_state("frame")
            return {"success": True, "waited": secs, "url": self.url}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def close(self) -> Dict[str, Any]:
        self.running = False
        self.take_control = False
        self.stopped_by_user = True
        try:
            if self._ws is not None:
                self._run_coro(self._ws.close(), timeout=2.0)
        except Exception:
            pass
        self._ws = None
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
        if self._profile_dir and os.path.isdir(self._profile_dir):
            shutil.rmtree(self._profile_dir, ignore_errors=True)
            self._profile_dir = None
        self.latest_frame = b""
        self.elements = []
        self._emit_state("closed")
        return {"success": True, "closed": True}


_ENGINE_SINGLETON: Optional[BrowserEngine] = None
_ENGINE_LOCK = threading.Lock()


def get_browser_engine() -> BrowserEngine:
    global _ENGINE_SINGLETON
    with _ENGINE_LOCK:
        if _ENGINE_SINGLETON is None:
            _ENGINE_SINGLETON = BrowserEngine()
        return _ENGINE_SINGLETON
