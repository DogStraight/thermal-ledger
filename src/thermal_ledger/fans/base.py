"""Fan provider interface (read-only)."""

from __future__ import annotations

from typing import Protocol


class FanProvider(Protocol):
    id: str
    name: str

    def available(self) -> bool: ...
    def read_rpm(self) -> int | None: ...
    def close(self) -> None: ...
