"""Spawn an arbitrary command and monitor it."""

from __future__ import annotations

import subprocess
import threading


class CommandLoad:
    id = "command"
    name = "Command load"
    description = "Start any command, monitor until it exits or test ends"

    def __init__(self, command: str = ""):
        self.command = command
        self.proc: subprocess.Popen | None = None

    def available(self) -> bool:
        return bool(self.command.strip())

    def start(self) -> None:
        if not self.command.strip():
            raise RuntimeError("empty command")
        self.proc = subprocess.Popen(self.command, shell=True)

    def poll(self, stop: threading.Event) -> None:
        if self.proc and self.proc.poll() is not None:
            stop.set()

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=5)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
