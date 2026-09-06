import argparse
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Optional

from clipto import __version__
from clipto.server import CliptoHTTPServer, CliptoRequestHandler
from clipto.utils import (
    find_available_port,
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
        help="Display a terminal QR code for the network URL (easy mobile phone scanning).",
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
    return parser


def get_mobile_url(port: int) -> str:
    """Determine best URL for mobile access (Tailscale > LAN > Localhost)."""
    tailscale_ip = get_tailscale_ip()
    if tailscale_ip:
        return f"http://{tailscale_ip}:{port}"
    lan_ip = get_local_ip()
    if lan_ip and lan_ip != "127.0.0.1":
        return f"http://{lan_ip}:{port}"
    return f"http://localhost:{port}"


def print_banner(
    port: int,
    target_dir: Path,
    title: Optional[str] = None,
    once: bool = False,
    show_qr: bool = False,
):
    local_url = f"http://localhost:{port}"
    lan_ip = get_local_ip()
    tailscale_ip = get_tailscale_ip()

    lines = [
        f"📎 Clipto v{__version__}" + (" [ONE-SHOT MODE]" if once else ""),
        f"Saving to: {target_dir.resolve()}",
    ]
    if title:
        lines.append(f"Session:   {title}")

    lines.append(f"Local:     {terminal_hyperlink(local_url)}")
    if lan_ip and lan_ip != "127.0.0.1":
        lines.append(f"Network:   {terminal_hyperlink(f'http://{lan_ip}:{port}')}")
    if tailscale_ip:
        lines.append(f"Tailscale: {terminal_hyperlink(f'http://{tailscale_ip}:{port}')}")

    max_w = max(visible_width(line) for line in lines)
    border = "─" * (max_w + 4)

    print(f"\n┌{border}┐", file=sys.stderr)
    for line in lines:
        padding = " " * (max_w - visible_width(line))
        print(f"│  {line}{padding}  │", file=sys.stderr)
    print(f"└{border}┘", file=sys.stderr)

    if show_qr:
        mobile_url = get_mobile_url(port)
        qr_ascii = render_qr_terminal(mobile_url)
        print(f"\nScan with your phone to open ({mobile_url}):\n{qr_ascii}\n", file=sys.stderr)
    else:
        print("", file=sys.stderr)

    print("Press Cmd+V or drag files into the browser tab. Press Ctrl+C to stop.\n", file=sys.stderr)


def main():
    parser = build_parser()
    args = parser.parse_args()

    target_dir = args.dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    # Determine port
    if args.no_hunt:
        port = args.port
    else:
        try:
            port = find_available_port(args.port)
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        server = CliptoHTTPServer(
            (args.host, port),
            CliptoRequestHandler,
            upload_dir=target_dir,
            title=args.title,
            once=args.once,
        )
    except OSError as e:
        print(f"Error binding to port {port}: {e}", file=sys.stderr)
        sys.exit(1)

    print_banner(port, target_dir, title=args.title, once=args.once, show_qr=args.qr)

    if args.open:
        webbrowser.open(f"http://localhost:{port}")

    # Start server thread
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    start_time = time.time()

    try:
        while not server.shutdown_event.is_set():
            if args.timeout and (time.time() - start_time) > args.timeout:
                print("\nOperation timed out.", file=sys.stderr)
                server.shutdown()
                sys.exit(124)
            time.sleep(0.1)

        # Shutdown triggered (in once mode)
        server.shutdown()

        # In once mode, output the uploaded file path(s) to stdout
        for file_path in server.uploaded_files:
            print(str(file_path.resolve()))

    except KeyboardInterrupt:
        print("\nStopping Clipto server...", file=sys.stderr)
        server.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
