"""Hugging Face GGUF discovery, RAM-fit estimation, and resumable downloader."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import psutil
import requests

from .model_paths import resolve_models_dir

HF_API_BASE = "https://huggingface.co"
HF_USER_AGENT = "CMDAI/1.0"

CURATED_GGUF_REPOS: List[Dict[str, Any]] = [
    {
        "repo_id": "Qwen/Qwen2.5-7B-Instruct-GGUF",
        "label": "Qwen 2.5 7B Instruct",
        "description": "Strong general reasoning, chat, and tool calling",
        "tags": ["qwen", "chat", "tools"],
    },
    {
        "repo_id": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "label": "Qwen 2.5 Coder 7B",
        "description": "Fast local coding and repository assistance",
        "tags": ["qwen", "coding"],
    },
    {
        "repo_id": "bartowski/Llama-3.2-3B-Instruct-GGUF",
        "label": "Llama 3.2 3B Instruct",
        "description": "Lightweight everyday assistant for modest RAM",
        "tags": ["llama", "fast", "lightweight"],
    },
    {
        "repo_id": "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        "label": "Llama 3.1 8B Instruct",
        "description": "Balanced 8B general-purpose assistant",
        "tags": ["llama", "general"],
    },
    {
        "repo_id": "bartowski/gemma-2-9b-it-GGUF",
        "label": "Gemma 2 9B Instruct",
        "description": "High-quality Google Gemma 2 instruct weights",
        "tags": ["gemma", "google"],
    },
    {
        "repo_id": "microsoft/Phi-3.5-mini-instruct-GGUF",
        "label": "Phi-3.5 Mini 3.8B",
        "description": "Compact reasoning model with 128k context",
        "tags": ["phi", "fast", "lightweight"],
    },
    {
        "repo_id": "bartowski/DeepSeek-R1-Distill-Qwen-7B-GGUF",
        "label": "DeepSeek R1 Distill Qwen 7B",
        "description": "Step-by-step chain-of-thought reasoning model",
        "tags": ["deepseek", "reasoning"],
    },
    {
        "repo_id": "bartowski/Mistral-7B-Instruct-v0.3-GGUF",
        "label": "Mistral 7B Instruct v0.3",
        "description": "Classic 7B instruction-tuned model",
        "tags": ["mistral", "general"],
    },
]

_QUANT_RE = re.compile(
    r"(?<![A-Za-z0-9])(I?Q\d+(?:_[A-Z0-9]+)*|BF16|F16|F32)(?![A-Za-z0-9])",
    re.IGNORECASE,
)

_QUANT_PRIORITY: Dict[str, int] = {
    "Q4_K_M": 0,
    "Q4_K_S": 1,
    "Q5_K_M": 2,
    "Q5_K_S": 3,
    "Q6_K": 4,
    "Q8_0": 5,
    "IQ4_XS": 6,
    "Q3_K_M": 7,
    "Q4_0": 8,
    "F16": 20,
    "BF16": 21,
}


def get_system_ram_gb() -> float:
    """Return total physical system memory in GiB."""
    try:
        return max(1.0, psutil.virtual_memory().total / (1024 ** 3))
    except Exception:
        return 16.0


def parse_quant_tag(filename: str) -> str:
    """Extract normalized quantization label (e.g., Q4_K_M) from a GGUF filename."""
    stem = os.path.basename(filename or "")
    if "mmproj" in stem.lower():
        return "MMPROJ"
    match = _QUANT_RE.search(stem)
    if match:
        return match.group(1).upper()
    return "GGUF"


def format_bytes(num_bytes: int) -> str:
    """Human-readable IEC size formatting."""
    size = float(max(0, int(num_bytes or 0)))
    if size >= 1024 ** 3:
        return f"{size / (1024 ** 3):.2f} GB"
    if size >= 1024 ** 2:
        return f"{size / (1024 ** 2):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.0f} KB"
    return f"{int(size)} B"


def assess_ram_fit(size_bytes: int, ram_gb: Optional[float] = None) -> Dict[str, Any]:
    """Estimate whether a GGUF quantization fits into system RAM."""
    total_ram = float(ram_gb if ram_gb is not None else get_system_ram_gb())
    if size_bytes <= 0:
        return {
            "status": "unknown",
            "label": "Unknown",
            "color": "#8b949e",
            "est_gb": 0.0,
            "ram_gb": total_ram,
        }
    weights_gb = float(size_bytes) / (1024 ** 3)
    est_gb = weights_gb * 1.15 + 0.5
    if est_gb <= total_ram * 0.65:
        return {
            "status": "fits",
            "label": "Full fit",
            "color": "#7ee787",
            "est_gb": round(est_gb, 2),
            "ram_gb": round(total_ram, 1),
        }
    if est_gb <= total_ram * 0.90:
        return {
            "status": "tight",
            "label": "Tight fit",
            "color": "#d29922",
            "est_gb": round(est_gb, 2),
            "ram_gb": round(total_ram, 1),
        }
    return {
        "status": "heavy",
        "label": "Exceeds RAM",
        "color": "#f85149",
        "est_gb": round(est_gb, 2),
        "ram_gb": round(total_ram, 1),
    }


def get_curated_repos(query: str = "") -> List[Dict[str, Any]]:
    """Return curated GGUF repositories filtered by an optional query string."""
    q = (query or "").strip().lower()
    out: List[Dict[str, Any]] = []
    for item in CURATED_GGUF_REPOS:
        hay = f"{item['repo_id']} {item['label']} {item['description']} {' '.join(item.get('tags', []))}".lower()
        if not q or all(tok in hay for tok in q.split()):
            out.append(
                {
                    "repo_id": item["repo_id"],
                    "label": item["label"],
                    "description": item["description"],
                    "downloads": 0,
                    "likes": 0,
                    "curated": True,
                }
            )
    return out


def search_hf_models(
    query: str = "",
    limit: int = 20,
    timeout: float = 12.0,
) -> List[Dict[str, Any]]:
    """Search Hugging Face Hub for GGUF repositories."""
    params: Dict[str, Any] = {
        "filter": "gguf",
        "sort": "downloads",
        "direction": -1,
        "limit": max(1, min(int(limit), 50)),
    }
    clean_q = (query or "").strip()
    if clean_q:
        params["search"] = clean_q

    resp = requests.get(
        f"{HF_API_BASE}/api/models",
        params=params,
        headers={"User-Agent": HF_USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list):
        return []

    results: List[Dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        repo_id = str(entry.get("id") or entry.get("modelId") or "").strip()
        if not repo_id:
            continue
        results.append(
            {
                "repo_id": repo_id,
                "label": repo_id.split("/")[-1],
                "description": "",
                "downloads": int(entry.get("downloads") or 0),
                "likes": int(entry.get("likes") or 0),
                "last_modified": str(entry.get("lastModified") or ""),
                "curated": False,
            }
        )
    return results


def _build_gguf_entry(repo_id: str, rfilename: str, size_bytes: int, ram_gb: float) -> Dict[str, Any]:
    base = os.path.basename(rfilename)
    is_mmproj = "mmproj" in base.lower()
    quant = parse_quant_tag(base)
    return {
        "repo_id": repo_id,
        "rfilename": rfilename,
        "filename": base,
        "size_bytes": int(size_bytes or 0),
        "size_str": format_bytes(size_bytes) if size_bytes > 0 else "Unknown size",
        "quant": quant,
        "is_mmproj": is_mmproj,
        "ram_fit": assess_ram_fit(size_bytes, ram_gb=ram_gb),
        "download_url": f"{HF_API_BASE}/{repo_id}/resolve/main/{rfilename}",
    }


def list_repo_gguf_files(repo_id: str, timeout: float = 12.0) -> List[Dict[str, Any]]:
    """List GGUF artifacts inside a Hugging Face repository with sizes and RAM-fit info."""
    clean_repo = (repo_id or "").strip().strip("/")
    if not clean_repo or "/" not in clean_repo:
        raise ValueError(f"Expected '<owner>/<repo>', got: {repo_id!r}")

    ram_gb = get_system_ram_gb()
    files: List[Dict[str, Any]] = []

    resp = requests.get(
        f"{HF_API_BASE}/api/models/{clean_repo}",
        params={"blobs": "true"},
        headers={"User-Agent": HF_USER_AGENT},
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json() or {}
    siblings = data.get("siblings") if isinstance(data, dict) else []

    size_map: Dict[str, int] = {}
    gguf_names: List[str] = []
    if isinstance(siblings, list):
        for item in siblings:
            if not isinstance(item, dict):
                continue
            rname = str(item.get("rfilename") or "").strip()
            if not rname.lower().endswith(".gguf"):
                continue
            gguf_names.append(rname)
            sz = item.get("size")
            if not sz and isinstance(item.get("lfs"), dict):
                sz = item["lfs"].get("size")
            if sz:
                size_map[rname] = int(sz)

    # Fetch /tree/main sizes if blobs payload lacked LFS sizes.
    if gguf_names and len(size_map) < len(gguf_names):
        try:
            tree_resp = requests.get(
                f"{HF_API_BASE}/api/models/{clean_repo}/tree/main",
                params={"recursive": "true"},
                headers={"User-Agent": HF_USER_AGENT},
                timeout=timeout,
            )
            if tree_resp.ok:
                for node in tree_resp.json() or []:
                    if not isinstance(node, dict):
                        continue
                    path = str(node.get("path") or "").strip()
                    sz = node.get("size") or (node.get("lfs") or {}).get("size")
                    if path and sz:
                        size_map[path] = int(sz)
        except Exception:
            pass

    for rname in gguf_names:
        files.append(_build_gguf_entry(clean_repo, rname, size_map.get(rname, 0), ram_gb))

    files.sort(
        key=lambda f: (
            1 if f["is_mmproj"] else 0,
            _QUANT_PRIORITY.get(f["quant"], 15),
            f["size_bytes"] or 0,
            f["filename"].lower(),
        )
    )
    return files


def pick_best_gguf_file(
    files: List[Dict[str, Any]],
    quant_hint: str = "",
) -> Optional[Dict[str, Any]]:
    """Select the best GGUF file matching an optional quantization hint or Q4_K_M default."""
    candidates = [f for f in files if not f.get("is_mmproj")]
    if not candidates:
        candidates = list(files)
    if not candidates:
        return None

    hint = (quant_hint or "").strip().lower()
    if hint:
        for f in candidates:
            if f["quant"].lower() == hint or hint in f["filename"].lower():
                return f

    ram_gb = get_system_ram_gb()
    # Prefer Q4_K_M / Q5_K_M / Q4_K_S that fits in RAM first.
    fitting = [f for f in candidates if assess_ram_fit(f.get("size_bytes", 0), ram_gb)["status"] in ("fits", "tight", "unknown")]
    pool = fitting or candidates
    for preferred in ("Q4_K_M", "Q4_K_S", "Q5_K_M", "Q8_0"):
        for f in pool:
            if f.get("quant") == preferred:
                return f
    return pool[0]


def resolve_pull_target(model_or_repo: str, quant_hint: str = "") -> Tuple[str, Dict[str, Any]]:
    """Resolve `<owner>/<repo>[:quant]` or free-text query to `(repo_id, file_entry)`."""
    raw = (model_or_repo or "").strip()
    if not raw:
        raise ValueError("Model name or Hugging Face repo is required.")

    effective_hint = quant_hint.strip()
    if ":" in raw and "/" in raw:
        raw, _, suffix = raw.partition(":")
        if suffix and not effective_hint:
            effective_hint = suffix.strip()
    elif ":" in raw and "/" not in raw:
        raw, _, suffix = raw.partition(":")
        if suffix and not effective_hint:
            effective_hint = suffix.strip()

    repo_id = raw
    if "/" not in raw:
        matches = search_hf_models(query=raw, limit=8)
        if not matches:
            curated = get_curated_repos(raw)
            if not curated:
                raise RuntimeError(f"No Hugging Face GGUF repositories found for {raw!r}.")
            matches = curated
        repo_id = matches[0]["repo_id"]

    files = list_repo_gguf_files(repo_id)
    if not files:
        raise RuntimeError(f"No .gguf files found in Hugging Face repository {repo_id!r}.")

    picked = pick_best_gguf_file(files, quant_hint=effective_hint)
    if picked is None:
        raise RuntimeError(f"Could not select a GGUF artifact in {repo_id!r}.")
    return repo_id, picked


def download_gguf_model(
    repo_id: str,
    rfilename: str,
    dest_dir: Optional[str] = None,
    on_progress: Optional[Callable[[Dict[str, Any]], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    timeout: float = 30.0,
) -> str:
    """Download a GGUF file from Hugging Face Hub with HTTP Range resume support."""
    target_dir = os.path.abspath(dest_dir or resolve_models_dir())
    os.makedirs(target_dir, exist_ok=True)

    local_name = os.path.basename(rfilename)
    dest_path = os.path.join(target_dir, local_name)
    part_path = dest_path + ".part"
    url = f"{HF_API_BASE}/{repo_id.strip('/')}/resolve/main/{rfilename.lstrip('/')}"

    existing = os.path.getsize(part_path) if os.path.exists(part_path) else 0
    headers: Dict[str, str] = {"User-Agent": HF_USER_AGENT}
    if existing > 0:
        headers["Range"] = f"bytes={existing}-"

    with requests.get(
        url,
        headers=headers,
        stream=True,
        allow_redirects=True,
        timeout=timeout,
    ) as resp:
        if resp.status_code == 416 and existing > 0:
            os.replace(part_path, dest_path)
            return dest_path

        resp.raise_for_status()
        resuming = resp.status_code == 206 and existing > 0
        downloaded = existing if resuming else 0
        mode = "ab" if resuming else "wb"

        content_len = int(resp.headers.get("Content-Length") or 0)
        total_bytes = (existing + content_len) if (resuming and content_len > 0) else content_len
        if total_bytes <= 0 and "Content-Range" in resp.headers:
            cr = resp.headers["Content-Range"]
            if "/" in cr:
                try:
                    total_bytes = int(cr.rsplit("/", 1)[1])
                except Exception:
                    pass

        started_at = time.monotonic()
        last_emit = 0.0
        session_bytes = 0

        with open(part_path, mode) as out_f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if is_cancelled and is_cancelled():
                    raise InterruptedError("Download cancelled by user.")
                if not chunk:
                    continue
                out_f.write(chunk)
                chunk_len = len(chunk)
                downloaded += chunk_len
                session_bytes += chunk_len

                now = time.monotonic()
                if on_progress and (now - last_emit >= 0.15 or (total_bytes > 0 and downloaded >= total_bytes)):
                    elapsed = max(0.05, now - started_at)
                    speed = session_bytes / elapsed
                    pct = (downloaded / total_bytes * 100.0) if total_bytes > 0 else 0.0
                    eta = ((total_bytes - downloaded) / speed) if (total_bytes > 0 and speed > 1.0) else 0.0
                    on_progress(
                        {
                            "repo_id": repo_id,
                            "filename": local_name,
                            "dest_path": dest_path,
                            "downloaded_bytes": downloaded,
                            "total_bytes": total_bytes,
                            "percent": min(100.0, pct),
                            "speed_bps": speed,
                            "eta_sec": eta,
                        }
                    )
                    last_emit = now

    os.replace(part_path, dest_path)
    if on_progress:
        on_progress(
            {
                "repo_id": repo_id,
                "filename": local_name,
                "dest_path": dest_path,
                "downloaded_bytes": downloaded,
                "total_bytes": downloaded,
                "percent": 100.0,
                "speed_bps": 0.0,
                "eta_sec": 0.0,
            }
        )
    return dest_path
