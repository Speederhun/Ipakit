"""High-level operations: install an IPA and renew apps before they expire."""
from __future__ import annotations

import logging
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path

from .paths import ipa_store_dir
from .provisioner import Provisioner
from .signer import sign_ipa
from .store import InstalledApp, Store, utcnow

log = logging.getLogger("ipakit")

DEFAULT_MARGIN = timedelta(days=2)


class Ipakit:
    def __init__(self, provisioner: Provisioner, backend, store: Store | None = None,
                 signer=sign_ipa, ipa_dir: Path | None = None):
        self.provisioner = provisioner
        self.backend = backend
        self.store = store or Store()
        self.signer = signer
        self.ipa_dir = ipa_dir or ipa_store_dir()

    def _sign_and_install(self, name: str, udid: str, source: Path):
        if hasattr(self.provisioner, "sign_and_install"):
            # external engine does signing and installing itself
            return self.provisioner.sign_and_install(source, udid)
        creds = self.provisioner.credentials_for(udid, name)
        with tempfile.TemporaryDirectory() as tmp:
            signed = Path(tmp) / f"{name}-signed.ipa"
            self.signer(source, signed, creds)
            self.backend.install(udid, signed)
        return creds.expires_at()

    def install(self, ipa: str | Path, udid: str, name: str | None = None) -> InstalledApp:
        ipa = Path(ipa)
        name = name or ipa.stem
        stored = self.ipa_dir / f"{name}.ipa"
        if ipa.resolve() != stored.resolve():
            shutil.copyfile(ipa, stored)
        expires = self._sign_and_install(name, udid, stored)
        app = InstalledApp(
            name=name, udid=udid, source_ipa=str(stored),
            expires_at=expires.isoformat(), installed_at=utcnow().isoformat(),
        )
        self.store.upsert(app)
        log.info("Installed %s on %s (expires %s)", name, udid, expires)
        return app

    def renew_due(self, margin: timedelta = DEFAULT_MARGIN) -> list[str]:
        """Renew every app that is within `margin` of expiry and whose device
        is currently reachable. Returns names of renewed apps."""
        now = utcnow()
        reachable = self.backend.connected_udids()
        renewed: list[str] = []
        for app in list(self.store.apps):
            if not app.due(now, margin):
                continue
            if app.udid not in reachable:
                log.info("%s is due but device %s is not reachable", app.name, app.udid)
                continue
            try:
                expires = self._sign_and_install(app.name, app.udid, Path(app.source_ipa))
            except Exception:
                log.exception("Renewing %s failed", app.name)
                continue
            app.expires_at = expires.isoformat()
            app.installed_at = utcnow().isoformat()
            self.store.upsert(app)
            renewed.append(app.name)
        return renewed
