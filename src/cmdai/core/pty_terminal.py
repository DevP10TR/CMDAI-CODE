from __future__ import annotations

import atexit
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import winpty  # type: ignore
except Exception:
    winpty = None

if os.name != "nt":
    try:
        import fcntl
        import pty as _posix_pty
        import struct
        import termios
    except Exception:
        _posix_pty = None
        fcntl = None
        struct = None
        termios = None
else:
    _posix_pty = None
    fcntl = None
    struct = None
    termios = None


_MAX_BUFFER_CHARS = 65536


def _resolve_shell(preferred: str = "") -> Tuple[List[str], str]:
    pref = (preferred or "").strip()
    if os.name == "nt":
        candidates = []
        if pref:
            candidates.append(pref)
        candidates.extend(["pwsh.exe", "powershell.exe", "cmd.exe"])
        for c in candidates:
            exe = shutil.which(c) or (c if Path(c).is_file() else None)
            if exe:
                low = Path(exe).name.lower()
                if "pwsh" in low or "powershell" in low:
                    return [exe, "-NoLogo"], Path(exe).name
                return [exe], Path(exe).name
        return ["powershell.exe", "-NoLogo"], "powershell.exe"
    else:
        candidates = []
        if pref:
            candidates.append(pref)
        env_shell = os.environ.get("SHELL", "")
        if env_shell:
            candidates.append(env_shell)
        candidates.extend(["bash", "zsh", "sh"])
        for c in candidates:
            exe = shutil.which(c) or (c if Path(c).is_file() else None)
            if exe:
                return [exe, "-i"], Path(exe).name
        return ["/bin/sh", "-i"], "sh"


class PtyTerminalSession:
    """Thread-safe interactive PTY terminal session with SSE fan-out."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._proc: Any = None
        self._master_fd: Optional[int] = None
        self._backend: str = "none"
        self._shell_name: str = ""
        self._workdir: str = ""
        self._cols: int = 100
        self._rows: int = 28
        self._running: bool = False
        self._pid: int = 0
        self._buffer: str = ""
        self._subscribers: List[queue.Queue] = []
        self._reader_thread: Optional[threading.Thread] = None
        self._generation: int = 0

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "backend": self._backend,
                "shell": self._shell_name or ("powershell.exe" if os.name == "nt" else "bash"),
                "pid": self._pid,
                "workdir": self._workdir,
                "cols": self._cols,
                "rows": self._rows,
            }

    def _broadcast(self, event: str, payload: Any) -> None:
        with self._lock:
            if event == "data" and isinstance(payload, str):
                self._buffer += payload
                if len(self._buffer) > _MAX_BUFFER_CHARS:
                    self._buffer = self._buffer[-_MAX_BUFFER_CHARS:]
            subs = list(self._subscribers)
        item = (event, payload)
        for q in subs:
            try:
                q.put_nowait(item)
            except queue.Full:
                try:
                    q.get_nowait()
                    q.put_nowait(item)
                except Exception:
                    pass

    def subscribe(self) -> Tuple[queue.Queue, str, Dict[str, Any]]:
        q: queue.Queue = queue.Queue(maxsize=512)
        with self._lock:
            self._subscribers.append(q)
            buf = self._buffer
            st = self.get_state()
        return q, buf, st

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def clear_buffer(self) -> None:
        with self._lock:
            self._buffer = ""

    def ensure_started(
        self,
        workdir: str,
        shell: str = "",
        cols: int = 100,
        rows: int = 28,
    ) -> Dict[str, Any]:
        with self._lock:
            if self._running and self._proc is not None:
                return self.get_state()
            return self._spawn_locked(workdir=workdir, shell=shell, cols=cols, rows=rows)

    def restart(
        self,
        workdir: str,
        shell: str = "",
        cols: int = 100,
        rows: int = 28,
    ) -> Dict[str, Any]:
        with self._lock:
            self._terminate_locked()
            self._buffer = ""
            st = self._spawn_locked(workdir=workdir, shell=shell, cols=cols, rows=rows)
        self._broadcast("state", st)
        return st

    def _spawn_locked(
        self,
        workdir: str,
        shell: str = "",
        cols: int = 100,
        rows: int = 28,
    ) -> Dict[str, Any]:
        wd = str(Path(workdir).resolve()) if workdir else os.getcwd()
        if not os.path.isdir(wd):
            wd = os.getcwd()
        cols = max(20, min(400, int(cols or 100)))
        rows = max(6, min(160, int(rows or 28)))
        argv, shell_name = _resolve_shell(shell)

        self._generation += 1
        gen = self._generation
        self._workdir = wd
        self._shell_name = shell_name
        self._cols = cols
        self._rows = rows

        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")
        env.setdefault("COLORTERM", "truecolor")

        if os.name == "nt" and winpty is not None:
            proc = winpty.PtyProcess.spawn(
                argv,
                cwd=wd,
                env=env,
                dimensions=(rows, cols),
            )
            self._proc = proc
            self._master_fd = None
            self._backend = "conpty"
            self._running = True
            self._pid = int(getattr(proc, "pid", 0) or 0)
            self._reader_thread = threading.Thread(
                target=self._read_loop_winpty,
                args=(proc, gen),
                daemon=True,
                name=f"cmdai-pty-win-{gen}",
            )
            self._reader_thread.start()
        elif os.name != "nt" and _posix_pty is not None:
            master_fd, slave_fd = _posix_pty.openpty()
            try:
                if fcntl is not None and termios is not None and struct is not None:
                    winsize = struct.pack("HHHH", rows, cols, 0, 0)
                    fcntl.ioctl(slave_fd, termios.TIOCSWINSZ, winsize)
                proc = subprocess.Popen(
                    argv,
                    cwd=wd,
                    env=env,
                    stdin=slave_fd,
                    stdout=slave_fd,
                    stderr=slave_fd,
                    close_fds=True,
                    start_new_session=True,
                )
            finally:
                try:
                    os.close(slave_fd)
                except OSError:
                    pass
            self._proc = proc
            self._master_fd = master_fd
            self._backend = "pty"
            self._running = True
            self._pid = int(getattr(proc, "pid", 0) or 0)
            self._reader_thread = threading.Thread(
                target=self._read_loop_posix,
                args=(proc, master_fd, gen),
                daemon=True,
                name=f"cmdai-pty-posix-{gen}",
            )
            self._reader_thread.start()
        else:
            # Pipe fallback when winpty is unavailable
            proc = subprocess.Popen(
                argv,
                cwd=wd,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=0,
            )
            self._proc = proc
            self._master_fd = None
            self._backend = "pipe"
            self._running = True
            self._pid = int(getattr(proc, "pid", 0) or 0)
            self._reader_thread = threading.Thread(
                target=self._read_loop_pipe,
                args=(proc, gen),
                daemon=True,
                name=f"cmdai-pty-pipe-{gen}",
            )
            self._reader_thread.start()

        return self.get_state()

    def _read_loop_winpty(self, proc: Any, gen: int) -> None:
        try:
            while True:
                try:
                    chunk = proc.read(4096)
                except EOFError:
                    break
                except Exception:
                    if not proc.isalive():
                        break
                    time.sleep(0.03)
                    continue
                if not chunk:
                    if not proc.isalive():
                        break
                    time.sleep(0.02)
                    continue
                if isinstance(chunk, bytes):
                    text = chunk.decode("utf-8", errors="replace")
                else:
                    text = str(chunk)
                if text:
                    self._broadcast("data", text)
        finally:
            self._on_proc_exit(gen)

    def _read_loop_posix(self, proc: Any, master_fd: int, gen: int) -> None:
        try:
            while True:
                try:
                    raw = os.read(master_fd, 4096)
                except OSError:
                    break
                if not raw:
                    break
                self._broadcast("data", raw.decode("utf-8", errors="replace"))
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass
            self._on_proc_exit(gen)

    def _read_loop_pipe(self, proc: Any, gen: int) -> None:
        try:
            stream = proc.stdout
            if stream is None:
                return
            while True:
                raw = stream.read(1024)
                if not raw:
                    break
                self._broadcast("data", raw.decode("utf-8", errors="replace"))
        finally:
            self._on_proc_exit(gen)

    def _on_proc_exit(self, gen: int) -> None:
        with self._lock:
            if gen != self._generation:
                return
            self._running = False
            self._proc = None
            self._master_fd = None
            st = self.get_state()
        self._broadcast("data", "\r\n\x1b[90m[Process exited. Click Restart or press Enter to start a new shell.]\x1b[0m\r\n")
        self._broadcast("state", st)

    def write(self, data: str) -> bool:
        if data is None:
            return False
        with self._lock:
            if not self._running or self._proc is None:
                return False
            proc = self._proc
            backend = self._backend
            master_fd = self._master_fd
        try:
            if backend == "conpty":
                proc.write(data)
            elif backend == "pty" and master_fd is not None:
                os.write(master_fd, data.encode("utf-8", errors="replace"))
            elif backend == "pipe" and proc.stdin is not None:
                # Translate CR to CRLF/LF for piped fallback
                payload = data.replace("\r", "\n").encode("utf-8", errors="replace")
                proc.stdin.write(payload)
                proc.stdin.flush()
            else:
                return False
            return True
        except Exception:
            return False

    def resize(self, cols: int, rows: int) -> bool:
        cols = max(20, min(400, int(cols or 100)))
        rows = max(6, min(160, int(rows or 28)))
        with self._lock:
            self._cols = cols
            self._rows = rows
            if not self._running or self._proc is None:
                return False
            proc = self._proc
            backend = self._backend
            master_fd = self._master_fd
        try:
            if backend == "conpty":
                proc.setwinsize(rows, cols)
                return True
            if backend == "pty" and master_fd is not None and fcntl is not None and termios is not None and struct is not None:
                winsize = struct.pack("HHHH", rows, cols, 0, 0)
                fcntl.ioctl(master_fd, termios.TIOCSWINSZ, winsize)
                return True
        except Exception:
            pass
        return False

    def _terminate_locked(self) -> None:
        self._generation += 1
        proc = self._proc
        backend = self._backend
        master_fd = self._master_fd
        self._proc = None
        self._master_fd = None
        self._running = False
        self._pid = 0
        if proc is not None:
            try:
                if backend == "conpty":
                    if proc.isalive():
                        proc.terminate(force=True)
                else:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1.5)
                    except Exception:
                        proc.kill()
            except Exception:
                pass
        if master_fd is not None:
            try:
                os.close(master_fd)
            except OSError:
                pass

    def close(self) -> None:
        with self._lock:
            self._terminate_locked()


_GLOBAL_PTY: Optional[PtyTerminalSession] = None
_GLOBAL_PTY_LOCK = threading.Lock()


def get_pty_terminal() -> PtyTerminalSession:
    global _GLOBAL_PTY
    with _GLOBAL_PTY_LOCK:
        if _GLOBAL_PTY is None:
            _GLOBAL_PTY = PtyTerminalSession()
            atexit.register(_GLOBAL_PTY.close)
        return _GLOBAL_PTY
