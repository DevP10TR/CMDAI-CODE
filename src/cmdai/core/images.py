"""Clipboard image capture, path detection, and multimodal base64 encoding."""

from __future__ import annotations

import base64
import io
import os
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def _pasted_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "cmdaicode-pasted")
    os.makedirs(d, exist_ok=True)
    return d


def is_image_file_path(raw: str) -> Optional[str]:
    """Return normalized path if `raw` is a single existing image file path."""
    s = (raw or "").strip()
    if not s or "\n" in s:
        return None
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    if not s:
        return None
    ext = os.path.splitext(s)[1].lower()
    if ext not in IMAGE_EXTS:
        return None
    if os.path.isfile(s):
        return os.path.abspath(s)
    return None


def grab_clipboard_image_to_temp() -> Optional[str]:
    """Capture an image from the OS clipboard into a temp PNG file, or return None."""
    out_path = os.path.join(_pasted_dir(), f"paste_{int(time.time() * 1000)}.png")

    # 1. Try Pillow ImageGrab (works on Windows & macOS)
    try:
        from PIL import ImageGrab, Image  # type: ignore

        clip = ImageGrab.grabclipboard()
        if isinstance(clip, Image.Image):
            clip.save(out_path, format="PNG")
            if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                return out_path
        elif isinstance(clip, list):
            for item in clip:
                p = is_image_file_path(str(item))
                if p:
                    return p
    except Exception:
        pass

    # 2. Windows PowerShell fallback using System.Windows.Forms.Clipboard
    if os.name == "nt":
        try:
            ps_script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "if ([System.Windows.Forms.Clipboard]::ContainsImage()) { "
                "$img = [System.Windows.Forms.Clipboard]::GetImage(); "
                f"$img.Save('{out_path}', [System.Drawing.Imaging.ImageFormat]::Png); "
                "Write-Output 'OK' "
                "} elseif ([System.Windows.Forms.Clipboard]::ContainsFileDropList()) { "
                "$f = [System.Windows.Forms.Clipboard]::GetFileDropList()[0]; "
                "Write-Output ('FILE:' + $f) "
                "}"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-STA", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=4,
            )
            out = (res.stdout or "").strip()
            if out == "OK" and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                return out_path
            if out.startswith("FILE:"):
                return is_image_file_path(out[5:].strip())
        except Exception:
            pass

    return None


def encode_image_data_url(path: str, max_dim: int = 1600) -> Optional[str]:
    """Read `path`, optionally resize to `max_dim`, and return `data:image/...;base64,...`."""
    if not path or not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    mime = "image/png"
    if ext in (".jpg", ".jpeg"):
        mime = "image/jpeg"
    elif ext == ".webp":
        mime = "image/webp"
    elif ext == ".gif":
        mime = "image/gif"

    try:
        from PIL import Image  # type: ignore

        with Image.open(path) as img:
            w, h = img.size
            if max(w, h) > max_dim:
                scale = max_dim / float(max(w, h))
                img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            if img.mode in ("RGBA", "P", "LA"):
                bg = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                bg.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = bg
            elif img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=85)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return f"data:image/jpeg;base64,{b64}"
    except Exception:
        pass

    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return None


def build_multimodal_content(text: str, image_paths: List[str], max_dim: int = 1600) -> Any:
    """Build OpenAI-compatible multimodal content list if images encode cleanly, else `text`."""
    parts: List[Dict[str, Any]] = [{"type": "text", "text": text}]
    added = 0
    for p in image_paths:
        url = encode_image_data_url(p, max_dim=max_dim)
        if url:
            parts.append({"type": "image_url", "image_url": {"url": url}})
            added += 1
    return parts if added > 0 else text
