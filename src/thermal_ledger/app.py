"""Thermal Ledger GUI (PySide6)."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import __app_name__, __version__
from .config import Config
from .i18n import LANGUAGE_LABELS, install_translator
from .metrics import ThermalMetrics
from .providers import create_fan, create_load, create_sensor, fan_classes, load_classes, sensor_classes
from .storage import Storage


class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.data: list[tuple[float, float]] = []
        self.threshold = 85.0
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), QColor("#111111"))
        self.setPalette(p)

    def set_data(self, data: list[tuple[float, float]], threshold: float) -> None:
        self.data = data
        self.threshold = threshold
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.fillRect(0, 0, w, h, QColor("#111111"))
        left, top, right, bottom = 48, 16, 16, 28
        plot_w, plot_h = w - left - right, h - top - bottom
        p.setPen(QPen(QColor("#333333"), 1))
        for i in range(5):
            y = top + plot_h * i / 4
            p.drawLine(left, y, w - right, y)
            p.drawText(6, y + 4, f"{int(100 - i * 15)}")
        p.setPen(QPen(QColor("#F26A1B"), 1, Qt.DashLine))
        ty = top + plot_h * (1 - (self.threshold - 40) / 60)
        p.drawLine(left, ty, w - right, ty)
        p.setPen(QPen(QColor("#F26A1B"), 2))
        if len(self.data) >= 2:
            t0 = self.data[0][0]
            tmax = max(1.0, self.data[-1][0] - t0)
            pts = []
            for t, temp in self.data:
                x = left + (t - t0) / tmax * plot_w
                y = top + plot_h * (1 - (temp - 40) / 60)
                pts.append((x, y))
            for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
                p.drawLine(int(x1), int(y1), int(x2), int(y2))
        p.setPen(QPen(QColor("#888888"), 1))
        p.drawText(left, h - 8, "0s")
        p.drawText(w - right - 40, h - 8, f"{int(self.data[-1][0] - self.data[0][0]) if self.data else 0}s")
        p.end()


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication, config: Config):
        super().__init__()
        self.app = app
        self.cfg = config
        self.sensor = None
        self.fan = None
        self.storage: Storage | None = None
        self.metrics = ThermalMetrics()
        self.plot_data: list[tuple[float, float]] = []
        self.state = "ready"
        self.load = None
        self.run_id: int | None = None
        self.started_at = 0.0
        self.idle_started = 0.0
        self.idle_temps: list[float] = []
        self.idle_powers: list[float] = []
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.tick)
        self._build_ui()
        self._open_storage()
        self._open_providers()
        self.refresh_history()
        self.retranslate()

    # ---------- UI ----------
    def _build_ui(self) -> None:
        self.setWindowTitle(f"{__app_name__} {__version__}")
        self.resize(980, 760)
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self._build_dashboard(), "")
        self.tabs.addTab(self._build_history(), "")
        self.tabs.addTab(self._build_settings(), "")
        self.tabs.addTab(self._build_about(), "")

    def _build_dashboard(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)

        header = QHBoxLayout()
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(28)
        header.addWidget(self.status_label, 1)
        self.start_btn = QPushButton()
        self.stop_btn = QPushButton()
        self.stop_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.start_test)
        self.stop_btn.clicked.connect(self.stop_test)
        header.addWidget(self.start_btn)
        header.addWidget(self.stop_btn)
        lay.addLayout(header)

        self.metric_labels: dict[str, QLabel] = {}
        self.metrics_box = QGroupBox(self.tr("Live"))
        grid = QGridLayout(self.metrics_box)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(2)
        for i, key in enumerate(("temp", "power", "fan", "slope", "rth", "peak", "elapsed")):
            title = QLabel()
            value = QLabel("--")
            value.setFont(QFont("Consolas", 15, QFont.Weight.Bold))
            self.metric_labels[key] = value
            grid.addWidget(title, 0, i)
            grid.addWidget(value, 1, i)
            setattr(self, f"metric_title_{key}", title)
        lay.addWidget(self.metrics_box)

        self.plot = PlotWidget()
        self.plot.setMinimumHeight(260)
        lay.addWidget(self.plot, 1)

        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        lay.addWidget(self.note_label)
        return page

    def _build_history(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        self.history_table = QTableWidget(0, 9)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        lay.addWidget(self.history_table)
        row = QHBoxLayout()
        self.refresh_btn = QPushButton()
        self.export_btn = QPushButton()
        self.open_db_btn = QPushButton()
        self.refresh_btn.clicked.connect(self.refresh_history)
        self.export_btn.clicked.connect(self.export_selected)
        self.open_db_btn.clicked.connect(self.open_db_folder)
        row.addWidget(self.refresh_btn)
        row.addWidget(self.export_btn)
        row.addWidget(self.open_db_btn)
        row.addStretch()
        lay.addLayout(row)
        return page

    def _build_settings(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        box = QGroupBox()
        form = QFormLayout(box)
        self.language_combo = QComboBox()
        for code, label in LANGUAGE_LABELS.items():
            self.language_combo.addItem(label, code)
        self.db_edit = QLineEdit(str(self.cfg.db_path))
        browse = QPushButton(self.tr("Browse..."))
        self.browse_btn = browse
        browse.clicked.connect(self.browse_db)
        db_row = QHBoxLayout()
        db_row.addWidget(self.db_edit)
        db_row.addWidget(browse)
        db_widget = QWidget()
        db_widget.setLayout(db_row)
        self.load_combo = QComboBox()
        self.load_combo.addItem(self.tr("Built-in CUDA load"), "builtin")
        self.load_combo.addItem(self.tr("External load (monitor only)"), "external")
        self.load_combo.addItem(self.tr("Command"), "command")
        for pid in load_classes():
            if self.load_combo.findData(pid) < 0:
                self.load_combo.addItem(pid, pid)
        self.command_edit = QLineEdit(self.cfg.command)
        self.fan_mode_combo = QComboBox()
        self.fan_mode_combo.addItem(self.tr("Max"), "max")
        self.fan_mode_combo.addItem(self.tr("Auto"), "auto")
        self.fan_mode_combo.addItem(self.tr("Custom"), "custom")
        self.cutoff_spin = QSpinBox()
        self.cutoff_spin.setRange(75, 88)
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(10, 600)
        self.ambient_spin = QDoubleSpinBox()
        self.ambient_spin.setRange(-20, 60)
        self.ambient_spin.setSuffix(" °C")
        self.sensor_combo = QComboBox()
        for pid in sensor_classes():
            self.sensor_combo.addItem(pid, pid)
        self.fan_combo = QComboBox()
        for pid in fan_classes():
            self.fan_combo.addItem(pid, pid)
        form.addRow(QLabel(self.tr("Language")), self.language_combo)
        form.addRow(QLabel(self.tr("Database")), db_widget)
        form.addRow(QLabel(self.tr("Load")), self.load_combo)
        form.addRow(QLabel(self.tr("Command")), self.command_edit)
        form.addRow(QLabel(self.tr("Fan mode (recorded)")), self.fan_mode_combo)
        form.addRow(QLabel(self.tr("Temperature cutoff")), self.cutoff_spin)
        form.addRow(QLabel(self.tr("Max duration")), self.duration_spin)
        form.addRow(QLabel(self.tr("Ambient")), self.ambient_spin)
        form.addRow(QLabel(self.tr("Sensor")), self.sensor_combo)
        form.addRow(QLabel(self.tr("Fan provider")), self.fan_combo)
        self._set_combo(self.language_combo, self.cfg.language)
        self._set_combo(self.load_combo, self.cfg.load)
        self._set_combo(self.fan_mode_combo, self.cfg.fan_mode)
        self._set_combo(self.sensor_combo, self.cfg.sensor)
        self._set_combo(self.fan_combo, self.cfg.fan_provider)
        self.command_edit.setText(self.cfg.command)
        self.cutoff_spin.setValue(self.cfg.cutoff)
        self.duration_spin.setValue(self.cfg.duration)
        self.ambient_spin.setValue(self.cfg.ambient)
        self.save_btn = QPushButton()
        self.save_btn.clicked.connect(self.save_settings)
        form.addRow(self.save_btn)
        self.settings_box = box
        lay.addWidget(box)
        lay.addStretch()
        self.language_title = form.labelForField(self.language_combo)
        return page

    def _build_about(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        self.about_label = QLabel()
        self.about_label.setWordWrap(True)
        self.about_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.about_label)
        lay.addStretch()
        return page

    def _set_combo(self, combo, data: str) -> None:
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        else:
            combo.addItem(data, data)
            combo.setCurrentIndex(combo.count() - 1)

    def retranslate(self) -> None:
        self.tabs.setTabText(0, self.tr("Dashboard"))
        self.tabs.setTabText(1, self.tr("History"))
        self.tabs.setTabText(2, self.tr("Settings"))
        self.tabs.setTabText(3, self.tr("About"))
        self.status_label.setText(self.tr("Ready. Set fans to max before running a test."))
        titles = {
            "temp": self.tr("Temp"),
            "power": self.tr("Power"),
            "fan": self.tr("Fan"),
            "slope": self.tr("dT/dt"),
            "rth": self.tr("Thermal R"),
            "peak": self.tr("Peak"),
            "elapsed": self.tr("Elapsed"),
        }
        for key, text in titles.items():
            getattr(self, f"metric_title_{key}").setText(text)
        self.start_btn.setText(self.tr("Start test"))
        self.stop_btn.setText(self.tr("Stop"))
        self.note_label.setText(self.tr(
            "Thermal R = (T - idle T) / (P - idle P). Higher means worse cooling. "
            "Fan RPM is shown only when a provider can read it."
        ))
        self.history_table.setHorizontalHeaderLabels([
            self.tr("ID"), self.tr("Started"), self.tr("Load"), self.tr("Fan"),
            self.tr("Peak"), self.tr("ΔT"), self.tr("t80"), self.tr("Rth"), self.tr("Score"),
        ])
        self.refresh_btn.setText(self.tr("Refresh"))
        self.export_btn.setText(self.tr("Export CSV"))
        self.open_db_btn.setText(self.tr("Open DB folder"))
        self.save_btn.setText(self.tr("Save settings"))
        self.browse_btn.setText(self.tr("Browse..."))
        self.settings_box.setTitle(self.tr("Settings"))
        self.about_label.setText(
            self.tr(
                "Thermal Ledger {version}\n\n"
                "A minimal, pluggable GPU thermal coefficient and long-term ledger.\n"
                "License: MIT\n"
                "Database: {db}\n\n"
                "Plugins: sensor / fan / load providers via Python entry points."
            ).format(version=__version__, db=self.cfg.db_path)
        )

    # ---------- providers/storage ----------
    def _open_providers(self) -> None:
        try:
            if self.sensor:
                self.sensor.close()
            self.sensor = create_sensor(self.cfg.sensor)
        except Exception:
            self.sensor = None
        try:
            if self.fan:
                self.fan.close()
            self.fan = create_fan(self.cfg.fan_provider)
        except Exception:
            self.fan = None

    def _open_storage(self) -> None:
        if self.storage:
            self.storage.close()
        self.storage = Storage(self.cfg.db_path)

    # ---------- test flow ----------
    def start_test(self) -> None:
        if self.state in ("idle", "load", "stopping"):
            return
        if not self.sensor or not self.sensor.available():
            QMessageBox.critical(self, self.tr("Error"), self.tr("No sensor available."))
            return
        try:
            self.load = create_load(self.cfg.load, self.cfg.command)
        except Exception as exc:
            QMessageBox.critical(self, self.tr("Error"), str(exc))
            return
        if not self.load.available():
            QMessageBox.critical(self, self.tr("Error"), self.tr("Selected load is not available."))
            return
        self.metrics.reset()
        self.plot_data = []
        self.idle_temps = []
        self.idle_powers = []
        self.started_at = time.time()
        self.idle_started = self.started_at
        self.state = "idle"
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText(self.tr("Idle baseline (5 s)..."))
        self.timer.start()

    def stop_test(self) -> None:
        if self.state in ("idle", "load"):
            self.state = "stopping"

    def _finish(self) -> None:
        self.timer.stop()
        if self.load:
            try:
                self.load.stop()
            except Exception:
                pass
            self.load = None
        summary = self.metrics.summary(time.time() - self.started_at)
        duration = time.time() - self.started_at
        if self.run_id is not None and self.storage:
            self.storage.finish_run(self.run_id, summary)
        self.run_id = None
        self.state = "ready"
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.refresh_history()
        self.status_label.setText(self.tr(
            "Done: peak {peak}°C, ΔT {delta}°C, Rth {rth}, score {score}."
        ).format(
            peak=summary.max_temp,
            delta=summary.delta_temp,
            rth="--" if summary.rth is None else summary.rth,
            score="--" if summary.score is None else summary.score,
        ))

    def tick(self) -> None:
        if self.state not in ("idle", "load"):
            return
        try:
            s = self.sensor.read()
        except Exception:
            return
        temp = s.temp_c
        power = s.power_w
        if temp is None or power is None:
            return
        fan = None
        if self.fan:
            try:
                fan = self.fan.read_rpm()
            except Exception:
                fan = None
        now = time.time()
        if self.state == "stopping":
            self._finish()
            return
        if self.state == "idle":
            self.idle_temps.append(temp)
            self.idle_powers.append(power)
            self._update_metrics_display(temp, power, fan, None, None)
            if now - self.idle_started >= 5.0:
                idle_t = sum(self.idle_temps) / max(1, len(self.idle_temps))
                idle_p = sum(self.idle_powers) / max(1, len(self.idle_powers))
                self.metrics.set_idle(idle_t, idle_p)
                self.metrics.start_load(now)
                self.storage = self.storage or Storage(self.cfg.db_path)
                self.run_id = self.storage.start_run(
                    self.cfg.load, self.cfg.fan_mode, self.cfg.ambient, self.cfg.cutoff, self.cfg.duration
                )
                try:
                    self.load.start()
                except Exception as exc:
                    self.status_label.setText(self.tr("Load failed: {error}").format(error=exc))
                    self.state = "stopping"
                    return
                self.state = "load"
                self.status_label.setText(self.tr("Running..."))
            return

        # load state
        self.metrics.update(now, temp, power)
        elapsed = now - self.metrics.load_started_at if self.metrics.load_started_at else 0.0
        slope = self.metrics.slope()
        rth = self.metrics.resistance(temp, power)
        self.plot_data.append((elapsed, temp))
        if len(self.plot_data) > 7200:
            self.plot_data = self.plot_data[-7200:]
        self.plot.set_data(self.plot_data, self.cfg.cutoff)
        if self.run_id is not None and self.storage:
            self.storage.add_sample(self.run_id, elapsed, temp, power, fan, slope, rth)
        self._update_metrics_display(temp, power, fan, slope, rth)
        if self.load and hasattr(self.load, "error") and getattr(self.load, "error"):
            self._finish()
            return
        if self.state == "stopping" or temp >= self.cfg.cutoff or elapsed >= self.cfg.duration:
            self._finish()
            return
        if self.load:
            stop_event = threading.Event()
            self.load.poll(stop_event)
            if stop_event.is_set():
                self._finish()

    def _update_metrics_display(self, temp: float, power: float, fan: int | None,
                                slope: float | None, rth: float | None) -> None:
        peak = self.metrics.max_temp
        elapsed = time.time() - self.started_at
        fan_text = "--" if fan is None else f"{fan} RPM"
        values = {
            "temp": f"{temp:.1f} °C",
            "power": f"{power:.1f} W",
            "fan": fan_text,
            "slope": "--" if slope is None else f"{slope:.2f} °C/s",
            "rth": "--" if rth is None else f"{rth:.2f} °C/W",
            "peak": "--" if peak is None else f"{peak:.1f} °C",
            "elapsed": f"{elapsed:.0f} s",
        }
        for key, value in values.items():
            self.metric_labels[key].setText(value)

    # ---------- history/settings ----------
    def refresh_history(self) -> None:
        if not self.storage:
            return
        rows = self.storage.recent_runs(100)
        self.history_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            values = [
                str(r["id"]), r["started_at"], r["load"], r["fan_mode"] or "--",
                f'{r["max_temp"]:.1f}' if r["max_temp"] is not None else "--",
                f'{r["delta_temp"]:.1f}' if r["delta_temp"] is not None else "--",
                f'{r["t80"]:.1f}' if r["t80"] is not None else "--",
                f'{r["rth"]:.2f}' if r["rth"] is not None else "--",
                f'{r["score"]:.1f}' if r["score"] is not None else "--",
            ]
            for j, v in enumerate(values):
                self.history_table.setItem(i, j, QTableWidgetItem(v))

    def export_selected(self) -> None:
        row = self.history_table.currentRow()
        if row < 0:
            QMessageBox.information(self, self.tr("Export"), self.tr("Select a run first."))
            return
        run_id = int(self.history_table.item(row, 0).text())
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export CSV"), f"thermal-run-{run_id}.csv", "CSV (*.csv)")
        if path and self.storage:
            self.storage.export_csv(run_id, path)
            QMessageBox.information(self, self.tr("Export"), path)

    def open_db_folder(self) -> None:
        import subprocess

        folder = Path(self.cfg.db_path).parent
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(folder)])

    def browse_db(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Database file"), self.db_edit.text(), "SQLite database (*.db)"
        )
        if path:
            self.db_edit.setText(path)

    def save_settings(self) -> None:
        old_db = self.cfg.db_path
        self.cfg.db_path = self.db_edit.text().strip() or self.cfg.db_path
        self.cfg.language = self.language_combo.currentData()
        self.cfg.load = self.load_combo.currentData()
        self.cfg.command = self.command_edit.text()
        self.cfg.fan_mode = self.fan_mode_combo.currentData()
        self.cfg.cutoff = self.cutoff_spin.value()
        self.cfg.duration = self.duration_spin.value()
        self.cfg.ambient = self.ambient_spin.value()
        self.cfg.sensor = self.sensor_combo.currentData()
        self.cfg.fan_provider = self.fan_combo.currentData()
        self.cfg.save()
        if self.cfg.db_path != old_db:
            try:
                self._open_storage()
                self.refresh_history()
            except Exception as exc:
                QMessageBox.critical(self, self.tr("Error"), str(exc))
                return
        self._open_providers()
        self.retranslate()
        QMessageBox.information(self, self.tr("Settings"), self.tr("Saved. Language changes apply after restart."))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.timer.stop()
        if self.state in ("idle", "load", "stopping"):
            self._finish()
        if self.sensor:
            self.sensor.close()
        if self.fan:
            self.fan.close()
        if self.storage:
            self.storage.close()
        self.cfg.save()
        super().closeEvent(event)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="thermal-ledger")
    p.add_argument("--version", action="store_true")
    args = p.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    cfg = Config.load_file()
    install_translator(app, cfg.language)
    win = MainWindow(app, cfg)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
