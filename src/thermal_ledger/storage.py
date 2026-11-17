"""SQLite storage for runs and samples."""

from __future__ import annotations

import csv
import sqlite3
import time
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    load TEXT NOT NULL,
    fan_mode TEXT,
    ambient REAL,
    cutoff REAL,
    planned_seconds REAL,
    idle_temp REAL,
    max_temp REAL,
    delta_temp REAL,
    t80 REAL,
    avg_power REAL,
    rth REAL,
    slope REAL,
    score REAL,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS samples (
    run_id INTEGER NOT NULL,
    t REAL NOT NULL,
    temp REAL,
    power REAL,
    fan REAL,
    slope REAL,
    rth REAL,
    PRIMARY KEY (run_id, t),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);
"""


class Storage:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.commit()

    def start_run(self, load: str, fan_mode: str, ambient: float, cutoff: float, planned_seconds: float) -> int:
        cur = self.conn.execute(
            "INSERT INTO runs (started_at, load, fan_mode, ambient, cutoff, planned_seconds) VALUES (?,?,?,?,?,?)",
            (time.strftime("%Y-%m-%d %H:%M:%S"), load, fan_mode, ambient, cutoff, planned_seconds),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def add_sample(self, run_id: int, t: float, temp: float, power: float, fan: int | None,
                   slope: float, rth: float | None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO samples (run_id,t,temp,power,fan,slope,rth) VALUES (?,?,?,?,?,?,?)",
            (run_id, t, temp, power, fan, slope, rth),
        )
        self.conn.commit()

    def finish_run(self, run_id: int, summary: Any) -> None:
        self.conn.execute(
            """UPDATE runs SET ended_at=?, idle_temp=?, max_temp=?, delta_temp=?, t80=?,
               avg_power=?, rth=?, slope=?, score=? WHERE id=?""",
            (time.strftime("%Y-%m-%d %H:%M:%S"), summary.idle_temp, summary.max_temp,
             summary.delta_temp, summary.t80, summary.avg_power, summary.rth,
             summary.slope, summary.score, run_id),
        )
        self.conn.commit()

    def recent_runs(self, limit: int = 50) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)))

    def samples_for(self, run_id: int) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM samples WHERE run_id=? ORDER BY t", (run_id,)))

    def export_csv(self, run_id: int, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        rows = self.samples_for(run_id)
        with open(target, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["t_s", "temp_c", "power_w", "fan_rpm", "slope_c_per_s", "rth_c_per_w"])
            for r in rows:
                w.writerow([r["t"], r["temp"], r["power"], r["fan"], r["slope"], r["rth"]])
        return target

    def close(self) -> None:
        self.conn.close()
