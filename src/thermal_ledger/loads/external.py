"""Monitor an externally started load; never touches the process."""

from __future__ import annotations

import threading


class ExternalLoad:
    id = "external"
    name = "External load"
    description = "Only monitor; start your game/render yourself"

    def available(self) -> bool:
        return True

    def start(self) -> None:
        pass

    def poll(self, stop: threading.Event) -> None:
        pass

    def stop(self) -> None:
        pass
