import base64
import getpass
import hashlib
import hmac
import os
import re
import secrets
import socket
import struct
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Optional, Set, Tuple

from clipto.utils import render_qr_terminal


def get_config_dir() -> Path:
    """Get the standard ~/.clipto configuration directory."""
    config_dir = Path.home() / ".clipto"
    config_dir.mkdir(parents=True, exist_ok=True)
    # Ensure directory permissions are 0700 on Unix
    try:
        os.chmod(config_dir, 0o700)
    except Exception:
        pass
    return config_dir


def get_totp_key_path() -> Path:
    """Return path to ~/.clipto/totp.key."""
    return get_config_dir() / "totp.key"


def generate_totp_secret() -> str:
    """Generate a random 160-bit cryptographically secure Base32 secret."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("utf-8").rstrip("=").upper()


def save_totp_secret(secret: str) -> Path:
    """Save the TOTP secret to ~/.clipto/totp.key with restricted permissions."""
    key_path = get_totp_key_path()
    key_path.write_text(secret.strip().upper(), encoding="utf-8")
    try:
        os.chmod(key_path, 0o600)
    except Exception:
        pass
    return key_path


def load_totp_secret() -> Optional[str]:
    """Load the TOTP secret from ~/.clipto/totp.key if it exists."""
    key_path = get_totp_key_path()
    if key_path.is_file():
        secret = key_path.read_text(encoding="utf-8").strip().replace(" ", "").upper()
        if secret:
            return secret
    return None


def calculate_totp(secret_b32: str, timestamp: Optional[float] = None, step: int = 30, digits: int = 6) -> str:
    """
    Calculate the RFC 6238 TOTP code for a given Base32 secret.
    Standard: HMAC-SHA1, 30-second time steps, 6 digits.
    """
    if timestamp is None:
        timestamp = time.time()
    counter = int(timestamp // step)

    secret_clean = secret_b32.strip().replace(" ", "").upper()
    missing_padding = len(secret_clean) % 8
    if missing_padding:
        secret_clean += "=" * (8 - missing_padding)

    key = base64.b32decode(secret_clean)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()

    offset = digest[-1] & 0x0F
    binary_code = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    code = binary_code % (10 ** digits)
    return f"{code:0{digits}d}"


def verify_totp(
    secret_b32: str,
    code: str,
    timestamp: Optional[float] = None,
    step: int = 30,
    digits: int = 6,
    window: int = 1,
    used_steps: Optional[Set[int]] = None,
) -> bool:
    """
    Verify a TOTP code with a ±1 time step tolerance window (30s past and 30s future)
    to gracefully handle minor clock drift between the server and phone.
    Optionally records and checks used_steps to prevent replay attacks (RFC 6238 §5.2).
    """
    if not code or len(code.strip()) != digits:
        return False

    code_clean = code.strip()
    if timestamp is None:
        timestamp = time.time()

    current_counter = int(timestamp // step)

    # Clean up counters older than validity window from used_steps to bound memory
    if used_steps is not None:
        min_valid_counter = current_counter - window - 2
        for old in list(used_steps):
            if old < min_valid_counter:
                used_steps.discard(old)

    for offset in range(-window, window + 1):
        counter = current_counter + offset
        if used_steps is not None and counter in used_steps:
            continue
        expected = calculate_totp(secret_b32, timestamp=counter * step, step=step, digits=digits)
        if hmac.compare_digest(expected, code_clean):
            if used_steps is not None:
                used_steps.add(counter)
            return True

    return False


def get_totp_uri(secret_b32: str, issuer: str = "Clipto", account: Optional[str] = None) -> str:
    """Generate standard otpauth:// URI for authenticator apps."""
    if not account:
        user = getpass.getuser()
        host = socket.gethostname().split(".")[0]
        account = f"{user}@{host}"

    secret_clean = secret_b32.strip().replace(" ", "").upper()
    label = urllib.parse.quote(f"{issuer}:{account}")
    params = urllib.parse.urlencode({
        "secret": secret_clean,
        "issuer": issuer,
        "algorithm": "SHA1",
        "digits": "6",
        "period": "30",
    })
    return f"otpauth://totp/{label}?{params}"


def format_secret_spaced(secret: str) -> str:
    """Format Base32 secret in readable 4-character chunks (e.g. ABCD EFGH)."""
    clean = secret.strip().replace(" ", "").upper()
    return " ".join(clean[i:i + 4] for i in range(0, len(clean), 4))


def run_totp_setup():
    """Interactive CLI command to initialize and display TOTP configuration."""
    existing_secret = load_totp_secret()
    if existing_secret:
        print(f"\nExisting TOTP secret found in {get_totp_key_path()}.", file=sys.stderr)
        choice = input("Do you want to generate a new key and overwrite it? (y/N): ").strip().lower()
        if choice != "y":
            secret = existing_secret
            print("\nUsing existing TOTP secret key.", file=sys.stderr)
        else:
            secret = generate_totp_secret()
            save_totp_secret(secret)
            print(f"\nGenerated new TOTP key and saved to {get_totp_key_path()}.", file=sys.stderr)
    else:
        secret = generate_totp_secret()
        save_totp_secret(secret)
        print(f"\nGenerated new TOTP secret and saved to {get_totp_key_path()}.", file=sys.stderr)

    uri = get_totp_uri(secret)
    qr_code = render_qr_terminal(uri, border=2)

    border = "─" * 66
    print(f"\n┌{border}┐", file=sys.stderr)
    print("│  🔐 Clipto Authenticator Setup (Google / MS / 1Password / Apple)  │", file=sys.stderr)
    print(f"├{border}┤", file=sys.stderr)
    print("│  Scan this QR code with your authenticator app on your phone:     │", file=sys.stderr)
    print(f"└{border}┘", file=sys.stderr)

    print(f"\n{qr_code}\n", file=sys.stderr)

    print("Secret key (for manual entry into authenticator):", file=sys.stderr)
    print(f"  {format_secret_spaced(secret)}\n", file=sys.stderr)
    print(f"Saved to: {get_totp_key_path()}\n", file=sys.stderr)

    # Verification prompt
    print("Let's test it! Enter the 6-digit code from your authenticator app:", file=sys.stderr)
    try:
        user_code = input("Code: ").strip()
        if verify_totp(secret, user_code):
            print("\n✓ SUCCESS! Your authenticator is verified and ready.", file=sys.stderr)
            print("To start with TOTP protection, run:", file=sys.stderr)
            print("  clipto --totp", file=sys.stderr)
            print("  clipto --tunnel --totp\n", file=sys.stderr)
        else:
            print("\n⚠️  Verification failed: code did not match.", file=sys.stderr)
            print("Check that your device time is accurate and try scanning again.\n", file=sys.stderr)
    except (KeyboardInterrupt, EOFError):
        print("\nSetup cancelled.\n", file=sys.stderr)
