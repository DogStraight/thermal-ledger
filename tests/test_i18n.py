import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtWidgets import QApplication

from thermal_ledger.app import MainWindow
from thermal_ledger.config import Config
from thermal_ledger.i18n import install_translator


def test_chinese_translation(tmp_path):
    app = QApplication.instance() or QApplication([])
    cfg = Config(db_path=str(tmp_path / "test.db"), language="zh_CN")
    tr, code = install_translator(app, cfg.language)
    assert code == "zh_CN"
    assert tr is not None
    win = MainWindow(app, cfg)
    assert win.tabs.tabText(0) == "仪表盘"
    assert win.start_btn.text() == "开始测试"
    win.cfg.save = lambda: None
    win.close()
