"""Cloudflare Quick Tunnel manager, auto-installer, and terminal QR renderer.

Powers both:
- `/tunnel` (Remote Web UI paired with the live CMDAI CODE session via Rust web host)
- `/share`  (Read-only session sharing served in an ephemeral terminal window)
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from typing import Callable, List, Optional, Tuple

CLOUDFLARED_WIN_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)
TRYCLOUDFLARE_RE = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


def get_app_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def get_local_cloudflared_path() -> str:
    exe = "cloudflared.exe" if sys.platform == "win32" else "cloudflared"
    return os.path.join(get_app_root(), "bin", exe)


def get_rust_web_binary() -> Optional[str]:
    root = get_app_root()
    exe = "cmdai-web.exe" if sys.platform == "win32" else "cmdai-web"
    candidates = [
        os.path.join(root, "web", "target", "release", exe),
        os.path.join(root, "bin", exe),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def find_cloudflared() -> Optional[str]:
    local_bin = get_local_cloudflared_path()
    if os.path.isfile(local_bin):
        return local_bin
    on_path = shutil.which("cloudflared")
    if on_path:
        return on_path
    return None


def install_cloudflared(
    on_status: Optional[Callable[[str], None]] = None,
) -> Tuple[bool, str]:
    """Download official cloudflared binary into `bin/cloudflared.exe` (no admin needed)."""
    target = get_local_cloudflared_path()
    os.makedirs(os.path.dirname(target), exist_ok=True)

    if sys.platform != "win32":
        return False, "Automatic binary download is currently configured for Windows. Install cloudflared via your package manager."

    tmp_path = target + ".downloading"
    try:
        if on_status:
            on_status("Connecting to GitHub Releases (cloudflare/cloudflared)...")

        req = urllib.request.Request(
            CLOUDFLARED_WIN_URL,
            headers={"User-Agent": "CMDAI-CODE-Installer/1.0"},
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            downloaded = 0
            chunk_size = 256 * 1024
            with open(tmp_path, "wb") as out:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if on_status:
                        mb = downloaded / (1024 * 1024)
                        if total > 0:
                            pct = min(100, int(downloaded * 100 / total))
                            tot_mb = total / (1024 * 1024)
                            on_status(f"Downloading cloudflared.exe... {pct}% ({mb:.1f} / {tot_mb:.1f} MB)")
                        else:
                            on_status(f"Downloading cloudflared.exe... {mb:.1f} MB")

        if os.path.exists(target):
            os.remove(target)
        os.replace(tmp_path, target)
        if on_status:
            on_status("cloudflared installed successfully.")
        return True, target
    except Exception as exc:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False, f"Failed to install cloudflared: {exc}"


# ---------------------------------------------------------------------------
# Pure-Python QR Code (Byte mode, ECC Level L, Versions 1..8) + Half-Blocks
# ---------------------------------------------------------------------------

_QR_VERSION_INFO = {
    # version: (total_codewords, ec_per_block, num_blocks, data_capacity_bytes, align_centers)
    1: (26, 7, 1, 17, []),
    2: (44, 10, 1, 32, [6, 18]),
    3: (70, 15, 1, 53, [6, 22]),
    4: (100, 20, 1, 78, [6, 26]),
    5: (134, 26, 1, 106, [6, 30]),
    6: (172, 18, 2, 134, [6, 34]),
    7: (196, 20, 2, 154, [6, 22, 38]),
    8: (242, 24, 2, 192, [6, 24, 42]),
}

_GF_EXP = [0] * 512
_GF_LOG = [0] * 256
_x = 1
for _i in range(255):
    _GF_EXP[_i] = _x
    _GF_LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _GF_EXP[_i] = _GF_EXP[_i - 255]


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _GF_EXP[_GF_LOG[a] + _GF_LOG[b]]


def _rs_generator(degree: int) -> List[int]:
    poly = [1]
    for i in range(degree):
        next_poly = [0] * (len(poly) + 1)
        factor = _GF_EXP[i]
        for j, coef in enumerate(poly):
            next_poly[j] ^= coef
            next_poly[j + 1] ^= _gf_mul(coef, factor)
        poly = next_poly
    return poly


def _rs_encode(data: List[int], ec_count: int) -> List[int]:
    gen = _rs_generator(ec_count)
    rem = list(data) + [0] * ec_count
    for i in range(len(data)):
        coef = rem[i]
        if coef != 0:
            for j in range(1, len(gen)):
                rem[i + j] ^= _gf_mul(gen[j], coef)
    return rem[len(data):]


def _format_bits_l_mask(mask: int) -> int:
    # ECC Level L = 01
    data = (0b01 << 3) | (mask & 0x7)
    rem = data << 10
    for i in range(4, -1, -1):
        if rem & (1 << (i + 10)):
            rem ^= 0x537 << i
    return ((data << 10) | rem) ^ 0x5412


def _version_bits(version: int) -> int:
    rem = version << 12
    for i in range(5, -1, -1):
        if rem & (1 << (i + 12)):
            rem ^= 0x1F25 << i
    return (version << 12) | rem


def _build_qr_matrix(text: str) -> List[List[bool]]:
    raw = text.encode("utf-8")
    version = None
    for v, info in _QR_VERSION_INFO.items():
        if len(raw) <= info[3]:
            version = v
            break
    if version is None:
        raise ValueError("QR payload too long for built-in encoder")

    total_cw, ec_per_block, num_blocks, _, align_centers = _QR_VERSION_INFO[version]
    data_cw_total = total_cw - ec_per_block * num_blocks

    # Encode bit stream: Mode 0100 (Byte), 8-bit length (versions 1..9), payload, terminator
    bits: List[int] = []

    def _push(val: int, length: int) -> None:
        for i in range(length - 1, -1, -1):
            bits.append((val >> i) & 1)

    _push(0b0100, 4)
    _push(len(raw), 8)
    for b in raw:
        _push(b, 8)
    term = min(4, data_cw_total * 8 - len(bits))
    _push(0, term)
    while len(bits) % 8 != 0:
        bits.append(0)

    data_bytes = []
    for i in range(0, len(bits), 8):
        byte_val = 0
        for j in range(8):
            byte_val = (byte_val << 1) | bits[i + j]
        data_bytes.append(byte_val)

    pad_cycle = (0xEC, 0x11)
    pi = 0
    while len(data_bytes) < data_cw_total:
        data_bytes.append(pad_cycle[pi % 2])
        pi += 1

    # Split into blocks and interleave
    block_size = data_cw_total // num_blocks
    data_blocks = [
        data_bytes[i * block_size : (i + 1) * block_size]
        for i in range(num_blocks)
    ]
    ec_blocks = [_rs_encode(blk, ec_per_block) for blk in data_blocks]

    interleaved: List[int] = []
    for i in range(block_size):
        for blk in data_blocks:
            interleaved.append(blk[i])
    for i in range(ec_per_block):
        for blk in ec_blocks:
            interleaved.append(blk[i])

    # Build matrix
    size = 17 + 4 * version
    mat: List[List[Optional[bool]]] = [[None] * size for _ in range(size)]
    func: List[List[bool]] = [[False] * size for _ in range(size)]

    def _set(r: int, c: int, val: bool, is_func: bool = True) -> None:
        if 0 <= r < size and 0 <= c < size:
            mat[r][c] = val
            if is_func:
                func[r][c] = True

    # Finder patterns + separators
    for fr, fc in ((0, 0), (0, size - 7), (size - 7, 0)):
        for r in range(-1, 8):
            for c in range(-1, 8):
                rr, cc = fr + r, fc + c
                if 0 <= rr < size and 0 <= cc < size:
                    in_outer = 0 <= r <= 6 and 0 <= c <= 6
                    on_border = r in (0, 6) or c in (0, 6)
                    in_center = 2 <= r <= 4 and 2 <= c <= 4
                    _set(rr, cc, bool(in_outer and (on_border or in_center)), True)

    # Timing patterns
    for i in range(8, size - 8):
        _set(6, i, i % 2 == 0, True)
        _set(i, 6, i % 2 == 0, True)

    # Alignment patterns
    for ar in align_centers:
        for ac in align_centers:
            if func[ar][ac]:
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    val = max(abs(dr), abs(dc)) != 1
                    _set(ar + dr, ac + dc, val, True)

    # Dark module & reserve format areas
    _set(size - 8, 8, True, True)
    for i in range(9):
        if not func[8][i]:
            _set(8, i, False, True)
        if not func[i][8]:
            _set(i, 8, False, True)
    for i in range(8):
        _set(8, size - 1 - i, False, True)
        _set(size - 1 - i, 8, False, True)

    # Version info for v >= 7
    if version >= 7:
        vb = _version_bits(version)
        for i in range(18):
            bit = bool((vb >> i) & 1)
            r = i // 3
            c = size - 11 + (i % 3)
            _set(r, c, bit, True)
            _set(c, r, bit, True)

    # Place data bits with mask 0: (r + c) % 2 == 0
    bit_stream: List[bool] = []
    for byte_val in interleaved:
        for shift in range(7, -1, -1):
            bit_stream.append(bool((byte_val >> shift) & 1))

    idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for dc in (0, -1):
                c = col + dc
                if not func[r][c]:
                    b = bit_stream[idx] if idx < len(bit_stream) else False
                    idx += 1
                    if (r + c) % 2 == 0:
                        b = not b
                    mat[r][c] = b
        col -= 2
        upward = not upward

    # Write format bits for ECC L, mask 0
    fmt = _format_bits_l_mask(0)
    fmt_coords_1 = [
        (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
        (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
    ]
    fmt_coords_2 = [
        (size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8),
        (size - 5, 8), (size - 6, 8), (size - 7, 8),
        (8, size - 8), (8, size - 7), (8, size - 6), (8, size - 5),
        (8, size - 4), (8, size - 3), (8, size - 2), (8, size - 1),
    ]
    for i in range(15):
        bit = bool((fmt >> (14 - i)) & 1)
        r1, c1 = fmt_coords_1[i]
        r2, c2 = fmt_coords_2[i]
        mat[r1][c1] = bit
        mat[r2][c2] = bit

    return [[bool(cell) for cell in row] for row in mat]


def render_qr_unicode(data: str, border: int = 2, indent: str = "  ") -> str:
    """Render a compact scannable QR code using Unicode half-blocks (dark-on-light inverted for dark terminals)."""
    matrix: Optional[List[List[bool]]] = None

    try:
        import segno  # type: ignore
        qr = segno.make(data, error="l")
        matrix = [[bool(cell) for cell in row] for row in qr.matrix]
    except Exception:
        try:
            import qrcode  # type: ignore
            qr = qrcode.QRCode(border=0)
            qr.add_data(data)
            qr.make(fit=True)
            matrix = qr.get_matrix()
        except Exception:
            try:
                matrix = _build_qr_matrix(data)
            except Exception:
                return f"{indent}[QR unavailable for URL length {len(data)}]"

    # Pad with white quiet zone (False = light module)
    w = len(matrix[0]) + border * 2
    padded: List[List[bool]] = [[False] * w for _ in range(border)]
    for row in matrix:
        padded.append([False] * border + row + [False] * border)
    for _ in range(border):
        padded.append([False] * w)

    # On dark terminals, render light quiet-zone/modules as filled white blocks (█)
    # and dark QR modules as dark terminal background (space) so phone cameras scan instantly.
    lines: List[str] = []
    for r in range(0, len(padded), 2):
        top = padded[r]
        bot = padded[r + 1] if r + 1 < len(padded) else [False] * w
        chars = []
        for c in range(w):
            t_light = not top[c]
            b_light = not bot[c]
            if t_light and b_light:
                chars.append("█")
            elif t_light and not b_light:
                chars.append("▀")
            elif not t_light and b_light:
                chars.append("▄")
            else:
                chars.append(" ")
        lines.append(indent + "".join(chars))
    return "\n".join(lines)


def launch_tunnel_terminal(
    mode: str,
    backend_port: int = 8080,
    token: str = "",
    pin: str = "",
    share_html_path: str = "",
    session_title: str = "",
    title: str = "",
    session_id: str = "",
) -> subprocess.Popen:
    """Spawn a dedicated new Windows console running `tunnel_console.py`."""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tunnel_console.py")
    cmd = [
        sys.executable,
        script_path,
        "--mode",
        mode,
        "--backend-port",
        str(backend_port),
    ]
    if token:
        cmd += ["--token", token]
    if pin:
        cmd += ["--pin", pin]
    if share_html_path:
        cmd += ["--share-file", share_html_path]
    resolved_title = title or session_title
    if resolved_title:
        cmd += ["--title", resolved_title]
    if session_id:
        cmd += ["--session-id", session_id]

    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)

    return subprocess.Popen(cmd, creationflags=creationflags, cwd=get_app_root())


def write_temp_share_html(html_content: str, session_id: str = "session") -> str:
    safe = "".join(c for c in session_id if c.isalnum() or c in ("-", "_")) or "session"
    fd, path = tempfile.mkstemp(prefix=f"cmdai_share_{safe}_", suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html_content)
    return path
