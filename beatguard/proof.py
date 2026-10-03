"""Proof of creation: a SHA-256 fingerprint of the exact file, plus an optional
Bitcoin-anchored timestamp via OpenTimestamps (https://opentimestamps.org)."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ots_available() -> bool:
    return shutil.which("ots") is not None


def stamp(path: str) -> str | None:
    """Create <file>.ots next to the file. Returns its path, or None if unavailable."""
    if not ots_available():
        return None
    result = subprocess.run(["ots", "stamp", path], capture_output=True, text=True)
    ots_path = path + ".ots"
    return ots_path if result.returncode == 0 and Path(ots_path).exists() else None


def verify_ots(ots_path: str) -> tuple[bool, str]:
    """Ask OpenTimestamps whether the timestamp is confirmed on Bitcoin yet."""
    if not ots_available():
        return False, "OpenTimestamps client not installed (pip install opentimestamps-client)"
    result = subprocess.run(["ots", "verify", ots_path], capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output.splitlines()[-1] if output else "no output"
