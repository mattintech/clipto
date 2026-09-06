import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


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
            # Doesn't actually send packets, but prompts OS to select route
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
    # Remove null bytes and control chars
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)
    # Replace unsafe characters
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
    """Return an OSC 8 terminal hyperlink if terminal is interactive."""
    display_text = text or url
    if sys.stdout.isatty():
        return f"\033]8;;{url}\033\\{display_text}\033]8;;\033\\"
    return display_text
