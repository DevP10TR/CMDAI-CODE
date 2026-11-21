"""Standalone `cmdai code web` runner combining CMDAI CODE's `desktop_bridge` FastAPI backend
with the lightweight Rust `cmdai-web` host serving the authentic CMDAI CODE DESKTOP UI."""

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from typing import Optional

from .tunnel import get_app_root, get_rust_web_binary


def _pick_free_port(preferred: int = 8787) -> int:
    for port in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return int(s.getsockname()[1])
        except OSError:
            continue
    return 8787


def _wait_for_http(url: str, timeout: float = 15.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as r:
                if r.status < 500:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def start_desktop_bridge_process(workdir: str, port: int) -> subprocess.Popen:
    app_root = get_app_root()
    bridge_script = os.path.join(app_root, "src", "cmdai", "desktop_bridge", "server.py")
    env = os.environ.copy()
    src_dir = os.path.join(app_root, "src")
    env["PYTHONPATH"] = src_dir + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return subprocess.Popen(
        [
            sys.executable,
            bridge_script,
            "--host", "127.0.0.1",
            "--port", str(port),
            "--workdir", os.path.abspath(workdir),
        ],
        cwd=app_root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _resolve_initial_web_workdir(explicit_workdir: str) -> str:
    if explicit_workdir and os.path.isdir(explicit_workdir):
        return os.path.abspath(explicit_workdir)
    try:
        from .settings import get_settings
        cfg = get_settings().config
        ws_list = cfg.get("desktop_workspaces") or cfg.get("recent_workspaces") or []
        for ws in ws_list:
            p = ws.get("path") if isinstance(ws, dict) else ws
            if isinstance(p, str) and os.path.isdir(p):
                return os.path.abspath(p)
        last_wd = cfg.get("last_workdir") or ""
        if isinstance(last_wd, str) and os.path.isdir(last_wd):
            return os.path.abspath(last_wd)
    except Exception:
        pass
    return get_app_root()


def run_web_ui(
    workdir: str = "",
    port: int = 8787,
    open_browser: bool = True,
    provider: str = "",
    model: str = "",
) -> int:
    rust_bin = get_rust_web_binary()
    if not rust_bin:
        print("\n  [!] Rust web host binary (web/target/release/cmdai-web.exe) not found.")
        print("      Build it with: cargo build --release --manifest-path web/Cargo.toml")
        return 1

    workdir = _resolve_initial_web_workdir(workdir)

    backend_port = _pick_free_port(7860)
    web_port = _pick_free_port(port)
    web_url = f"http://127.0.0.1:{web_port}"

    print(f"\n  ⌬  CMDAI CODE · Rust Web UI")
    print(f"  {'━' * 54}")
    print(f"  · Starting CMDAI CODE backend (127.0.0.1:{backend_port})...")

    bridge_proc = start_desktop_bridge_process(workdir, backend_port)
    if not _wait_for_http(f"http://127.0.0.1:{backend_port}/api/bootstrap", timeout=15.0):
        print("  [!] Backend failed to start in time.")
        try:
            bridge_proc.terminate()
        except Exception:
            pass
        return 1

    web_proc = subprocess.Popen(
        [
            rust_bin,
            "--host", "127.0.0.1",
            "--port", str(web_port),
            "--backend", f"127.0.0.1:{backend_port}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print(f"  ● Web UI    : {web_url}")
    print(f"  ● Workspace : {os.path.abspath(workdir)}")
    print(f"  Press Ctrl+C to stop.\n")

    if open_browser:
        time.sleep(0.35)
        try:
            webbrowser.open(web_url)
        except Exception:
            pass

    def _cleanup(*_):
        for p in (web_proc, bridge_proc):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    try:
        web_proc.wait()
    finally:
        for p in (web_proc, bridge_proc):
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
    return 0
