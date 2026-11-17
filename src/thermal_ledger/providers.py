"""Provider discovery: built-ins + optional entry points."""

from __future__ import annotations

from importlib import metadata
from typing import Any

from .fans.nvml import NullFan, NvmlFan
from .loads import BUILTIN as BUILTIN_LOADS
from .sensors.nvml import NvmlSensor


def _entry_points(group: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        eps = metadata.entry_points()
        selected = eps.select(group=group) if hasattr(eps, "select") else [e for e in eps if e.group == group]
        for ep in selected:
            try:
                out[ep.name] = ep.load()
            except Exception:
                continue
    except Exception:
        pass
    return out


def sensor_classes() -> dict[str, Any]:
    out: dict[str, Any] = {"nvml": NvmlSensor}
    out.update(_entry_points("thermal_ledger.sensors"))
    return out


def fan_classes() -> dict[str, Any]:
    out: dict[str, Any] = {"nvml": NvmlFan, "none": NullFan}
    out.update(_entry_points("thermal_ledger.fans"))
    return out


def load_classes() -> dict[str, Any]:
    out: dict[str, Any] = dict(BUILTIN_LOADS)
    out.update(_entry_points("thermal_ledger.loads"))
    return out


def create_sensor(provider_id: str):
    cls = sensor_classes().get(provider_id)
    if not cls:
        raise KeyError(provider_id)
    return cls()


def create_fan(provider_id: str):
    cls = fan_classes().get(provider_id)
    if not cls:
        raise KeyError(provider_id)
    return cls()


def create_load(provider_id: str, command: str = ""):
    cls = load_classes().get(provider_id)
    if not cls:
        raise KeyError(provider_id)
    if provider_id == "command":
        return cls(command)
    return cls()
