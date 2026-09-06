import argparse
import atexit
import os
import sys
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Optional

from clipto import __version__
from clipto.server import CliptoHTTPServer, CliptoRequestHandler
from clipto.totp import (
    calculate_totp,
    load_totp_secret,
    run_totp_setup,
)
from clipto.tunnel import print_tunnel_guide, start_tunnel, stop_tunnel
from clipto.utils import (
    find_available_port,
    generate_pin,
    get_local_ip,
    get_tailscale_ip,
    render_qr_terminal,
    terminal_hyperlink,
    visible_width,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clipto",
        description="Instant clipboard, screenshot, and file bridge from browser to terminal.",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8765,
        help="Port to listen on (default: 8765, auto-increments if occupied; use 0 for random).",
    )
    parser.add_argument(
        "--no-hunt",
        action="store_true",
        help="Disable automatic port hunting if specified port is in use.",
    )
    parser.add_argument(
        "-d", "--dir",
        type=Path,
        default=Path("."),
        help="Target directory where files will be saved (default: current directory).",
    )
    parser.add_argument(
        "-1", "--once",
        action="store_true",
        help="One-shot mode: exit immediately after receiving an upload and print saved file path(s).",
    )
    parser.add_argument(
        "-t", "--title",
        type=str,
        default=None,
        help="Custom session title or prompt shown in the web UI header.",
    )
    parser.add_argument(
        "-o", "--open",
        action="store_true",
        help="Automatically open the web UI in the default browser on launch.",
    )
    parser.add_argument(
        "-q", "--qr",
        action="store_true",
        help="Display a terminal QR code for the network/tunnel URL (easy mobile phone scanning).",
    )
    parser.add_argument(
        "--pin",
        action="store_true",
        help="Protect access with an auto-generated 4-digit PIN.",
    )
    parser.add_argument(
        "--pass", "--password",
        dest="password",
        type=str,
        default=None,
        help="Protect access with a custom password/passphrase.",
    )
    parser.add_argument(
        "--totp",
        action="store_true",
        help="Protect access with a standard 6-digit TOTP Authenticator code (Google/MS/1Password).",
    )
    parser.add_argument(
        "--totp-setup",
        action="store_true",
        help="Initialize or configure TOTP Authenticator with a terminal QR code.",
    )
    parser.add_argument(
        "--tunnel",
        nargs="?",
        const="auto",
        default=None,
        help="Expose server over an encrypted public HTTPS tunnel (e.g. Cloudflare).",
    )
    parser.add_argument(
        "--help-tunnel",
        action="store_true",
        help="Show comprehensive guide on tunneling, remote connections, and SSH port forwarding.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host address to bind to (default: 0.0.0.0).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Timeout in seconds (useful with --once to prevent hanging indefinitely).",
    )
    parser.add_argument(
        "share_args",
        nargs="*",
        default=[],
        help="Optional: 'share [path]' or path to share a specific file, binary, or directory.",
    )
    return parser


def get_mobile_url(
    port: int,
    auth_key: Optional[str] = None,
    tunnel_url: Optional[str] = None,
) -> str:
    """Determine best URL for mobile access (Tunnel > Tailscale > LAN > Localhost)."""
    if tunnel_url:
        base = tunnel_url
    else:
        tailscale_ip = get_tailscale_ip()
        if tailscale_ip:
            base = f"http://{tailscale_ip}:{port}"
        else:
            lan_ip = get_local_ip()
            if lan_ip and lan_ip != "127.0.0.1":
                base = f"http://{lan_ip}:{port}"
            else:
                base = f"http://localhost:{port}"

    if auth_key:
        sep = "&" if "?" in base else "/?"
        return f"{base}{sep}k={auth_key}"
    return base


def format_file_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024.0
    return f"{size:.1f} TB"


def print_banner(
    port: int,
    target_dir: Path,
    title: Optional[str] = None,
    once: bool = False,
    show_qr: bool = False,
    auth_token: Optional[str] = None,
    totp_secret: Optional[str] = None,
    tunnel_url: Optional[str] = None,
    share_mode: bool = False,
    share_file: Optional[Path] = None,
):
    current_key = None
    if totp_secret:
        current_key = calculate_totp(totp_secret)
    elif auth_token:
        current_key = auth_token

    query_suffix = f"/?k={current_key}" if current_key else ""
    local_url = f"http://localhost:{port}{query_suffix}"
    lan_ip = get_local_ip()
    tailscale_ip = get_tailscale_ip()

    mode_tag = ""
    if share_file:
        mode_tag = " [SHARING FILE]"
    elif share_mode:
        mode_tag = " [SHARING DIRECTORY]"
    elif once:
        mode_tag = " [ONE-SHOT MODE]"

    lines = [
        f"📎 Clipto v{__version__}{mode_tag}",
    ]
    if share_file:
        try:
            sz = format_file_size(share_file.stat().st_size)
        except Exception:
            sz = ""
        lines.append(f"File:       {share_file.name} ({sz})")
        lines.append(f"Directory:  {target_dir.resolve()}")
    else:
        lines.append(f"Directory:  {target_dir.resolve()}")

    if title:
        lines.append(f"Session:    {title}")
    if totp_secret:
        lines.append(f"Security:   TOTP Active (6-digit authenticator) 🔐")
    elif auth_token:
        lines.append(f"PIN / Key:  {auth_token} 🔒")

    if tunnel_url:
        t_url = f"{tunnel_url}{query_suffix}"
        lines.append(f"Tunnel:     {terminal_hyperlink(t_url)} 🌍")

    lines.append(f"Local:      {terminal_hyperlink(local_url)}")
    if lan_ip and lan_ip != "127.0.0.1":
        lan_url = f"http://{lan_ip}:{port}{query_suffix}"
        lines.append(f"Network:    {terminal_hyperlink(lan_url)}")
    if tailscale_ip:
        tail_url = f"http://{tailscale_ip}:{port}{query_suffix}"
        lines.append(f"Tailscale:  {terminal_hyperlink(tail_url)}")

    if share_file:
        base_dl = tunnel_url or (f"http://{lan_ip}:{port}" if lan_ip and lan_ip != "127.0.0.1" else f"http://localhost:{port}")
        token_dl = f"?k={current_key}" if current_key else ""
        curl_cmd = f'curl -sSL "{base_dl}/raw/{urllib.parse.quote(share_file.name)}{token_dl}" -o {share_file.name}'
        lines.append(f"Curl (CLI): {curl_cmd}")

    max_w = max(visible_width(line) for line in lines)
    border = "─" * (max_w + 4)

    print(f"\n┌{border}┐", file=sys.stderr)
    for line in lines:
        padding = " " * (max_w - visible_width(line))
        print(f"│  {line}{padding}  │", file=sys.stderr)
    print(f"└{border}┘", file=sys.stderr)

    if show_qr:
        mobile_url = get_mobile_url(port, auth_key=current_key, tunnel_url=tunnel_url)
        qr_ascii = render_qr_terminal(mobile_url)
        print(f"\nScan with your phone to open ({mobile_url}):\n{qr_ascii}\n", file=sys.stderr)
    else:
        print("", file=sys.stderr)

    if share_file:
        print("Share link ready. File can be viewed, downloaded, or curled directly.\n", file=sys.stderr)
    else:
        print("Press Cmd+V or drag files into the browser tab. Press Ctrl+C to stop.\n", file=sys.stderr)


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.totp_setup:
        run_totp_setup()
        sys.exit(0)

    if args.help_tunnel:
        print_tunnel_guide()
        sys.exit(0)

    share_mode = False
    share_file = None

    if args.share_args:
        first = args.share_args[0]
        if first == "share":
            share_mode = True
            if len(args.share_args) > 1:
                p = Path(args.share_args[1]).expanduser().resolve()
                if p.is_file():
                    share_file = p
                    target_dir = p.parent
                elif p.is_dir():
                    target_dir = p
                else:
                    print(f"Error: Path '{args.share_args[1]}' not found.", file=sys.stderr)
                    sys.exit(1)
            else:
                target_dir = args.dir.resolve()
        else:
            p = Path(first).expanduser().resolve()
            if p.is_file():
                share_mode = True
                share_file = p
                target_dir = p.parent
            elif p.is_dir():
                share_mode = True
                target_dir = p
            else:
                print(f"Error: Unrecognized command or path '{first}'.", file=sys.stderr)
                sys.exit(1)
    else:
        target_dir = args.dir.resolve()

    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine security credentials
    totp_secret = None
    auth_token = None

    if args.totp:
        totp_secret = load_totp_secret()
        if not totp_secret:
            print(
                "\n⚠️  No TOTP secret key found.\n"
                "Run setup first to generate a key and QR code for your authenticator app:\n"
                "    clipto --totp-setup\n",
                file=sys.stderr,
            )
            sys.exit(1)
    elif args.password:
        auth_token = args.password.strip()
    elif args.pin or args.tunnel:
        # If tunnel is active and user didn't specify credentials, auto-generate PIN
        auth_token = generate_pin()

    # Determine port
    if args.no_hunt:
        port = args.port
    else:
        try:
            port = find_available_port(args.port)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Handle public tunnel
    tunnel_url = None
    tunnel_proc = None

    if args.tunnel:
        print(f"Starting public tunnel ({args.tunnel})...", file=sys.stderr)
        try:
            tunnel_url, tunnel_proc = start_tunnel(port, provider=args.tunnel)
            atexit.register(stop_tunnel, tunnel_proc)
        except Exception as e:
            print(f"\n⚠️  Tunnel creation failed: {e}\n", file=sys.stderr)
            print("Run 'clipto --help-tunnel' for setup instructions.", file=sys.stderr)
            sys.exit(1)

    try:
        server = CliptoHTTPServer(
            (args.host, port),
            CliptoRequestHandler,
            upload_dir=target_dir,
            title=args.title,
            once=args.once,
            auth_token=auth_token,
            totp_secret=totp_secret,
            tunnel_url=tunnel_url,
            share_mode=share_mode,
            share_file=share_file,
        )
    except OSError as e:
        stop_tunnel(tunnel_proc)
        print(f"Error binding to port {port}: {e}", file=sys.stderr)
        sys.exit(1)

    print_banner(
        port,
        target_dir,
        title=args.title,
        once=args.once,
        show_qr=args.qr,
        auth_token=auth_token,
        totp_secret=totp_secret,
        tunnel_url=tunnel_url,
        share_mode=share_mode,
        share_file=share_file,
    )

    if args.open:
        active_key = server.get_current_auth_key()
        target_open = tunnel_url or f"http://localhost:{port}"
        query_suffix = f"/?k={active_key}" if active_key else ""
        hash_suffix = ""
        if share_file:
            hash_suffix = f"#gist={urllib.parse.quote(share_file.name)}"
        elif share_mode:
            hash_suffix = "#files"
        webbrowser.open(f"{target_open}{query_suffix}{hash_suffix}")

    # Start server thread
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    start_time = time.time()

    try:
        while not server.shutdown_event.is_set():
            if args.timeout and (time.time() - start_time) > args.timeout:
                print("\nOperation timed out.", file=sys.stderr)
                server.shutdown()
                stop_tunnel(tunnel_proc)
                sys.exit(124)
            time.sleep(0.1)

        # Shutdown triggered (in once mode)
        server.shutdown()
        stop_tunnel(tunnel_proc)

        # In once mode, output the uploaded file path(s) to stdout
        for file_path in server.uploaded_files:
            print(str(file_path.resolve()))

    except KeyboardInterrupt:
        print("\nStopping Clipto server...", file=sys.stderr)
        server.shutdown()
        stop_tunnel(tunnel_proc)
        sys.exit(0)


if __name__ == "__main__":
    main()
