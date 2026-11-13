"""Re-sign an unsigned IPA using zsign (https://github.com/zhlynn/zsign)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .provisioner import Credentials


class SignerError(RuntimeError):
    pass


def find_zsign() -> str:
    exe = shutil.which("zsign") or shutil.which("zsign.exe")
    if not exe:
        local = Path(__file__).parent / "bin" / "zsign.exe"
        if local.exists():
            exe = str(local)
    if not exe:
        raise SignerError(
            "zsign not found. Put zsign.exe on PATH or in ipakit/bin/."
        )
    return exe


def sign_ipa(src: Path, dst: Path, creds: Credentials) -> Path:
    cmd = [
        find_zsign(),
        "-k", str(creds.p12_path),
        "-p", creds.p12_password,
        "-m", str(creds.profile_path),
        "-o", str(dst),
        "-z", "5",
        str(src),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not dst.exists():
        raise SignerError(proc.stderr.strip() or proc.stdout.strip() or "zsign failed")
    return dst
