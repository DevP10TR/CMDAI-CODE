"""Standalone terminal host window for CMDAI CODE `/tunnel` and `/share`.

Runs inside a dedicated Windows console window (`CREATE_NEW_CONSOLE`) so:
- Opening `/tunnel` or `/share` displays a clean QR code + Cloudflare URL dashboard.
- Closing this terminal window (or pressing Q / Ctrl+C) immediately kills `cloudflared`,
  shuts down the local share/web server, and revokes any active remote pairing token.
"""

import argparse
import http.server
import importlib.util
import os
import re
import secrets
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from typing import Optional

# Load sibling tunnel.py directly by file path so an installed `cmdai` package
# in site-packages or root `cmdai.py` can never shadow `src/cmdai/core/tunnel.py`.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
if _SRC_DIR in sys.path:
    sys.path.remove(_SRC_DIR)
sys.path.insert(0, _SRC_DIR)

_tunnel_spec = importlib.util.spec_from_file_location(
    "_cmdai_code_tunnel_mod", os.path.join(_THIS_DIR, "tunnel.py")
)
assert _tunnel_spec is not None and _tunnel_spec.loader is not None
_tunnel_mod = importlib.util.module_from_spec(_tunnel_spec)
_tunnel_spec.loader.exec_module(_tunnel_mod)

TRYCLOUDFLARE_RE = _tunnel_mod.TRYCLOUDFLARE_RE
find_cloudflared = _tunnel_mod.find_cloudflared
get_rust_web_binary = _tunnel_mod.get_rust_web_binary
render_qr_unicode = _tunnel_mod.render_qr_unicode


def _enable_ansi() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            k32 = ctypes.windll.kernel32
            h = k32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            if k32.GetConsoleMode(h, ctypes.byref(mode)):
                k32.SetConsoleMode(h, mode.value | 0x0004)
        except Exception:
            pass


def _copy_clipboard(text: str) -> bool:
    try:
        if sys.platform == "win32":
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=False)
            p.communicate(input=text.encode("utf-8"))
            return p.returncode == 0
    except Exception:
        pass
    return False


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _revoke_remote_backend(backend_port: int, token: str) -> None:
    if not backend_port or not token:
        return
    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{backend_port}/api/remote/revoke",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "X-CMDAI-Token": token,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=2.0)
    except Exception:
        pass


def _start_share_http_server(html_path: str, token: str) -> tuple[socketserver.ThreadingTCPServer, int]:
    state = {"html": b""}

    def _reload() -> None:
        try:
            with open(html_path, "rb") as f:
                state["html"] = f.read()
        except Exception:
            state["html"] = b"<html><body><h1>Session unavailable</h1></body></html>"

    _reload()
    target_path = f"/s/{token}"

    class ShareHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            clean_path = self.path.split("?", 1)[0]
            if clean_path == target_path or clean_path == "/":
                body = state["html"]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("X-Robots-Tag", "noindex, nofollow")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
            else:
                msg = b"Not Found"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)

    port = _pick_free_port()
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), ShareHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv, port


def _start_cloudflared(cf_bin: str, local_url: str, timeout: float = 25.0) -> tuple[subprocess.Popen, Optional[str]]:
    proc = subprocess.Popen(
        [cf_bin, "tunnel", "--url", local_url, "--no-autoupdate"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    found_url: list[Optional[str]] = [None]
    done = threading.Event()

    def _reader() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            m = TRYCLOUDFLARE_RE.search(line)
            if m and not found_url[0]:
                found_url[0] = m.group(0)
                done.set()

    threading.Thread(target=_reader, daemon=True).start()
    done.wait(timeout=timeout)
    return proc, found_url[0]


def _render_dashboard(
    mode: str,
    public_url: str,
    local_url: str,
    pin: str = "",
    title: str = "",
    copied: bool = False,
) -> None:
    os.system("cls" if sys.platform == "win32" else "clear")
    accent = "\033[38;5;75m"
    green = "\033[38;5;114m"
    amber = "\033[38;5;215m"
    dim = "\033[38;5;244m"
    bold = "\033[1m"
    reset = "\033[0m"

    heading = "REMOTE TUNNEL · PHONE ↔ PC" if mode == "tunnel" else "LIVE SESSION SHARE · READ-ONLY"
    print(f"\n  {accent}{bold}⌬  CMDAI CODE{reset}  {dim}·  {heading}{reset}")
    print(f"  {dim}{'━' * 62}{reset}\n")

    if title:
        print(f"  {dim}Session   :{reset} {bold}{title}{reset}")
    print(f"  {dim}Public URL:{reset} {green}{bold}{public_url}{reset}")
    if pin:
        print(f"  {dim}Pair PIN  :{reset} {amber}{bold}{pin}{reset}  {dim}(required on first browser visit){reset}")
    print(f"  {dim}Local Host:{reset} {dim}{local_url}{reset}")
    if copied:
        print(f"  {green}✔ Link copied to clipboard.{reset}")

    print(f"\n  {dim}Scan QR code on your phone:{reset}\n")
    print(render_qr_unicode(public_url, border=2, indent="    "))

    print(f"\n  {dim}{'─' * 62}{reset}")
    if mode == "tunnel":
        print(f"  {green}● ONLINE{reset}  {dim}Close this window or press [Q] to disconnect remote access.{reset}")
    else:
        print(f"  {green}● SHARED{reset}  {dim}Close this window or press [Q] to stop sharing immediately.{reset}")
    print(f"  {dim}[C] Copy URL   [Q] Stop & Close{reset}\n")


def main() -> int:
    _enable_ansi()
    parser = argparse.ArgumentParser(description="CMDAI CODE Cloudflare Tunnel Console")
    parser.add_argument("--mode", choices=["tunnel", "share"], required=True)
    parser.add_argument("--backend-port", type=int, default=8080)
    parser.add_argument("--token", default="")
    parser.add_argument("--pin", default="")
    parser.add_argument("--share-file", default="")
    parser.add_argument("--title", default="")
    parser.add_argument("--session-id", default="")
    args = parser.parse_args()

    cf_bin = find_cloudflared()
    if not cf_bin:
        print("\n  [!] cloudflared not found. Please install it via /tunnel or /share in CMDAI CODE.")
        input("\n  Press Enter to close...")
        return 1

    if sys.platform == "win32":
        try:
            title_str = "CMDAI CODE — Remote Tunnel" if args.mode == "tunnel" else "CMDAI CODE — Session Share"
            os.system(f"title {title_str}")
        except Exception:
            pass

    token = args.token or secrets.token_urlsafe(18)
    bridge_proc: Optional[subprocess.Popen] = None
    web_proc: Optional[subprocess.Popen] = None
    share_srv: Optional[socketserver.ThreadingTCPServer] = None
    cf_proc: Optional[subprocess.Popen] = None

    def _cleanup() -> None:
        for proc in (cf_proc, web_proc, bridge_proc):
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        if share_srv:
            try:
                share_srv.shutdown()
                share_srv.server_close()
            except Exception:
                pass
        if args.mode == "tunnel":
            _revoke_remote_backend(args.backend_port, token)
        if args.mode == "share" and args.share_file and os.path.isfile(args.share_file):
            try:
                os.remove(args.share_file)
            except Exception:
                pass

    def _sig_handler(signum, frame):
        _cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _sig_handler)

    try:
        print("\n  ⌬  CMDAI CODE — Starting Cloudflare Quick Tunnel...")
        if args.mode == "share":
            if not args.share_file or not os.path.isfile(args.share_file):
                print("  [!] Share HTML file missing.")
                input("\n  Press Enter to close...")
                return 1
            share_srv, local_port = _start_share_http_server(args.share_file, token)
            local_url = f"http://127.0.0.1:{local_port}"
            route_suffix = f"/s/{token}"
        else:
            rust_web = get_rust_web_binary()
            if rust_web:
                # Start the full desktop_bridge FastAPI backend so the exact CMDAI CODE DESKTOP UI
                # works with 100% real features (chat, editor, mind map, diff, models, settings, voice)
                bridge_port = _pick_free_port()
                app_root = os.path.abspath(os.path.join(_THIS_DIR, "..", "..", ".."))
                bridge_script = os.path.join(app_root, "src", "cmdai", "desktop_bridge", "server.py")
                env = os.environ.copy()
                env["PYTHONPATH"] = _SRC_DIR + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
                bridge_proc = subprocess.Popen(
                    [
                        sys.executable,
                        bridge_script,
                        "--host", "127.0.0.1",
                        "--port", str(bridge_port),
                        "--workdir", os.getcwd(),
                    ],
                    cwd=app_root,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                # Wait briefly for FastAPI bridge to accept connections
                deadline = time.time() + 12.0
                while time.time() < deadline:
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{bridge_port}/api/bootstrap", timeout=1.0) as r:
                            if r.status < 500:
                                break
                    except Exception:
                        time.sleep(0.25)

                web_port = _pick_free_port()
                web_cmd = [
                    rust_web,
                    "--host", "127.0.0.1",
                    "--port", str(web_port),
                    "--backend", f"127.0.0.1:{bridge_port}",
                    "--token", token,
                ]
                if args.pin:
                    web_cmd += ["--pin", args.pin]
                web_proc = subprocess.Popen(
                    web_cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(0.35)
                local_url = f"http://127.0.0.1:{web_port}"
            else:
                local_url = f"http://127.0.0.1:{args.backend_port}"
            route_suffix = f"/r/{token}"

        cf_proc, base_url = _start_cloudflared(cf_bin, local_url, timeout=25.0)
        if not base_url:
            print("\n  [!] Timed out waiting for trycloudflare.com URL.")
            print("      Check your internet connection and try again.")
            input("\n  Press Enter to close...")
            return 1

        public_url = f"{base_url}{route_suffix}"
        copied = _copy_clipboard(public_url)
        _render_dashboard(
            mode=args.mode,
            public_url=public_url,
            local_url=local_url,
            pin=args.pin,
            title=args.title,
            copied=copied,
        )

        # Interactive key loop
        if sys.platform == "win32":
            import msvcrt
            while True:
                if cf_proc.poll() is not None:
                    print("\n  [!] cloudflared tunnel exited unexpectedly.")
                    break
                if msvcrt.kbhit():
                    ch = msvcrt.getwch().lower()
                    if ch in ("q", "\x03", "\x1b"):
                        break
                    elif ch == "c":
                        ok = _copy_clipboard(public_url)
                        _render_dashboard(
                            mode=args.mode,
                            public_url=public_url,
                            local_url=local_url,
                            pin=args.pin,
                            title=args.title,
                            copied=ok,
                        )
                time.sleep(0.1)
        else:
            while cf_proc.poll() is None:
                time.sleep(0.5)
    finally:
        _cleanup()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:
        print("\n  [!] Unexpected error in CMDAI CODE Tunnel Console:\n")
        traceback.print_exc()
        try:
            input("\n  Press Enter to close...")
        except Exception:
            pass
        raise SystemExit(1)
