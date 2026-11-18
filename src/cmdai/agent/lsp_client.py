import atexit
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_LSP_SERVERS: Dict[str, List[List[str]]] = {
    "python": [
        ["pyright-langserver", "--stdio"],
        ["pylsp"],
    ],
    "jsts": [
        ["typescript-language-server", "--stdio"],
    ],
}

_EXT_TO_LANG: Dict[str, Tuple[str, str]] = {
    ".py": ("python", "python"),
    ".pyw": ("python", "python"),
    ".ts": ("jsts", "typescript"),
    ".tsx": ("jsts", "typescriptreact"),
    ".js": ("jsts", "javascript"),
    ".jsx": ("jsts", "javascriptreact"),
}

_LSP_CLIENTS: Dict[Tuple[str, str], "PersistentLSPClient"] = {}
_LSP_REGISTRY_LOCK = threading.Lock()


def _detect_lsp_command(lang_group: str) -> Optional[List[str]]:
    for cmd in _LSP_SERVERS.get(lang_group, []):
        if shutil.which(cmd[0]) is not None:
            return cmd
    return None


class PersistentLSPClient:
    """Lightweight persistent JSON-RPC LSP client over stdio."""

    def __init__(self, command: List[str], workdir: str, lang_group: str):
        self.command = command
        self.workdir = os.path.abspath(workdir)
        self.lang_group = lang_group
        self._proc: Optional[subprocess.Popen] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._io_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._next_id = 1
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._events: Dict[int, threading.Event] = {}
        self._diagnostics: Dict[str, List[Dict[str, Any]]] = {}
        self._diag_events: Dict[str, threading.Event] = {}
        self._opened_versions: Dict[str, int] = {}
        self._initialized = False

    def is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> bool:
        with self._state_lock:
            if self.is_alive() and self._initialized:
                return True
            self.stop()
            try:
                cflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
                self._proc = subprocess.Popen(
                    self.command,
                    cwd=self.workdir,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    creationflags=cflags,
                )
            except Exception:
                self._proc = None
                return False

            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()

            root_uri = Path(self.workdir).as_uri()
            init_res = self._request(
                "initialize",
                {
                    "processId": os.getpid(),
                    "rootUri": root_uri,
                    "capabilities": {
                        "textDocument": {
                            "publishDiagnostics": {"relatedInformation": True},
                            "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                        }
                    },
                },
                timeout=4.0,
            )
            if init_res is None:
                self.stop()
                return False
            self._notify("initialized", {})
            self._initialized = True
            return True

    def stop(self) -> None:
        self._initialized = False
        if self._proc is not None:
            try:
                if self._proc.poll() is None:
                    self._notify("shutdown", None)
                    self._notify("exit", None)
                    self._proc.terminate()
            except Exception:
                pass
            self._proc = None

    def _send_raw(self, payload: Dict[str, Any]) -> bool:
        if not self._proc or not self._proc.stdin:
            return False
        body = json.dumps(payload).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
        try:
            with self._io_lock:
                self._proc.stdin.write(header + body)
                self._proc.stdin.flush()
            return True
        except Exception:
            return False

    def _notify(self, method: str, params: Any) -> None:
        msg: Dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        self._send_raw(msg)

    def _request(self, method: str, params: Any, timeout: float = 3.0) -> Optional[Any]:
        with self._state_lock:
            req_id = self._next_id
            self._next_id += 1
            ev = threading.Event()
            self._events[req_id] = ev

        if not self._send_raw({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params}):
            self._events.pop(req_id, None)
            return None

        if not ev.wait(timeout=timeout):
            self._events.pop(req_id, None)
            self._pending.pop(req_id, None)
            return None

        self._events.pop(req_id, None)
        resp = self._pending.pop(req_id, {})
        if "error" in resp:
            return None
        return resp.get("result")

    def _read_loop(self) -> None:
        stdout = self._proc.stdout if self._proc else None
        if stdout is None:
            return
        try:
            while self.is_alive():
                headers: Dict[str, str] = {}
                while True:
                    line = stdout.readline()
                    if not line:
                        return
                    text = line.decode("ascii", errors="ignore").strip()
                    if not text:
                        break
                    if ":" in text:
                        k, v = text.split(":", 1)
                        headers[k.strip().lower()] = v.strip()
                length = int(headers.get("content-length", "0") or "0")
                if length <= 0:
                    continue
                raw_body = stdout.read(length)
                if not raw_body:
                    return
                try:
                    msg = json.loads(raw_body.decode("utf-8", errors="replace"))
                except Exception:
                    continue

                if "id" in msg and ("result" in msg or "error" in msg):
                    req_id = msg["id"]
                    self._pending[req_id] = msg
                    ev = self._events.get(req_id)
                    if ev is not None:
                        ev.set()
                elif msg.get("method") == "textDocument/publishDiagnostics":
                    params = msg.get("params") or {}
                    uri = str(params.get("uri") or "")
                    if uri:
                        self._diagnostics[uri] = list(params.get("diagnostics") or [])
                        ev = self._diag_events.get(uri)
                        if ev is not None:
                            ev.set()
        except Exception:
            pass

    def _sync_file(self, file_path: str, language_id: str) -> str:
        uri = Path(os.path.abspath(file_path)).as_uri()
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        ver = self._opened_versions.get(uri, 0) + 1
        self._opened_versions[uri] = ver
        if ver == 1:
            self._notify(
                "textDocument/didOpen",
                {
                    "textDocument": {
                        "uri": uri,
                        "languageId": language_id,
                        "version": ver,
                        "text": text,
                    }
                },
            )
        else:
            self._notify(
                "textDocument/didChange",
                {
                    "textDocument": {"uri": uri, "version": ver},
                    "contentChanges": [{"text": text}],
                },
            )
        return uri

    def get_diagnostics(self, file_path: str, language_id: str, wait_sec: float = 1.2) -> List[Dict[str, Any]]:
        if not self.start():
            return []
        ev = threading.Event()
        uri = Path(os.path.abspath(file_path)).as_uri()
        self._diag_events[uri] = ev
        self._sync_file(file_path, language_id)
        ev.wait(timeout=wait_sec)
        self._diag_events.pop(uri, None)
        raw_diags = self._diagnostics.get(uri, [])
        sev_map = {1: "error", 2: "warning", 3: "info", 4: "hint"}
        out: List[Dict[str, Any]] = []
        for d in raw_diags:
            line_no = int((d.get("range") or {}).get("start", {}).get("line", 0)) + 1
            out.append({
                "source": self.command[0],
                "message": f"Line {line_no}: {d.get('message', '')}",
                "severity": sev_map.get(int(d.get("severity", 1) or 1), "error"),
            })
        return out

    def get_document_symbols(self, file_path: str, language_id: str) -> List[Dict[str, Any]]:
        if not self.start():
            return []
        uri = self._sync_file(file_path, language_id)
        res = self._request("textDocument/documentSymbol", {"textDocument": {"uri": uri}}, timeout=2.5)
        if not isinstance(res, list):
            return []
        rel_path = os.path.relpath(os.path.abspath(file_path), self.workdir)
        kind_map = {5: "class", 6: "method", 12: "function", 13: "variable"}
        out: List[Dict[str, Any]] = []

        def _collect(items: List[Dict[str, Any]]) -> None:
            for item in items:
                if not isinstance(item, dict):
                    continue
                rng = item.get("range") or (item.get("location") or {}).get("range") or {}
                start_line = int((rng.get("start") or {}).get("line", 0)) + 1
                end_line = int((rng.get("end") or {}).get("line", start_line - 1)) + 1
                kind_name = kind_map.get(int(item.get("kind", 0) or 0), "symbol")
                name = str(item.get("name") or "")
                if name:
                    out.append({
                        "name": name,
                        "filepath": rel_path,
                        "symbol_type": kind_name,
                        "start_line": start_line,
                        "end_line": end_line,
                        "signature": str(item.get("detail") or name),
                        "docstring": "",
                    })
                if isinstance(item.get("children"), list):
                    _collect(item["children"])

        _collect(res)
        return sorted(out, key=lambda s: s["start_line"])


def get_lsp_client(file_path: str, workdir: Optional[str] = None) -> Tuple[Optional[PersistentLSPClient], str]:
    ext = os.path.splitext(file_path)[1].lower()
    lang_info = _EXT_TO_LANG.get(ext)
    if not lang_info:
        return None, ""
    lang_group, language_id = lang_info
    cmd = _detect_lsp_command(lang_group)
    if not cmd:
        return None, language_id
    abs_workdir = os.path.abspath(workdir or os.path.dirname(os.path.abspath(file_path)))
    key = (lang_group, abs_workdir)
    with _LSP_REGISTRY_LOCK:
        client = _LSP_CLIENTS.get(key)
        if client is None:
            client = PersistentLSPClient(cmd, abs_workdir, lang_group)
            _LSP_CLIENTS[key] = client
    return client, language_id


def shutdown_all_lsp_clients() -> None:
    with _LSP_REGISTRY_LOCK:
        for client in _LSP_CLIENTS.values():
            try:
                client.stop()
            except Exception:
                pass
        _LSP_CLIENTS.clear()


atexit.register(shutdown_all_lsp_clients)


def is_tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def run_file_diagnostics(file_path: str, workdir: Optional[str] = None) -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        return []

    ext = os.path.splitext(file_path)[1].lower()
    cwd = workdir or os.path.dirname(os.path.abspath(file_path))
    diagnostics: List[Dict[str, Any]] = []

    try:
        client, lang_id = get_lsp_client(file_path, cwd)
        if client is not None and lang_id:
            lsp_diags = client.get_diagnostics(file_path, lang_id)
            if lsp_diags:
                return lsp_diags
    except Exception:
        pass

    if ext == ".py":
        if is_tool_available("ruff"):
            try:
                res = subprocess.run(
                    ["ruff", "check", "--output-format=concise", file_path],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                for line in res.stdout.splitlines():
                    clean = line.strip()
                    if clean and ":" in clean:
                        diagnostics.append({"source": "ruff", "message": clean, "severity": "error" if "E" in clean or "F" in clean else "warning"})
            except Exception:
                pass
        elif is_tool_available("pyright"):
            try:
                res = subprocess.run(
                    ["pyright", "--outputjson", file_path],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                import json
                data = json.loads(res.stdout or "{}")
                for d in data.get("generalDiagnostics", []):
                    diagnostics.append({
                        "source": "pyright",
                        "message": f"Line {d.get('range', {}).get('start', {}).get('line', 0) + 1}: {d.get('message', '')}",
                        "severity": d.get("severity", "error"),
                    })
            except Exception:
                pass

        if not diagnostics:
            try:
                import ast
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                ast.parse(content, filename=file_path)
            except SyntaxError as e:
                diagnostics.append({
                    "source": "syntax",
                    "message": f"SyntaxError line {e.lineno or 1}: {e.msg}",
                    "severity": "error"
                })
            except Exception:
                pass

    elif ext in (".ts", ".tsx", ".js", ".jsx"):
        if is_tool_available("tsc"):
            try:
                res = subprocess.run(
                    ["tsc", "--noEmit", file_path],
                    cwd=cwd,
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                for line in res.stdout.splitlines():
                    clean = line.strip()
                    if "error TS" in clean:
                        diagnostics.append({"source": "tsc", "message": clean, "severity": "error"})
            except Exception:
                pass

    return diagnostics


def format_diagnostics_summary(diagnostics: List[Dict[str, Any]]) -> str:
    if not diagnostics:
        return ""
    lines = ["[LSP DIAGNOSTICS DETECTED]"]
    for d in diagnostics[:5]:
        lines.append(f"• [{d.get('source', 'lsp')}] {d.get('message', '')}")
    if len(diagnostics) > 5:
        lines.append(f"... and {len(diagnostics) - 5} more diagnostic warnings.")
    return "\n".join(lines)


_IGNORED_DIRS = {
    ".git", ".svn", "node_modules", "venv", ".venv", "env",
    "__pycache__", ".pytest_cache", ".cmdai_code_project",
    "dist", "build", "target", ".idea", ".vscode",
}

_CODE_EXTS = {
    ".py", ".pyw", ".js", ".ts", ".jsx", ".tsx",
    ".json", ".toml", ".md", ".yaml", ".yml",
    ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".java",
}


def get_document_symbols(file_path: str, workdir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return AST/indexed symbols (outline) for a single file."""
    abs_workdir = os.path.abspath(workdir) if workdir else os.path.dirname(os.path.abspath(file_path))
    full_path = file_path if os.path.isabs(file_path) else os.path.join(abs_workdir, file_path)
    full_path = os.path.abspath(full_path)
    if not os.path.isfile(full_path):
        return []

    rel_path = os.path.relpath(full_path, abs_workdir)
    try:
        client, lang_id = get_lsp_client(full_path, abs_workdir)
        if client is not None and lang_id:
            lsp_syms = client.get_document_symbols(full_path, lang_id)
            if lsp_syms:
                return lsp_syms
    except Exception:
        pass

    try:
        from ..indexer.ast_indexer import ProjectIndexer
        indexer = ProjectIndexer(abs_workdir)
        indexer.index_file(full_path)
        syms = indexer.db.get_file_symbols(rel_path)
        if syms:
            return syms
    except Exception:
        pass

    try:
        from ..indexer.ast_indexer import extract_symbols_from_code
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        raw = extract_symbols_from_code(rel_path, content)
        return [
            {
                "name": s.get("name", ""),
                "filepath": rel_path,
                "symbol_type": s.get("type", "symbol"),
                "start_line": s.get("start_line", 1),
                "end_line": s.get("end_line", 1),
                "signature": s.get("signature", ""),
                "docstring": s.get("docstring", ""),
            }
            for s in sorted(raw, key=lambda item: item.get("start_line", 1))
        ]
    except Exception:
        return []


def find_references(symbol: str, workdir: str = ".", limit: int = 30) -> List[Dict[str, Any]]:
    """Find whole-word references to a symbol across workspace code files."""
    clean = (symbol or "").strip()
    if not clean or len(clean) > 120:
        return []

    abs_workdir = os.path.abspath(workdir or ".")
    if not os.path.isdir(abs_workdir):
        return []

    pattern = re.compile(rf"\b{re.escape(clean)}\b")
    refs: List[Dict[str, Any]] = []

    for root, dirs, files in os.walk(abs_workdir):
        dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS and not d.startswith(".")]
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext not in _CODE_EXTS:
                continue
            full_path = os.path.join(root, filename)
            try:
                if os.path.getsize(full_path) > 512 * 1024:
                    continue
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, 1):
                        if pattern.search(line):
                            refs.append({
                                "filepath": os.path.relpath(full_path, abs_workdir),
                                "line": lineno,
                                "text": line.strip()[:160],
                            })
                            if len(refs) >= limit:
                                return refs
            except Exception:
                continue

    return refs
