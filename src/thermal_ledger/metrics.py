"""Thermal metrics: slope, thermal resistance, score."""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class RunSummary:
    idle_temp: float
    max_temp: float
    delta_temp: float
    t80: float | None
    avg_power: float
    rth: float | None
    slope: float
    score: float | None
    duration: float
    samples: int


def slope_of(points: list[tuple[float, float]]) -> float:
    """Least-squares dT/dt over (t, T) points."""
    n = len(points)
    if n < 4:
        return 0.0
    sx = sum(p[0] for p in points)
    sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points)
    sxy = sum(p[0] * p[1] for p in points)
    den = n * sxx - sx * sx
    if abs(den) < 1e-9:
        return 0.0
    return (n * sxy - sx * sy) / den


class ThermalMetrics:
    def __init__(self, slope_window_s: float = 8.0):
        self.slope_window_s = slope_window_s
        self.reset()

    def reset(self) -> None:
        self.idle_temp: float | None = None
        self.idle_power: float | None = None
        self.load_started_at: float | None = None
        self._window: deque[tuple[float, float]] = deque(maxlen=64)
        self._load_samples: list[tuple[float, float]] = []  # (t, power)
        self.max_temp: float | None = None
        self.t80: float | None = None
        self.sample_count = 0

    def set_idle(self, temp: float, power: float) -> None:
        self.idle_temp = temp
        self.idle_power = power

    def start_load(self, t: float | None = None) -> None:
        self.load_started_at = t if t is not None else time.time()

    def update(self, t: float, temp: float, power: float) -> None:
        self._window.append((t, temp))
        self.sample_count += 1
        if self.max_temp is None or temp > self.max_temp:
            self.max_temp = temp
        if self.load_started_at is not None:
            self._load_samples.append((t, power))
            if self.t80 is None and temp >= 80:
                self.t80 = max(0.0, t - self.load_started_at)

    def slope(self) -> float:
        if not self._window:
            return 0.0
        last_t = self._window[-1][0]
        pts = [(t - last_t, temp) for t, temp in self._window if last_t - t <= self.slope_window_s]
        return slope_of(pts)

    def resistance(self, temp: float, power: float) -> float | None:
        if self.idle_temp is None or self.idle_power is None:
            return None
        dp = power - self.idle_power
        if dp <= 1.0:
            return None
        return (temp - self.idle_temp) / dp

    def avg_power(self) -> float:
        if not self._load_samples:
            return 0.0
        return sum(p for _, p in self._load_samples) / len(self._load_samples)

    def summary(self, duration: float) -> RunSummary:
        idle = self.idle_temp if self.idle_temp is not None else 0.0
        max_temp = self.max_temp if self.max_temp is not None else idle
        delta = max_temp - idle
        avg_power = self.avg_power()
        rth = (delta / avg_power) if avg_power > 1.0 and delta > 1.0 else None
        slope = self.slope()
        if delta < 3.0 or avg_power < 5.0:
            score = None
        else:
            score_delta = max(0.0, min(100.0, 100 * (1 - (delta - 20) / 50)))
            score_time = 100.0 if self.t80 is None else max(0.0, min(100.0, 100 * min(self.t80, 120) / 120))
            score = round(0.5 * score_delta + 0.5 * score_time, 1)
        return RunSummary(
            idle_temp=round(idle, 1),
            max_temp=round(max_temp, 1),
            delta_temp=round(delta, 1),
            t80=None if self.t80 is None else round(self.t80, 2),
            avg_power=round(avg_power, 1),
            rth=None if rth is None else round(rth, 2),
            slope=round(slope, 2),
            score=score,
            duration=round(duration, 1),
            samples=self.sample_count,
        )
