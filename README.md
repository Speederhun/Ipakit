# Ipakit

Install unsigned `.ipa` files on your iPhone from Windows, and keep them
alive: Ipakit re-signs and reinstalls apps in the background before their
signing profile expires.

## How it works

1. Talks to the iPhone over USB or Wi-Fi (`pymobiledevice3`; needs iTunes or
   the Apple Devices app installed for the USB driver).
2. Re-signs the IPA with [zsign](https://github.com/zhlynn/zsign).
3. Installs it through the iOS installation service.
4. Remembers every app's expiry. A background loop (tray icon in the GUI, or
   `ipakit watch`) renews apps 2 days before expiry whenever the phone is
   reachable.

## Status

| Part | State |
|---|---|
| Device discovery + install | written, needs testing on a real iPhone |
| Signing via zsign | written, needs testing |
| Paid Developer account (`.p12` + `.mobileprovision`, valid 1 year) | works end to end |
| Auto-renew logic, state, CLI, GUI/tray | works, covered by tests (mocked devices) |
| Free Apple ID (7-day certs) | via an external engine (see below); a built-in Apple ID login is not implemented |

### Free Apple ID

Apple's developer login (GrandSlam/anisette) is hard to maintain, so Ipakit
delegates it to a tool that already does it, such as
[Impactor](https://github.com/claration/Impactor)'s `plumesign` CLI (MIT).
Ipakit schedules and repeats the call before the 7 days run out:

```
ipakit setup-external --cmd "plumesign <sign/install args> {ipa} {udid}"
```

`{ipa}` and `{udid}` are filled in by Ipakit. Check `plumesign --help` for the
exact arguments; the first run may ask for your Apple ID and 2FA code in a
console, and the tool must keep its login so later runs are unattended.
This path has not been tested against a real Apple ID yet.

## Easy install (Windows)

Download the repo, double-click **install.bat**. It installs Python, the Apple
USB driver (iTunes), Ipakit and zsign if missing, and puts an **Ipakit** icon
on the desktop.

## Manual setup

```
pip install -e .
# put zsign.exe on PATH (or into ipakit/bin/)
ipakit setup --p12 cert.p12 --password secret --profile app.mobileprovision
ipakit devices
ipakit install MyApp.ipa
ipakit watch          # or run: ipakit-gui
```

On the iPhone: enable Developer Mode (Settings > Privacy & Security) and
trust the developer profile.

## Limits

- Free Apple IDs get 7-day certificates and max 3 apps; renewal only works
  while the PC and phone are on the same network. Paid accounts last 1 year.
- Apple changes its developer services from time to time, which can break the
  free-account flow.

## Development

```
pip install -e ".[dev]"
pytest
```

MIT licensed.
