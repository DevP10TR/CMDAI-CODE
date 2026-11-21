import http.server
import json
import os
import secrets
import socketserver
import threading
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .model_directory import (
    get_structured_directory,
    record_recent_model,
    toggle_pin_model,
)
from .sessions import SessionManager, clean_title_from_prompt, format_relative_time
from .web_overview import (
    build_ast_overview,
    get_git_overview,
    get_settings_payload,
    list_workspace_files,
    read_workspace_file,
    transcribe_web_voice_wav,
    update_settings_payload,
)


class BackgroundHTTPServer:

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8080,
        app_ref: Optional[Any] = None,
    ):
        self.host = host
        self.port = port
        self.app_ref = app_ref
        self._server: Optional[socketserver.ThreadingTCPServer] = None
        self._thread: Optional[threading.Thread] = None
        self.is_running = False

        # Remote tunnel auth state (enabled by /tunnel; empty token when local-only web mode)
        self._lock = threading.Lock()
        self._remote_token: str = ""
        self._remote_pin: str = ""
        self._remote_enabled: bool = False
        self._allow_local_web: bool = False

    def start(self) -> bool:
        if self.is_running:
            return True

        handler_cls = self._create_handler()
        for candidate_port in (self.port, 0):
            try:
                socketserver.ThreadingTCPServer.allow_reuse_address = True
                self._server = socketserver.ThreadingTCPServer((self.host, candidate_port), handler_cls)
                self.port = int(self._server.server_address[1])
                self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
                self._thread.start()
                self.is_running = True
                return True
            except Exception:
                self._server = None
        self.is_running = False
        return False

    def stop(self) -> None:
        if self._server:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            self._server = None
        self.is_running = False

    def enable_remote(self, pin: Optional[str] = None) -> Tuple[str, str]:
        with self._lock:
            token = secrets.token_urlsafe(18)
            pin_val = pin if pin is not None else f"{secrets.randbelow(1000000):06d}"
            self._remote_token = token
            self._remote_pin = pin_val
            self._remote_enabled = True
            return token, pin_val

    def enable_local_web(self) -> None:
        with self._lock:
            self._allow_local_web = True

    def revoke_remote(self) -> None:
        with self._lock:
            self._remote_token = ""
            self._remote_pin = ""
            self._remote_enabled = False

    def is_remote_authorized(self, token_header: str) -> bool:
        with self._lock:
            if self._allow_local_web and not self._remote_enabled:
                return True
            if self._remote_enabled and self._remote_token and token_header == self._remote_token:
                return True
            return self._allow_local_web

    def _get_state_payload(self) -> Dict[str, Any]:
        app = self.app_ref
        if app is None:
            return {
                "messages": [],
                "streaming_text": "",
                "is_generating": False,
                "model_id": "",
                "provider_id": "",
                "mode": "auto",
                "workdir": os.getcwd(),
                "session_id": "",
                "session_title": "CMDAI CODE",
            }

        raw_msgs = list(getattr(app, "messages", []) or [])
        ui_msgs: List[Dict[str, Any]] = []
        for m in raw_msgs:
            role = m.get("role", "")
            if role not in ("user", "assistant"):
                continue
            content = m.get("content", "")
            if isinstance(content, list):
                content = "\n".join(
                    str(part.get("text", "")) for part in content if isinstance(part, dict)
                )
            ui_msgs.append({
                "role": role,
                "content": str(content or ""),
                "thinking": str(m.get("thinking") or ""),
                "tools": m.get("tools") or [],
                "model": str(m.get("model") or getattr(app, "current_model_id", "")),
            })

        title = "CMDAI CODE"
        for m in ui_msgs:
            if m["role"] == "user" and m["content"].strip():
                title = clean_title_from_prompt(m["content"]) or "CMDAI CODE"
                break

        mode = str(getattr(app, "agent_mode", None) or getattr(app, "mode", "auto") or "auto").lower()
        return {
            "messages": ui_msgs,
            "streaming_text": str(getattr(app, "_remote_stream_buffer", "") or ""),
            "is_generating": bool(getattr(app, "is_generating", False)),
            "model_id": str(getattr(app, "current_model_id", "") or ""),
            "provider_id": str(getattr(app, "current_provider", "") or ""),
            "mode": mode,
            "workdir": str(getattr(app, "workdir", os.getcwd()) or ""),
            "session_id": str(getattr(app, "current_session_id", "") or ""),
            "session_title": title,
        }

    def _get_sessions_payload(self) -> Dict[str, Any]:
        app = self.app_ref
        workdir = getattr(app, "workdir", os.getcwd()) if app else os.getcwd()
        sm: SessionManager = getattr(app, "session_manager", None) or SessionManager(project_dir=workdir)
        raw_list = sm.list_sessions(current_dir=workdir) or []
        out = []
        for item in raw_list[:60]:
            out.append({
                "id": item.get("id", ""),
                "title": item.get("title") or item.get("id", "Session"),
                "updated_rel": format_relative_time(item.get("updated_at") or item.get("timestamp")),
                "msg_count": int(item.get("msg_count") or item.get("message_count") or 0),
                "model": item.get("model") or "",
            })
        return {"sessions": out}

    def _call_app(self, fn_name: str, *args: Any) -> bool:
        app = self.app_ref
        if app is None:
            return False
        fn = getattr(app, fn_name, None)
        if not callable(fn):
            return False
        call_from_thread = getattr(app, "call_from_thread", None)
        if callable(call_from_thread):
            try:
                call_from_thread(fn, *args)
                return True
            except Exception:
                pass
        try:
            fn(*args)
            return True
        except Exception:
            return False

    def _create_handler(self):
        server_self = self

        class CMDAIHTTPHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def _check_remote_auth(self) -> bool:
                tok = self.headers.get("X-CMDAI-Token", "")
                if server_self.is_remote_authorized(tok):
                    return True
                self._send_json({"error": "Unauthorized"}, status=401)
                return False

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path
                query = parse_qs(parsed.query)

                if path in ("/", "/api/version"):
                    self._send_json({
                        "version": "1.2.0",
                        "status": "CMDAI CODE background server online",
                        "active_model": getattr(server_self.app_ref, "current_model_id", "none"),
                    })
                elif path == "/api/tags":
                    self._send_json({
                        "models": [
                            {
                                "name": getattr(server_self.app_ref, "current_model_id", "cmdai-code"),
                                "model": getattr(server_self.app_ref, "current_model_id", "cmdai-code"),
                                "modified_at": "2026-11-19T00:00:00Z",
                                "size": 7000000000,
                            }
                        ]
                    })
                elif path == "/api/remote/state":
                    if not self._check_remote_auth():
                        return
                    self._send_json(server_self._get_state_payload())
                elif path == "/api/remote/sessions":
                    if not self._check_remote_auth():
                        return
                    self._send_json(server_self._get_sessions_payload())
                elif path == "/api/remote/models":
                    if not self._check_remote_auth():
                        return
                    force = query.get("refresh", ["0"])[0] in ("1", "true")
                    app = server_self.app_ref
                    ap = getattr(app, "current_provider", "") if app else ""
                    am = getattr(app, "current_model_id", "") if app else ""
                    directory = get_structured_directory(
                        active_provider=ap,
                        active_model=am,
                        force_refresh=force,
                    )
                    self._send_json(directory)
                elif path == "/api/remote/ast":
                    if not self._check_remote_auth():
                        return
                    wd = getattr(server_self.app_ref, "workdir", os.getcwd()) if server_self.app_ref else os.getcwd()
                    self._send_json(build_ast_overview(wd))
                elif path == "/api/remote/git":
                    if not self._check_remote_auth():
                        return
                    wd = getattr(server_self.app_ref, "workdir", os.getcwd()) if server_self.app_ref else os.getcwd()
                    self._send_json(get_git_overview(wd))
                elif path == "/api/remote/files":
                    if not self._check_remote_auth():
                        return
                    wd = getattr(server_self.app_ref, "workdir", os.getcwd()) if server_self.app_ref else os.getcwd()
                    self._send_json({"files": list_workspace_files(wd)})
                elif path == "/api/remote/file":
                    if not self._check_remote_auth():
                        return
                    wd = getattr(server_self.app_ref, "workdir", os.getcwd()) if server_self.app_ref else os.getcwd()
                    rel = query.get("path", [""])[0]
                    self._send_json(read_workspace_file(wd, rel))
                elif path == "/api/remote/settings":
                    if not self._check_remote_auth():
                        return
                    self._send_json(get_settings_payload())
                else:
                    self._send_json({"error": "Endpoint not found"}, status=404)

            def do_POST(self):
                parsed = urlparse(self.path)
                path = parsed.path
                content_len = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_len).decode("utf-8", errors="replace") if content_len > 0 else "{}"
                try:
                    data = json.loads(body)
                except Exception:
                    data = {}

                if path in ("/api/chat", "/api/generate", "/v1/chat/completions"):
                    self._send_json({
                        "id": "chatcmpl-cmdai",
                        "object": "chat.completion",
                        "choices": [
                            {
                                "message": {
                                    "role": "assistant",
                                    "content": "CMDAI CODE background server response.",
                                },
                                "finish_reason": "stop",
                            }
                        ],
                    })
                elif path == "/api/remote/prompt":
                    if not self._check_remote_auth():
                        return
                    prompt = str(data.get("prompt", "")).strip()
                    if not prompt:
                        self._send_json({"ok": False, "error": "Empty prompt"}, status=400)
                        return
                    ok = server_self._call_app("submit_remote_prompt", prompt)
                    self._send_json({"ok": ok})
                elif path == "/api/remote/stop":
                    if not self._check_remote_auth():
                        return
                    ok = server_self._call_app("stop_remote_generation")
                    self._send_json({"ok": ok})
                elif path == "/api/remote/mode":
                    if not self._check_remote_auth():
                        return
                    mode = str(data.get("mode", "auto")).strip().lower()
                    ok = server_self._call_app("set_remote_mode", mode)
                    self._send_json({"ok": ok, "mode": mode})
                elif path == "/api/remote/models/select":
                    if not self._check_remote_auth():
                        return
                    pid = str(data.get("provider_id", "")).strip()
                    mid = str(data.get("model_id", "")).strip()
                    if not pid or not mid:
                        self._send_json({"ok": False, "error": "Missing provider_id or model_id"}, status=400)
                        return
                    record_recent_model(pid, mid)
                    ok = server_self._call_app("select_remote_model", pid, mid)
                    self._send_json({"ok": ok, "provider_id": pid, "model_id": mid})
                elif path == "/api/remote/models/pin":
                    if not self._check_remote_auth():
                        return
                    pid = str(data.get("provider_id", "")).strip()
                    mid = str(data.get("model_id", "")).strip()
                    pinned = toggle_pin_model(pid, mid)
                    self._send_json({"ok": True, "pinned": pinned})
                elif path == "/api/remote/sessions/select":
                    if not self._check_remote_auth():
                        return
                    sid = str(data.get("session_id", "")).strip()
                    ok = server_self._call_app("select_remote_session", sid)
                    self._send_json({"ok": ok, "session_id": sid})
                elif path == "/api/remote/sessions/new":
                    if not self._check_remote_auth():
                        return
                    ok = server_self._call_app("new_remote_session")
                    self._send_json({"ok": ok})
                elif path == "/api/remote/revoke":
                    if not self._check_remote_auth():
                        return
                    server_self.revoke_remote()
                    self._send_json({"ok": True})
                elif path == "/api/remote/settings":
                    if not self._check_remote_auth():
                        return
                    updated = update_settings_payload(data if isinstance(data, dict) else {})
                    self._send_json({"ok": True, "settings": updated})
                elif path == "/api/remote/voice/transcribe":
                    if not self._check_remote_auth():
                        return
                    wav_b64 = str(data.get("audio_wav_base64") or "")
                    res = transcribe_web_voice_wav(wav_b64)
                    self._send_json(res, status=200 if res.get("ok") else 400)
                else:
                    self._send_json({"error": "Endpoint not found"}, status=404)

            def _send_json(self, data: Dict[str, Any], status: int = 200):
                payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)

        return CMDAIHTTPHandler
