import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from thermal_ledger.config import Config, default_db_path
from thermal_ledger.metrics import ThermalMetrics, slope_of
from thermal_ledger.storage import Storage


def test_slope_linear():
    pts = [(0, 40), (1, 42), (2, 44), (3, 46)]
    assert slope_of(pts) == pytest.approx(2.0, abs=1e-6)


def test_metrics_resistance_and_summary():
    m = ThermalMetrics()
    m.set_idle(45.0, 1.0)
    m.start_load(0.0)
    for i in range(1, 21):
        m.update(float(i), 45.0 + i * 2.0, 51.0)
    assert m.max_temp == pytest.approx(85.0)
    assert m.t80 is not None and m.t80 > 0
    rth = m.resistance(65.0, 51.0)
    assert rth == pytest.approx(20.0 / 50.0)
    s = m.summary(20.0)
    assert s.max_temp == pytest.approx(85.0)
    assert s.delta_temp == pytest.approx(40.0)
    assert s.rth == pytest.approx(0.78)
    assert s.score is not None


def test_config_roundtrip(tmp_path):
    cfg = Config(db_path=str(tmp_path / "x.db"), language="zh_CN", cutoff=99, duration=5)
    cfg = cfg.normalized()
    assert cfg.cutoff == 88
    assert cfg.duration == 10
    p = tmp_path / "config.json"
    cfg.save(p)
    loaded = Config.load_file(p)
    assert loaded.language == "zh_CN"
    assert loaded.db_path == str(tmp_path / "x.db")


def test_storage_roundtrip(tmp_path):
    store = Storage(tmp_path / "thermal.db")
    run_id = store.start_run("builtin", "max", 25.0, 85, 120)
    store.add_sample(run_id, 0.5, 50.0, 50.0, None, 1.0, 0.1)
    store.add_sample(run_id, 1.0, 52.0, 51.0, 2200, 2.0, 0.14)
    m = ThermalMetrics()
    m.set_idle(45.0, 1.0)
    m.start_load(0.0)
    m.update(1.0, 50.0, 50.0)
    store.finish_run(run_id, m.summary(1.0))
    rows = store.recent_runs()
    assert rows and rows[0]["load"] == "builtin"
    csv_path = store.export_csv(run_id, tmp_path / "run.csv")
    assert csv_path.exists() and "temp_c" in csv_path.read_text(encoding="utf-8-sig")
    store.close()
