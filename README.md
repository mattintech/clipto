# 📎 Clipto

[![PyPI](https://img.shields.io/pypi/v/clipto.svg)](https://pypi.org/project/clipto/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/mattintech/clipto/actions/workflows/ci.yml/badge.svg)](https://github.com/mattintech/clipto/actions/workflows/ci.yml)

> **Instant clipboard, screenshot, and file bridge from your browser or phone to your terminal/remote server.**

Ever run an AI agent, Docker container, or SSH session on a remote server, but need to get a screenshot or log file from your local machine to that server? 

**Clipto** solves this. Run `clipto` in any directory on your machine or remote server, open the link in your browser, and hit **Cmd+V / Ctrl+V**. Your screenshot or clipboard contents are immediately saved right into that folder.

---

## ✨ Features

- **⚡ Zero-Click Paste:** Open the page and press `Cmd+V` or `Ctrl+V` anywhere. No buttons or input selection required.
- **🖼️ Thumbnail Grid & Lightbox:** Visual thumbnail cards with click-to-enlarge full-screen preview.
- **🚇 Public HTTPS Tunnels (`--tunnel`):** Instant, secure internet access from cellular or remote servers via Cloudflare Quick Tunnels.
- **📱 Phone QR Code (`--qr`):** Print a high-contrast terminal QR code or click "Phone QR" in the web UI to snap and upload from your phone camera.
- **🔒 PIN & Password Protection (`--pin` / `--pass`):** Protect access with an auto-generated 4-digit PIN or custom passphrase (auto-enabled on `--tunnel`).
- **📖 Built-in Guides (`--help-tunnel`):** Help modal right in the browser and CLI cheat sheets for remote connections.
- **🎯 Drag & Drop:** Drop multiple files, images, or documents straight onto the window.
- **📝 Text & Note Box:** Paste stack traces, error logs, or notes to save directly as `.txt` files.
- **🤖 AI Agent Friendly (`--once`):** One-shot mode spins up the server, waits for an upload, writes the file, prints the saved path to `stdout`, and exits cleanly.
- **🔀 Smart Port Hunting:** Automatically picks the next free port (`8765`, `8766`, etc.) so multiple instances never collide.
- **🏷️ Multi-Instance Context:** The UI prominently shows the host machine, target directory, and optional custom `--title`.
- **🪶 Zero Dependencies:** Powered purely by Python's standard library. Installs in milliseconds with zero dependency conflicts.

---

## 🚀 Quick Start

### Installation

```bash
pip install clipto
```

### Basic Usage

Run `clipto` in whichever directory you want files to land:

```bash
clipto
```

You'll see a clean terminal banner with the local and LAN URLs:

```text
┌─────────────────────────────────────────┐
│  📎 Clipto v0.1.2                       │
│  Saving to: /Users/matt/code/my-project │
│  Local:     http://localhost:8765       │
│  Network:   http://192.168.1.50:8765    │
└─────────────────────────────────────────┘
```

1. Open the URL in your browser (or pass `-o / --open` to auto-open).
2. Hit `Cmd+V` to paste a screenshot, or drag files onto the page.
3. The files are instantly written to your current directory!

---

## 🚇 Remote Access & Public Tunneling

When running on a cloud VM, Docker container, or uploading from your phone on cellular data:

```bash
clipto --tunnel
```

Clipto launches an encrypted, free public HTTPS tunnel via Cloudflare:

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│  📎 Clipto v0.1.2                                                           │
│  Saving to: /Users/matt/code/my-project                                     │
│  PIN / Key: 8421 🔒                                                         │
│  Tunnel:    https://gentle-winds-example.trycloudflare.com/?k=8421 🌍       │
│  Local:     http://localhost:8765/?k=8421                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

* **Zero-Typing For You:** The tunnel link and QR code already contain your PIN token (`?k=PIN`), logging you in automatically.
* **Locked For Everyone Else:** Anyone discovering your public tunnel URL hits a clean PIN lock screen.
* **Want to learn more?** Run `clipto --help-tunnel` for a cheat sheet on tunnels and SSH port forwarding.

---

## 📱 Mobile & Security Options

### Phone Upload with QR Code

```bash
clipto --qr
# or combined with tunnel:
clipto --tunnel --qr
```

A QR code is rendered directly in your terminal pointing to your reachable address. Point your phone camera at your terminal to open the upload page instantly!

### PIN & Password Protection

```bash
# Auto-generate a 4-digit PIN:
clipto --pin

# Or use a custom password:
clipto --pass secret123
```

---

## 🤖 Using with AI Agents & Scripts

```bash
# Agent or script runs this:
FILE_PATH=$(clipto --once --title "Submit bug screenshot" --timeout 120)

echo "Agent received file at: $FILE_PATH"
```

The agent gets the exact file path back into its visual/multimodal context!

---

## ⚙️ CLI Reference

```text
usage: clipto [-h] [-v] [-p PORT] [--no-hunt] [-d DIR] [-1] [-t TITLE] [-o] [-q] [--pin] [--pass PASSWORD] [--tunnel [TUNNEL]] [--help-tunnel] [--host HOST] [--timeout TIMEOUT]

Instant clipboard, screenshot, and file bridge from browser to terminal.

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -p PORT, --port PORT  Port to listen on (default: 8765; use 0 for random).
  --no-hunt             Disable automatic port hunting if port is busy.
  -d DIR, --dir DIR     Target directory to save files (default: .).
  -1, --once            One-shot mode: exit after upload and print file path(s).
  -t TITLE, --title TITLE
                        Custom session title or prompt shown in the UI header.
  -o, --open            Automatically open web UI in default browser on launch.
  -q, --qr              Display a terminal QR code for the network/tunnel URL.
  --pin                 Protect access with an auto-generated 4-digit PIN.
  --pass PASSWORD       Protect access with a custom password.
  --tunnel [TUNNEL]     Expose server over an encrypted public HTTPS tunnel.
  --help-tunnel         Show guide on tunneling and remote connections.
  --host HOST           Host to bind to (default: 0.0.0.0).
  --timeout TIMEOUT     Timeout in seconds (useful with --once).
```

---

## 📄 License

MIT © Matt
