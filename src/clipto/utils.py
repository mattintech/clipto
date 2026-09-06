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
