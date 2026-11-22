import atexit
import glob as py_glob
import os
import re
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from .verifier import verify_code_syntax
from .test_runner import run_project_tests


class AgentContext:
    def __init__(self, workdir: str = "."):
        self._workdir = os.path.abspath(workdir)
        self.current_cwd = self._workdir

    @property
    def workdir(self) -> str:
        return self._workdir

    @workdir.setter
    def workdir(self, value: str) -> None:
        new_w = os.path.abspath(value or ".")
        self._workdir = new_w
        self.current_cwd = new_w
        self.session_id: str = ""
        self.todo_list: List[str] = []
        self.mode: str = "auto"
        self.pending_images: List[Dict[str, str]] = []
        self.on_before_file_modify: Optional[Callable[[str], None]] = None

    def resolve_path(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        base = getattr(self, "current_cwd", None) or self.workdir
        cand = os.path.normpath(os.path.join(base, path))
        if os.path.exists(cand):
            return cand
        return os.path.normpath(os.path.join(self.workdir, path))

    def rel_path(self, path: str) -> str:
        try:
            return os.path.relpath(path, self.workdir)
        except Exception:
            return path


def _smart_replace(content: str, old: str, new: str) -> Optional[Tuple[str, int, str]]:
    """OpenCode-inspired multi-stage replacer.

    Returns `(new_content, start_line_1based, matched_old_text)` or `None` if no
    stage could uniquely locate `old` inside `content`.
    """
    if not old:
        return None

    # Stage 1: Exact substring match
    if old in content:
        idx = content.find(old)
        line_no = content[:idx].count("\n") + 1
        return content.replace(old, new, 1), line_no, old

    # Stage 2: CRLF / LF normalized match
    use_crlf = "\r\n" in content
    norm_content = content.replace("\r\n", "\n")
    norm_old = old.replace("\r\n", "\n")
    norm_new = new.replace("\r\n", "\n")
    if norm_old in norm_content:
        idx = norm_content.find(norm_old)
        line_no = norm_content[:idx].count("\n") + 1
        replaced = norm_content.replace(norm_old, norm_new, 1)
        if use_crlf:
            replaced = replaced.replace("\n", "\r\n")
        return replaced, line_no, norm_old

    content_lines = norm_content.split("\n")
    old_lines = norm_old.strip("\n").split("\n")
    new_lines = norm_new.strip("\n").split("\n")
    n_old = len(old_lines)
    if n_old == 0 or n_old > len(content_lines):
        return None

    # Stage 3: Line-trimmed match (ignores trailing spaces on each line)
    old_rstripped = [ln.rstrip() for ln in old_lines]
    for i in range(len(content_lines) - n_old + 1):
        window = content_lines[i : i + n_old]
        if [ln.rstrip() for ln in window] == old_rstripped:
            matched_old = "\n".join(window)
            replaced_lines = content_lines[:i] + new_lines + content_lines[i + n_old :]
            replaced = ("\r\n" if use_crlf else "\n").join(replaced_lines)
            return replaced, i + 1, matched_old

    # Stage 4: Indentation-flexible match (preserves file's actual base indentation)
    def _min_indent(lines_list: List[str]) -> int:
        non_empty = [len(ln) - len(ln.lstrip(" \t")) for ln in lines_list if ln.strip()]
        return min(non_empty) if non_empty else 0

    old_base_indent = _min_indent(old_lines)
    old_dedented = [
        (ln[old_base_indent:].rstrip() if len(ln) >= old_base_indent else ln.strip())
        for ln in old_lines
    ]
    for i in range(len(content_lines) - n_old + 1):
        window = content_lines[i : i + n_old]
        win_base_indent = _min_indent(window)
        win_dedented = [
            (ln[win_base_indent:].rstrip() if len(ln) >= win_base_indent else ln.strip())
            for ln in window
        ]
        if win_dedented == old_dedented and any(ln.strip() for ln in old_dedented):
            # Calculate indentation delta and apply to new_lines
            first_non_empty_win = next((ln for ln in window if ln.strip()), "")
            indent_prefix = first_non_empty_win[: len(first_non_empty_win) - len(first_non_empty_win.lstrip(" \t"))]
            new_base_indent = _min_indent(new_lines)
            adjusted_new = []
            for nl in new_lines:
                if not nl.strip():
                    adjusted_new.append("")
                else:
                    rel = nl[new_base_indent:] if len(nl) >= new_base_indent else nl.lstrip(" \t")
                    adjusted_new.append(indent_prefix + rel)
            matched_old = "\n".join(window)
            replaced_lines = content_lines[:i] + adjusted_new + content_lines[i + n_old :]
            replaced = ("\r\n" if use_crlf else "\n").join(replaced_lines)
            return replaced, i + 1, matched_old

    # Stage 5: Whitespace-collapsed line match (tolerates internal spacing differences)
    old_collapsed = [" ".join(ln.split()) for ln in old_lines]
    if any(old_collapsed):
        matches: List[Tuple[int, List[str]]] = []
        for i in range(len(content_lines) - n_old + 1):
            window = content_lines[i : i + n_old]
            if [" ".join(ln.split()) for ln in window] == old_collapsed:
                matches.append((i, window))
        if len(matches) == 1:
            i, window = matches[0]
            first_non_empty_win = next((ln for ln in window if ln.strip()), "")
            indent_prefix = first_non_empty_win[: len(first_non_empty_win) - len(first_non_empty_win.lstrip(" \t"))]
            new_base_indent = _min_indent(new_lines)
            adjusted_new = []
            for nl in new_lines:
                if not nl.strip():
                    adjusted_new.append("")
                else:
                    rel = nl[new_base_indent:] if len(nl) >= new_base_indent else nl.lstrip(" \t")
                    adjusted_new.append(indent_prefix + rel)
            matched_old = "\n".join(window)
            replaced_lines = content_lines[:i] + adjusted_new + content_lines[i + n_old :]
            replaced = ("\r\n" if use_crlf else "\n").join(replaced_lines)
            return replaced, i + 1, matched_old

    return None


def tool_read(ctx: AgentContext, path: str, lines: Optional[str] = None) -> Dict[str, Any]:
    full_path = ctx.resolve_path(path)
    if not os.path.exists(full_path):
        parent_dir = os.path.dirname(full_path)
        if not parent_dir or not os.path.isdir(parent_dir):
            parent_dir = ctx.workdir
        hint = ""
        try:
            avail = [e for e in sorted(os.listdir(parent_dir)) if not e.startswith(".")][:15]
            if avail:
                rel_parent = ctx.rel_path(parent_dir)
                hint = f" (Available in '{rel_parent}': {', '.join(avail)}. Do NOT retry '{path}'; read one of the existing files instead.)"
        except Exception:
            pass
        return {"success": False, "error": f"File not found: {path}{hint}"}

    if os.path.isdir(full_path):
        try:
            entries = sorted(os.listdir(full_path))[:60]
            listing = "\n".join(entries) if entries else "(empty directory)"
            return {
                "success": True,
                "path": ctx.rel_path(full_path),
                "content": f"[Directory listing for {path}]\n{listing}",
                "total_lines": len(entries),
            }
        except Exception as e:
            return {"success": False, "error": f"'{path}' is a directory, not a file ({e})."}

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total = len(all_lines)
        if lines:
            parts = lines.split("-")
            start = max(1, int(parts[0]))
            end = min(total, int(parts[1])) if len(parts) > 1 else start
            selected = all_lines[start - 1 : end]
            content = "".join(selected)
            return {
                "success": True,
                "path": ctx.rel_path(full_path),
                "content": content,
                "line_range": f"{start}-{end}",
                "total_lines": total,
            }
        else:
            return {
                "success": True,
                "path": ctx.rel_path(full_path),
                "content": "".join(all_lines),
                "total_lines": total,
            }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _build_diff_entries(
    old_lines: List[str],
    start_line_num: int,
    matched_old: str,
    new: str,
) -> List[Tuple[int, str, str]]:
    old_chunk_lines = matched_old.splitlines()
    new_chunk_lines = new.splitlines()
    diff_entries: List[Tuple[int, str, str]] = []

    ctx_before_start = max(1, start_line_num - 2)
    for i in range(ctx_before_start, start_line_num):
        if i <= len(old_lines):
            diff_entries.append((i, "ctx", old_lines[i - 1]))

    for idx, line in enumerate(old_chunk_lines):
        diff_entries.append((start_line_num + idx, "del", line))

    for idx, line in enumerate(new_chunk_lines):
        diff_entries.append((start_line_num + idx, "add", line))

    after_start = start_line_num + len(old_chunk_lines)
    ctx_after_end = min(len(old_lines), after_start + 2)
    for i in range(after_start, ctx_after_end + 1):
        if i <= len(old_lines):
            diff_entries.append((i, "ctx", old_lines[i - 1]))

    return diff_entries


def _finalize_file_edit(
    ctx: AgentContext,
    full_path: str,
    prev_content: str,
    new_content: str,
    diff_entries: List[Tuple[int, str, str]],
) -> Dict[str, Any]:
    if getattr(ctx, "on_before_file_modify", None):
        try:
            ctx.on_before_file_modify(full_path)
        except Exception:
            pass

    with open(full_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    is_valid, verify_err = verify_code_syntax(full_path, new_content)
    if not is_valid:
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(prev_content)
        return {
            "success": False,
            "error": f"Syntax verification failed: {verify_err}",
            "path": ctx.rel_path(full_path),
            "verification": "FAILED",
            "verification_error": verify_err,
        }

    test_res = run_project_tests(ctx.workdir, target_file=full_path)
    test_status = ""
    if test_res.get("has_tests"):
        if test_res["passed"]:
            test_status = f"[AUTO-TEST: PASSED] {test_res.get('summary', '')}"
        else:
            test_status = (
                f"⚠️ [AUTO-TEST: FAILURE DETECTED]\n"
                f"Runner: {test_res.get('runner', 'tests')}\n"
                f"{test_res.get('output', '')}\n\n"
                "CRITICAL AUTONOMOUS REPAIR DIRECTIVE: The code edit caused test failures above. "
                "Analyze the error output, locate the bug, and immediately use <tool:edit> or <tool:write> to repair the code until tests pass!"
            )

    res_dict: Dict[str, Any] = {
        "success": True,
        "path": ctx.rel_path(full_path),
        "diff_entries": diff_entries,
        "verification": "OK",
        "verification_error": "",
        "test_result": test_res,
    }
    try:
        from .lsp_client import run_file_diagnostics, format_diagnostics_summary
        diags = run_file_diagnostics(full_path, ctx.workdir)
        if diags:
            res_dict["diagnostics"] = format_diagnostics_summary(diags)
    except Exception:
        pass

    if test_status:
        res_dict["test_status"] = test_status
    return res_dict


def tool_edit(
    ctx: AgentContext, path: str, old: str, new: str
) -> Dict[str, Any]:
    full_path = ctx.resolve_path(path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {path}"}

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        match_res = _smart_replace(content, old, new)
        if match_res is None:
            return {
                "success": False,
                "error": f"Target chunk <old> does not match file content in '{path}' (don't match). Ensure matching lines or use <tool:read> first.",
            }

        new_content, start_line_num, matched_old = match_res
        diff_entries = _build_diff_entries(content.splitlines(), start_line_num, matched_old, new)
        return _finalize_file_edit(ctx, full_path, content, new_content, diff_entries)
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_multi_edit(
    ctx: AgentContext, path: str, edits: List[Dict[str, str]]
) -> Dict[str, Any]:
    """Atomically apply multiple {old, new} edits to a single file."""
    full_path = ctx.resolve_path(path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"File not found: {path}"}
    if not isinstance(edits, list) or not edits:
        return {"success": False, "error": "multi_edit requires a non-empty list of {old, new} edits."}

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            orig_content = f.read()

        working = orig_content
        all_diffs: List[Tuple[int, str, str]] = []
        for idx, item in enumerate(edits, start=1):
            if not isinstance(item, dict):
                return {"success": False, "error": f"Edit #{idx} must be an object with 'old' and 'new'."}
            old_str = str(item.get("old") or "")
            new_str = str(item.get("new") or "")
            match_res = _smart_replace(working, old_str, new_str)
            if match_res is None:
                return {
                    "success": False,
                    "error": f"Edit #{idx} in multi_edit did not match '{path}'. No changes were written.",
                }
            next_working, start_line_num, matched_old = match_res
            all_diffs.extend(_build_diff_entries(working.splitlines(), start_line_num, matched_old, new_str))
            working = next_working

        res = _finalize_file_edit(ctx, full_path, orig_content, working, all_diffs)
        if res.get("success"):
            res["edits_applied"] = len(edits)
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_write(ctx: AgentContext, path: str, content: str) -> Dict[str, Any]:
    full_path = ctx.resolve_path(path)
    try:
        if getattr(ctx, "on_before_file_modify", None):
            try:
                ctx.on_before_file_modify(full_path)
            except Exception:
                pass
        os.makedirs(os.path.dirname(full_path) or ".", exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        is_valid, verify_err = verify_code_syntax(full_path, content)
        if not is_valid:
            return {
                "success": False,
                "error": f"Syntax verification failed: {verify_err}",
                "path": ctx.rel_path(full_path),
                "verification": "FAILED",
                "verification_error": verify_err,
            }

        test_res = run_project_tests(ctx.workdir, target_file=full_path)
        test_status = ""
        if test_res.get("has_tests"):
            if test_res["passed"]:
                test_status = f"[AUTO-TEST: PASSED] {test_res.get('summary', '')}"
            else:
                test_status = (
                    f"⚠️ [AUTO-TEST: FAILURE DETECTED]\n"
                    f"Runner: {test_res.get('runner', 'tests')}\n"
                    f"{test_res.get('output', '')}\n\n"
                    "CRITICAL AUTONOMOUS REPAIR DIRECTIVE: The written file caused test failures above. "
                    "Analyze the error output, locate the bug, and immediately use <tool:edit> or <tool:write> to repair the code until tests pass!"
                )

        res_dict = {
            "success": True,
            "path": ctx.rel_path(full_path),
            "lines": len(content.splitlines()),
            "content": content,
            "verification": "OK",
            "verification_error": "",
            "test_result": test_res,
        }
        try:
            from .lsp_client import run_file_diagnostics, format_diagnostics_summary
            diags = run_file_diagnostics(full_path, ctx.workdir)
            if diags:
                res_dict["diagnostics"] = format_diagnostics_summary(diags)
        except Exception:
            pass

        if test_status:
            res_dict["test_status"] = test_status
        return res_dict

    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_ls(ctx: AgentContext, path: str = ".") -> Dict[str, Any]:
    full_path = ctx.resolve_path(path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"Path not found: {path}"}

    IGNORED_SUBDIRS = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", ".cmdai_code_project", ".gemini"}

    try:
        raw_items = []
        with os.scandir(full_path) as it:
            for entry in it:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    size = None if is_dir else entry.stat(follow_symlinks=False).st_size
                except Exception:
                    is_dir = False
                    size = None
                raw_items.append((entry, is_dir, size))

        raw_items.sort(key=lambda x: (not x[1], x[0].name.lower()))

        entries = []
        for entry, is_dir, size in raw_items[:60]:
            children = []
            if is_dir and entry.name not in IGNORED_SUBDIRS:
                try:
                    with os.scandir(entry.path) as sub_it:
                        for sub in sub_it:
                            sub_is_dir = sub.is_dir(follow_symlinks=False)
                            children.append({
                                "name": sub.name + ("/" if sub_is_dir else ""),
                                "is_dir": sub_is_dir,
                            })
                            if len(children) >= 4:
                                break
                except Exception:
                    pass

            entries.append({
                "name": entry.name,
                "type": "dir" if is_dir else "file",
                "children": children,
                "size": size,
            })

        return {
            "success": True,
            "path": ctx.rel_path(full_path),
            "entries": entries,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_glob(ctx: AgentContext, pattern: str = "*", dir: str = ".") -> Dict[str, Any]:
    full_dir = ctx.resolve_path(dir)
    if not os.path.exists(full_dir):
        return {"success": False, "error": f"Directory not found: {dir}", "matches": [], "count": 0}
    if not os.path.isdir(full_dir):
        return {"success": False, "error": f"Not a directory: {dir}", "matches": [], "count": 0}
    search_pattern = os.path.join(full_dir, pattern)
    ignored = {".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", ".cmdai_code_project", ".gemini"}
    try:
        matches = py_glob.glob(search_pattern, recursive=True)
        rel_matches = []
        for m in matches:
            rel = ctx.rel_path(m)
            parts = set(rel.replace("\\", "/").split("/"))
            if parts & ignored:
                continue
            rel_matches.append(rel)
            if len(rel_matches) >= 100:
                break
        res: Dict[str, Any] = {
            "success": True,
            "pattern": pattern,
            "matches": rel_matches,
            "count": len(rel_matches),
        }
        if not rel_matches:
            res["note"] = "No matching workspace files found."
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_search(
    ctx: AgentContext,
    query: str,
    path: str = ".",
    literal: bool = False,
) -> Dict[str, Any]:
    full_path = ctx.resolve_path(path)
    if not os.path.exists(full_path):
        return {"success": False, "error": f"Path not found: {path}"}

    compiled_re = None
    if not literal and query:
        try:
            compiled_re = re.compile(query)
        except re.error:
            compiled_re = None

    def _line_matches(line_str: str) -> bool:
        if query in line_str:
            return True
        if compiled_re is not None and compiled_re.search(line_str):
            return True
        return False

    def _scan_file(file_path: str, acc: List[Dict[str, Any]]) -> None:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                for line_num, line in enumerate(file_obj, 1):
                    if _line_matches(line):
                        acc.append({
                            "file": ctx.rel_path(file_path),
                            "line": line_num,
                            "content": line.strip(),
                        })
                        if len(acc) >= 50:
                            break
        except Exception:
            pass

    results: List[Dict[str, Any]] = []
    try:
        if os.path.isfile(full_path):
            _scan_file(full_path, results)
        else:
            ignored = {".git", "node_modules", ".venv", "__pycache__", ".cmdai_code_project"}
            for root, dirs, files in os.walk(full_path):
                dirs[:] = [d for d in dirs if d not in ignored]
                for f in files:
                    _scan_file(os.path.join(root, f), results)
                    if len(results) >= 50:
                        break
                if len(results) >= 50:
                    break
        return {"success": True, "query": query, "path": ctx.rel_path(full_path), "results": results}
    except Exception as e:
        return {"success": False, "error": str(e)}


def tool_command(
    ctx: AgentContext,
    cmd: str,
    timeout: int = 60,
    background: bool = False,
    detach_check: Optional[Callable[[], bool]] = None,
    on_output: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    from .tasks import BackgroundTaskManager
    active_cwd = getattr(ctx, "current_cwd", None) or ctx.workdir
    if not os.path.isdir(active_cwd):
        active_cwd = ctx.workdir

    # Autonomous detection: persistent servers, watchers and daemons auto-detach to background
    cmd_lower = cmd.lower()
    if getattr(ctx, "is_subagent", False):
        timeout = min(timeout, 15)
        background = False
        blocked = ["msedge", "chrome", "firefox", "brave", "opera", "start-process", "explorer"]
        if any(b in cmd_lower for b in blocked):
            return {
                "success": False,
                "cmd": cmd,
                "error": "Launching GUI applications or browsers is prohibited for subagents. Please inspect files directly using <tool:read>.",
            }
    auto_bg_triggers = ["run dev", "npm start", "yarn start", "pnpm dev", "vite", "next dev", "uvicorn", "http.server", "flask run", "nodemon", "cargo watch"]
    if not background and any(t in cmd_lower for t in auto_bg_triggers):
        background = True

    s_id = str(getattr(ctx, "session_id", "") or "")
    if background:
        return BackgroundTaskManager.get_instance().spawn(cmd, active_cwd, session_id=s_id)

    temp_dir = tempfile.gettempdir()
    import uuid as _uuid
    log_path = os.path.join(temp_dir, f"cmdai_fg_{_uuid.uuid4().hex[:8]}.log")
    log_file = open(log_path, "w+", encoding="utf-8", errors="replace")

    creation_flags = 0
    if os.name == "nt":
        creation_flags = 0x08000000

    try:
        proc = subprocess.Popen(
            cmd,
            shell=True,
            cwd=active_cwd,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=creation_flags,
        )
    except Exception as e:
        log_file.close()
        return {"success": False, "cmd": cmd, "error": str(e)}

    start = time.time()
    while proc.poll() is None:
        if detach_check and detach_check():
            adopted = BackgroundTaskManager.get_instance().adopt(cmd, proc, log_path, session_id=s_id)
            return {
                "success": True,
                "background": True,
                "task_id": adopted["task_id"],
                "pid": proc.pid,
                "cmd": cmd,
                "message": f"Command moved to background as {adopted['task_id']}.",
            }
        if time.time() - start > timeout:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except Exception:
                    proc.kill()
            except Exception:
                pass
            log_file.seek(0)
            out = log_file.read()
            log_file.close()
            return {"success": False, "cmd": cmd, "error": f"Command timed out after {timeout}s", "stdout": out}
        time.sleep(0.1)

    log_file.seek(0)
    out = log_file.read()
    log_file.close()

    if proc.returncode == 0:
        for sub_cmd in re.split(r"&&|;", cmd):
            m_cd = re.match(r"^\s*cd(?:\s+/d)?\s+([^\r\n]+)$", sub_cmd.strip(), flags=re.IGNORECASE)
            if m_cd:
                target_dir = m_cd.group(1).strip().strip('"\'')
                new_cwd = target_dir if os.path.isabs(target_dir) else os.path.normpath(os.path.join(active_cwd, target_dir))
                if os.path.isdir(new_cwd):
                    active_cwd = new_cwd
                    ctx.current_cwd = new_cwd

    if proc.returncode != 0 and "not a git repository" in (out or "").lower():
        out = (out or "") + "\n[Workspace is not a git repository. Do not use git; inspect files directly with ls, read, or glob]"

    return {
        "success": proc.returncode == 0,
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout": out,
        "stderr": "",
    }


_STATIC_PREVIEW_SERVERS: Dict[str, Tuple[Any, int]] = {}
_STATIC_PREVIEW_LOCK = threading.Lock()


def _shutdown_static_preview_servers() -> None:
    with _STATIC_PREVIEW_LOCK:
        for _, (srv, _p) in list(_STATIC_PREVIEW_SERVERS.items()):
            try:
                srv.shutdown()
                srv.server_close()
            except Exception:
                pass
        _STATIC_PREVIEW_SERVERS.clear()


atexit.register(_shutdown_static_preview_servers)


def _is_local_port_open(port: int) -> bool:
    import socket
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.25):
            return True
    except OSError:
        return False


def _start_static_preview_server(serve_dir: str, preferred_port: Optional[int] = None) -> int:
    """Start a quiet threaded static HTTP server on a free local port (random by default)."""
    import functools
    import http.server
    import socketserver

    norm_dir = os.path.abspath(serve_dir)
    with _STATIC_PREVIEW_LOCK:
        existing = _STATIC_PREVIEW_SERVERS.get(norm_dir)
        if existing is not None:
            srv_obj, ex_port = existing
            if (preferred_port is None or ex_port == preferred_port) and _is_local_port_open(ex_port):
                return ex_port
            # Port changed or server died: stop old one cleanly
            try:
                srv_obj.shutdown()
                srv_obj.server_close()
            except Exception:
                pass
            _STATIC_PREVIEW_SERVERS.pop(norm_dir, None)

        class _QuietStaticHandler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                pass

        class _ReusableThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
            daemon_threads = True
            allow_reuse_address = True

        handler_cls = functools.partial(_QuietStaticHandler, directory=norm_dir)
        bind_port = int(preferred_port) if (preferred_port and 1 <= int(preferred_port) <= 65535) else 0
        try:
            httpd = _ReusableThreadingHTTPServer(("127.0.0.1", bind_port), handler_cls)
        except OSError:
            # Preferred port busy or restricted -> automatically pick a random unused local port
            httpd = _ReusableThreadingHTTPServer(("127.0.0.1", 0), handler_cls)

        actual_port = int(httpd.server_address[1])
        t = threading.Thread(target=httpd.serve_forever, daemon=True, name=f"cmdai-static-{actual_port}")
        t.start()
        _STATIC_PREVIEW_SERVERS[norm_dir] = (httpd, actual_port)
        return actual_port


def _find_static_root(workdir: str) -> str:
    """Find the best directory containing index.html inside workdir."""
    base = os.path.abspath(workdir or os.getcwd())
    for rel in ("", "src", "public", "dist", "build"):
        cand = os.path.join(base, rel) if rel else base
        if os.path.isfile(os.path.join(cand, "index.html")):
            return cand
    return base


def _resolve_browser_url(raw_url: str, workdir: str, port: Optional[int] = None) -> str:
    """Resolve local file paths (e.g. 'src/index.html') or dead localhost ports via Auto-Static-Server."""
    import urllib.parse

    u = (raw_url or "").strip()
    if not u:
        return u

    # Convert file:///... to local path
    if u.lower().startswith("file://"):
        parsed_f = urllib.parse.urlparse(u)
        fpath = urllib.parse.unquote(parsed_f.path or "")
        if os.name == "nt" and fpath.startswith("/") and len(fpath) > 2 and fpath[2] == ":":
            fpath = fpath[1:]
        u = fpath

    # Case 1: Explicit HTTP/HTTPS URL
    if u.lower().startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(u)
        host = (parsed.hostname or "").lower()
        if host in ("127.0.0.1", "localhost", "::1"):
            req_port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if not _is_local_port_open(req_port):
                # Check if URL path points to a file inside workdir (e.g. /src/index.html)
                rel_p = (parsed.path or "").lstrip("/")
                abs_work = os.path.abspath(workdir or os.getcwd())
                if rel_p and os.path.isfile(os.path.join(abs_work, rel_p)):
                    serve_dir = abs_work
                    actual_port = _start_static_preview_server(serve_dir, preferred_port=req_port)
                    return f"http://127.0.0.1:{actual_port}/{rel_p}"
                serve_dir = _find_static_root(abs_work)
                actual_port = _start_static_preview_server(serve_dir, preferred_port=req_port)
                path_part = parsed.path or "/"
                q_part = f"?{parsed.query}" if parsed.query else ""
                f_part = f"#{parsed.fragment}" if parsed.fragment else ""
                return f"http://127.0.0.1:{actual_port}{path_part}{q_part}{f_part}"
        return u

    # Case 2: Local file or directory path inside workspace (e.g. 'src/index.html', 'index.html', '.')
    abs_work = os.path.abspath(workdir or os.getcwd())
    cand = os.path.abspath(u) if os.path.isabs(u) else os.path.abspath(os.path.join(abs_work, u))
    if os.path.isfile(cand):
        serve_dir = os.path.dirname(cand)
        fname = urllib.parse.quote(os.path.basename(cand))
        actual_port = _start_static_preview_server(serve_dir, preferred_port=port)
        return f"http://127.0.0.1:{actual_port}/{fname}"
    if os.path.isdir(cand):
        serve_dir = _find_static_root(cand)
        actual_port = _start_static_preview_server(serve_dir, preferred_port=port)
        return f"http://127.0.0.1:{actual_port}/"

    # Fallback: if it looks like a bare domain (e.g. example.com), prepend https://
    if "." in u and not u.lower().endswith((".html", ".htm")):
        return f"https://{u}"
    return u


def tool_browser(
    ctx: AgentContext,
    action: str = "run",
    url: str = "",
    task: str = "",
    port: Optional[int] = None,
    device: str = "desktop",
    selector: str = "",
    index: Optional[int] = None,
    text: str = "",
    direction: str = "down",
    submit: bool = False,
    x: Optional[int] = None,
    y: Optional[int] = None,
    on_step: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Control the isolated headless CDP browser without touching the user's mouse or keyboard."""
    from ..browser import get_browser_engine
    from ..browser.agent import run_browser_agent
    from ..core.settings import get_settings

    try:
        cfg = get_settings().config or {}
        if not bool((cfg.get("browser") or {}).get("enabled", False)):
            return {
                "success": False,
                "error": "Browser Control is disabled. Enable 'Browser Control' in Settings first.",
            }
    except Exception:
        pass

    if url:
        url = _resolve_browser_url(url, ctx.workdir, port=port)

    act = str(action or ("run" if task else "snapshot")).strip().lower()
    if act == "run" or (task and act in ("open", "run", "browse", "test")):
        return run_browser_agent(
            task=task or f"Open and inspect {url}",
            url=url,
            workdir=ctx.workdir,
            device=device or "desktop",
            on_step=on_step,
        )

    eng = get_browser_engine()
    if act in ("open", "goto", "navigate"):
        res = eng.open_url(url)
        # Also attach a real visual screenshot right inside `open` so vision models
        # can inspect the page in ONE single tool call without needing a separate screenshot step!
        if res.get("success") and eng.latest_frame:
            try:
                cache_dir = os.path.join(ctx.workdir, ".cmdai", "browser_shots")
                os.makedirs(cache_dir, exist_ok=True)
                shot_path = os.path.join(cache_dir, f"browser_open_{int(time.time() * 1000)}.jpg")
                with open(shot_path, "wb") as sf:
                    sf.write(eng.latest_frame)
                if not hasattr(ctx, "pending_images") or ctx.pending_images is None:
                    ctx.pending_images = []
                ctx.pending_images.append({"path": shot_path, "question": "Inspect this browser webpage screenshot."})
                res["screenshot_attached"] = True
            except Exception:
                pass
        return res
    if act == "snapshot":
        return eng.snapshot()
    if act == "click":
        res = eng.click(index=index, selector=selector, x=x, y=y)
        if res.get("success") and eng.latest_frame:
            try:
                cache_dir = os.path.join(ctx.workdir, ".cmdai", "browser_shots")
                os.makedirs(cache_dir, exist_ok=True)
                shot_path = os.path.join(cache_dir, f"browser_click_{int(time.time() * 1000)}.jpg")
                with open(shot_path, "wb") as sf:
                    sf.write(eng.latest_frame)
                if not hasattr(ctx, "pending_images") or ctx.pending_images is None:
                    ctx.pending_images = []
                ctx.pending_images.append({"path": shot_path, "question": "Inspect updated browser page after click."})
            except Exception:
                pass
        return res
    if act in ("type", "fill", "input"):
        return eng.type_text(text=text, index=index, selector=selector, submit=submit)
    if act == "scroll":
        return eng.scroll(direction=direction or "down")
    if act == "screenshot":
        cache_dir = os.path.join(ctx.workdir, ".cmdai", "browser_shots")
        res = eng.screenshot(save_dir=cache_dir)
        if res.get("success") and res.get("path"):
            try:
                if not hasattr(ctx, "pending_images") or ctx.pending_images is None:
                    ctx.pending_images = []
                ctx.pending_images.append({"path": res["path"], "question": "Inspect this browser webpage screenshot."})
            except Exception:
                pass
        return res
    if act == "console":
        return eng.get_console()
    if act == "close":
        return eng.close()
    return {"success": False, "error": f"Unknown browser action: {act}"}


def tool_web(ctx: AgentContext, url_or_query: str) -> Dict[str, Any]:
    target = url_or_query.strip()
    if target.startswith("http://") or target.startswith("https://"):
        try:
            resp = requests.get(
                target,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=3.5,
            )
            html = resp.text
            html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', html)
            text = re.sub(r'\s+', ' ', text).strip()
            return {"success": True, "url": target, "content": text[:4000]}
        except Exception as e:
            return {"success": False, "url": target, "error": str(e)}
    else:
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            with DDGS(timeout=4) as ddgs:
                results = list(ddgs.text(target, max_results=3))

            if not results:
                return {
                    "success": True,
                    "query": target,
                    "content": f"No web search results found for: \"{target}\"",
                    "results": [],
                }

            formatted_results = []
            output_parts = [f"Web search results for: \"{target}\":\n"]
            for i, res in enumerate(results, 1):
                title = res.get("title", "No title").strip()
                href = res.get("href", "").strip()
                raw_body = res.get("body") or ""
                clean_body = re.sub(r"\s+", " ", raw_body).strip()
                if len(clean_body) > 220:
                    truncated = clean_body[:220].rsplit(" ", 1)[0].rstrip(".,;:-") + "..."
                else:
                    truncated = clean_body
                formatted_results.append({"title": title, "url": href, "snippet": truncated})
                output_parts.append(f"{i}. {title}\n   Link: {href}\n   Snippet: {truncated}\n")

            return {
                "success": True,
                "query": target,
                "content": "\n".join(output_parts),
                "results": formatted_results,
            }
        except Exception as e:
            return {"success": False, "query": target, "error": f"Web search timeout or error: {str(e)}"}


def tool_bugs(ctx: AgentContext) -> Dict[str, Any]:
    from .verifier import scan_project_bugs
    report = scan_project_bugs(ctx.workdir)
    return {
        "success": True,
        "scanned_files": report["scanned_files"],
        "errors": report["errors"],
    }


def tool_code_search(ctx: AgentContext, query: str) -> Dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"success": False, "error": "Empty query."}

    candidate = q if os.path.isabs(q) else os.path.join(ctx.workdir, q)
    if os.path.isfile(candidate):
        try:
            from .lsp_client import get_document_symbols
            symbols = get_document_symbols(candidate, ctx.workdir)
            return {
                "success": True,
                "query": q,
                "mode": "document_symbols",
                "symbols": symbols,
                "count": len(symbols),
            }
        except Exception:
            pass

    symbols: List[Dict[str, Any]] = []
    references: List[Dict[str, Any]] = []
    try:
        from ..indexer.ast_indexer import ProjectIndexer
        indexer = ProjectIndexer(ctx.workdir)
        symbols = indexer.search(q, limit=20)
    except Exception:
        pass

    try:
        from .lsp_client import find_references
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", q):
            references = find_references(q, ctx.workdir, limit=25)
    except Exception:
        pass

    if symbols or references:
        return {
            "success": True,
            "query": q,
            "symbols": symbols,
            "references": references,
            "count": len(symbols) + len(references),
        }
    return tool_search(ctx, q)


def _run_git_readonly(ctx: AgentContext, git_args: List[str], timeout: int = 10) -> Dict[str, Any]:
    """Run a read-only git command in ctx.workdir without invoking a shell."""
    safe_dir = os.path.abspath(ctx.workdir).replace("\\", "/")
    try:
        proc = subprocess.run(
            ["git", "-c", f"safe.directory={safe_dir}", *git_args],
            cwd=ctx.workdir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout,
            "stderr": proc.stderr.strip(),
            "returncode": proc.returncode,
        }
    except FileNotFoundError:
        return {"success": False, "stdout": "", "stderr": "git executable not found in PATH.", "returncode": -1}
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": f"git command timed out after {timeout}s.", "returncode": -1}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e), "returncode": -1}


def tool_git_status(ctx: AgentContext) -> Dict[str, Any]:
    """Return concise read-only git branch and working tree status."""
    res = _run_git_readonly(ctx, ["status", "--short", "--branch"])
    if not res["success"]:
        return {"success": False, "error": res["stderr"] or "git status failed"}
    output = res["stdout"].strip()
    return {
        "success": True,
        "status": output,
        "clean": len(output.splitlines()) <= 1,
    }


def tool_git_diff(ctx: AgentContext, path: str = "", staged: bool = False) -> Dict[str, Any]:
    """Return read-only git diff (unstaged or staged, optionally scoped to a path)."""
    args = ["diff"]
    if staged:
        args.append("--staged")
    clean_path = (path or "").strip()
    if clean_path:
        try:
            full_path = _safe_path(ctx, clean_path)
            rel_path = os.path.relpath(full_path, ctx.workdir)
            args.extend(["--", rel_path])
        except ValueError as e:
            return {"success": False, "error": str(e)}

    res = _run_git_readonly(ctx, args)
    if not res["success"]:
        return {"success": False, "error": res["stderr"] or "git diff failed"}

    diff_text = res["stdout"]
    truncated = False
    max_chars = 12000
    if len(diff_text) > max_chars:
        diff_text = diff_text[:max_chars] + "\n... [diff truncated]"
        truncated = True
    return {
        "success": True,
        "path": clean_path,
        "staged": bool(staged),
        "diff": diff_text,
        "empty": not bool(diff_text.strip()),
        "truncated": truncated,
    }


def tool_scratch(
    ctx: AgentContext,
    action: str,
    note: str = "",
    index: Optional[int] = None,
    new_text: str = "",
    todos: Optional[str] = None,
) -> Dict[str, Any]:
    action_lower = action.lower().strip()
    if action_lower in ("add", "push"):
        if note:
            parts = re.split(r'(?:\r?\n|\s+)(?=\d+[\.\)]\s+)', note.strip())
            if len(parts) > 1:
                for p in parts:
                    clean_p = p.strip().rstrip(".;")
                    clean_p = re.sub(r'^(?:plan\s*(?:prac)?|todo|zadania)\s*:\s*', '', clean_p, flags=re.IGNORECASE).strip()
                    if clean_p:
                        ctx.todo_list.append({"text": clean_p, "done": False})
            else:
                ctx.todo_list.append({"text": note.strip(), "done": False})
    elif action_lower in ("set", "init"):
        raw_todos = todos or note
        if raw_todos:
            items = [t.strip() for t in re.split(r"[|\n]", raw_todos) if t.strip()]
            ctx.todo_list = [{"text": it, "done": False} for it in items]
    elif action_lower in ("edit", "update"):
        target_idx = index if index is not None else 0
        if 0 <= target_idx < len(ctx.todo_list):
            ctx.todo_list[target_idx]["text"] = new_text or note
        elif note and new_text:
            for item in ctx.todo_list:
                if note.lower() in item["text"].lower():
                    item["text"] = new_text
                    break
    elif action_lower in ("done", "complete"):
        target_idx = index if index is not None else 0
        if 0 <= target_idx < len(ctx.todo_list):
            ctx.todo_list[target_idx]["done"] = True
        elif note:
            for item in ctx.todo_list:
                if note.lower() in item["text"].lower():
                    item["done"] = True
                    break
    elif action_lower in ("remove", "delete"):
        target_idx = index if index is not None else 0
        if 0 <= target_idx < len(ctx.todo_list):
            ctx.todo_list.pop(target_idx)
    elif action_lower in ("clear", "reset"):
        ctx.todo_list.clear()

    return {
        "success": True,
        "action": action,
        "visible_steps": ctx.todo_list,
        "total_remaining": len([t for t in ctx.todo_list if not t.get("done")]),
    }


tool_todo = tool_scratch


SCREENSHOT_MAX_BYTES = 2_000_000
SCREENSHOT_MAX_DIM = 1920


def _screenshot_dir() -> str:
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "cmdai_screenshots")
    os.makedirs(d, exist_ok=True)
    return d


def _find_window_rect(title_sub: str = "") -> Optional[Dict[str, int]]:
    if os.name != "nt":
        return None
    try:
        import win32gui
    except ImportError:
        return None
    needle = (title_sub or "").strip().lower()
    found: Dict[str, int] = {}

    def _cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        try:
            text = win32gui.GetWindowText(hwnd) or ""
        except Exception:
            return
        if needle and needle not in text.lower():
            return
        try:
            l, t, r, b = win32gui.GetWindowRect(hwnd)
        except Exception:
            return
        if r - l > 50 and b - t > 50 and not found:
            found.update({"left": l, "top": t, "width": r - l, "height": b - t})

    try:
        if not needle:
            import win32gui as _wg
            hwnd = _wg.GetForegroundWindow()
            l, t, r, b = _wg.GetWindowRect(hwnd)
            if r - l > 50 and b - t > 50:
                return {"left": l, "top": t, "width": r - l, "height": b - t}
            return None
        win32gui.EnumWindows(_cb, None)
    except Exception:
        return None
    return found or None


def tool_screenshot(ctx: AgentContext, target: str = "active_window") -> Dict[str, Any]:
    import uuid
    target = (target or "active_window").strip()
    rect = _find_window_rect("" if target.lower() == "active_window" else target)
    try:
        import mss
    except ImportError:
        return {"success": False, "error": "mss package not installed (pip install mss)"}
    try:
        out = os.path.join(_screenshot_dir(), f"{uuid.uuid4().hex}.png")
        with mss.mss() as sct:
            monitor = {"left": rect["left"], "top": rect["top"], "width": rect["width"], "height": rect["height"]} if rect else sct.monitors[0]
            shot = sct.grab(monitor)
            try:
                from PIL import Image
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                img.thumbnail((SCREENSHOT_MAX_DIM, SCREENSHOT_MAX_DIM))
                img.save(out, "PNG")
            except ImportError:
                import mss.tools
                mss.tools.to_png(shot.rgb, shot.size, output=out)
        size = os.path.getsize(out)
        if size > SCREENSHOT_MAX_BYTES:
            try:
                from PIL import Image
                img = Image.open(out)
                img.thumbnail((1280, 1280))
                img.save(out, "PNG", optimize=True)
                size = os.path.getsize(out)
            except ImportError:
                pass
        res = {"success": True, "path": out, "size_bytes": size, "target": target}
        if "." in target and any(target.lower().endswith(ext) for ext in (".html", ".htm", ".py", ".js", ".ts", ".css", ".md", ".txt", ".json")):
            res["note"] = (
                f"Captured desktop because '{target}' is a file name, not an OS window title. "
                "To screenshot a web page, open it in a browser window first and capture that window."
            )
        return res
    except Exception as e:
        return {"success": False, "error": f"screenshot failed: {e}"}


def tool_vision(ctx: AgentContext, image_path: str = "", question: str = "") -> Dict[str, Any]:
    p = (image_path or "").strip()
    if re.fullmatch(r"\[?\s*image\s+\d+\s*\]?", p, flags=re.IGNORECASE):
        return {
            "success": True,
            "path": p,
            "question": (question or "").strip(),
            "note": "This attached image is already embedded in your conversation prompt — inspect it directly and answer the user without calling <tool:vision> again.",
        }
    if not p or not os.path.exists(p):
        return {"success": False, "error": f"image not found: {image_path}"}
    if os.path.getsize(p) > SCREENSHOT_MAX_BYTES * 2:
        return {"success": False, "error": "image too large (>4MB)"}
    entry = {"path": os.path.abspath(p), "question": (question or "").strip()}
    ctx.pending_images.append(entry)
    return {"success": True, "path": entry["path"], "question": entry["question"],
            "note": "image queued, it will be attached to the next model request"}


def tool_memory(
    ctx: AgentContext,
    action: str = "list",
    content: str = "",
    scope: str = "project",
    index: int = 0,
    query: str = "",
) -> Dict[str, Any]:
    """Read or update cross-session persistent memory (.cmdai/memory.md / ~/.cmdai/memory.md)."""
    from ..core.memory import (
        add_memory_entry,
        clear_memory,
        list_memory_entries,
        remove_memory_entry,
    )

    act = (action or "list").strip().lower()
    sc = (scope or "project").strip().lower()
    if act == "list":
        data = list_memory_entries(ctx.workdir, scope=sc or "all")
        return {"success": True, "action": "list", "entries": data}
    if act == "add":
        return add_memory_entry(ctx.workdir, content=content, scope=sc)
    if act == "remove":
        return remove_memory_entry(ctx.workdir, index=index, query=query, scope=sc)
    if act == "clear":
        return clear_memory(ctx.workdir, scope=sc)
    return {"success": False, "error": f"Unknown memory action: {action}. Use add, list, remove, or clear."}
