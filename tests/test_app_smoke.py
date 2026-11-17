import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication

from thermal_ledger.app import MainWindow
from thermal_ledger.config import Config


def _app():
    return QApplication.instance() or QApplication([])


def test_window_smoke(tmp_path):
    app = _app()
    cfg = Config(db_path=str(tmp_path / "test.db"), language="en")
    win = MainWindow(app, cfg)
    assert win.tabs.count() == 4
    assert win.tabs.tabText(0) == "Dashboard"
    win.cfg.save = lambda: None  # do not overwrite user config in tests
    win.close()
