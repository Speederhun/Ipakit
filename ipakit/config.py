"""User settings: which credentials to sign with."""
from __future__ import annotations

import json
from pathlib import Path

from .paths import data_dir
from .provisioner import AppleIDProvisioner, ManualProvisioner, Provisioner


def _path() -> Path:
    return data_dir() / "settings.json"


def load() -> dict:
    p = _path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def save(settings: dict) -> None:
    _path().write_text(json.dumps(settings, indent=2), encoding="utf-8")


def build_provisioner(settings: dict | None = None) -> Provisioner:
    s = settings if settings is not None else load()
    mode = s.get("mode")
    if mode == "manual":
        return ManualProvisioner(s["p12"], s.get("p12_password", ""), s["profile"])
    if mode == "external":
        from datetime import timedelta
        from .provisioner import ExternalEngine
        return ExternalEngine(s["command"], timedelta(days=s.get("validity_days", 7)))
    if mode == "appleid":
        return AppleIDProvisioner(s["apple_id"], s.get("password", ""))
    raise RuntimeError("No signing credentials set. Run: ipakit setup --p12 ... --profile ...")
