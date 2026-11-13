"""Read data out of a .mobileprovision file (a CMS-wrapped plist)."""
from __future__ import annotations

import plistlib
from datetime import datetime, timezone
from pathlib import Path

_START = b"<?xml"
_END = b"</plist>"


def read_profile(path: str | Path) -> dict:
    raw = Path(path).read_bytes()
    start = raw.find(_START)
    end = raw.rfind(_END)
    if start < 0 or end < 0:
        raise ValueError(f"{path}: not a valid .mobileprovision file")
    return plistlib.loads(raw[start : end + len(_END)])


def expiration(path: str | Path) -> datetime:
    """Expiry of the provisioning profile, as an aware UTC datetime."""
    exp = read_profile(path)["ExpirationDate"]
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp


def provisioned_udids(path: str | Path) -> list[str]:
    return list(read_profile(path).get("ProvisionedDevices", []))
