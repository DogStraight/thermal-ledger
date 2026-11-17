"""Sensor provider interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class SensorSnapshot:
    ts: float
    temp_c: float | None
    power_w: float | None
    hotspot_c: float | None = None
    clock_mhz: float | None = None
    provider: str = ""


class SensorProvider(Protocol):
    id: str
    name: str

    def available(self) -> bool: ...
    def read(self) -> SensorSnapshot: ...
    def close(self) -> None: ...
