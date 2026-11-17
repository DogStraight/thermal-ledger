"""Load provider interface."""

from __future__ import annotations

import threading
from typing import Protocol


class LoadProvider(Protocol):
    id: str
    name: str
    description: str

    def available(self) -> bool: ...
    def start(self) -> None: ...
    def poll(self, stop: threading.Event) -> None: ...
    def stop(self) -> None: ...
