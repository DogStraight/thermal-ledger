"""Regenerate Qt .ts from source and compile .qm."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TS = ROOT / "translations" / "thermal_ledger_zh_CN.ts"
QM_DIR = ROOT / "src" / "thermal_ledger" / "translations"
QM = QM_DIR / "thermal_ledger_zh_CN.qm"


def main() -> int:
    lupdate = Path(sys.executable).parent / "pyside6-lupdate.exe"
    lrelease = Path(sys.executable).parent / "pyside6-lrelease.exe"
    if not lupdate.exists():
        lupdate = Path("pyside6-lupdate")
    if not lrelease.exists():
        lrelease = Path("pyside6-lrelease")
    QM_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(lupdate), "-extensions", "py", str(ROOT / "src" / "thermal_ledger"), "-ts", str(TS)], check=True)
    subprocess.run([str(lrelease), str(TS), "-qm", str(QM)], check=True)
    print(f"ok: {QM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
