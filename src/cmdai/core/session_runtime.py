"""SessionRuntime for CMDAI CODE.

Encapsulates autonomous agent session state, message history, transcripts,
tool execution loop, and provides headless execution (e.g. `cmdai run <prompt>`)
independent of the Textual UI.
"""

import os
import sys
import time
import json
from typing import Any, Callable, Dict, List, Optional, Tuple

from .settings import SettingsManager
from ..agent.tools import AgentContext
from ..agent.runner import AgentRunner, get_agent_system_prompt
from ..agent.tool_specs import get_native_tool_schemas
from .providers import stream_chat_completion


class SessionRuntime:
    """Manages an autonomous agent session, its state, and execution loop."""

    def __init__(
        self,
        workdir: str = ".",
        provider: str = "",
        model: str = "",
        mode: str = "auto",
        api_key: str = "",
        settings_manager: Optional[SettingsManager] = None,
        ask_handler: Optional[Callable[[str, List[str], Optional[Dict[str, Any]]], str]] = None,
    ):
        self.workdir = os.path.abspath(workdir)
        self.settings = settings_manager or SettingsManager(self.workdir)

        cfg = self.settings.config
        self.current_provider = provider or cfg.get("default_provider", "openrouter")
        self.current_model_id = model or cfg.get("default_model", "")
        self.mode = mode or cfg.get("agent", {}).get("mode", "auto")
        self.api_key = api_key or self.settings.get_api_key(self.current_provider) or ""

        self.messages: List[Dict[str, Any]] = []
        self.transcript: List[Dict[str, Any]] = []
        self.abort_requested = False

        self.agent_ctx = AgentContext(workdir=self.workdir)
        self.agent_ctx.mode = self.mode
        self.agent_ctx.permissions = cfg.get("permissions")

        self.agent_runner = AgentRunner(
            ctx=self.agent_ctx,
            ask_handler=ask_handler,
        )

    def _subagent_target(self) -> Tuple[str, str]:
        """Resolve (provider, model) for subagents from settings.subagent_model or current model."""
        raw = str(self.settings.config.get("subagent_model") or "").strip()
        if raw:
            if ":" in raw:
                p, m = raw.split(":", 1)
                if p.strip() and m.strip():
                    return p.strip(), m.strip()
            return self.current_provider, raw
        return self.current_provider, self.current_model_id

    def run_turn(
        self,
        user_prompt: str,
        on_token: Optional[Callable[[str], None]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
        on_tool_start: Optional[Callable[[str, str], None]] = None,
        on_tool_finish: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
        on_tool_stream: Optional[Callable[[str, str, int, str], None]] = None,
        on_subagent_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        max_steps: int = 15,
    ) -> str:
        """Run a full autonomous agent turn for the given prompt."""
        self.abort_requested = False
        self.messages.append({"role": "user", "content": user_prompt})
        self.transcript.append({"kind": "user", "text": user_prompt})

        gen_params = self.settings.config.get("generation", {})
        final_answer = ""

        for step in range(max_steps):
            if self.abort_requested:
                break

            # Build system prompt with tools and AGENTS.md rules
            sys_prompt = get_agent_system_prompt(self.workdir, mode=self.mode)
            payload_messages = [{"role": "system", "content": sys_prompt}] + self.messages

            native_tools = get_native_tool_schemas(mode=self.mode) if self.current_provider != "local_gguf" else None

            step_chunks: List[str] = []
            import re as _re
            _tool_open_re = _re.compile(r'<(?:tool:(\w+)|\|tool_call>call:(\w+)|tool_call>(?:call:)?(\w+))', _re.IGNORECASE)
            _partial_tag_re = _re.compile(r'<(?:t(?:o(?:o(?:l(?::\w*|_c(?:a(?:l(?:l)?)?)?)?)?)?)?|\|(?:t(?:o(?:o(?:l(?:_c(?:a(?:l(?:l(?:>(?:c(?:a(?:l(?:l(?::\w*)?)?)?)?)?)?)?)?)?)?)?)?)?)?)?$', _re.IGNORECASE)
            _path_re = _re.compile(r'(?:path|file_path|target_file|cmd|command)\s*[:=]\s*(?:<\|"\|>|["\'])?([^"\'<>,}\r\n]+)', _re.IGNORECASE)
            _in_tool_tag = False
            _last_stream_emit = 0.0
            _emitted_prose_len = 0

            def _step_token(token: str):
                nonlocal _in_tool_tag, _last_stream_emit, _emitted_prose_len
                step_chunks.append(token)
                joined = "".join(step_chunks)
                m = _tool_open_re.search(joined)
                if m:
                    # Flush any clean prose strictly before the tool tag
                    if not _in_tool_tag and on_token and m.start() > _emitted_prose_len:
                        on_token(joined[_emitted_prose_len:m.start()])
                        _emitted_prose_len = m.start()
                    _in_tool_tag = True
                    if on_tool_stream:
                        now = time.time()
                        if now - _last_stream_emit >= 0.12 or "\n" in token:
                            _last_stream_emit = now
                            t_name = (m.group(1) or m.group(2) or m.group(3) or "tool").lower()
                            tail = joined[m.start():]
                            pm = _path_re.search(tail)
                            t_target = pm.group(1).strip() if pm else ""
                            gt_idx = tail.find(">")
                            brace_idx = tail.find("{")
                            body_start = max(gt_idx, brace_idx)
                            body_preview = tail[body_start + 1:] if body_start >= 0 else ""
                            body_preview = body_preview.replace('<|"|>', '"')
                            lines_list = body_preview.splitlines()
                            line_count = len(lines_list)
                            clipped = "\n".join(lines_list[-16:])[-1400:]
                            on_tool_stream(t_name, t_target, line_count, clipped)
                    return
                if not _in_tool_tag and on_token:
                    # Hold back any trailing partial `<tool:` / `<|tool_call` prefix so it never leaks into chat
                    pm_part = _partial_tag_re.search(joined[_emitted_prose_len:])
                    safe_end = (_emitted_prose_len + pm_part.start()) if pm_part else len(joined)
                    if safe_end > _emitted_prose_len:
                        on_token(joined[_emitted_prose_len:safe_end])
                        _emitted_prose_len = safe_end

            try:
                if self.current_provider == "local_gguf":
                    from .engine import SimpleGGUFLoader
                    loader = SimpleGGUFLoader()
                    ok, err = loader.ensure_loaded(self.current_model_id)
                    if not ok:
                        raise RuntimeError(err or f"Failed to load local GGUF model: {self.current_model_id}")
                    for chunk in loader.stream_chat(payload_messages, max_tokens=int(gen_params.get("max_tokens") or 2048)):
                        if self.abort_requested:
                            break
                        _step_token(chunk)
                    resp, think = "".join(step_chunks), ""
                else:
                    resp, think = stream_chat_completion(
                        provider_id=self.current_provider,
                        model_id=self.current_model_id,
                        messages=payload_messages,
                        api_key=self.api_key,
                        generation_params=gen_params,
                        tools=native_tools,
                        on_token=_step_token,
                        on_thinking=on_thinking,
                        is_aborted=lambda: self.abort_requested,
                    )
            except Exception as e:
                err_msg = f"Error during model completion: {e}"
                if on_token:
                    on_token(f"\n{err_msg}\n")
                return err_msg

            streamed_text = "".join(step_chunks)
            # CRITICAL: stream_chat_completion returns `resp` containing BOTH streamed text
            # AND synthesized XML tags for native OpenAI tool_calls (e.g. LocalLLMAPI / Gemma 4).
            # Never discard `resp` just because `streamed_text` is non-empty!
            if resp and len(resp) >= len(streamed_text):
                full_resp = resp
            else:
                full_resp = streamed_text or resp or ""
            self.messages.append({"role": "assistant", "content": full_resp})
            self.transcript.append({"kind": "assistant", "text": full_resp})
            final_answer = full_resp

            # Check if assistant invoked tools (XML or synthesized native tool_calls)
            tool_calls = self.agent_runner.parse_xml_tool_calls(full_resp)
            if not tool_calls:
                # No more tools called -> turn completed!
                break

            # Execute consecutive read-only tools in parallel (matching CLI worker_mixin.py)
            _READ_ONLY = {"read", "ls", "glob", "search", "code_search", "git_status", "git_diff"}
            if len(tool_calls) > 1 and all(t_name in _READ_ONLY for t_name, _ in tool_calls):
                from concurrent.futures import ThreadPoolExecutor
                for t_name, t_args in tool_calls:
                    if on_tool_start:
                        on_tool_start(t_name, str(t_args))
                with ThreadPoolExecutor(max_workers=min(6, len(tool_calls))) as pool:
                    futures = [
                        (t_name, t_args, pool.submit(self.agent_runner.execute_tool, t_name, t_args))
                        for t_name, t_args in tool_calls
                    ]
                    for t_name, t_args, fut in futures:
                        if self.abort_requested:
                            break
                        tool_res = fut.result()
                        if on_tool_finish:
                            on_tool_finish(t_name, str(t_args), tool_res)
                        formatted_res = self.agent_runner.format_tool_result_for_llm(t_name, tool_res)
                        self.messages.append({"role": "user", "content": formatted_res})
                        self.transcript.append({"kind": "tool_result", "name": t_name, "result": tool_res})
            else:
                idx_tc = 0
                while idx_tc < len(tool_calls):
                    if self.abort_requested:
                        break
                    t_name, t_args = tool_calls[idx_tc]

                    if t_name == "subagent":
                        # Batch consecutive <tool:subagent> calls exactly like CLI worker_mixin.py
                        batch = [t_args]
                        j_tc = idx_tc + 1
                        while j_tc < len(tool_calls) and tool_calls[j_tc][0] == "subagent":
                            batch.append(tool_calls[j_tc][1])
                            j_tc += 1
                        idx_tc = j_tc

                        from ..agent.tasks import BackgroundTaskManager
                        from ..agent.runner import clean_subagent_call
                        bg_mgr = BackgroundTaskManager.get_instance()
                        batch = [clean_subagent_call(a if isinstance(a, dict) else {}) for a in batch]
                        sid_by_role: Dict[str, str] = {}
                        for n_idx, call_args in enumerate(batch, start=1):
                            r_name = str(call_args.get("role") or "Subagent")
                            g_text = str(call_args.get("goal") or "")
                            sid = f"sub_{int(time.time() * 1000) % 100000}_{step + 1}_{n_idx}"
                            call_args["_sid"] = sid
                            if not call_args.get("workdir"):
                                call_args["workdir"] = self.workdir
                            sid_by_role[r_name] = sid
                            bg_mgr.register_subagent(sid, role=r_name, task=g_text, session_id=str(getattr(self.agent_ctx, "session_id", "") or "web"))
                            if on_subagent_event:
                                on_subagent_event({
                                    "phase": "start",
                                    "id": sid,
                                    "name": r_name,
                                    "role": r_name,
                                    "goal": g_text,
                                    "status": "running",
                                    "tool": "",
                                    "arg": "",
                                    "summary": g_text[:220] or "Starting subagent...",
                                })

                        sub_provider, sub_model = self._subagent_target()
                        is_local_sub = sub_provider in ("local_gguf", "local", "llama_cpp", "ollama")

                        def _serialize_sub_events(ev_list: Any) -> List[Dict[str, Any]]:
                            out_evs: List[Dict[str, Any]] = []
                            for ev in (ev_list or []):
                                if not isinstance(ev, dict):
                                    continue
                                e_type = str(ev.get("type") or "")
                                t_nm = str(ev.get("tool") or ev.get("name") or "")
                                raw_arg = ev.get("arg") if ev.get("arg") is not None else ev.get("args")
                                if isinstance(raw_arg, dict):
                                    t_arg = str(raw_arg.get("path") or raw_arg.get("cmd") or raw_arg.get("query") or raw_arg.get("file_path") or "")
                                else:
                                    t_arg = str(raw_arg or "")
                                    if t_arg.startswith("{") and t_arg.endswith("}"):
                                        try:
                                            import ast as _ast
                                            parsed_a = _ast.literal_eval(t_arg)
                                            if isinstance(parsed_a, dict):
                                                t_arg = str(parsed_a.get("path") or parsed_a.get("cmd") or parsed_a.get("query") or parsed_a.get("file_path") or t_arg)
                                        except Exception:
                                            pass
                                t_res = ev.get("result")
                                if isinstance(t_res, dict):
                                    res_txt = str(
                                        t_res.get("content")
                                        or t_res.get("output")
                                        or t_res.get("stdout")
                                        or t_res.get("error")
                                        or json.dumps(t_res, ensure_ascii=False)[:3000]
                                    )
                                    ok_flag = bool(t_res.get("success", True)) and "error" not in t_res
                                else:
                                    res_txt = str(ev.get("output") or ev.get("content") or (t_res if t_res is not None else ""))
                                    ok_flag = bool(ev.get("success", True))
                                out_evs.append({
                                    "type": e_type or ("tool" if t_nm else "text"),
                                    "tool": t_nm,
                                    "arg": t_arg[:300],
                                    "output": res_txt[:6000],
                                    "success": ok_flag,
                                })
                            return out_evs[-40:]

                        def _on_sub_progress(prog: Any) -> None:
                            p_role = str(getattr(prog, "role", "") or "Subagent")
                            p_sid = sid_by_role.get(p_role, "")
                            cur_t = str(getattr(prog, "current_tool", "") or "")
                            cur_a = str(getattr(prog, "tool_arg", "") or "")
                            p_stat = str(getattr(prog, "status", "") or "running")
                            p_thought = str(getattr(prog, "thought", "") or "")
                            p_events = _serialize_sub_events(getattr(prog, "events", None))
                            if p_sid and cur_t:
                                bg_mgr.update_subagent_tool(p_sid, cur_t, cur_a)
                            if on_subagent_event:
                                detail = f"{cur_t} {cur_a}".strip() if cur_t else p_thought[:180]
                                on_subagent_event({
                                    "phase": "progress",
                                    "id": p_sid or p_role,
                                    "name": p_role,
                                    "role": p_role,
                                    "status": p_stat,
                                    "tool": cur_t,
                                    "arg": cur_a,
                                    "summary": detail or "Working...",
                                    "events": p_events,
                                })

                        def _sub_model_call(history: List[Dict[str, Any]], task: Any = None) -> str:
                            task_sid = (getattr(task, "context", {}) or {}).get("subagent_id", "") if task and isinstance(getattr(task, "context", None), dict) else ""
                            is_aborted_fn = lambda: (
                                self.abort_requested
                                or getattr(task, "abort_requested", False)
                                or (bool(task_sid) and bg_mgr.is_subagent_cancelled(task_sid))
                            )
                            if is_aborted_fn():
                                return ""
                            sub_params = dict(gen_params)
                            sub_params["is_subagent"] = True
                            if sub_provider == "local_gguf":
                                from .engine import SimpleGGUFLoader
                                loader = SimpleGGUFLoader()
                                ok_l, err_l = loader.ensure_loaded(sub_model)
                                if not ok_l:
                                    return f"Error loading local subagent model: {err_l}"
                                parts_l: List[str] = []
                                for ch in loader.stream_chat(history, max_tokens=int(sub_params.get("max_tokens") or 2048)):
                                    if is_aborted_fn():
                                        break
                                    parts_l.append(ch)
                                return "".join(parts_l)
                            sub_key = (
                                self.api_key
                                if sub_provider == self.current_provider
                                else (self.settings.get_api_key(sub_provider) or "")
                            )
                            txt, _ = stream_chat_completion(
                                provider_id=sub_provider,
                                model_id=sub_model,
                                messages=history,
                                api_key=sub_key,
                                generation_params=sub_params,
                                is_aborted=is_aborted_fn,
                            )
                            return txt or ""

                        try:
                            tool_res = self.agent_runner.execute_subagents(
                                batch,
                                on_progress=_on_sub_progress,
                                is_local=is_local_sub,
                                model_call=_sub_model_call,
                            )
                        except Exception as exc_sub:
                            tool_res = {"success": False, "error": str(exc_sub), "subagents": []}

                        sub_results = tool_res.get("subagents") or []
                        for call_args, ag in zip(batch, sub_results + [{}] * max(0, len(batch) - len(sub_results))):
                            r_name = str(call_args.get("role") or ag.get("role") or "Subagent")
                            sid = str(call_args.get("_sid") or ag.get("subagent_id") or sid_by_role.get(r_name, ""))
                            res_sum = str(ag.get("summary") or tool_res.get("error") or "")
                            ok_st = str(ag.get("status") or ("finished" if tool_res.get("success", True) else "failed"))
                            final_st = "finished" if ok_st in ("completed", "finished") else "failed"
                            if sid:
                                bg_mgr.finish_subagent(sid, status=final_st, result=res_sum)
                            if on_subagent_event:
                                on_subagent_event({
                                    "phase": "finish",
                                    "id": sid or r_name,
                                    "name": r_name,
                                    "role": r_name,
                                    "status": final_st,
                                    "tool": "",
                                    "arg": "",
                                    "summary": res_sum[:260] or ("Completed" if final_st == "finished" else "Failed"),
                                    "output": res_sum,
                                    "events": _serialize_sub_events(ag.get("events")),
                                    "elapsed": float(ag.get("elapsed") or 0.0),
                                })

                        if on_tool_finish:
                            roles_lbl = ", ".join(str(c.get("role") or "Subagent") for c in batch)
                            on_tool_finish("subagent", roles_lbl, tool_res)

                        formatted_res = self.agent_runner.format_tool_result_for_llm("subagent", tool_res)
                        self.messages.append({"role": "user", "content": formatted_res})
                        self.transcript.append({"kind": "tool_result", "name": "subagent", "result": tool_res})
                        continue

                    idx_tc += 1
                    if on_tool_start:
                        on_tool_start(t_name, str(t_args))

                    tool_res = self.agent_runner.execute_tool(t_name, t_args)

                    if on_tool_finish:
                        on_tool_finish(t_name, str(t_args), tool_res)

                    formatted_res = self.agent_runner.format_tool_result_for_llm(t_name, tool_res)
                    self.messages.append({"role": "user", "content": formatted_res})
                    self.transcript.append({"kind": "tool_result", "name": t_name, "result": tool_res})

        return final_answer
