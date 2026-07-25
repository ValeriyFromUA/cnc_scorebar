"""Пошук бандлованих ассетів (Icons/) — однаково працює і з вихідників,
і зі зібраного PyInstaller onefile-екзешника (де файли розпаковуються у
тимчасову sys._MEIPASS)."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*parts)
