"""Qt translation loading."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTranslator

from .config import system_language


LANGUAGE_LABELS = {
    "system": "System",
    "en": "English",
    "zh_CN": "简体中文",
}


def resolve_language(setting: str) -> str:
    return system_language() if setting == "system" else setting


def _locale_candidates(code: str) -> list[str]:
    if code == "zh_CN":
        return ["zh_CN", "zh"]
    return [code]


def install_translator(app, setting: str) -> tuple[QTranslator | None, str]:
    code = resolve_language(setting)
    base_dirs = [
        Path(__file__).resolve().parent / "translations",
        Path(__file__).resolve().parent.parent.parent / "translations",
    ]
    for name in _locale_candidates(code):
        for base in base_dirs:
            qm = base / f"thermal_ledger_{name}.qm"
            if not qm.exists():
                continue
            tr = QTranslator(app)
            if tr.load(str(qm)):
                app.installTranslator(tr)
                return tr, code
    return None, code
