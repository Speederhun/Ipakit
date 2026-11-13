"""Windows GUI: device list, drag-free IPA install, and a tray icon that keeps
renewing apps in the background."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import config
from .devices import DeviceBackend, list_devices
from .service import Ipakit
from .store import Store

CHECK_EVERY_SECONDS = 900


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ipakit")
        self.geometry("520x380")
        self._devices = []
        self._stop = threading.Event()

        ttk.Label(self, text="iPhone").pack(anchor="w", padx=10, pady=(10, 0))
        self.dev_box = ttk.Combobox(self, state="readonly")
        self.dev_box.pack(fill="x", padx=10)
        row = ttk.Frame(self)
        row.pack(fill="x", padx=10, pady=8)
        ttk.Button(row, text="Refresh devices", command=self.refresh_devices).pack(side="left")
        ttk.Button(row, text="Install IPA...", command=self.install_ipa).pack(side="left", padx=6)
        ttk.Button(row, text="Renew now", command=self.renew_now).pack(side="left")
        ttk.Button(row, text="Settings...", command=self.open_settings).pack(side="right")

        self.apps = ttk.Treeview(self, columns=("udid", "exp"), show="headings", height=10)
        self.apps.heading("udid", text="Device")
        self.apps.heading("exp", text="Expires")
        self.apps.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.status = ttk.Label(self, text="Ready")
        self.status.pack(anchor="w", padx=10, pady=(0, 8))

        self.protocol("WM_DELETE_WINDOW", self.withdraw)  # close -> tray
        self.refresh_devices()
        self.refresh_apps()
        threading.Thread(target=self._loop, daemon=True).start()
        threading.Thread(target=self._tray, daemon=True).start()

    # --- helpers
    def _ipakit(self) -> Ipakit:
        return Ipakit(config.build_provisioner(), DeviceBackend())

    def _set(self, text: str) -> None:
        self.after(0, lambda: self.status.config(text=text))

    def refresh_apps(self) -> None:
        self.apps.delete(*self.apps.get_children())
        for a in Store().apps:
            self.apps.insert("", "end", text=a.name, values=(a.udid[:12], a.expires_at[:16]))

    def refresh_devices(self) -> None:
        try:
            self._devices = list_devices()
        except Exception as e:
            self._devices = []
            self._set(f"Device error: {e}")
        if not self._devices and "error" not in self.status.cget("text").lower():
            self._set("No iPhone found: connect by USB, unlock it, tap Trust, install Apple Devices.")
        self.dev_box["values"] = [f"{d.name} [{d.connection}]" for d in self._devices]
        if self._devices:
            self.dev_box.current(0)

    # --- settings
    def open_settings(self) -> None:
        import shlex
        cur = config.load()
        win = tk.Toplevel(self)
        win.title("Signing settings")
        win.geometry("520x330")
        mode = tk.StringVar(value=cur.get("mode", "manual"))
        p12 = tk.StringVar(value=cur.get("p12", ""))
        pw = tk.StringVar(value=cur.get("p12_password", ""))
        prof = tk.StringVar(value=cur.get("profile", ""))
        cmd = tk.StringVar(value=" ".join(cur.get("command", [])))

        def pick(var, types):
            f = filedialog.askopenfilename(filetypes=types)
            if f:
                var.set(f)

        ttk.Radiobutton(win, text="Paid developer account (.p12 + .mobileprovision)",
                        variable=mode, value="manual").pack(anchor="w", padx=10, pady=(10, 0))
        for label, var, types, browse in (
            (".p12", p12, [("p12", "*.p12")], True),
            ("Password", pw, None, False),
            (".mobileprovision", prof, [("profile", "*.mobileprovision")], True),
        ):
            r = ttk.Frame(win)
            r.pack(fill="x", padx=30, pady=2)
            ttk.Label(r, text=label, width=16).pack(side="left")
            ttk.Entry(r, textvariable=var, show="*" if label == "Password" else "").pack(
                side="left", fill="x", expand=True)
            if browse:
                ttk.Button(r, text="...", width=3,
                           command=lambda v=var, t=types: pick(v, t)).pack(side="left", padx=2)
        ttk.Radiobutton(win, text="Free Apple ID via external tool (use {ipa} and {udid})",
                        variable=mode, value="external").pack(anchor="w", padx=10, pady=(14, 0))
        ttk.Entry(win, textvariable=cmd).pack(fill="x", padx=30, pady=2)

        def save():
            if mode.get() == "manual":
                config.save({"mode": "manual", "p12": p12.get(),
                             "p12_password": pw.get(), "profile": prof.get()})
            else:
                config.save({"mode": "external",
                             "command": shlex.split(cmd.get(), posix=False),
                             "validity_days": 7})
            self._set("Settings saved")
            win.destroy()

        ttk.Button(win, text="Save", command=save).pack(pady=14)

    # --- actions
    def install_ipa(self) -> None:
        idx = self.dev_box.current()
        if idx < 0:
            return messagebox.showwarning("Ipakit", "No iPhone selected.")
        path = filedialog.askopenfilename(filetypes=[("IPA", "*.ipa")])
        if not path:
            return
        udid = self._devices[idx].udid

        def work():
            try:
                self._set("Signing and installing...")
                app = self._ipakit().install(path, udid)
                self._set(f"Installed {app.name}")
                self.after(0, self.refresh_apps)
            except Exception as e:
                self._set(f"Error: {e}")

        threading.Thread(target=work, daemon=True).start()

    def renew_now(self) -> None:
        def work():
            try:
                done = self._ipakit().renew_due()
                self._set("Renewed: " + (", ".join(done) or "nothing due"))
                self.after(0, self.refresh_apps)
            except Exception as e:
                self._set(f"Error: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _loop(self) -> None:
        while not self._stop.wait(CHECK_EVERY_SECONDS):
            try:
                self._ipakit().renew_due()
                self.after(0, self.refresh_apps)
            except Exception as e:
                self._set(f"Auto-renew error: {e}")

    def _tray(self) -> None:
        import pystray
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (64, 64), "#1c6ef2")
        ImageDraw.Draw(img).rectangle((18, 18, 46, 46), fill="white")
        menu = pystray.Menu(
            pystray.MenuItem("Open", lambda: self.after(0, self.deiconify), default=True),
            pystray.MenuItem("Renew now", lambda: self.after(0, self.renew_now)),
            pystray.MenuItem("Quit", lambda: self._quit()),
        )
        self.icon = pystray.Icon("ipakit", img, "Ipakit", menu)
        self.icon.run()

    def _quit(self) -> None:
        self._stop.set()
        self.icon.stop()
        self.after(0, self.destroy)


def main() -> None:
    App().mainloop()


if __name__ == "__main__":
    main()
