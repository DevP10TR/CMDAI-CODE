"""Standalone Live Browser Viewer HTTP server for CMDAI CODE CLI & TUI.

Styled 1:1 like `cmdai code web` & `/share`:
- Authentic CMDAI CODE block-letter SVG logo in top-left
- Clear Light default + Obsidian Dark toggle (persisted in localStorage)
- Rounded `.app-shell` canvas with full-height crisp browser viewport
- 1:1 rounded black Bibata virtual cursor + Frosted Whisper pill + Tap Burst click animation
- Interactive `Take Control` toggle and live JS Console error badge
Closing the viewer tab NEVER stops the agent's background headless browser.
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import socketserver
import threading
import webbrowser
from typing import Optional

from .engine import get_browser_engine


_VIEWER_HTML = r"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>CMDAI CODE · Live Browser</title>
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
    --accent-green: #15803d;
    --accent-red: #dc2626;
    --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
    --shadow-stage: 0 10px 30px rgba(15, 23, 42, 0.08);
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
    --accent-green: #34d399;
    --accent-red: #f87171;
    --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.35);
    --shadow-stage: 0 14px 40px rgba(0, 0, 0, 0.45);
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
  .mode-tag {
    display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 999px;
    background: var(--accent-blue-soft); color: var(--accent-blue);
    border: 1px solid rgba(59, 130, 246, 0.28);
    font-family: var(--font-mono); font-size: 10.5px; font-weight: 650; letter-spacing: 0.05em;
  }
  .divider { width: 1px; height: 16px; background: var(--border-strong); }
  .status-pill {
    display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px;
    border-radius: 999px; background: var(--bg-card); border: 1px solid var(--border-hairline);
    font-size: 11.8px; font-weight: 500; color: var(--text-secondary); box-shadow: var(--shadow-xs);
  }
  .status-pill i { width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); display: block; }
  .status-pill.live i { background: var(--accent-green); box-shadow: 0 0 6px var(--accent-green); }
  .status-pill.user i { background: var(--accent-blue); }

  .omnibox-wrap { flex: 1; min-width: 0; max-width: 580px; display: flex; align-items: center; gap: 6px; }
  .omnibox {
    flex: 1; min-width: 0; height: 30px; display: flex; align-items: center; gap: 7px;
    padding: 0 4px 0 11px; border-radius: 999px; background: var(--bg-card);
    border: 1px solid var(--border-hairline); box-shadow: var(--shadow-xs);
    transition: border-color 0.14s ease;
  }
  .omnibox:focus-within { border-color: var(--accent-blue); }
  .omnibox svg { color: var(--text-muted); flex-shrink: 0; }
  .omnibox-fav { width: 14px; height: 14px; border-radius: 3px; object-fit: contain; flex-shrink: 0; display: none; }
  .omnibox input {
    flex: 1; min-width: 0; border: none; outline: none; background: transparent;
    color: var(--text-primary); font-family: var(--font-mono); font-size: 12px;
  }
  .go-btn {
    width: 22px; height: 22px; border-radius: 50%; border: none; background: var(--bg-subtle);
    color: var(--text-primary); font-size: 12px; cursor: pointer; display: inline-flex;
    align-items: center; justify-content: center; flex-shrink: 0;
  }
  .go-btn:hover { background: var(--accent-blue); color: #ffffff; }

  .top-right { display: flex; align-items: center; gap: 7px; flex-shrink: 0; }
  .top-btn {
    height: 28px; padding: 0 10px; border-radius: 7px; border: 1px solid var(--border-hairline);
    background: var(--bg-card); color: var(--text-primary); font-size: 12px; font-weight: 500;
    cursor: pointer; display: inline-flex; align-items: center; gap: 5px; box-shadow: var(--shadow-xs);
  }
  .top-btn:hover { border-color: var(--border-strong); background: var(--bg-hover); }
  .top-btn.active { border-color: var(--accent-blue); background: var(--accent-blue-soft); color: var(--accent-blue); }

  .main {
    flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center;
    padding: 12px 16px; background: var(--bg-app); overflow: auto;
  }
  .stage {
    position: relative; width: 100%; max-width: 1360px; max-height: calc(100vh - 116px);
    aspect-ratio: 1280 / 800; border-radius: 11px; overflow: hidden;
    border: 1px solid var(--border-strong); box-shadow: var(--shadow-stage);
    background: var(--bg-card); line-height: 0;
    transition: border-radius 180ms ease, border-width 180ms ease;
  }
  .stage.device-mobile {
    width: auto; max-width: calc(100vw - 32px); height: min(calc(100vh - 116px), 844px);
    border-radius: 18px; border: 1px solid var(--border-strong);
    box-shadow: var(--shadow-stage);
  }
  .stage.device-tablet {
    width: auto; max-width: calc(100vw - 32px); height: min(calc(100vh - 116px), 900px);
    border-radius: 16px; border: 1px solid var(--border-strong);
    box-shadow: var(--shadow-stage);
  }
  .stage.user { border-color: var(--accent-blue); box-shadow: 0 0 0 2px rgba(59,130,246,0.22); cursor: pointer; }
  .stage img { display: block; width: 100%; height: 100%; object-fit: fill; user-select: none; }

  .cursor { position: absolute; top: 0; left: 0; pointer-events: none; z-index: 20; transition: transform 0.32s cubic-bezier(0.22,1,0.36,1), opacity 0.2s ease; will-change: transform; }
  .cursor svg { display: block; filter: drop-shadow(0 4px 6px rgba(0,0,0,0.45)); transition: transform 0.12s ease; transform-origin: 2px 3px; }
  .cursor.pressing svg { transform: scale(0.88); }
  .whisper {
    position: absolute; top: 18px; left: 18px; display: inline-flex; align-items: center; gap: 7px;
    padding: 4px 10px; border-radius: 9px; background: rgba(18,18,22,0.78);
    backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.12);
    color: #f4f4f5; font-size: 11.5px; line-height: 1.3; white-space: nowrap;
    max-width: 240px; overflow: hidden; text-overflow: ellipsis;
    box-shadow: 0 4px 14px rgba(0,0,0,0.28);
    transition: left 0.14s ease, top 0.14s ease, transform 0.14s ease;
  }
  .whisper.flip-left { left: auto; right: 10px; }
  .whisper.flip-top { top: -32px; }
  .whisper.hidden { display: none; }
  #wht { overflow: hidden; text-overflow: ellipsis; }
  .summary-card {
    width: 100%; max-width: 680px; background: var(--bg-card); border: 1px solid var(--border-hairline);
    border-radius: 14px; padding: 22px 24px; box-shadow: var(--shadow-stage);
    display: none; flex-direction: column; gap: 14px;
  }
  .summary-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
  .summary-title { font-size: 15px; font-weight: 650; color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
  .summary-pills { display: flex; flex-wrap: wrap; gap: 6px; }
  .summary-pill { font-size: 11.5px; font-family: var(--font-mono); padding: 2px 9px; border-radius: 999px; background: var(--bg-subtle); border: 1px solid var(--border-hairline); color: var(--text-secondary); }
  .summary-body { font-size: 13.5px; line-height: 1.65; color: var(--text-primary); white-space: pre-wrap; }
  .summary-steps { border: 1px solid var(--border-hairline); border-radius: 10px; background: var(--bg-app); overflow: hidden; }
  .summary-steps summary { cursor: pointer; padding: 8px 12px; font-size: 12px; font-weight: 600; color: var(--text-secondary); list-style: none; }
  .summary-steps ol { padding: 4px 14px 10px 30px; font-family: var(--font-mono); font-size: 11.5px; color: var(--text-secondary); display: flex; flex-direction: column; gap: 4px; }
  .dots { display: inline-flex; gap: 3px; }
  .dots i { width: 4px; height: 4px; border-radius: 50%; background: #fff; display: block; animation: wp 1.15s ease-in-out infinite; }
  .dots i:nth-child(2) { animation-delay: 0.18s; }
  .dots i:nth-child(3) { animation-delay: 0.36s; }
  @keyframes wp { 0%,100% { opacity: 0.22; transform: scale(0.85); } 50% { opacity: 0.95; transform: scale(1.1); } }
  .tap { position: absolute; top: 0; left: 0; width: 0; height: 0; pointer-events: none; z-index: 15; }
  .tap.active::before, .tap.active::after { content: ""; position: absolute; top: 0; left: 0; border-radius: 50%; transform: translate(-50%,-50%) scale(0.2); }
  .tap.active::before { width: 46px; height: 46px; background: radial-gradient(circle, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0.12) 48%, transparent 72%); border: 1.5px solid rgba(255,255,255,0.78); animation: tb1 0.48s cubic-bezier(0.16,1,0.3,1) forwards; }
  .tap.active::after { width: 68px; height: 68px; border: 1.2px solid rgba(255,255,255,0.45); animation: tb2 0.58s cubic-bezier(0.16,1,0.3,1) forwards; }
  @keyframes tb1 { 0% { opacity: 0.95; transform: translate(-50%,-50%) scale(0.22); } 100% { opacity: 0; transform: translate(-50%,-50%) scale(1.15); } }
  @keyframes tb2 { 0% { opacity: 0.7; transform: translate(-50%,-50%) scale(0.25); } 100% { opacity: 0; transform: translate(-50%,-50%) scale(1.25); } }
  .shutter-flash {
    position: absolute; inset: 0; pointer-events: none; z-index: 28; opacity: 0;
    border-radius: inherit;
    background: rgba(255, 255, 255, 0.48);
  }
  .shutter-flash.active { animation: shutterFlash 0.28s cubic-bezier(0.22, 1, 0.36, 1) forwards; }
  @keyframes shutterFlash {
    0% { opacity: 0.48; }
    100% { opacity: 0; }
  }
  .shots-gallery {
    width: 100%; max-width: 1040px; align-self: flex-start; margin: 0 auto;
    display: none; flex-direction: column; gap: 14px; padding: 6px 2px 16px;
  }
  .shots-head {
    display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap;
    background: var(--bg-card); border: 1px solid var(--border-hairline);
    border-radius: 12px; padding: 12px 16px; box-shadow: var(--shadow-xs);
  }
  .shots-title { font-size: 14px; font-weight: 650; color: var(--text-primary); display: flex; align-items: center; gap: 8px; min-width: 0; }
  .shots-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px;
  }
  .shot-card {
    background: var(--bg-card); border: 1px solid var(--border-hairline);
    border-radius: 12px; overflow: hidden; box-shadow: var(--shadow-xs);
    cursor: pointer; display: flex; flex-direction: column;
    transition: border-color 0.14s ease, transform 0.14s ease, box-shadow 0.14s ease;
  }
  .shot-card:hover { border-color: var(--accent-blue); transform: translateY(-1px); box-shadow: var(--shadow-stage); }
  .shot-thumb {
    width: 100%; aspect-ratio: 16 / 10; background: var(--bg-subtle);
    overflow: hidden; border-bottom: 1px solid var(--border-hairline);
    display: flex; align-items: center; justify-content: center; padding: 6px;
  }
  .shot-thumb img { max-width: 100%; max-height: 100%; width: auto; height: auto; object-fit: contain; display: block; border-radius: 4px; }
  .shot-meta { padding: 9px 11px; display: flex; flex-direction: column; gap: 3px; }
  .shot-lbl { font-size: 12.6px; font-weight: 600; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .shot-sub { font-family: var(--font-mono); font-size: 11px; color: var(--text-muted); }

  .lightbox {
    position: fixed; inset: 0; z-index: 60; display: none; padding: 8px;
    background: var(--bg-app);
  }
  .lightbox.open { display: flex; }
  .lb-shell {
    flex: 1; min-height: 0; display: flex; flex-direction: column;
    background: var(--bg-stage); border: 1px solid var(--border-hairline);
    border-radius: 12px; overflow: hidden; box-shadow: var(--shadow-xs);
  }
  .lb-bar {
    height: 46px; padding: 0 14px; background: var(--bg-topbar);
    border-bottom: 1px solid var(--border-hairline);
    display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-shrink: 0;
  }
  .lb-left { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
  .lb-center { flex: 1; min-width: 0; display: flex; align-items: center; justify-content: center; }
  .lb-pill {
    display: inline-flex; align-items: center; gap: 8px; max-width: 100%;
    height: 30px; padding: 0 12px; border-radius: 999px;
    background: var(--bg-card); border: 1px solid var(--border-hairline);
    box-shadow: var(--shadow-xs); min-width: 0;
  }
  .lb-tag {
    font-family: var(--font-mono); font-size: 10.5px; font-weight: 600;
    letter-spacing: 0.04em; padding: 2px 7px; border-radius: 999px;
    background: var(--accent-blue-soft); color: var(--accent-blue); flex-shrink: 0;
  }
  .lb-title { font-size: 12.2px; font-weight: 500; color: var(--text-primary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .lb-dims { font-family: var(--font-mono); font-size: 11.2px; color: var(--text-muted); flex-shrink: 0; }
  .lb-btns { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
  .lb-count { font-family: var(--font-mono); font-size: 11.5px; color: var(--text-secondary); padding: 0 5px; user-select: none; }
  .lb-stage {
    flex: 1; min-height: 0; overflow: auto; display: flex; align-items: center; justify-content: center; padding: 20px;
    background-image:
      linear-gradient(45deg, var(--checker-b) 25%, transparent 25%),
      linear-gradient(-45deg, var(--checker-b) 25%, transparent 25%),
      linear-gradient(45deg, transparent 75%, var(--checker-b) 75%),
      linear-gradient(-45deg, transparent 75%, var(--checker-b) 75%);
    background-size: 20px 20px;
    background-position: 0 0, 0 10px, 10px -10px, -10px 0;
    background-color: var(--checker-a);
  }
  .lb-stage.zoomed { align-items: flex-start; justify-content: flex-start; }
  .lb-frame {
    display: inline-flex; border-radius: 10px; overflow: hidden;
    border: 1px solid var(--border-hairline); box-shadow: var(--shadow-stage); background: var(--bg-card);
  }
  .lb-frame img {
    display: block; max-width: calc(100vw - 64px); max-height: calc(100vh - 110px);
    width: auto; height: auto; cursor: zoom-in; user-select: none;
  }
  .lb-stage.zoomed .lb-frame img { max-width: none; max-height: none; cursor: zoom-out; }

  .footer {
    height: 32px; padding: 0 14px; background: var(--bg-topbar);
    border-top: 1px solid var(--border-hairline);
    display: flex; align-items: center; justify-content: space-between;
    font-size: 11.5px; color: var(--text-muted); flex-shrink: 0;
  }
  .empty { text-align: center; color: var(--text-secondary); max-width: 380px; }
</style>
</head>
<body>
  <div class="app-shell">
    <header class="topbar">
      <div class="top-left">
        <span id="brand-logo" class="cc-vector-badge" aria-label="CMDAI CODE"></span>
        <span id="mode-tag" class="mode-tag" style="display:none;">SHOTS</span>
      </div>
      <div class="omnibox-wrap">
        <button id="reload" class="top-btn" style="width:30px;height:30px;padding:0;justify-content:center;border-radius:999px;" type="button" title="Reload">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8.1 8.1 0 0 0 -15.5 -2m-.5 -4v4h4"/><path d="M4 13a8.1 8.1 0 0 0 15.5 2m.5 4v-4h-4"/></svg>
        </button>
        <div class="omnibox">
          <img id="fav" class="omnibox-fav" alt="" />
          <svg id="globe" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3.6 9h16.8"/><path d="M3.6 15h16.8"/><path d="M11.5 3a17 17 0 0 0 0 18"/><path d="M12.5 3a17 17 0 0 1 0 18"/></svg>
          <input id="url" type="text" placeholder="http://127.0.0.1:3000" />
          <button id="go" class="go-btn" type="button" title="Navigate">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M13 6l6 6l-6 6"/></svg>
          </button>
        </div>
      </div>
      <div class="top-right">
        <button id="take" class="top-btn" type="button">Take Control</button>
        <button id="stop" class="top-btn" type="button">Stop</button>
        <button id="theme" class="top-btn" type="button">Dark</button>
      </div>
    </header>
    <main class="main">
      <div id="empty" class="empty">Waiting for headless browser... Enter a URL above or let the CMDAI CODE agent open a page.</div>
      <div id="summary" class="summary-card">
        <div class="summary-head">
          <div class="summary-title">
            <img id="sum-fav" class="omnibox-fav" alt="" />
            <span id="sum-title">Browser Session Complete</span>
          </div>
          <button id="sum-reopen" class="top-btn" type="button">Reopen URL</button>
        </div>
        <div id="sum-pills" class="summary-pills"></div>
        <div id="sum-body" class="summary-body"></div>
        <details id="sum-steps-wrap" class="summary-steps">
          <summary id="sum-steps-lbl">Steps Performed</summary>
          <ol id="sum-steps"></ol>
        </details>
      </div>
      <div id="shots-gallery" class="shots-gallery">
        <div class="shots-head">
          <div class="shots-title">
            <img id="sg-fav" class="omnibox-fav" alt="" />
            <span id="sg-title">Captured Screenshots</span>
          </div>
          <div id="sg-pills" class="summary-pills"></div>
        </div>
        <div id="sg-grid" class="shots-grid"></div>
      </div>
      <div id="stage" class="stage" style="display:none;">
        <img id="img" alt="Live Browser" draggable="false" />
        <div id="shutter" class="shutter-flash"></div>
        <div id="tap" class="tap"></div>
        <div id="cur" class="cursor">
          <svg width="22" height="22" viewBox="0 0 24 24"><path d="M 2,3.0 C 2,1.1 4.1,0.3 5.5,1.5 L 18.0,12.2 C 19.6,13.6 18.8,16.2 16.7,16.4 L 11.8,16.7 C 10.1,16.8 8.6,17.5 7.4,18.7 L 5.0,21.0 C 3.6,22.3 2,21.3 2,19.4 Z" fill="#09090b" stroke="#ffffff" stroke-width="2.0" stroke-linejoin="round" stroke-linecap="round"/></svg>
          <div id="wh" class="whisper hidden"><span class="dots"><i></i><i></i><i></i></span><span id="wht">Thinking</span></div>
        </div>
      </div>
    </main>
    <footer class="footer">
      <span>Headless CDP · Your physical mouse is untouched</span>
      <span id="cerr">0 console errors</span>
    </footer>
  </div>
  <div id="lightbox" class="lightbox" aria-hidden="true">
    <div class="lb-shell">
      <div class="lb-bar">
        <div class="lb-left">
          <button id="lb-close" class="top-btn" type="button">← Gallery</button>
        </div>
        <div class="lb-center">
          <div class="lb-pill">
            <span class="lb-tag">SCREENSHOT</span>
            <span id="lb-title" class="lb-title">Screenshot</span>
            <span id="lb-dims" class="lb-dims"></span>
          </div>
        </div>
        <div class="lb-btns">
          <button id="lb-prev" class="top-btn" type="button" title="Previous (Left arrow)">←</button>
          <span id="lb-count" class="lb-count">1 / 1</span>
          <button id="lb-next" class="top-btn" type="button" title="Next (Right arrow)">→</button>
          <button id="lb-zoom" class="top-btn" type="button">100%</button>
          <a id="lb-dl" class="top-btn" href="#" download="screenshot.png" style="text-decoration:none;">Download</a>
        </div>
      </div>
      <div id="lb-stage" class="lb-stage">
        <div class="lb-frame">
          <img id="lb-img" src="" alt="Screenshot" draggable="false" />
        </div>
      </div>
    </div>
  </div>
<script>
  // Exact CMDAI CODE vector block logo
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

  let lastFrame = -1, lastClick = 0, lastCapSeq = -1, capWhisperUntil = 0, capWhisperText = "", bw = 1280, bh = 800, takeCtrl = false, lastCur = {x:640,y:400}, lastFav = "", lastSumKey = "";
  const img = document.getElementById('img'), cur = document.getElementById('cur'), tap = document.getElementById('tap');
  const wh = document.getElementById('wh'), wht = document.getElementById('wht'), stage = document.getElementById('stage');
  const modeTag = document.getElementById('mode-tag'), shutterEl = document.getElementById('shutter');
  const empty = document.getElementById('empty'), urlInp = document.getElementById('url'), pill = document.getElementById('pill'), pillLbl = document.getElementById('pill-lbl');
  const takeBtn = document.getElementById('take'), cerr = document.getElementById('cerr');
  const favEl = document.getElementById('fav'), globeEl = document.getElementById('globe');
  const sumCard = document.getElementById('summary'), sumTitle = document.getElementById('sum-title'), sumPills = document.getElementById('sum-pills');
  const sumBody = document.getElementById('sum-body'), sumSteps = document.getElementById('sum-steps'), sumStepsLbl = document.getElementById('sum-steps-lbl'), sumReopen = document.getElementById('sum-reopen'), sumFav = document.getElementById('sum-fav');
  const sgWrap = document.getElementById('shots-gallery'), sgTitle = document.getElementById('sg-title'), sgPills = document.getElementById('sg-pills'), sgGrid = document.getElementById('sg-grid'), sgFav = document.getElementById('sg-fav');
  const lb = document.getElementById('lightbox'), lbStage = document.getElementById('lb-stage'), lbImg = document.getElementById('lb-img'), lbTitle = document.getElementById('lb-title'), lbDims = document.getElementById('lb-dims'), lbCount = document.getElementById('lb-count'), lbDl = document.getElementById('lb-dl'), lbZoom = document.getElementById('lb-zoom');
  let lastShotsKey = "", currentCaptures = [], lbIndex = 0;

  function openLightbox(idx) {
    if (!currentCaptures.length) return;
    lbIndex = ((idx % currentCaptures.length) + currentCaptures.length) % currentCaptures.length;
    const cap = currentCaptures[lbIndex];
    const src = `/api/shot/${lbIndex}?v=${encodeURIComponent(lastShotsKey)}`;
    lbImg.src = src;
    lbDl.href = src;
    const slug = (cap.label || 'screenshot').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'screenshot';
    lbDl.download = `${slug}.png`;
    const meta = [cap.device, (cap.width && cap.height) ? `${cap.width}×${cap.height}` : '', cap.size_bytes ? `${Math.max(1, Math.round(cap.size_bytes / 1024))} KB` : ''].filter(Boolean).join(' · ');
    lbTitle.textContent = cap.label || 'Screenshot';
    if (lbDims) lbDims.textContent = meta;
    lbCount.textContent = `${lbIndex + 1} / ${currentCaptures.length}`;
    lbStage.classList.remove('zoomed');
    lbZoom.textContent = '100%';
    lb.classList.add('open');
  }
  function closeLightbox() { lb.classList.remove('open'); }
  document.getElementById('lb-close').onclick = closeLightbox;
  document.getElementById('lb-prev').onclick = () => openLightbox(lbIndex - 1);
  document.getElementById('lb-next').onclick = () => openLightbox(lbIndex + 1);
  function toggleLbZoom() {
    const z = lbStage.classList.toggle('zoomed');
    lbZoom.textContent = z ? 'Fit' : '100%';
  }
  lbImg.onclick = toggleLbZoom;
  lbZoom.onclick = toggleLbZoom;
  lb.onclick = (e) => { if (e.target === lb || e.target === lbStage) closeLightbox(); };
  document.addEventListener('keydown', (e) => {
    if (!lb.classList.contains('open')) return;
    if (e.key === 'Escape') closeLightbox();
    else if (e.key === 'ArrowLeft') openLightbox(lbIndex - 1);
    else if (e.key === 'ArrowRight') openLightbox(lbIndex + 1);
  });

  function setFavicon(src) {
    if (src === lastFav) return;
    lastFav = src || "";
    if (!lastFav) { favEl.style.display = 'none'; globeEl.style.display = 'block'; return; }
    favEl.onload = () => { favEl.style.display = 'block'; globeEl.style.display = 'none'; };
    favEl.onerror = () => { favEl.style.display = 'none'; globeEl.style.display = 'block'; };
    favEl.src = lastFav;
  }

  function posCur() {
    const r = img.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const px = Math.round((Number(lastCur.x||0) / bw) * r.width);
    const py = Math.round((Number(lastCur.y||0) / bh) * r.height);
    cur.style.transform = `translate3d(${px}px,${py}px,0)`;
    cur.style.opacity = takeCtrl ? '0.25' : '1';
    const flipLim = Math.min(240, Math.round(r.width * 0.48));
    wh.classList.toggle('flip-left', px > r.width - flipLim);
    wh.classList.toggle('flip-top', py > r.height - 64);
  }
  img.addEventListener('load', posCur);
  window.addEventListener('resize', posCur);

  async function poll() {
    try {
      const r = await fetch('/api/state');
      if (!r.ok) return;
      const st = await r.json();
      const isShotsMode = st.mode === 'shots';
      if (modeTag) modeTag.style.display = isShotsMode ? 'inline-flex' : 'none';
      document.title = isShotsMode ? 'CMDAI CODE · Live Shots' : 'CMDAI CODE · Live Browser';
      bw = st.width || 1280; bh = st.height || 800; takeCtrl = !!st.take_control;
      const dev = st.device || (bw < bh ? (bw <= 480 ? 'mobile' : 'tablet') : 'desktop');
      stage.style.aspectRatio = `${bw} / ${bh}`;
      stage.classList.toggle('device-mobile', dev === 'mobile');
      stage.classList.toggle('device-tablet', dev === 'tablet');
      if (st.url && document.activeElement !== urlInp) urlInp.value = st.url;
      setFavicon(st.favicon || (st.last_session && st.last_session.favicon) || "");
      const run = !!(st.running && st.has_frame);
      const isShotsDone = !run && st.last_session && st.last_session.mode === 'shots' && Array.isArray(st.last_session.captures) && st.last_session.captures.length > 0;
      const hasSum = !run && !isShotsDone && st.last_session && st.last_session.summary;
      if (run) { closeLightbox(); lastShotsKey = ""; }
      empty.style.display = (!run && !hasSum && !isShotsDone) ? 'block' : 'none';
      sumCard.style.display = hasSum ? 'flex' : 'none';
      sgWrap.style.display = isShotsDone ? 'flex' : 'none';
      stage.style.display = run ? 'block' : 'none';
      if (isShotsDone) {
        const s = st.last_session;
        const sk = `${s.url}|${s.elapsed}|${s.count}`;
        if (sk !== lastShotsKey) {
          lastShotsKey = sk;
          currentCaptures = s.captures;
          sgTitle.textContent = s.title || s.url || 'Captured Screenshots';
          if (s.favicon) {
            sgFav.onload = () => { sgFav.style.display = 'block'; };
            sgFav.onerror = () => { sgFav.style.display = 'none'; };
            sgFav.src = s.favicon;
          } else { sgFav.style.display = 'none'; }
          sgPills.innerHTML = '';
          [s.model, `${s.count} capture${s.count === 1 ? '' : 's'}`, (s.elapsed !== undefined ? `${s.elapsed}s` : '')].filter(Boolean).forEach((t) => {
            const sp = document.createElement('span'); sp.className = 'summary-pill'; sp.textContent = t; sgPills.appendChild(sp);
          });
          sgGrid.innerHTML = '';
          s.captures.forEach((c, idx) => {
            const card = document.createElement('div');
            card.className = 'shot-card';
            card.onclick = () => openLightbox(idx);
            const th = document.createElement('div');
            th.className = 'shot-thumb';
            const thImg = document.createElement('img');
            thImg.src = `/api/shot/${idx}?v=${encodeURIComponent(sk)}`;
            thImg.alt = c.label || `Capture ${idx + 1}`;
            thImg.loading = 'lazy';
            th.appendChild(thImg);
            const mt = document.createElement('div');
            mt.className = 'shot-meta';
            const lbEl = document.createElement('div');
            lbEl.className = 'shot-lbl';
            lbEl.textContent = c.label || `Capture ${idx + 1}`;
            const subEl = document.createElement('div');
            subEl.className = 'shot-sub';
            subEl.textContent = [c.device, (c.width && c.height) ? `${c.width}×${c.height}` : '', c.size_bytes ? `${Math.max(1, Math.round(c.size_bytes / 1024))} KB` : ''].filter(Boolean).join(' · ');
            mt.appendChild(lbEl);
            mt.appendChild(subEl);
            card.appendChild(th);
            card.appendChild(mt);
            sgGrid.appendChild(card);
          });
        }
      }
      if (hasSum) {
        const s = st.last_session;
        const skey = `${s.url}|${s.elapsed}|${s.steps_count}`;
        if (skey !== lastSumKey) {
          lastSumKey = skey;
          sumTitle.textContent = s.title || s.url || 'Browser Session Complete';
          if (s.favicon) {
            sumFav.onload = () => { sumFav.style.display = 'block'; };
            sumFav.onerror = () => { sumFav.style.display = 'none'; };
            sumFav.src = s.favicon;
          } else { sumFav.style.display = 'none'; }
          sumPills.innerHTML = '';
          [s.model, `${s.steps_count || 0} steps`, `${s.elapsed || 0}s`, `${s.console_errors || 0} errors`].filter(Boolean).forEach((t) => {
            const sp = document.createElement('span'); sp.className = 'summary-pill'; sp.textContent = t; sumPills.appendChild(sp);
          });
          sumBody.textContent = s.summary || '';
          sumSteps.innerHTML = '';
          const stList = Array.isArray(s.steps) ? s.steps : [];
          sumStepsLbl.textContent = `Steps Performed (${stList.length})`;
          stList.forEach((stepTxt) => { const li = document.createElement('li'); li.textContent = stepTxt; sumSteps.appendChild(li); });
          sumReopen.onclick = () => { if (s.url) { urlInp.value = s.url; doOpen(); } };
        }
      }
      stage.classList.toggle('user', takeCtrl);
      takeBtn.classList.toggle('active', takeCtrl);
      takeBtn.textContent = takeCtrl ? 'Release Control' : 'Take Control';
      if (pill && pillLbl) {
        pill.classList.toggle('live', run && !takeCtrl);
        pill.classList.toggle('user', run && takeCtrl);
        pillLbl.textContent = !run ? 'Idle' : (takeCtrl ? 'You' : 'Agent');
      }
      cerr.textContent = `${st.console_errors || 0} console errors`;
      cerr.style.color = (st.console_errors || 0) > 0 ? 'var(--accent-red)' : '';
      if (run && st.frame_seq !== lastFrame) {
        lastFrame = st.frame_seq;
        img.src = `/api/frame?seq=${lastFrame}&t=${Date.now()}`;
      }
      if (typeof st.capture_seq === 'number') {
        if (lastCapSeq < 0) {
          lastCapSeq = st.capture_seq;
        } else if (st.capture_seq > lastCapSeq) {
          lastCapSeq = st.capture_seq;
          if (shutterEl) {
            shutterEl.classList.remove('active');
            void shutterEl.offsetWidth;
            shutterEl.classList.add('active');
          }
          capWhisperText = `Saved · ${st.capture_label || 'Screenshot'}`;
          capWhisperUntil = Date.now() + 1200;
        }
      }
      if (run && st.cursor) {
        lastCur = st.cursor;
        posCur();
        const activeCapWh = (Date.now() < capWhisperUntil) && !takeCtrl;
        const showWh = activeCapWh || !!(lastCur.label && lastCur.state !== 'idle' && !takeCtrl);
        wh.classList.toggle('hidden', !showWh);
        if (showWh) wht.textContent = activeCapWh ? capWhisperText : lastCur.label;
        if ((lastCur.click_seq || 0) > lastClick) {
          lastClick = lastCur.click_seq;
          cur.classList.add('pressing'); setTimeout(() => cur.classList.remove('pressing'), 180);
          const rect = img.getBoundingClientRect();
          if (rect.width) {
            tap.style.left = Math.round((lastCur.x / bw) * rect.width) + 'px';
            tap.style.top = Math.round((lastCur.y / bh) * rect.height) + 'px';
            tap.classList.remove('active'); void tap.offsetWidth; tap.classList.add('active');
          }
        }
      }
    } catch (_) {}
  }
  setInterval(poll, 260);
  poll();

  async function doOpen() {
    const u = urlInp.value.trim(); if (!u) return;
    await fetch('/api/open', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({url: u}) });
    poll();
  }
  document.getElementById('go').onclick = doOpen;
  document.getElementById('reload').onclick = doOpen;
  urlInp.onkeydown = (e) => { if (e.key === 'Enter') doOpen(); };
  takeBtn.onclick = async () => {
    await fetch('/api/take-control', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({enabled: !takeCtrl}) });
    poll();
  };
  document.getElementById('stop').onclick = async () => {
    await fetch('/api/close', { method: 'POST' });
    lastFrame = -1; poll();
  };
  img.onclick = async (e) => {
    if (!takeCtrl) return;
    const r = img.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const x = Math.round(((e.clientX - r.left) / r.width) * bw);
    const y = Math.round(((e.clientY - r.top) / r.height) * bh);
    await fetch('/api/click', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({x, y}) });
    poll();
  };
  let wheelBusy = false;
  img.addEventListener('wheel', async (e) => {
    if (!takeCtrl) return;
    e.preventDefault();
    if (wheelBusy) return;
    wheelBusy = true;
    try {
      const dir = e.deltaY < 0 ? 'up' : 'down';
      const amt = Math.min(800, Math.max(220, Math.abs(Math.round(e.deltaY * 2.5))));
      await fetch('/api/scroll', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({direction: dir, amount: amt}) });
      poll();
    } finally {
      setTimeout(() => { wheelBusy = false; }, 160);
    }
  }, { passive: false });
</script>
</body>
</html>
"""


_VIEWER_SERVER: Optional[socketserver.ThreadingTCPServer] = None
_VIEWER_PORT: int = 0
_VIEWER_LOCK = threading.Lock()


class _ViewerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, obj: dict, status: int = 200) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        eng = get_browser_engine()
        if path in ("/", "/index.html"):
            raw = _VIEWER_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        elif path == "/api/state":
            self._send_json(eng.get_state())
        elif path == "/api/frame":
            frame = eng.latest_frame
            if not frame:
                self.send_response(204)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(frame)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(frame)
        elif path.startswith("/api/shot/"):
            raw_idx = path[len("/api/shot/"):].strip("/")
            ls = getattr(eng, "last_session", None)
            caps = ls.get("captures") if isinstance(ls, dict) and ls.get("mode") == "shots" else None
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                idx = -1
            if not isinstance(caps, list) or idx < 0 or idx >= len(caps):
                self.send_response(404)
                self.end_headers()
                return
            shot_path = str((caps[idx] or {}).get("path") or "").strip()
            if not shot_path or not os.path.isfile(shot_path):
                self.send_response(404)
                self.end_headers()
                return
            try:
                with open(shot_path, "rb") as f:
                    data = f.read()
            except OSError:
                self.send_response(500)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
        eng = get_browser_engine()
        if path == "/api/open":
            self._send_json(eng.open_url(str(body.get("url") or "")))
        elif path == "/api/take-control":
            self._send_json(eng.set_take_control(bool(body.get("enabled", False))))
        elif path == "/api/click":
            self._send_json(eng.click(x=int(body.get("x", 0)), y=int(body.get("y", 0)), from_user=True))
        elif path == "/api/scroll":
            self._send_json(eng.scroll(direction=str(body.get("direction") or "down"), amount=int(body.get("amount") or 420)))
        elif path == "/api/close":
            self._send_json(eng.close())
        else:
            self._send_json({"ok": False}, status=404)


def ensure_viewer_server() -> str:
    global _VIEWER_SERVER, _VIEWER_PORT
    with _VIEWER_LOCK:
        if _VIEWER_SERVER is None:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", 0))
                _VIEWER_PORT = int(s.getsockname()[1])
            srv = socketserver.ThreadingTCPServer(("127.0.0.1", _VIEWER_PORT), _ViewerHandler)
            srv.daemon_threads = True
            threading.Thread(target=srv.serve_forever, daemon=True, name="cmdai-browser-viewer").start()
            _VIEWER_SERVER = srv
        return f"http://127.0.0.1:{_VIEWER_PORT}/"


def open_live_browser_viewer(open_browser: bool = True) -> str:
    url = ensure_viewer_server()
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    return url
