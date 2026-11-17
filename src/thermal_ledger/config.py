"""User configuration and default paths."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


def default_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "ThermalLedger"


def config_path() -> Path:
    return default_data_dir() / "config.json"


def default_db_path() -> Path:
    return default_data_dir() / "thermal.db"


@dataclass
class Config:
    db_path: str = str(default_db_path())
    language: str = "system"          # system | en | zh_CN
    load: str = "builtin"             # builtin | external | command
    command: str = ""
    fan_mode: str = "max"             # max | auto | custom (recorded only)
    cutoff: int = 85                  # °C, 75..88
    duration: int = 120               # seconds, 10..600
    ambient: float = 25.0             # °C used for display only
    sensor: str = "nvml"
    fan_provider: str = "nvml"

    def normalized(self) -> "Config":
        cfg = Config(**asdict(self))
        cfg.cutoff = max(75, min(88, int(cfg.cutoff)))
        cfg.duration = max(10, min(600, int(cfg.duration)))
        cfg.ambient = max(-20.0, min(60.0, float(cfg.ambient)))
        return cfg

    def save(self, path: Path | None = None) -> Path:
        target = path or config_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self.normalized()), ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    @classmethod
    def load_file(cls, path: Path | None = None) -> "Config":
        target = path or config_path()
        if not target.exists():
            return cls().normalized()
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return cls().normalized()
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known}).normalized()


def system_language() -> str:
    """Best-effort UI language from the OS."""
    for env in ("LC_ALL", "LC_MESSAGES", "LANG"):
        val = os.environ.get(env, "")
        if "zh" in val.lower():
            return "zh_CN"
    if os.name == "nt":
        try:
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            # 0x0804 simplified Chinese, 0x0404 traditional Chinese
            if (lang_id & 0x3FF) == 0x04:
                return "zh_CN"
        except Exception:
            pass
    return "en"
