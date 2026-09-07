import os
import re
import shutil
import subprocess
import sys
import time
from typing import Optional, Tuple


def is_cloudflared_available() -> bool:
    """Check if cloudflared binary is installed in PATH."""
    return shutil.which("cloudflared") is not None


def is_tailscale_available() -> bool:
    """Check if tailscale binary is installed in PATH."""
    return shutil.which("tailscale") is not None


def start_cloudflare_tunnel(port: int, timeout: float = 18.0) -> Tuple[str, subprocess.Popen]:
    """
    Start a Cloudflare Quick Tunnel using cloudflared.
    Passes --config /dev/null to ensure pre-existing named tunnel configurations
    in ~/.cloudflared/config.yml do not intercept or block quick tunnel traffic.
    Waits for both edge connector registration and Anycast DNS propagation
    before returning to prevent premature local requests from caching NXDOMAIN or 404.
    Returns (public_https_url, process).
    """
    if not is_cloudflared_available():
        raise RuntimeError(
            "cloudflared is not installed.\n"
            "Install it with:\n"
            "  • macOS: brew install cloudflared\n"
            "  • Linux: sudo apt-get install cloudflared\n"
            "  • Or visit: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/\n"
            "For more details, run: clipto --help-tunnel"
        )

    cmd = [
        "cloudflared",
        "tunnel",
        "--config",
        "/dev/null",
        "--url",
        f"http://127.0.0.1:{port}",
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    url = None
    registered = False
    start_time = time.time()

    # cloudflared prints its quick tunnel URL and connection registration to stderr
    while time.time() - start_time < timeout:
        if proc.poll() is not None:
            err = proc.stderr.read() if proc.stderr else "Unknown error"
            raise RuntimeError(f"cloudflared exited unexpectedly: {err}")

        line = proc.stderr.readline()
        if not line:
            time.sleep(0.1)
            continue

        if not url:
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match:
                url = match.group(0)

        if "Registered tunnel connection" in line:
            registered = True
            break

    if not url:
        proc.terminate()
        raise TimeoutError("Timed out waiting for Cloudflare tunnel URL to establish.")

    # Cloudflare Anycast edge and third-party ISP recursive resolvers need ~6-7 seconds
    # after connector registration to fully propagate the random subdomain globally.
    # Waiting ensures immediate browser launches (-o) and user clicks don't hit
    # an unpropagated DNS record and trigger a cached NXDOMAIN or 404.
    if registered:
        time.sleep(6.5)

    return url, proc


def start_tunnel(port: int, provider: str = "auto") -> Tuple[str, subprocess.Popen]:
    """
    Start a public tunnel based on provider preference.
    Default 'auto' uses Cloudflare Quick Tunnel.
    """
    prov = provider.lower() if provider else "auto"

    if prov in ("auto", "cloudflare", "cf"):
        return start_cloudflare_tunnel(port)
    else:
        raise ValueError(f"Unsupported tunnel provider: '{provider}'. Supported: cloudflare")


def stop_tunnel(proc: Optional[subprocess.Popen]):
    """Terminate tunnel process cleanly."""
    if proc:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def print_tunnel_guide():
    """Print an approachable, well-formatted guide to tunneling and remote connections."""
    guide = """
┌─────────────────────────────────────────────────────────────────────────────┐
│  🚇 Clipto Remote Access & Tunneling Guide                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ❓ WHEN DO I NEED A TUNNEL?                                                │
│                                                                             │
│  • Same Wi-Fi / Local Network:                                              │
│    You DO NOT need a tunnel! Just run 'clipto --qr' and scan the terminal   │
│    code with your phone camera or use the 'Network:' address.               │
│                                                                             │
│  • Cellular Data / Different Network / Remote Cloud VM:                     │
│    You DO need a tunnel. Run:                                               │
│        clipto --tunnel                                                      │
│    This creates an instant, secure HTTPS link accessible from anywhere.     │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  🚀 PROVIDERS & SETUP                                                       │
│                                                                             │
│  1. Cloudflare Quick Tunnels (Default & Recommended)                        │
│     • Fast, globally distributed HTTPS via Cloudflare edge network.         │
│     • Free, no account, no API key, no configuration needed.                │
│     • Install once:                                                         │
│         macOS: brew install cloudflared                                     │
│         Linux: sudo apt-get install cloudflared                             │
│                                                                             │
│  2. SSH Port Forwarding (Direct, No Third Parties)                          │
│     • If you are already SSHed into a remote server, you can forward        │
│       the clipto port directly to your laptop with zero tunnels:            │
│         ssh -N -L 8765:localhost:8765 user@remote-server                    │
│     • Then open http://localhost:8765 on your laptop!                       │
│                                                                             │
│  3. Tailscale (Private Mesh VPN)                                            │
│     • If your server and phone are on the same Tailscale network, clipto    │
│       automatically detects and displays your Tailscale URL in the banner.  │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│  🔒 AUTOMATIC SECURITY                                                      │
│                                                                             │
│  • Whenever '--tunnel' is used, a 4-digit PIN is automatically generated    │
│    to protect your machine from internet bots and scanners.                 │
│  • Your printed link and QR code already include '?k=PIN', so clicking or   │
│    scanning logs you in automatically with zero typing!                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
"""
    print(guide, file=sys.stderr)
