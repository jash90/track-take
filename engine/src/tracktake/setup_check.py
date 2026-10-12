"""What a fresh machine needs before the first video, checked in one call for the UI's setup checklist."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from tracktake import config, vast

VAST_KEY_FILE = Path.home() / ".config" / "vastai" / "vast_api_key"


def _codex_logged_in() -> bool:
    if not shutil.which("codex"):
        return False
    r = subprocess.run(["codex", "login", "status"], capture_output=True, text=True, timeout=20, check=False)
    return r.returncode == 0 and "logged in" in (r.stdout + r.stderr).lower()


def _pub_key() -> Path:
    return Path(config.load().vast.ssh_key).expanduser().with_suffix(".pub")


def _key_body(line: str) -> str:
    """'ssh-ed25519 AAAA... comment' -> 'ssh-ed25519 AAAA...' (comments differ between copies)."""
    return " ".join(line.split()[:2])


def ssh_key_registered() -> bool:
    pub = _pub_key()
    if not pub.exists():
        return False
    mine = _key_body(pub.read_text())
    keys = json.loads(vast.run_cli(["show", "ssh-keys", "--raw"]))
    return any(_key_body(k.get("public_key") or "") == mine for k in keys)


def status() -> dict:
    vast_key = VAST_KEY_FILE.exists() or bool(os.environ.get("VAST_API_KEY"))
    registered = None
    if vast_key:
        try:
            registered = ssh_key_registered()
        except Exception:  # noqa: BLE001 - network / API trouble shows as "unknown"
            registered = None
    checks = {
        "claude": bool(shutil.which("claude")),  # the director (codex is the fallback)
        "codex": bool(shutil.which("codex")),
        "codex_login": _codex_logged_in(),  # keyframes are drawn with the ChatGPT login
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "vast_key": vast_key,
        "ssh_key": _pub_key().exists(),
        "ssh_key_on_vast": registered,
    }
    required = ("codex", "codex_login", "ffmpeg", "vast_key", "ssh_key", "ssh_key_on_vast")
    return {"checks": checks, "ready": all(checks[k] for k in required) and (checks["claude"] or checks["codex"])}


def ensure_ssh_key_on_vast() -> dict:
    """Create a local key if there is none and add it to the Vast account if it is not there yet."""
    pub = _pub_key()
    if not pub.exists():
        priv = pub.with_suffix("")
        priv.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(priv), "-C", "tracktake"],
                       check=True)
    if not ssh_key_registered():
        vast.run_cli(["create", "ssh-key", pub.read_text().strip(), "-y"])
    return status()
