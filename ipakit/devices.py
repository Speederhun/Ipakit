"""iPhone discovery (USB + Wi-Fi) and IPA installation via pymobiledevice3.

pymobiledevice3 is imported lazily so the rest of Ipakit stays importable
(and testable) without it.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Device:
    udid: str
    name: str
    connection: str  # "USB" or "Network"


def list_devices() -> list[Device]:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.usbmux import list_devices as mux_list

    out: list[Device] = []
    for d in mux_list():
        try:
            ld = create_using_usbmux(serial=d.serial)
            name = ld.get_value(key="DeviceName") or d.serial
        except Exception:
            name = d.serial
        out.append(Device(d.serial, str(name), str(d.connection_type)))
    return out


def install_ipa(udid: str, ipa: Path) -> None:
    from pymobiledevice3.lockdown import create_using_usbmux
    from pymobiledevice3.services.installation_proxy import InstallationProxyService

    ld = create_using_usbmux(serial=udid)
    InstallationProxyService(lockdown=ld).install_from_local(str(ipa))


class DeviceBackend:
    """Thin object so the refresher can be tested with a fake."""

    def connected_udids(self) -> set[str]:
        return {d.udid for d in list_devices()}

    def install(self, udid: str, ipa: Path) -> None:
        install_ipa(udid, ipa)
