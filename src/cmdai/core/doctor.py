import os
import shutil
import subprocess
import sys
from typing import Any, List, Tuple


def _line(icon: str, color: str, label: str, value: str) -> None:
    print(f"  {color}{icon}\x1b[0m  {label:<22} {value}")


def _section(title: str) -> None:
    print(f"\n  \x1b[1;97m{title}\x1b[0m")
    print(f"  \x1b[90m{'─' * 64}\x1b[0m")


def run_doctor() -> int:
    import psutil
    from .providers import PROVIDERS_CATALOG, load_custom_providers
    from .resource_limits import get_dynamic_context_limit
    from .settings import get_settings

    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    settings = get_settings()
    cfg = settings.config
    try:
        load_custom_providers()
    except Exception:
        pass

    print("\n  \x1b[1;36m⌬  CMDAI CODE\x1b[0m \x1b[90m·\x1b[0m \x1b[1;97mSystem & Provider Doctor\x1b[0m")
    print(f"  \x1b[90m{'━' * 64}\x1b[0m")

    # ── 1. System & Runtime ──────────────────────────────────────────────────
    _section("System & Runtime")

    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    _line("✔" if py_ok else "✖", "\x1b[32m" if py_ok else "\x1b[31m", "Python", f"{py_ver} \x1b[90m({sys.executable})\x1b[0m")

    git_ver = "Not installed"
    git_ok = False
    try:
        git_ver = subprocess.check_output(["git", "--version"], stderr=subprocess.DEVNULL, text=True).strip()
        git_ok = True
    except Exception:
        pass
    _line("✔" if git_ok else "✖", "\x1b[32m" if git_ok else "\x1b[31m", "Git", git_ver)

    vm = psutil.virtual_memory()
    total_ram_gb = vm.total / (1024**3)
    avail_ram_gb = vm.available / (1024**3)
    ram_ok = avail_ram_gb >= 2.0
    _line(
        "✔" if ram_ok else "!",
        "\x1b[32m" if ram_ok else "\x1b[33m",
        "System RAM",
        f"{avail_ram_gb:.1f} GB free \x1b[90m/ {total_ram_gb:.1f} GB total\x1b[0m",
    )

    vulkan_installed = bool(
        os.environ.get("VULKAN_SDK") or shutil.which("vulkan-1.dll") or os.path.exists(r"C:\VulkanSDK")
    )
    _line(
        "✔" if vulkan_installed else "!",
        "\x1b[32m" if vulkan_installed else "\x1b[33m",
        "Vulkan SDK",
        "Detected" if vulkan_installed else "\x1b[90mNot detected (CPU mode)\x1b[0m",
    )

    llama_ok = False
    try:
        import llama_cpp
        llama_ok = True
        llama_ver = getattr(llama_cpp, "__version__", "installed")
    except Exception:
        llama_ver = "Not installed"
    _line("✔" if llama_ok else "!", "\x1b[32m" if llama_ok else "\x1b[33m", "llama-cpp-python", llama_ver)

    # ── 2. Active Configuration & Voice ──────────────────────────────────────
    _section("Active Configuration")

    active_loader = str(cfg.get("active_loader", "cpu") or "cpu").upper()
    flash_attn = bool(cfg.get("flash_attn", True))
    kv_type = str(cfg.get("kv_cache_type", "auto") or "auto")
    use_kr = bool(cfg.get("settings", {}).get("use_system_keyring", False))

    def_prov = str(cfg.get("default_provider", "local_gguf") or "local_gguf")
    def_mod = str(cfg.get("default_model", "") or "(not set)")
    dyn_limit = get_dynamic_context_limit(def_mod, def_prov)

    _line("·", "\x1b[36m", "Default Provider", def_prov)
    _line("·", "\x1b[36m", "Default Model", f"{def_mod} \x1b[90m(L_ctx: {dyn_limit:,} tokens)\x1b[0m")
    _line("·", "\x1b[36m", "GGUF Runtime", f"loader={active_loader}  flash_attn={'ON' if flash_attn else 'OFF'}  kv={kv_type}")
    _line("·", "\x1b[36m", "API Keyring", "ON (Windows Credential Manager)" if use_kr else "\x1b[90mOFF (config.json / env)\x1b[0m")

    vcfg = cfg.get("voice", {}) if isinstance(cfg.get("voice"), dict) else {}
    v_prov = str(vcfg.get("provider", "local") or "local")
    v_mod = str(vcfg.get("model", "small") or "small")
    v_lang = str(vcfg.get("language", "auto") or "auto")
    try:
        from .voice import is_voice_model_ready
        v_ready, _ = is_voice_model_ready()
    except Exception:
        v_ready = False
    _line(
        "✔" if v_ready else "!",
        "\x1b[32m" if v_ready else "\x1b[33m",
        "Voice Dictation",
        f"{v_prov}:{v_mod} ({v_lang}) — {'\x1b[32mReady\x1b[0m' if v_ready else '\x1b[33mNot installed / no key\x1b[0m'}",
    )

    # ── 3. All API & Local Providers ─────────────────────────────────────────
    all_pids = list(PROVIDERS_CATALOG.keys())
    _section(f"All Providers ({len(all_pids)})")

    ready_rows: List[Tuple[str, str]] = []
    unset_rows: List[Tuple[str, str]] = []

    for pid in all_pids:
        pinfo = PROVIDERS_CATALOG[pid]
        pname = str(getattr(pinfo, "name", pid) or pid)
        if len(pname) > 26:
            pname = pname[:23] + "..."
        key_val = settings.get_api_key(pid)
        key_src = settings.get_api_key_source(pid)

        is_local_or_keyless = (
            pid in ("local_gguf", "localllmapi", "ollama", "lmstudio", "opencode")
            or not getattr(pinfo, "requires_key", True)
        )
        if is_local_or_keyless and not key_val:
            ready_rows.append((pname, "\x1b[32mLocal / Keyless\x1b[0m"))
        elif key_val:
            masked = key_val[:4] + "..." + key_val[-3:] if len(key_val) > 8 else "***"
            src_tag = f", {key_src}" if key_src else ""
            ready_rows.append((pname, f"\x1b[32mConfigured\x1b[0m \x1b[90m({masked}{src_tag})\x1b[0m"))
        else:
            unset_rows.append((pname, "\x1b[90mNot set\x1b[0m"))

    for pname, status in ready_rows:
        print(f"  \x1b[32m●\x1b[0m  {pname:<28} {status}")
    for pname, status in unset_rows:
        print(f"  \x1b[90m○\x1b[0m  {pname:<28} {status}")

    # ── 4. Workspace / Sessions Summary ──────────────────────────────────────
    app_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    sessions_dir = os.path.join(app_root, "app", "sessions")
    sess_count = 0
    if os.path.exists(sessions_dir):
        sess_count = sum(1 for f in os.listdir(sessions_dir) if f.endswith(".json"))

    print(f"\n  \x1b[90m{'━' * 64}\x1b[0m")
    print(
        f"  \x1b[32m✔ Doctor complete.\x1b[0m  "
        f"\x1b[90mReady providers: {len(ready_rows)}/{len(all_pids)} · Saved sessions: {sess_count}\x1b[0m\n"
    )
    return 0
