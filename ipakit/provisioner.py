"""Sources of signing credentials.

A provisioner hands the signer a .p12 certificate (+ password) and a
.mobileprovision profile for a given device.

* ManualProvisioner - you supply files exported from a paid Apple Developer
  account (valid 1 year). Fully working.
* AppleIDProvisioner - free-account flow (7-day certificates). The interface
  is defined; the Apple ID authentication backend still has to be plugged in.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Protocol

from . import profile


@dataclass
class Credentials:
    p12_path: Path
    p12_password: str
    profile_path: Path

    def expires_at(self):
        return profile.expiration(self.profile_path)


class Provisioner(Protocol):
    def credentials_for(self, udid: str, app_name: str) -> Credentials: ...


class ManualProvisioner:
    def __init__(self, p12: str | Path, password: str, mobileprovision: str | Path):
        self._creds = Credentials(Path(p12), password, Path(mobileprovision))

    def credentials_for(self, udid: str, app_name: str) -> Credentials:
        udids = profile.provisioned_udids(self._creds.profile_path)
        if udids and udid not in udids:
            raise ValueError(
                f"Device {udid} is not listed in the provisioning profile."
            )
        return self._creds


class ExternalEngine:
    """Delegates signing + installing to another command-line tool that can
    log in with a free Apple ID (for example Impactor's `plumesign`).

    `command` is an argument list with the placeholders {ipa} and {udid}.
    The tool is expected to sign the IPA and install it on the device, exiting
    with status 0 on success. A free Apple ID certificate lasts `validity`
    (7 days by default); Ipakit uses that to schedule the next renewal.
    """

    def __init__(self, command: list[str], validity: timedelta = timedelta(days=7)):
        if not command:
            raise ValueError("External engine command is empty.")
        self.command = command
        self.validity = validity

    def sign_and_install(self, ipa: Path, udid: str):
        cmd = [part.format(ipa=str(ipa), udid=udid) for part in self.command]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                (proc.stderr or proc.stdout).strip() or f"{cmd[0]} exited {proc.returncode}"
            )
        return datetime.now(timezone.utc) + self.validity


class AppleIDProvisioner:
    """Free Apple ID flow: registers the device, requests a development
    certificate and a profile, and returns fresh 7-day credentials.

    Needs an Apple ID authentication backend (anisette data + the developer
    services API). Implement `credentials_for` here to enable the free path;
    everything else (signing, install, auto-renew) already works with it.
    """

    def __init__(self, apple_id: str, password: str):
        self.apple_id = apple_id
        self._password = password

    def credentials_for(self, udid: str, app_name: str) -> Credentials:
        raise NotImplementedError(
            "Apple ID provisioning backend is not implemented yet."
        )
