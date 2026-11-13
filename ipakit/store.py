"""Persistent record of apps Ipakit installed and when they expire."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .paths import data_dir


@dataclass
class InstalledApp:
    name: str
    udid: str                 # target device
    source_ipa: str           # stored original (unsigned) IPA
    expires_at: str           # ISO 8601, UTC
    installed_at: str

    def expiry(self) -> datetime:
        return datetime.fromisoformat(self.expires_at)

    def due(self, now: datetime, margin: timedelta) -> bool:
        return now >= self.expiry() - margin


class Store:
    def __init__(self, path: Path | None = None):
        self.path = path or data_dir() / "state.json"
        self.apps: list[InstalledApp] = []
        self.load()

    def load(self) -> None:
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.apps = [InstalledApp(**a) for a in data.get("apps", [])]

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps({"apps": [asdict(a) for a in self.apps]}, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.path)

    def upsert(self, app: InstalledApp) -> None:
        self.apps = [
            a for a in self.apps
            if not (a.name == app.name and a.udid == app.udid)
        ]
        self.apps.append(app)
        self.save()

    def remove(self, name: str, udid: str | None = None) -> None:
        self.apps = [
            a for a in self.apps
            if not (a.name == name and (udid is None or a.udid == udid))
        ]
        self.save()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
