"""Clipto: Instant clipboard, screenshot, and file bridge from browser to terminal."""

import subprocess
from pathlib import Path

__base_version__ = "0.3.2"


def _get_git_version() -> str:
    """Return release version with git short hash if running from a git checkout."""
    repo_dir = Path(__file__).resolve().parent.parent.parent
    git_dir = repo_dir / ".git"
    if git_dir.exists():
        try:
            cmd = ["git", "rev-parse", "--short", "HEAD"]
            short_hash = subprocess.check_output(cmd, cwd=str(repo_dir), stderr=subprocess.DEVNULL, text=True).strip()
            if short_hash:
                status = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(repo_dir), stderr=subprocess.DEVNULL, text=True).strip()
                dirty = "*" if status else ""
                return f"{__base_version__}-dev+{short_hash}{dirty}"
        except Exception:
            pass
    return __base_version__


__version__ = _get_git_version()
__all__ = ["__version__"]
