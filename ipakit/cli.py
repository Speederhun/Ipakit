"""Command line interface: `ipakit ...`"""
from __future__ import annotations

import argparse
import logging
import time

from . import config
from .devices import DeviceBackend, list_devices
from .service import Ipakit
from .store import Store


def _app() -> Ipakit:
    return Ipakit(config.build_provisioner(), DeviceBackend())


def cmd_devices(_a) -> None:
    for d in list_devices():
        print(f"{d.udid}  {d.name}  [{d.connection}]")


def cmd_setup(a) -> None:
    config.save({
        "mode": "manual",
        "p12": a.p12,
        "p12_password": a.password or "",
        "profile": a.profile,
    })
    print("Saved.")


def cmd_setup_external(a) -> None:
    import shlex
    config.save({
        "mode": "external",
        "command": shlex.split(a.cmd, posix=False),
        "validity_days": a.validity_days,
    })
    print("Saved.")


def cmd_install(a) -> None:
    udid = a.udid
    if not udid:
        devs = list_devices()
        if len(devs) != 1:
            raise SystemExit("Pass --udid (found %d devices)." % len(devs))
        udid = devs[0].udid
    app = _app().install(a.ipa, udid, a.name)
    print(f"Installed {app.name}, expires {app.expires_at}")


def cmd_list(_a) -> None:
    for app in Store().apps:
        print(f"{app.name}  {app.udid}  expires {app.expires_at}")


def cmd_renew(a) -> None:
    done = _app().renew_due()
    print("Renewed:", ", ".join(done) if done else "nothing due")


def cmd_watch(a) -> None:
    app = _app()
    print(f"Watching every {a.interval}s. Ctrl+C to stop.")
    while True:
        try:
            done = app.renew_due()
            if done:
                print("Renewed:", ", ".join(done))
        except Exception as e:  # keep the loop alive
            print("Error:", e)
        time.sleep(a.interval)


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(prog="ipakit")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("devices").set_defaults(fn=cmd_devices)

    s = sub.add_parser("setup", help="set signing credentials (.p12 + .mobileprovision)")
    s.add_argument("--p12", required=True)
    s.add_argument("--password")
    s.add_argument("--profile", required=True)
    s.set_defaults(fn=cmd_setup)

    e = sub.add_parser(
        "setup-external",
        help="free Apple ID: delegate sign+install to another tool; use {ipa} and {udid}",
    )
    e.add_argument("--cmd", required=True)
    e.add_argument("--validity-days", type=int, default=7)
    e.set_defaults(fn=cmd_setup_external)

    i = sub.add_parser("install")
    i.add_argument("ipa")
    i.add_argument("--udid")
    i.add_argument("--name")
    i.set_defaults(fn=cmd_install)

    sub.add_parser("list").set_defaults(fn=cmd_list)
    sub.add_parser("renew").set_defaults(fn=cmd_renew)

    w = sub.add_parser("watch", help="keep renewing in the background")
    w.add_argument("--interval", type=int, default=900)
    w.set_defaults(fn=cmd_watch)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
