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
        self.dev_box["values"] = [f"{d.name} [{d.connection}]" for d in self._devices]
        if self._devices:
            self.dev_box.current(0)

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
