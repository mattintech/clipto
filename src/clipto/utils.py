import os
import re
import socket
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Optional

ANSI_REGEX = re.compile(r"\033\]8;;.*?\033\\|\033\[[0-9;]*[a-zA-Z]|\033\]8;;\033\\|\033\][^\a\033]*(\a|\033\\)")


def strip_ansi(s: str) -> str:
    """Remove ANSI escape codes and OSC hyperlinks from a string."""
    return ANSI_REGEX.sub("", s)


def visible_width(s: str) -> int:
    """
    Calculate visual display column width in a terminal.
    Excludes invisible ANSI/OSC escape sequences and accounts for wide characters/emojis.
    """
    clean = strip_ansi(s)
    width = 0
    for ch in clean:
        ea = unicodedata.east_asian_width(ch)
        if ea in ("W", "F") or ord(ch) > 0x10000:
            width += 2
        else:
            width += 1
    return width


def find_available_port(preferred_port: int = 8765, max_attempts: int = 50) -> int:
    """
    Find an available TCP port.
    If preferred_port is 0, let the OS allocate an ephemeral port.
    Otherwise, check preferred_port up to preferred_port + max_attempts.
    """
    if preferred_port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    for port in range(preferred_port, preferred_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue

    raise RuntimeError(f"No available port found in range {preferred_port} - {preferred_port + max_attempts}")


def get_local_ip() -> Optional[str]:
    """Determine the LAN IP address of this machine."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return None


def get_tailscale_ip() -> Optional[str]:
    """Detect Tailscale IPv4 if available."""
    try:
        result = subprocess.run(
            ["tailscale", "ip", "-4"],
            capture_output=True,
            text=True,
            timeout=1,
            check=False,
        )
        if result.returncode == 0:
            ip = result.stdout.strip().split("\n")[0]
            if ip.startswith("100."):
                return ip
    except Exception:
        pass
    return None


def sanitize_filename(filename: str, default_name: str = "upload") -> str:
    """Sanitize uploaded filenames to prevent path traversal and unsafe characters."""
    filename = os.path.basename(filename).strip()
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)
    filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
    return filename or default_name


def get_unique_path(directory: Path, filename: str) -> Path:
    """
    Ensure the path does not overwrite an existing file.
    e.g., photo.png -> photo (1).png -> photo (2).png
    """
    target = directory / filename
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    counter = 1

    while True:
        candidate = directory / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def terminal_hyperlink(url: str, text: Optional[str] = None) -> str:
    """Return an OSC 8 terminal hyperlink if stdout/stderr is interactive."""
    display_text = text or url
    if sys.stderr.isatty():
        return f"\033]8;;{url}\033\\{display_text}\033]8;;\033\\"
    return display_text


def render_qr_terminal(url: str, border: int = 2) -> str:
    """Generate a compact ANSI half-block QR code for the terminal."""
    try:
        from clipto.qrcodegen import QrCode
    except ImportError:
        return ""

    qr = QrCode.encode_text(url, QrCode.Ecc.MEDIUM)
    size = qr.get_size()
    total_size = size + border * 2

    def is_dark(r, c):
        x = c - border
        y = r - border
        if 0 <= x < size and 0 <= y < size:
            return qr.get_module(x, y)
        return False

    lines = []
    for r in range(0, total_size, 2):
        row = []
        for c in range(total_size):
            top_dark = is_dark(r, c)
            bottom_dark = is_dark(r + 1, c) if r + 1 < total_size else False

            if top_dark and bottom_dark:
                row.append("\033[40m \033[0m")
            elif top_dark and not bottom_dark:
                row.append("\033[47;30m▀\033[0m")
            elif not top_dark and bottom_dark:
                row.append("\033[47;30m▄\033[0m")
            else:
                row.append("\033[47m \033[0m")
        lines.append("  " + "".join(row))
    return "\n".join(lines)


def render_qr_svg(url: str, border: int = 2) -> str:
    """Generate a crisp standalone SVG QR code."""
    try:
        from clipto.qrcodegen import QrCode
    except ImportError:
        return ""

    qr = QrCode.encode_text(url, QrCode.Ecc.MEDIUM)
    size = qr.get_size()
    total = size + border * 2
    path_data = " ".join(
        f"M{x + border},{y + border}h1v1h-1z"
        for y in range(size)
        for x in range(size)
        if qr.get_module(x, y)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" shape-rendering="crispEdges">'
        f'<rect width="{total}" height="{total}" fill="#ffffff" rx="1"/>'
        f'<path fill="#0f172a" d="{path_data}"/>'
        f"</svg>"
    )
