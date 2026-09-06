# 📎 Clipto

[![PyPI](https://img.shields.io/pypi/v/clipto.svg)](https://pypi.org/project/clipto/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/mattintech/clipto/actions/workflows/ci.yml/badge.svg)](https://github.com/mattintech/clipto/actions/workflows/ci.yml)

> **Instant clipboard, screenshot, and file bridge from your browser to your terminal or remote server.**

Ever run an AI agent, Docker container, or SSH session on a remote server, but need to get a screenshot or log file from your local machine to that server? 

**Clipto** solves this. Run `clipto` in any directory on your machine or remote server, open the link in your browser, and hit **Cmd+V / Ctrl+V**. Your screenshot or clipboard contents are immediately saved right into that folder.

---

## ✨ Features

- **⚡ Zero-Click Paste:** Open the page and press `Cmd+V` or `Ctrl+V` anywhere. No buttons or input selection required.
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
┌──────────────────────────────────────────────────────────┐
│  📎 Clipto v0.1.0                                        │
│  Saving to: /Users/matt/code/my-project                  │
│  Local:     http://localhost:8765                        │
│  Network:   http://192.168.1.50:8765                     │
└──────────────────────────────────────────────────────────┘
```

1. Open the URL in your browser (or pass `-o / --open` to auto-open).
2. Hit `Cmd+V` to paste a screenshot, or drag files onto the page.
3. The files are instantly written to your current directory!

---

## 🤖 Using with AI Agents & Scripts

Clipto is built from the ground up to integrate cleanly into automated agent workflows (Antigravity, Claude Code, Aider, OpenHands, etc.).

### One-Shot Mode (`--once`)

When run with `--once` (or `-1`), Clipto waits for a single upload batch, saves the file(s), prints the resolved absolute path to `stdout`, and shuts down:

```bash
# Agent or script runs this:
FILE_PATH=$(clipto --once --title "Submit login bug screenshot" --timeout 120)

echo "Agent received file at: $FILE_PATH"
```

The agent gets the exact file path back into its visual/multimodal context!

---

## ⚙️ CLI Reference

```text
usage: clipto [-h] [-v] [-p PORT] [--no-hunt] [-d DIR] [-1] [-t TITLE] [-o] [--host HOST] [--timeout TIMEOUT]

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
  --host HOST           Host to bind to (default: 0.0.0.0).
  --timeout TIMEOUT     Timeout in seconds (useful with --once).
```

---

## 🛠️ Multi-Instance Support

You can run multiple `clipto` instances simultaneously across different projects or terminals:
* Each instance automatically detects occupied ports and claims the next available one.
* Each browser tab displays its target folder path and optional session title so you always know where your file is landing.

---

## 🔒 Security

* By default, Clipto binds to `0.0.0.0` for convenience across local networks (e.g. testing with phone/laptop).
* If you only want local machine access, pass `--host 127.0.0.1`.
* Filenames are strictly sanitized to prevent directory traversal attacks.

---

## 📄 License

MIT © Matt
