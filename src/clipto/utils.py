import json
import os
import re
import socket
import subprocess
import sys
import unicodedata
import urllib.parse
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
    """Sanitize uploaded filenames to prevent path traversal, hidden files, and unsafe characters."""
    filename = os.path.basename(filename).strip()
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)
    filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
    filename = filename.strip(". ")
    return filename or default_name


def format_content_disposition(disposition_type: str, filename: str) -> str:
    """
    Format a Content-Disposition header safely according to RFC 6266 and RFC 5987.
    Prevents header injection (CRLF), quote breakouts, and UnicodeEncodeError in HTTP headers.
    """
    cleaned = re.sub(r"[\r\n\x00]", "", filename).strip()
    if not cleaned:
        cleaned = "download"
    ascii_name = cleaned.replace('"', '_').encode("ascii", "replace").decode("ascii")
    utf8_name = urllib.parse.quote(cleaned, encoding="utf-8")
    return f'{disposition_type}; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}'


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
import secrets


def generate_pin() -> str:
    """Generate a random cryptographically secure 4-digit PIN."""
    return f"{secrets.randbelow(9000) + 1000}"


def ensure_self_signed_cert() -> tuple:
    """
    Ensure a self-signed TLS certificate and private key exist in ~/.clipto/
    Generates them via openssl CLI if not already present.
    Returns (cert_path, key_path).
    """
    cert_dir = Path.home() / ".clipto"
    cert_dir.mkdir(parents=True, exist_ok=True)
    cert_path = cert_dir / "clipto.crt"
    key_path = cert_dir / "clipto.key"

    if cert_path.is_file() and key_path.is_file():
        return cert_path, key_path

    lan_ip = get_local_ip() or "127.0.0.1"
    tailscale_ip = get_tailscale_ip()
    san_list = ["DNS:localhost", "IP:127.0.0.1"]
    if lan_ip != "127.0.0.1":
        san_list.append(f"IP:{lan_ip}")
    if tailscale_ip:
        san_list.append(f"IP:{tailscale_ip}")
    san_str = ",".join(san_list)

    cmd = [
        "openssl",
        "req",
        "-x509",
        "-newkey", "rsa:2048",
        "-keyout", str(key_path),
        "-out", str(cert_path),
        "-days", "365",
        "-nodes",
        "-subj", "/CN=clipto",
        "-addext", f"subjectAltName={san_str}",
    ]
    try:
        subprocess.run(cmd, capture_output=True, check=True)
        key_path.chmod(0o600)
        return cert_path, key_path
    except FileNotFoundError:
        raise RuntimeError("openssl executable not found. Please install openssl or supply --cert and --key.")
    except subprocess.CalledProcessError:
        cmd_fallback = [
            "openssl",
            "req",
            "-x509",
            "-newkey", "rsa:2048",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-days", "365",
            "-nodes",
            "-subj", "/CN=clipto",
        ]
        try:
            subprocess.run(cmd_fallback, capture_output=True, check=True)
            key_path.chmod(0o600)
            return cert_path, key_path
        except Exception as ex:
            raise RuntimeError(f"Failed to generate self-signed certificate: {ex}")


DEFAULT_CONFIG = {
    "tab_order": ["dropzone", "files", "gist"],
    "default_tab": "first",
    "view_mode": "grid",
    "files_view_mode": "list",
}


def get_config_file() -> Path:
    config_dir = Path.home() / ".clipto"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def load_global_config() -> dict:
    """Load global configuration from ~/.clipto/config.json with default fallback."""
    cfg = dict(DEFAULT_CONFIG)
    config_file = get_config_file()
    if config_file.is_file():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                user_cfg = json.load(f)
                if isinstance(user_cfg, dict):
                    if "tab_order" in user_cfg and isinstance(user_cfg["tab_order"], list):
                        valid_tabs = [t for t in user_cfg["tab_order"] if t in ("dropzone", "files", "gist")]
                        for t in DEFAULT_CONFIG["tab_order"]:
                            if t not in valid_tabs:
                                valid_tabs.append(t)
                        user_cfg["tab_order"] = valid_tabs
                    cfg.update(user_cfg)
        except Exception:
            pass
    cfg["config_path"] = str(config_file)
    return cfg


def save_global_config(new_config: dict) -> dict:
    """Save updated global configuration to ~/.clipto/config.json."""
    current = load_global_config()
    current.pop("config_path", None)

    if isinstance(new_config, dict):
        for k, v in new_config.items():
            if k in DEFAULT_CONFIG:
                if k == "tab_order" and isinstance(v, list):
                    valid_tabs = [t for t in v if t in ("dropzone", "files", "gist")]
                    for t in DEFAULT_CONFIG["tab_order"]:
                        if t not in valid_tabs:
                            valid_tabs.append(t)
                    current["tab_order"] = valid_tabs
                elif k == "default_tab" and v in ("dropzone", "files", "gist", "first"):
                    current["default_tab"] = v
                elif k in ("view_mode", "files_view_mode") and v in ("list", "grid"):
                    current[k] = v

    config_file = get_config_file()
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)

    current["config_path"] = str(config_file)
    return current


