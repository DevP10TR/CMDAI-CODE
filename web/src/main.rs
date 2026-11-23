use std::collections::HashMap;
use std::env;
use std::io::{BufRead, BufReader, Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

const INDEX_HTML: &str = include_str!("../ui/index.html");
const STYLES_CSS: &str = include_str!("../ui/styles.css");
const APP_JS: &str = include_str!("../ui/app.js");
const EDITOR_JS: &str = include_str!("../ui/editor.js");
const MAP_JS: &str = include_str!("../ui/map.js");

const PIN_GATE_HTML: &str = r#"<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no" />
<title>CMDAI CODE · Unlock Remote Tunnel</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%2318181b'/%3E%3Cpath d='M7 9h7v3H10v8h4v3H7V9zm11 0h7v3h-4v8h4v3h-7V9z' fill='%23ffffff'/%3E%3C/svg%3E" />
<style>
  :root {
    --bg: #f4f5f7;
    --bg-glow-1: rgba(37, 99, 235, 0.08);
    --bg-glow-2: rgba(16, 185, 129, 0.06);
    --card: #ffffff;
    --card-border: rgba(15, 23, 42, 0.09);
    --card-shadow: 0 24px 60px rgba(15, 23, 42, 0.10), 0 2px 8px rgba(15, 23, 42, 0.04);
    --text: #111827;
    --text-muted: #6b7280;
    --text-subtle: #9ca3af;
    --pill-bg: #f3f4f6;
    --pill-border: rgba(15, 23, 42, 0.08);
    --slot-bg: #f9fafb;
    --slot-border: #d1d5db;
    --slot-focus: #2563eb;
    --slot-focus-ring: rgba(37, 99, 235, 0.16);
    --slot-filled-bg: #ffffff;
    --slot-filled-border: #18181b;
    --btn-bg: #18181b;
    --btn-fg: #ffffff;
    --btn-hover: #27272a;
    --logo-solid: #18181b;
    --logo-accent: #52525b;
    --err: #dc2626;
    --err-ring: rgba(220, 38, 38, 0.18);
    --ok: #16a34a;
    --ok-ring: rgba(22, 163, 74, 0.18);
  }

  [data-theme="dark"] {
    --bg: #0c0d10;
    --bg-glow-1: rgba(59, 130, 246, 0.12);
    --bg-glow-2: rgba(16, 185, 129, 0.07);
    --card: #13151a;
    --card-border: rgba(255, 255, 255, 0.08);
    --card-shadow: 0 28px 70px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(255, 255, 255, 0.03);
    --text: #f4f4f5;
    --text-muted: #a1a1aa;
    --text-subtle: #71717a;
    --pill-bg: rgba(255, 255, 255, 0.04);
    --pill-border: rgba(255, 255, 255, 0.09);
    --slot-bg: #0c0d10;
    --slot-border: rgba(255, 255, 255, 0.12);
    --slot-focus: #60a5fa;
    --slot-focus-ring: rgba(96, 165, 250, 0.22);
    --slot-filled-bg: #181b22;
    --slot-filled-border: rgba(255, 255, 255, 0.34);
    --btn-bg: #f4f4f5;
    --btn-fg: #09090b;
    --btn-hover: #ffffff;
    --logo-solid: #f4f4f5;
    --logo-accent: #a1a1aa;
    --err: #f87171;
    --err-ring: rgba(248, 113, 113, 0.22);
    --ok: #4ade80;
    --ok-ring: rgba(74, 222, 128, 0.22);
  }

  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body {
    min-height: 100dvh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
    background:
      radial-gradient(640px 380px at 50% 18%, var(--bg-glow-1), transparent 70%),
      radial-gradient(520px 360px at 80% 85%, var(--bg-glow-2), transparent 70%),
      var(--bg);
    font-family: -apple-system, BlinkMacSystemFont, "Inter", "Segoe UI", Roboto, sans-serif;
    color: var(--text);
    -webkit-font-smoothing: antialiased;
    transition: background 200ms ease, color 200ms ease;
  }

  .theme-btn {
    position: fixed;
    top: 18px;
    right: 18px;
    height: 34px;
    padding: 0 12px;
    border-radius: 999px;
    border: 1px solid var(--pill-border);
    background: var(--card);
    color: var(--text-muted);
    font-size: 12px;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
    box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
    transition: color 150ms ease, border-color 150ms ease, transform 120ms ease;
  }
  .theme-btn:hover { color: var(--text); border-color: var(--slot-filled-border); }
  .theme-btn:active { transform: scale(0.97); }

  .card {
    width: 100%;
    max-width: 410px;
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 20px;
    padding: 34px 30px 28px;
    box-shadow: var(--card-shadow);
    text-align: center;
    position: relative;
    overflow: hidden;
  }

  .brand-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    margin-bottom: 20px;
  }

  .brand-host {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
  }

  .brand-host svg {
    height: 36px;
    width: auto;
    max-width: 100%;
    display: block;
  }

  .brand-host .word-cmdai { fill: var(--logo-accent); }
  .brand-host .word-code { fill: var(--logo-solid); }

  h1 {
    margin: 0 0 7px;
    font-size: 20px;
    font-weight: 650;
    letter-spacing: -0.02em;
  }

  .sub {
    margin: 0 0 24px;
    font-size: 13px;
    line-height: 1.5;
    color: var(--text-muted);
  }

  .otp-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-bottom: 18px;
  }

  .otp-sep {
    width: 8px;
    height: 2px;
    border-radius: 2px;
    background: var(--slot-border);
    margin: 0 2px;
    flex-shrink: 0;
  }

  .otp-box {
    width: 46px;
    height: 56px;
    border-radius: 12px;
    border: 1.5px solid var(--slot-border);
    background: var(--slot-bg);
    color: var(--text);
    text-align: center;
    font-family: ui-monospace, "Cascadia Code", "JetBrains Mono", Consolas, monospace;
    font-size: 24px;
    font-weight: 700;
    outline: none;
    caret-color: var(--slot-focus);
    transition: border-color 140ms ease, box-shadow 140ms ease, background 140ms ease, transform 120ms ease;
    -moz-appearance: textfield;
  }
  .otp-box:focus {
    border-color: var(--slot-focus);
    box-shadow: 0 0 0 4px var(--slot-focus-ring);
    background: var(--slot-filled-bg);
    transform: translateY(-1px);
  }
  .otp-box.filled {
    border-color: var(--slot-filled-border);
    background: var(--slot-filled-bg);
  }
  .otp-row.is-error .otp-box {
    border-color: var(--err);
    box-shadow: 0 0 0 3px var(--err-ring);
  }
  .otp-row.is-ok .otp-box {
    border-color: var(--ok);
    box-shadow: 0 0 0 3px var(--ok-ring);
    color: var(--ok);
  }

  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-7px); }
    40% { transform: translateX(7px); }
    60% { transform: translateX(-5px); }
    80% { transform: translateX(5px); }
  }
  .otp-row.shake { animation: shake 320ms cubic-bezier(.36,.07,.19,.97); }

  .unlock-btn {
    width: 100%;
    height: 44px;
    border: none;
    border-radius: 12px;
    background: var(--btn-bg);
    color: var(--btn-fg);
    font-size: 14px;
    font-weight: 600;
    letter-spacing: -0.01em;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    transition: opacity 150ms ease, transform 120ms ease, background 150ms ease;
  }
  .unlock-btn:hover:not(:disabled) { background: var(--btn-hover); }
  .unlock-btn:active:not(:disabled) { transform: scale(0.99); }
  .unlock-btn:disabled { opacity: 0.45; cursor: not-allowed; }

  .status {
    min-height: 20px;
    margin-top: 12px;
    font-size: 12.5px;
    font-weight: 500;
    color: var(--text-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }
  .status.err { color: var(--err); }
  .status.ok { color: var(--ok); }

  .foot {
    margin-top: 18px;
    padding-top: 14px;
    border-top: 1px solid var(--card-border);
    font-size: 11.5px;
    color: var(--text-subtle);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
  }

  .spin {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 2px solid currentColor;
    border-top-color: transparent;
    animation: sp 700ms linear infinite;
  }
  @keyframes sp { to { transform: rotate(360deg); } }

  @media (max-width: 420px) {
    .card { padding: 28px 20px 24px; }
    .otp-box { width: 41px; height: 52px; font-size: 22px; }
    .otp-row { gap: 6px; }
  }
</style>
</head>
<body>
  <button id="themeBtn" class="theme-btn" type="button" aria-label="Toggle theme">
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3a6 6 0 0 0 9 9a9 9 0 1 1 -9 -9z"/></svg>
    <span id="themeLbl">Light</span>
  </button>

  <main class="card">
    <div class="brand-wrap">
      <div id="brandHost" class="brand-host" aria-label="CMDAI CODE"></div>
    </div>

    <h1>Unlock Workspace</h1>
    <p class="sub">Enter the 6-digit pairing PIN displayed in your PC tunnel console to connect.</p>

    <form id="f" autocomplete="off">
      <div id="otpRow" class="otp-row" role="group" aria-label="6-digit PIN">
        <input class="otp-box" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="1" autocomplete="one-time-code" aria-label="Digit 1" />
        <input class="otp-box" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="1" aria-label="Digit 2" />
        <input class="otp-box" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="1" aria-label="Digit 3" />
        <span class="otp-sep" aria-hidden="true"></span>
        <input class="otp-box" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="1" aria-label="Digit 4" />
        <input class="otp-box" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="1" aria-label="Digit 5" />
        <input class="otp-box" type="text" inputmode="numeric" pattern="[0-9]*" maxlength="1" aria-label="Digit 6" />
      </div>

      <button id="submitBtn" class="unlock-btn" type="submit" disabled>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        <span id="btnLbl">Unlock Workspace</span>
      </button>
    </form>

    <div id="status" class="status" role="status" aria-live="polite"></div>

    <div class="foot">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
      <span>Cloudflare Tunnel · Revokes when PC console closes</span>
    </div>
  </main>

  <script>
    // Exact CMDAI CODE block + bevel logo from the app
    (() => {
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
      function buildPaths(lines, colOffset, cellW, cellH) {
        let d = "";
        const sw = Math.max(1.5, cellW * 0.15);
        for (let r = 0; r < lines.length; r++) {
          const line = lines[r];
          for (let c = 0; c < line.length; c++) {
            const ch = line[c];
            if (ch === " ") continue;
            const x = (colOffset + c) * cellW, y = r * cellH;
            const xA = x + cellW * 0.28, xB = x + cellW * 0.64;
            const yA = y + cellH * 0.30, yB = y + cellH * 0.64;
            if (ch === "█") d += `M${(x-0.25).toFixed(2)},${(y-0.3).toFixed(2)}h${(cellW+0.5).toFixed(2)}v${(cellH+0.6).toFixed(2)}h-${(cellW+0.5).toFixed(2)}z`;
            else if (ch === "═") { d += `M${(x-0.2).toFixed(2)},${yA.toFixed(2)}h${(cellW+0.4).toFixed(2)}v${sw.toFixed(2)}h-${(cellW+0.4).toFixed(2)}z`; d += `M${(x-0.2).toFixed(2)},${yB.toFixed(2)}h${(cellW+0.4).toFixed(2)}v${sw.toFixed(2)}h-${(cellW+0.4).toFixed(2)}z`; }
            else if (ch === "║") { d += `M${xA.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}v${(cellH+0.4).toFixed(2)}h-${sw.toFixed(2)}z`; d += `M${xB.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}v${(cellH+0.4).toFixed(2)}h-${sw.toFixed(2)}z`; }
            else if (ch === "╔") { d += `M${xA.toFixed(2)},${yA.toFixed(2)}H${(x+cellW+0.2).toFixed(2)}v${sw.toFixed(2)}H${(xA+sw).toFixed(2)}V${(y+cellH+0.2).toFixed(2)}H${xA.toFixed(2)}z`; d += `M${xB.toFixed(2)},${yB.toFixed(2)}H${(x+cellW+0.2).toFixed(2)}v${sw.toFixed(2)}H${(xB+sw).toFixed(2)}V${(y+cellH+0.2).toFixed(2)}H${xB.toFixed(2)}z`; }
            else if (ch === "╗") { d += `M${(x-0.2).toFixed(2)},${yA.toFixed(2)}H${(xB+sw).toFixed(2)}V${(y+cellH+0.2).toFixed(2)}h-${sw.toFixed(2)}V${(yA+sw).toFixed(2)}H${(x-0.2).toFixed(2)}z`; d += `M${(x-0.2).toFixed(2)},${yB.toFixed(2)}H${(xA+sw).toFixed(2)}V${(y+cellH+0.2).toFixed(2)}h-${sw.toFixed(2)}V${(yB+sw).toFixed(2)}H${(x-0.2).toFixed(2)}z`; }
            else if (ch === "╚") { d += `M${xA.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}V${yB.toFixed(2)}H${(x+cellW+0.2).toFixed(2)}v${sw.toFixed(2)}H${xA.toFixed(2)}z`; d += `M${xB.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}V${yA.toFixed(2)}H${(x+cellW+0.2).toFixed(2)}v${sw.toFixed(2)}H${xB.toFixed(2)}z`; }
            else if (ch === "╝") { d += `M${xB.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}V${(yB+sw).toFixed(2)}H${(x-0.2).toFixed(2)}v-${sw.toFixed(2)}H${xB.toFixed(2)}z`; d += `M${xA.toFixed(2)},${(y-0.2).toFixed(2)}h${sw.toFixed(2)}V${(yA+sw).toFixed(2)}H${(x-0.2).toFixed(2)}v-${sw.toFixed(2)}H${xA.toFixed(2)}z`; }
          }
        }
        return d;
      }
      const host = document.getElementById("brandHost");
      if (!host) return;
      const cw = 10, ch = 23, gap = 3;
      const w = (CMDAI_PARTS[0].length + gap + CODE_PARTS[0].length) * cw;
      const h = CMDAI_PARTS.length * ch;
      const ns = "http://www.w3.org/2000/svg";
      const svg = document.createElementNS(ns, "svg");
      svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
      const g1 = document.createElementNS(ns, "g");
      g1.setAttribute("class", "word-cmdai");
      const p1 = document.createElementNS(ns, "path");
      p1.setAttribute("d", buildPaths(CMDAI_PARTS, 0, cw, ch));
      g1.appendChild(p1);
      const g2 = document.createElementNS(ns, "g");
      g2.setAttribute("class", "word-code");
      const p2 = document.createElementNS(ns, "path");
      p2.setAttribute("d", buildPaths(CODE_PARTS, CMDAI_PARTS[0].length + gap, cw, ch));
      g2.appendChild(p2);
      svg.appendChild(g1);
      svg.appendChild(g2);
      host.appendChild(svg);
    })();

    const root = document.documentElement;
    const themeBtn = document.getElementById("themeBtn");
    const themeLbl = document.getElementById("themeLbl");
    function applyTheme(t) {
      root.setAttribute("data-theme", t);
      themeLbl.textContent = t === "dark" ? "Light" : "Dark";
      try { localStorage.setItem("cmdai_pin_theme", t); } catch (_) {}
    }
    const initTheme = (() => {
      try {
        const s = localStorage.getItem("cmdai_pin_theme") || localStorage.getItem("cmdai_theme");
        if (s === "light" || s === "dark") return s;
      } catch (_) {}
      return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    })();
    applyTheme(initTheme);
    themeBtn.addEventListener("click", () => {
      applyTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
    });

    const boxes = Array.from(document.querySelectorAll(".otp-box"));
    const otpRow = document.getElementById("otpRow");
    const submitBtn = document.getElementById("submitBtn");
    const btnLbl = document.getElementById("btnLbl");
    const statusEl = document.getElementById("status");
    let busy = false;

    function getPin() { return boxes.map(b => b.value).join(""); }
    function syncState() {
      boxes.forEach(b => b.classList.toggle("filled", b.value.length === 1));
      const full = getPin().length === 6;
      submitBtn.disabled = busy || !full;
    }
    function setStatus(msg, cls = "") {
      statusEl.className = "status" + (cls ? " " + cls : "");
      statusEl.textContent = msg;
    }

    function fillFromString(raw, startIdx = 0) {
      const digits = String(raw || "").replace(/\D/g, "").slice(0, 6);
      if (!digits) return;
      for (let i = 0; i < digits.length && startIdx + i < 6; i++) {
        boxes[startIdx + i].value = digits[i];
      }
      otpRow.classList.remove("is-error");
      setStatus("");
      syncState();
      const next = Math.min(5, startIdx + digits.length);
      boxes[next].focus();
      if (getPin().length === 6) verifyPin();
    }

    boxes.forEach((box, idx) => {
      box.addEventListener("input", (e) => {
        const v = box.value.replace(/\D/g, "");
        if (v.length > 1) {
          box.value = "";
          fillFromString(v, idx);
          return;
        }
        box.value = v;
        otpRow.classList.remove("is-error");
        setStatus("");
        syncState();
        if (v && idx < 5) boxes[idx + 1].focus();
        if (getPin().length === 6) verifyPin();
      });

      box.addEventListener("keydown", (e) => {
        if (e.key === "Backspace") {
          if (box.value) {
            box.value = "";
            syncState();
          } else if (idx > 0) {
            boxes[idx - 1].value = "";
            boxes[idx - 1].focus();
            syncState();
          }
          e.preventDefault();
        } else if (e.key === "ArrowLeft" && idx > 0) {
          boxes[idx - 1].focus();
          e.preventDefault();
        } else if (e.key === "ArrowRight" && idx < 5) {
          boxes[idx + 1].focus();
          e.preventDefault();
        }
      });

      box.addEventListener("paste", (e) => {
        e.preventDefault();
        const text = (e.clipboardData || window.clipboardData).getData("text");
        fillFromString(text, 0);
      });

      box.addEventListener("focus", () => box.select());
    });

    async function verifyPin() {
      const pin = getPin();
      if (busy || pin.length !== 6) return;
      busy = true;
      syncState();
      btnLbl.innerHTML = '<span class="spin"></span> Verifying...';
      setStatus("");

      try {
        const r = await fetch("/api/web/verify-pin", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pin }),
        });
        const data = await r.json().catch(() => ({}));
        if (r.ok && data.ok) {
          otpRow.classList.add("is-ok");
          btnLbl.textContent = "Unlocked";
          setStatus("PIN verified · Opening CMDAI CODE...", "ok");
          setTimeout(() => location.reload(), 280);
          return;
        }
        otpRow.classList.add("is-error", "shake");
        setTimeout(() => otpRow.classList.remove("shake"), 360);
        if (r.status === 429) {
          setStatus(`Too many attempts · try again in ${data.retry_after || 30}s`, "err");
        } else {
          setStatus("Incorrect PIN · check your PC tunnel console", "err");
        }
        boxes.forEach(b => { b.value = ""; });
        boxes[0].focus();
      } catch (_) {
        setStatus("Connection lost · retry", "err");
      } finally {
        busy = false;
        btnLbl.textContent = "Unlock Workspace";
        syncState();
      }
    }

    document.getElementById("f").addEventListener("submit", (e) => {
      e.preventDefault();
      verifyPin();
    });

    boxes[0].focus();
  </script>
</body>
</html>"#;

struct PinGuard {
    failures: u32,
    locked_until: Option<Instant>,
}

struct Config {
    host: String,
    port: u16,
    backend: String,
    token: String,
    pin: String,
    spectate_token: String,
    pin_guard: Mutex<PinGuard>,
}

fn constant_time_eq(a: &str, b: &str) -> bool {
    let ab = a.as_bytes();
    let bb = b.as_bytes();
    if ab.len() != bb.len() {
        return false;
    }
    let mut diff: u8 = 0;
    for (&x, &y) in ab.iter().zip(bb.iter()) {
        diff |= x ^ y;
    }
    diff == 0
}

fn parse_args() -> Config {
    let mut cfg = Config {
        host: "127.0.0.1".to_string(),
        port: 8787,
        backend: "127.0.0.1:7860".to_string(),
        token: String::new(),
        pin: String::new(),
        spectate_token: String::new(),
        pin_guard: Mutex::new(PinGuard {
            failures: 0,
            locked_until: None,
        }),
    };
    let args: Vec<String> = env::args().collect();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--host" if i + 1 < args.len() => { cfg.host = args[i + 1].clone(); i += 2; }
            "--port" if i + 1 < args.len() => { if let Ok(p) = args[i + 1].parse::<u16>() { cfg.port = p; } i += 2; }
            "--backend" if i + 1 < args.len() => { cfg.backend = args[i + 1].clone(); i += 2; }
            "--token" if i + 1 < args.len() => { cfg.token = args[i + 1].clone(); i += 2; }
            "--pin" if i + 1 < args.len() => { cfg.pin = args[i + 1].clone(); i += 2; }
            "--spectate-token" if i + 1 < args.len() => { cfg.spectate_token = args[i + 1].clone(); i += 2; }
            _ => i += 1,
        }
    }
    cfg
}

fn send_response(
    stream: &mut TcpStream,
    status: &str,
    content_type: &str,
    extra_headers: &[(&str, &str)],
    body: &[u8],
) {
    let mut head = format!(
        "HTTP/1.1 {}\r\nContent-Type: {}\r\nContent-Length: {}\r\nX-Robots-Tag: noindex, nofollow\r\nCache-Control: no-store\r\nConnection: close\r\n",
        status,
        content_type,
        body.len()
    );
    for (k, v) in extra_headers {
        head.push_str(&format!("{}: {}\r\n", k, v));
    }
    head.push_str("\r\n");
    let _ = stream.write_all(head.as_bytes());
    let _ = stream.write_all(body);
    let _ = stream.flush();
}

fn parse_cookies(headers: &HashMap<String, String>) -> HashMap<String, String> {
    let mut out = HashMap::new();
    if let Some(raw) = headers.get("cookie") {
        for part in raw.split(';') {
            if let Some((k, v)) = part.trim().split_once('=') {
                out.insert(k.trim().to_string(), v.trim().to_string());
            }
        }
    }
    out
}

fn extract_json_field(body: &str, field: &str) -> String {
    let needle = format!("\"{}\"", field);
    if let Some(pos) = body.find(&needle) {
        let rest = &body[pos + needle.len()..];
        if let Some(colon) = rest.find(':') {
            let val = rest[colon + 1..].trim();
            if let Some(stripped) = val.strip_prefix('"') {
                if let Some(end) = stripped.find('"') {
                    return stripped[..end].to_string();
                }
            }
        }
    }
    String::new()
}

fn proxy_to_backend_streaming(
    client: &mut TcpStream,
    cfg: &Config,
    method: &str,
    path: &str,
    headers: &HashMap<String, String>,
    body: &[u8],
) {
    let mut backend = match TcpStream::connect(&cfg.backend) {
        Ok(s) => s,
        Err(_) => {
            let err = br#"{"error":"CMDAI CODE backend is offline"}"#;
            send_response(client, "502 Bad Gateway", "application/json", &[], err);
            return;
        }
    };
    // No artificial read timeout on SSE / agent streams so long multi-step tasks never drop with network error
    let _ = backend.set_nodelay(true);
    let _ = client.set_nodelay(true);
    let _ = backend.set_read_timeout(None);
    let _ = backend.set_write_timeout(Some(Duration::from_secs(30)));

    let mut req = format!(
        "{} {} HTTP/1.1\r\nHost: {}\r\nConnection: close\r\nContent-Length: {}\r\n",
        method,
        path,
        cfg.backend,
        body.len()
    );
    if let Some(ct) = headers.get("content-type") {
        req.push_str(&format!("Content-Type: {}\r\n", ct));
    }
    if let Some(acc) = headers.get("accept") {
        req.push_str(&format!("Accept: {}\r\n", acc));
    }
    if !cfg.spectate_token.is_empty() {
        req.push_str(&format!("X-CMDAI-Token: {}\r\n", cfg.spectate_token));
    } else if !cfg.token.is_empty() {
        req.push_str(&format!("X-CMDAI-Token: {}\r\n", cfg.token));
    }
    req.push_str("\r\n");

    if backend.write_all(req.as_bytes()).is_err() || backend.write_all(body).is_err() {
        let err = br#"{"error":"Failed to forward request to backend"}"#;
        send_response(client, "502 Bad Gateway", "application/json", &[], err);
        return;
    }
    let _ = backend.flush();

    // Stream response chunks immediately so SSE (text/event-stream) works in real time
    let mut buf = [0u8; 8192];
    loop {
        match backend.read(&mut buf) {
            Ok(0) => break,
            Ok(n) => {
                if client.write_all(&buf[..n]).is_err() {
                    break;
                }
                let _ = client.flush();
            }
            Err(_) => break,
        }
    }
}

fn read_chunked_body<R: BufRead>(reader: &mut R, max_bytes: usize) -> Vec<u8> {
    let mut out = Vec::new();
    loop {
        let mut size_line = String::new();
        if reader.read_line(&mut size_line).unwrap_or(0) == 0 {
            break;
        }
        let hex_part = size_line.trim().split(';').next().unwrap_or("").trim();
        let chunk_size = match usize::from_str_radix(hex_part, 16) {
            Ok(n) => n,
            Err(_) => break,
        };
        if chunk_size == 0 {
            // Drain trailing headers until empty line
            loop {
                let mut trailer = String::new();
                if reader.read_line(&mut trailer).unwrap_or(0) == 0 || trailer.trim().is_empty() {
                    break;
                }
            }
            break;
        }
        let remaining = max_bytes.saturating_sub(out.len());
        let to_read = chunk_size.min(remaining);
        let start = out.len();
        out.resize(start + to_read, 0);
        if to_read > 0 && reader.read_exact(&mut out[start..]).is_err() {
            break;
        }
        // Drain any excess bytes if chunk exceeded max_bytes
        if chunk_size > to_read {
            let mut skip = chunk_size - to_read;
            let mut trash = [0u8; 4096];
            while skip > 0 {
                let n = skip.min(trash.len());
                if reader.read_exact(&mut trash[..n]).is_err() {
                    break;
                }
                skip -= n;
            }
        }
        // Drain trailing CRLF after chunk payload
        let mut crlf = [0u8; 2];
        let _ = reader.read_exact(&mut crlf);
    }
    out
}

fn handle_client(mut stream: TcpStream, cfg: Arc<Config>) {
    let _ = stream.set_nodelay(true);
    let _ = stream.set_read_timeout(Some(Duration::from_secs(15)));
    let mut reader = match stream.try_clone() {
        Ok(cloned) => BufReader::new(cloned),
        Err(_) => return,
    };

    let mut request_line = String::new();
    if reader.read_line(&mut request_line).unwrap_or(0) == 0 {
        return;
    }
    let parts: Vec<&str> = request_line.trim().split_whitespace().collect();
    if parts.len() < 2 {
        return;
    }
    let method = parts[0];
    let full_path = parts[1];
    let clean_path = full_path.split('?').next().unwrap_or(full_path);

    let mut headers = HashMap::new();
    let mut content_len: usize = 0;
    let mut is_chunked = false;
    loop {
        let mut line = String::new();
        if reader.read_line(&mut line).unwrap_or(0) == 0 {
            break;
        }
        let trimmed = line.trim();
        if trimmed.is_empty() {
            break;
        }
        if let Some((k, v)) = trimmed.split_once(':') {
            let key = k.trim().to_ascii_lowercase();
            let val = v.trim().to_string();
            if key == "content-length" {
                content_len = val.parse::<usize>().unwrap_or(0).min(24 * 1024 * 1024);
            } else if key == "transfer-encoding" && val.to_ascii_lowercase().contains("chunked") {
                is_chunked = true;
            }
            headers.insert(key, val);
        }
    }

    let body = if is_chunked {
        read_chunked_body(&mut reader, 24 * 1024 * 1024)
    } else if content_len > 0 {
        let mut buf = vec![0u8; content_len];
        let _ = reader.read_exact(&mut buf);
        buf
    } else {
        Vec::new()
    };
    // Clear read timeout after request headers/body are received so long SSE streams never drop
    let _ = stream.set_read_timeout(None);

    let cookies = parse_cookies(&headers);
    let spectate_mode = !cfg.spectate_token.is_empty();
    let remote_mode = !spectate_mode && !cfg.token.is_empty();
    let pin_required = remote_mode && !cfg.pin.is_empty();

    // PIN verification endpoint (with brute-force rate limiting)
    if method == "POST" && clean_path == "/api/web/verify-pin" {
        let tok_ok = !remote_mode
            || cookies.get("cmdai_tok").map(|v| constant_time_eq(v, &cfg.token)).unwrap_or(false);
        if !tok_ok {
            send_response(&mut stream, "401 Unauthorized", "application/json", &[], br#"{"ok":false}"#);
            return;
        }

        // Check lockout
        if let Ok(mut guard) = cfg.pin_guard.lock() {
            if let Some(until) = guard.locked_until {
                let now = Instant::now();
                if now < until {
                    let secs = (until - now).as_secs().max(1);
                    let payload = format!(r#"{{"ok":false,"retry_after":{}}}"#, secs);
                    send_response(&mut stream, "429 Too Many Requests", "application/json", &[], payload.as_bytes());
                    return;
                } else {
                    guard.locked_until = None;
                    guard.failures = 0;
                }
            }
        }

        let body_str = String::from_utf8_lossy(&body);
        let supplied = extract_json_field(&body_str, "pin");
        if !cfg.pin.is_empty() && constant_time_eq(&supplied, &cfg.pin) {
            if let Ok(mut guard) = cfg.pin_guard.lock() {
                guard.failures = 0;
                guard.locked_until = None;
            }
            let cookie = format!("cmdai_pin={}; Path=/; HttpOnly; SameSite=Lax", cfg.pin);
            send_response(&mut stream, "200 OK", "application/json", &[("Set-Cookie", &cookie)], br#"{"ok":true}"#);
        } else {
            let mut locked_secs: Option<u64> = None;
            if let Ok(mut guard) = cfg.pin_guard.lock() {
                guard.failures += 1;
                if guard.failures >= 5 {
                    guard.locked_until = Some(Instant::now() + Duration::from_secs(30));
                    locked_secs = Some(30);
                }
            }
            if let Some(secs) = locked_secs {
                let payload = format!(r#"{{"ok":false,"retry_after":{}}}"#, secs);
                send_response(&mut stream, "429 Too Many Requests", "application/json", &[], payload.as_bytes());
            } else {
                send_response(&mut stream, "403 Forbidden", "application/json", &[], br#"{"ok":false}"#);
            }
        }
        return;
    }

    // Spectate entry route /l/<spectate_token>
    if spectate_mode {
        let expected_live = format!("/l/{}", cfg.spectate_token);
        if method == "GET" && clean_path == expected_live {
            let cookie = format!("cmdai_spectate={}; Path=/; HttpOnly; SameSite=Lax", cfg.spectate_token);
            send_response(&mut stream, "200 OK", "text/html; charset=utf-8", &[("Set-Cookie", &cookie)], INDEX_HTML.as_bytes());
            return;
        }
    }

    // Remote entry route /r/<token>
    if remote_mode {
        let expected_route = format!("/r/{}", cfg.token);
        if method == "GET" && clean_path == expected_route {
            let cookie = format!("cmdai_tok={}; Path=/; HttpOnly; SameSite=Lax", cfg.token);
            let pin_ok = !pin_required || cookies.get("cmdai_pin").map(|v| constant_time_eq(v, &cfg.pin)).unwrap_or(false);
            let html = if pin_ok { INDEX_HTML } else { PIN_GATE_HTML };
            send_response(&mut stream, "200 OK", "text/html; charset=utf-8", &[("Set-Cookie", &cookie)], html.as_bytes());
            return;
        }
    }

    // Local preview route for PIN Gate UI (only when not in remote/spectate mode)
    if !remote_mode && !spectate_mode && method == "GET" && full_path.contains("pin_preview=1") {
        send_response(&mut stream, "200 OK", "text/html; charset=utf-8", &[], PIN_GATE_HTML.as_bytes());
        return;
    }

    // Static assets (always served)
    if method == "GET" {
        match clean_path {
            "/styles.css" => { send_response(&mut stream, "200 OK", "text/css; charset=utf-8", &[], STYLES_CSS.as_bytes()); return; }
            "/app.js" => { send_response(&mut stream, "200 OK", "application/javascript; charset=utf-8", &[], APP_JS.as_bytes()); return; }
            "/editor.js" => { send_response(&mut stream, "200 OK", "application/javascript; charset=utf-8", &[], EDITOR_JS.as_bytes()); return; }
            "/map.js" => { send_response(&mut stream, "200 OK", "application/javascript; charset=utf-8", &[], MAP_JS.as_bytes()); return; }
            _ => {}
        }
    }

    // Mode discovery endpoint for Web UI
    if method == "GET" && clean_path == "/api/web/mode" {
        if spectate_mode {
            let spec_ok = cookies.get("cmdai_spectate").map(|v| constant_time_eq(v, &cfg.spectate_token)).unwrap_or(false)
                || headers.get("x-cmdai-token").map(|v| constant_time_eq(v, &cfg.spectate_token)).unwrap_or(false);
            if !spec_ok {
                send_response(&mut stream, "401 Unauthorized", "application/json", &[], br#"{"error":"Unauthorized"}"#);
                return;
            }
            send_response(&mut stream, "200 OK", "application/json", &[], br#"{"spectate":true,"readonly":true}"#);
            return;
        }
        if remote_mode {
            let tok_ok = cookies.get("cmdai_tok").map(|v| constant_time_eq(v, &cfg.token)).unwrap_or(false)
                || headers.get("x-cmdai-token").map(|v| constant_time_eq(v, &cfg.token)).unwrap_or(false);
            let pin_ok = !pin_required || cookies.get("cmdai_pin").map(|v| constant_time_eq(v, &cfg.pin)).unwrap_or(false);
            if !tok_ok || !pin_ok {
                send_response(&mut stream, "401 Unauthorized", "application/json", &[], br#"{"error":"Unauthorized"}"#);
                return;
            }
        }
        send_response(&mut stream, "200 OK", "application/json", &[], br#"{"spectate":false,"readonly":false}"#);
        return;
    }

    // Strict Read-Only Spectate gate
    if spectate_mode {
        let spec_ok = cookies.get("cmdai_spectate").map(|v| constant_time_eq(v, &cfg.spectate_token)).unwrap_or(false)
            || headers.get("x-cmdai-token").map(|v| constant_time_eq(v, &cfg.spectate_token)).unwrap_or(false);
        if !spec_ok {
            send_response(&mut stream, "401 Unauthorized", "text/plain; charset=utf-8", &[], b"Unauthorized - invalid or revoked live spectate link.");
            return;
        }
        if method != "GET" {
            send_response(&mut stream, "403 Forbidden", "application/json", &[], br#"{"error":"Spectate mode is read-only"}"#);
            return;
        }
        if clean_path == "/" {
            send_response(&mut stream, "200 OK", "text/html; charset=utf-8", &[], INDEX_HTML.as_bytes());
            return;
        }
        if clean_path == "/api/live/state" || clean_path == "/api/live/events" {
            proxy_to_backend_streaming(&mut stream, &cfg, method, full_path, &headers, &body);
            return;
        }
        send_response(&mut stream, "403 Forbidden", "application/json", &[], br#"{"error":"Spectate mode is read-only"}"#);
        return;
    }

    // Auth check for remote mode
    if remote_mode {
        let tok_ok = cookies.get("cmdai_tok").map(|v| v == &cfg.token).unwrap_or(false)
            || headers.get("x-cmdai-token").map(|v| v == &cfg.token).unwrap_or(false);
        if !tok_ok {
            send_response(&mut stream, "401 Unauthorized", "text/plain; charset=utf-8", &[], b"Unauthorized - scan the CMDAI CODE QR code to connect.");
            return;
        }
        if pin_required {
            let pin_ok = cookies.get("cmdai_pin").map(|v| v == &cfg.pin).unwrap_or(false);
            if !pin_ok {
                if clean_path == "/" {
                    send_response(&mut stream, "200 OK", "text/html; charset=utf-8", &[], PIN_GATE_HTML.as_bytes());
                } else {
                    send_response(&mut stream, "403 Forbidden", "application/json", &[], br#"{"error":"PIN required"}"#);
                }
                return;
            }
        }
    }

    // Root index.html (exact CMDAI CODE DESKTOP UI)
    if method == "GET" && clean_path == "/" {
        send_response(&mut stream, "200 OK", "text/html; charset=utf-8", &[], INDEX_HTML.as_bytes());
        return;
    }

    // Forward all /api/* calls (including SSE streaming) to FastAPI desktop_bridge
    if clean_path.starts_with("/api/") {
        proxy_to_backend_streaming(&mut stream, &cfg, method, full_path, &headers, &body);
        return;
    }

    send_response(&mut stream, "404 Not Found", "text/plain; charset=utf-8", &[], b"Not Found");
}

fn main() {
    let cfg = Arc::new(parse_args());
    let addr = format!("{}:{}", cfg.host, cfg.port);
    let listener = TcpListener::bind(&addr).unwrap_or_else(|e| {
        eprintln!("[cmdai-web] Failed to bind {}: {}", addr, e);
        std::process::exit(1);
    });
    println!("[cmdai-web] Listening on http://{} -> backend {}", addr, cfg.backend);

    for incoming in listener.incoming() {
        if let Ok(stream) = incoming {
            let cfg_ref = Arc::clone(&cfg);
            thread::spawn(move || handle_client(stream, cfg_ref));
        }
    }
}
