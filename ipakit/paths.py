"""Where Ipakit keeps its data (state, stored IPAs, settings)."""
from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    base = os.environ.get("IPAKIT_HOME")
    if base:
        root = Path(base)
    elif os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home())) / "Ipakit"
    else:
        root = Path.home() / ".ipakit"
    root.mkdir(parents=True, exist_ok=True)
    return root


def ipa_store_dir() -> Path:
    d = data_dir() / "ipas"
    d.mkdir(parents=True, exist_ok=True)
    return d
