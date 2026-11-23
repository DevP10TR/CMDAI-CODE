"""Standalone Web Screenshot Viewer HTTP server for CMDAI CODE CLI & TUI.

Styled 1:1 like `CMDAI CODE · Live Browser` (`cmdai.browser.viewer`):
- Authentic CMDAI CODE block-letter SVG logo in top-left
- Clear Light default + Obsidian Dark toggle (persisted in localStorage)
- Rounded `.app-shell` canvas with full-resolution crisp screenshot stage
- Click-to-zoom (Fit / 100%), Copy Path, Download, and resolution/size metadata
- Single persistent daemon HTTP server on a random free local port serving
  multiple screenshots across the entire CLI session.
"""

from __future__ import annotations

import atexit
import hashlib
import html
import http.server
import mimetypes
import os
import socketserver
import threading
import webbrowser
from typing import Any, Dict, List, Optional


_VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>CMDAI CODE · Screenshot</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2318181b'/%3E%3Cpath d='M7 9h7v3H10v8h4v3H7V9zm11 0h7v3h-4v8h4v3h-7V9z' fill='%23ffffff'/%3E%3C/svg%3E" />
<style>
  :root, [data-theme="light"] {
    --bg-app: #f4f5f7;
    --bg-topbar: #f4f5f7;
    --bg-stage: #ffffff;
    --bg-card: #ffffff;
    --bg-subtle: #eff1f5;
    --bg-hover: rgba(15, 23, 42, 0.05);
    --border-hairline: #e4e7ec;
    --border-strong: #cfd5e1;
    --text-primary: #111827;
    --text-secondary: #4b5563;
    --text-muted: #6b7280;
    --accent-blue: #2563eb;
    --accent-blue-soft: #eff6ff;
    --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
    --shadow-stage: 0 12px 34px rgba(15, 23, 42, 0.10);
    --checker-a: #f8fafc;
    --checker-b: #f1f5f9;
    --font-sans: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
    --font-mono: "JetBrains Mono", "Cascadia Mono", Consolas, monospace;
    color-scheme: light;
  }
  [data-theme="dark"] {
    --bg-app: #09090b;
    --bg-topbar: #0e0e12;
    --bg-stage: #111115;
    --bg-card: #17171c;
    --bg-subtle: #1f1f27;
    --bg-hover: rgba(255, 255, 255, 0.06);
    --border-hairline: #23232b;
    --border-strong: #32323e;
    --text-primary: #f4f4f5;
    --text-secondary: #a1a1aa;
    --text-muted: #71717a;
    --accent-blue: #3b82f6;
    --accent-blue-soft: rgba(59, 130, 246, 0.14);
    --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.35);
    --shadow-stage: 0 16px 46px rgba(0, 0, 0, 0.50);
    --checker-a: #121217;
    --checker-b: #16161d;
    color-scheme: dark;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    height: 100%;
    background: var(--bg-app);
    color: var(--text-primary);
    font-family: var(--font-sans);
    font-size: 13.5px;
    -webkit-font-smoothing: antialiased;
  }
  body { display: flex; flex-direction: column; overflow: hidden; padding: 8px; }
  .app-shell {
    flex: 1; min-height: 0; display: flex; flex-direction: column;
    background: var(--bg-stage); border: 1px solid var(--border-hairline);
    border-radius: 12px; overflow: hidden; box-shadow: var(--shadow-xs);
  }
  .topbar {
    height: 46px; padding: 0 14px; background: var(--bg-topbar);
    border-bottom: 1px solid var(--border-hairline);
    display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-shrink: 0;
  }
  .top-left { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
  .cc-vector-badge { width: 112px; height: 19px; display: inline-flex; align-items: center; flex-shrink: 0; }
  .cc-vector-badge svg { width: 100%; height: 100%; display: block; shape-rendering: geometricPrecision; }
  .top-center {
    flex: 1; min-width: 0; display: flex; align-items: center; justify-content: center; gap: 8px;
  }
  .meta-pill {
    display: inline-flex; align-items: center; gap: 8px; max-width: 100%;
    height: 30px; padding: 0 12px; border-radius: 999px;
    background: var(--bg-card); border: 1px solid var(--border-hairline);
    box-shadow: var(--shadow-xs); min-width: 0;
  }
  .tag {
    font-family: var(--font-mono); font-size: 10.5px; font-weight: 600;
    letter-spacing: 0.04em; padding: 2px 7px; border-radius: 999px;
    background: var(--accent-blue-soft); color: var(--accent-blue); flex-shrink: 0;
  }
  .title-text {
    font-size: 12.2px; font-weight: 500; color: var(--text-primary);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .dim-text {
    font-family: var(--font-mono); font-size: 11.2px; color: var(--text-muted); flex-shrink: 0;
  }
  .top-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .top-btn {
    height: 30px; padding: 0 11px; border-radius: 8px;
    border: 1px solid var(--border-hairline); background: var(--bg-card);
    color: var(--text-primary); font-family: var(--font-sans);
    font-size: 12px; font-weight: 500; cursor: pointer; text-decoration: none;
    display: inline-flex; align-items: center; gap: 5px; box-shadow: var(--shadow-xs);
    transition: border-color 0.14s ease, background 0.14s ease;
  }
  .top-btn:hover { border-color: var(--accent-blue); background: var(--bg-hover); }
  .top-btn.active { border-color: var(--accent-blue); color: var(--accent-blue); background: var(--accent-blue-soft); }
  .gallery-nav { display: inline-flex; align-items: center; gap: 4px; margin-right: 4px; }
  .gallery-nav.hidden { display: none; }
  .nav-count {
    font-family: var(--font-mono); font-size: 11.5px; color: var(--text-secondary);
    padding: 0 5px; user-select: none;
  }

  .main {
    flex: 1; min-height: 0; overflow: auto;
    display: flex; align-items: center; justify-content: center;
    padding: 20px;
    background-image:
      linear-gradient(45deg, var(--checker-b) 25%, transparent 25%),
      linear-gradient(-45deg, var(--checker-b) 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, var(--checker-b) 75%),
      linear-gradient(-45deg, transparent 75%, var(--checker-b) 75%);
    background-size: 20px 20px;
    background-position: 0 0, 0 10px, 10px -10px, -10px 0;
    background-color: var(--checker-a);
  }
  .main.zoomed { align-items: flex-start; justify-content: flex-start; }
  .shot-frame {
    display: inline-flex; border-radius: 10px; overflow: hidden;
    border: 1px solid var(--border-hairline); box-shadow: var(--shadow-stage);
    background: var(--bg-card);
  }
  .shot-frame img {
    display: block; max-width: calc(100vw - 64px); max-height: calc(100vh - 134px);
    width: auto; height: auto; cursor: zoom-in; user-select: none;
  }
  .main.zoomed .shot-frame img {
    max-width: none; max-height: none; cursor: zoom-out;
  }

  .footer {
    height: 32px; padding: 0 14px; background: var(--bg-topbar);
    border-top: 1px solid var(--border-hairline);
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    font-size: 11.5px; color: var(--text-muted); flex-shrink: 0;
  }
  .footer-path {
    font-family: var(--font-mono); font-size: 11px; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap;
  }
</style>
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div class="top-left">
        <span id="brand-logo" class="cc-vector-badge" aria-label="CMDAI CODE"></span>
      </div>
      <div class="top-center">
        <div class="meta-pill">
          <span class="tag">SCREENSHOT</span>
          <span class="title-text" title="__TITLE__">__TITLE__</span>
          <span id="dims" class="dim-text">__SIZE_KB__</span>
        </div>
      </div>
      <div class="top-right">
        <div id="gnav" class="gallery-nav __NAV_CLASS__">
          <a id="prev-btn" class="top-btn" href="__PREV_URL__" title="Previous capture (Left arrow)">←</a>
          <span class="nav-count">__NAV_LABEL__</span>
          <a id="next-btn" class="top-btn" href="__NEXT_URL__" title="Next capture (Right arrow)">→</a>
        </div>
        <button id="zoom" class="top-btn" type="button" title="Toggle Fit / 100% Zoom">100%</button>
        <button id="copy-path" class="top-btn" type="button" title="Copy local file path">Copy Path</button>
        <a class="top-btn" href="__IMG_URL__" download="__DOWNLOAD_NAME__">Download</a>
        <button id="theme" class="top-btn" type="button">Dark</button>
      </div>
    </header>
    <main id="stage" class="main">
      <div class="shot-frame">
        <img id="img" src="__IMG_URL__" alt="Screenshot" draggable="false" />
      </div>
    </main>
    <footer class="footer">
      <span class="footer-path" title="__FULL_PATH__">__FULL_PATH__</span>
      <span>Click image to toggle 100% zoom</span>
    </footer>
  </div>
<script>
  const NS_SVG = "http://www.w3.org/2000/svg";
  const CMDAI_PARTS = [
    " ██████╗███╗   ███╗██████╗  █████╗ ██╗",
    "██╔════╝████╗ ████║██╔══██╗██╔══██╗██║",
    "██║     ██╔████╔██║██║  ██║███████║██║",
    "██║     ██║╚██╔╝██║██║  ██║██╔══██║██║",
    "╚██████╗██║ ╚═╝ ██║██████╔╝██║  ██║██║",
    " ╚═════╝╚═╝     ╚═╝╚═════╝ ╚═╝  ╚═╝╚═╝",
  ];
  const CODE_PARTS = [
    " ██████╗ ██████╗ ██████╗ ███████╗",
    "██╔════╝██╔═══██╗██╔══██╗██╔════╝",
    "██║     ██║   ██║██║  ██║█████╗  ",
    "██║     ██║   ██║██║  ██║██╔══╝  ",
    "╚██████╗╚██████╔╝██████╔╝███████╗",
    " ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝",
  ];
  function buildPaths(lines, colOffset, cw, ch) {
    let d = ""; const sw = Math.max(1.5, cw * 0.15);
    for (let r = 0; r < lines.length; r++) {
      for (let c = 0; c < lines[r].length; c++) {
        const ch0 = lines[r][c]; if (ch0 === " ") continue;
        const x = (colOffset + c) * cw, y = r * ch;
        const xA = x + cw * 0.28, xB = x + cw * 0.64, yA = y + ch * 0.30, yB = y + ch * 0.64;
        if (ch0 === "█") d += `M${(x-0.25).toFixed(2)},${(y-0.3).toFixed(2)}h${(cw+0.5).toFixed(2)}v${(ch+0.6).toFixed(2)}h-${(cw+0.5).toFixed(2)}z`;
        else if (ch0 === "═") { d += `M${(x-0.2).toFixed(2)},${yA.toFixed(2)}h${(cw+0.4).toFixed(2)}v${sw.toFixed(2)}h-${(cw+0.4).toFixed(2)}z`; d += `M${(x-0.2).toFixed(2)},${yB.toFixed(2)}h${(cw+0.4).toFixed(2)}v${sw.toFixed(2)}h-${(cw+0.4).toFixed(2)}z`; }
        else if (ch0 === "║") { d += `M${xA.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}v${(ch+0.4).toFixed(2)}h-${sw.toFixed(2)}z`; d += `M${xB.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}v${(ch+0.4).toFixed(2)}h-${sw.toFixed(2)}z`; }
        else if (ch0 === "╔") { d += `M${xA.toFixed(2)},${yA.toFixed(2)}H${(x+cw+0.2).toFixed(2)}v${sw.toFixed(2)}H${(xA+sw).toFixed(2)}V${(y+ch+0.2).toFixed(2)}H${xA.toFixed(2)}z`; d += `M${xB.toFixed(2)},${yB.toFixed(2)}H${(x+cw+0.2).toFixed(2)}v${sw.toFixed(2)}H${(xB+sw).toFixed(2)}V${(y+ch+0.2).toFixed(2)}H${xB.toFixed(2)}z`; }
        else if (ch0 === "╗") { d += `M${(x-0.2).toFixed(2)},${yA.toFixed(2)}H${(xB+sw).toFixed(2)}V${(y+ch+0.2).toFixed(2)}h-${sw.toFixed(2)}V${(yA+sw).toFixed(2)}H${(x-0.2).toFixed(2)}z`; d += `M${(x-0.2).toFixed(2)},${yB.toFixed(2)}H${(xA+sw).toFixed(2)}V${(y+ch+0.2).toFixed(2)}h-${sw.toFixed(2)}V${(yB+sw).toFixed(2)}H${(x-0.2).toFixed(2)}z`; }
        else if (ch0 === "╚") { d += `M${xA.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}V${yB.toFixed(2)}H${(x+cw+0.2).toFixed(2)}v${sw.toFixed(2)}H${xA.toFixed(2)}z`; d += `M${xB.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}V${yA.toFixed(2)}H${(x+cw+0.2).toFixed(2)}v${sw.toFixed(2)}H${xB.toFixed(2)}z`; }
        else if (ch0 === "╝") { d += `M${xB.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}V${(yB+sw).toFixed(2)}H${(x-0.2).toFixed(2)}v-${sw.toFixed(2)}H${xB.toFixed(2)}z`; d += `M${xA.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}V${(yA+sw).toFixed(2)}H${(x-0.2).toFixed(2)}v-${sw.toFixed(2)}H${xA.toFixed(2)}z`; }
      }
    }
    return d;
  }
  (function renderLogo() {
    const host = document.getElementById('brand-logo'); if (!host) return;
    const cw = 10, ch = 23, gap = 3, w = (CMDAI_PARTS[0].length + gap + CODE_PARTS[0].length) * cw, h = CMDAI_PARTS.length * ch;
    const svg = document.createElementNS(NS_SVG, 'svg'); svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    const gL = document.createElementNS(NS_SVG, 'g'); gL.setAttribute('class', 'w-cmdai');
    const pL = document.createElementNS(NS_SVG, 'path'); pL.setAttribute('d', buildPaths(CMDAI_PARTS, 0, cw, ch)); gL.appendChild(pL);
    const gR = document.createElementNS(NS_SVG, 'g'); gR.setAttribute('class', 'w-code');
    const pR = document.createElementNS(NS_SVG, 'path'); pR.setAttribute('d', buildPaths(CODE_PARTS, CMDAI_PARTS[0].length + gap, cw, ch)); gR.appendChild(pR);
    svg.appendChild(gL); svg.appendChild(gR); host.appendChild(svg);
  })();

  const themeBtn = document.getElementById('theme');
  function applyTheme(t) {
    document.documentElement.setAttribute('data-theme', t);
    themeBtn.textContent = t === 'dark' ? 'Light' : 'Dark';
    const wL = document.querySelector('#brand-logo .w-cmdai'), wR = document.querySelector('#brand-logo .w-code');
    if (wL) wL.setAttribute('fill', t === 'dark' ? '#f4f4f5' : '#18181b');
    if (wR) wR.setAttribute('fill', t === 'dark' ? '#a1a1aa' : '#71717a');
  }
  applyTheme(localStorage.getItem('cmdai_browser_theme') || 'light');
  themeBtn.onclick = () => {
    const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    localStorage.setItem('cmdai_browser_theme', next);
    applyTheme(next);
  };

  const stage = document.getElementById('stage');
  const img = document.getElementById('img');
  const zoomBtn = document.getElementById('zoom');
  const dimsEl = document.getElementById('dims');
  const sizeKb = "__SIZE_KB__";

  function updateDims() {
    if (img.naturalWidth && img.naturalHeight) {
      dimsEl.textContent = `${img.naturalWidth}×${img.naturalHeight}` + (sizeKb ? ` · ${sizeKb}` : '');
    }
  }
  if (img.complete) updateDims();
  img.addEventListener('load', updateDims);

  function toggleZoom() {
    const z = stage.classList.toggle('zoomed');
    zoomBtn.textContent = z ? 'Fit' : '100%';
    zoomBtn.classList.toggle('active', z);
  }
  img.addEventListener('click', toggleZoom);
  zoomBtn.addEventListener('click', toggleZoom);

  const copyBtn = document.getElementById('copy-path');
  const rawPath = __RAW_PATH_JSON__;
  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(rawPath);
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy Path'; }, 1400);
    } catch (_) {
      copyBtn.textContent = 'Copy failed';
      setTimeout(() => { copyBtn.textContent = 'Copy Path'; }, 1400);
    }
  });

  const prevUrl = __PREV_URL_JSON__;
  const nextUrl = __NEXT_URL_JSON__;
  if (prevUrl || nextUrl) {
    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowLeft' && prevUrl) window.location.href = prevUrl;
      if (e.key === 'ArrowRight' && nextUrl) window.location.href = nextUrl;
    });
  }
</script>
</body>
</html>"""


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


_LOCK = threading.Lock()
_SERVER: Optional[_ThreadingHTTPServer] = None
_PORT: int = 0
_SHOTS: Dict[str, Dict[str, Any]] = {}


def _build_handler():
    class _ScreenshotHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            if path.startswith("/img/"):
                shot_id = path[len("/img/"):].split(".", 1)[0]
                with _LOCK:
                    entry = _SHOTS.get(shot_id)
                if not entry or not os.path.isfile(entry["path"]):
                    self.send_error(404, "Screenshot not found")
                    return
                try:
                    with open(entry["path"], "rb") as f:
                        data = f.read()
                except OSError:
                    self.send_error(500, "Failed to read screenshot")
                    return
                mime, _ = mimetypes.guess_type(entry["path"])
                mime = mime or "image/png"
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return

            if path.startswith("/view/"):
                shot_id = path[len("/view/"):].strip("/")
                with _LOCK:
                    entry = _SHOTS.get(shot_id)
                if not entry or not os.path.isfile(entry["path"]):
                    self.send_error(404, "Screenshot not found")
                    return
                img_path = entry["path"]
                title = entry["title"] or os.path.basename(img_path)
                try:
                    sz = os.path.getsize(img_path)
                    size_kb = f"{max(1, sz // 1024)} KB"
                except OSError:
                    size_kb = ""
                ext = os.path.splitext(img_path)[1] or ".png"
                dl_name = os.path.basename(img_path) or f"screenshot{ext}"
                gal_ids = entry.get("gallery_ids") or []
                idx = int(entry.get("index", 0) or 0)
                if len(gal_ids) > 1:
                    prev_id = gal_ids[(idx - 1) % len(gal_ids)]
                    next_id = gal_ids[(idx + 1) % len(gal_ids)]
                    nav_class = ""
                    nav_label = f"{idx + 1} / {len(gal_ids)}"
                    prev_url = f"/view/{prev_id}"
                    next_url = f"/view/{next_id}"
                else:
                    nav_class = "hidden"
                    nav_label = ""
                    prev_url = "#"
                    next_url = "#"
                import json
                page = (
                    _VIEWER_HTML
                    .replace("__TITLE__", html.escape(title, quote=True))
                    .replace("__SIZE_KB__", html.escape(size_kb, quote=True))
                    .replace("__NAV_CLASS__", nav_class)
                    .replace("__NAV_LABEL__", html.escape(nav_label, quote=True))
                    .replace("__PREV_URL__", prev_url)
                    .replace("__NEXT_URL__", next_url)
                    .replace("__PREV_URL_JSON__", json.dumps("" if nav_class else prev_url))
                    .replace("__NEXT_URL_JSON__", json.dumps("" if nav_class else next_url))
                    .replace("__IMG_URL__", f"/img/{shot_id}{ext}")
                    .replace("__DOWNLOAD_NAME__", html.escape(dl_name, quote=True))
                    .replace("__FULL_PATH__", html.escape(img_path, quote=True))
                    .replace("__RAW_PATH_JSON__", json.dumps(img_path))
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(page)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(page)
                return

            self.send_error(404, "Not found")

    return _ScreenshotHandler


def _shutdown_server() -> None:
    global _SERVER, _PORT
    with _LOCK:
        srv = _SERVER
        _SERVER = None
        _PORT = 0
    if srv is not None:
        try:
            srv.shutdown()
            srv.server_close()
        except Exception:
            pass


def _ensure_server() -> int:
    global _SERVER, _PORT
    with _LOCK:
        if _SERVER is not None and _PORT > 0:
            return _PORT
        srv = _ThreadingHTTPServer(("127.0.0.1", 0), _build_handler())
        port = int(srv.server_address[1])
        threading.Thread(
            target=srv.serve_forever,
            daemon=True,
            name=f"cmdai-screenshot-web-{port}",
        ).start()
        _SERVER = srv
        _PORT = port
        atexit.register(_shutdown_server)
        return port


def _make_shot_id(abs_path: str) -> str:
    try:
        mtime_ns = os.stat(abs_path).st_mtime_ns
    except OSError:
        mtime_ns = 0
    return hashlib.sha1(f"{abs_path}:{mtime_ns}".encode("utf-8")).hexdigest()[:12]


def open_screenshot_in_web(
    image_path: str,
    title: str = "",
    *,
    gallery: Optional[List[Dict[str, Any]]] = None,
    index: int = 0,
    open_browser: bool = True,
) -> str:
    """Register a screenshot (and optional gallery sequence) on the local HTTP viewer and open it."""
    abs_path = os.path.abspath(image_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Screenshot file not found: {abs_path}")
    port = _ensure_server()

    if gallery and len(gallery) > 1:
        items: List[Dict[str, str]] = []
        for g in gallery:
            if not isinstance(g, dict):
                continue
            gp = str(g.get("path") or "").strip()
            if not gp or not os.path.isfile(gp):
                continue
            g_abs = os.path.abspath(gp)
            g_id = _make_shot_id(g_abs)
            g_ttl = str(g.get("label") or g.get("target") or "").strip() or os.path.basename(g_abs)
            items.append({"id": g_id, "path": g_abs, "title": g_ttl})

        if items:
            gal_ids = [it["id"] for it in items]
            with _LOCK:
                for i, it in enumerate(items):
                    _SHOTS[it["id"]] = {
                        "path": it["path"],
                        "title": it["title"],
                        "gallery_ids": gal_ids,
                        "index": i,
                    }
            target_idx = index if 0 <= index < len(items) else 0
            if items[target_idx]["path"] != abs_path:
                for i, it in enumerate(items):
                    if it["path"] == abs_path:
                        target_idx = i
                        break
            target_id = items[target_idx]["id"]
            url = f"http://127.0.0.1:{port}/view/{target_id}"
            if open_browser:
                webbrowser.open(url)
            return url

    shot_id = _make_shot_id(abs_path)
    with _LOCK:
        _SHOTS[shot_id] = {
            "path": abs_path,
            "title": (title or "").strip() or os.path.basename(abs_path),
            "gallery_ids": [],
            "index": 0,
        }
    url = f"http://127.0.0.1:{port}/view/{shot_id}"
    if open_browser:
        webbrowser.open(url)
    return url
