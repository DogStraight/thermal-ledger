"""NVIDIA NVML fan speed (often unavailable on laptops; returns None honestly)."""

from __future__ import annotations

import ctypes
import ctypes.util


class NvmlFan:
    id = "nvml"
    name = "NVIDIA NVML fan"

    def __init__(self, index: int = 0):
        self.lib = None
        self.handle = ctypes.c_void_p()
        try:
            path = ctypes.util.find_library("nvml") or "nvml.dll"
            self.lib = ctypes.WinDLL(path)
            self.lib.nvmlInit_v2()
            self.lib.nvmlDeviceGetHandleByIndex_v2(index, ctypes.byref(self.handle))
        except Exception:
            self.lib = None

    def available(self) -> bool:
        return self.lib is not None

    def read_rpm(self) -> int | None:
        if not self.lib:
            return None
        v = ctypes.c_uint()
        try:
            if self.lib.nvmlDeviceGetFanSpeed(self.handle, ctypes.byref(v)) != 0:
                return None
            return int(v.value) if v.value > 0 else None
        except Exception:
            return None

    def close(self) -> None:
        if self.lib:
            try:
                self.lib.nvmlShutdown()
            except Exception:
                pass
            self.lib = None


class NullFan:
    id = "none"
    name = "No fan sensor"

    def available(self) -> bool:
        return True

    def read_rpm(self) -> int | None:
        return None

    def close(self) -> None:
        pass
