"""NVIDIA NVML sensor (ctypes, no torch / no pynvml)."""

from __future__ import annotations

import ctypes
import ctypes.util
import time

from .base import SensorSnapshot


class NvmlSensor:
    id = "nvml"
    name = "NVIDIA NVML"

    def __init__(self, index: int = 0):
        self.index = index
        self.lib = None
        self.handle = ctypes.c_void_p()
        self.gpu_name = ""
        try:
            path = ctypes.util.find_library("nvml") or "nvml.dll"
            self.lib = ctypes.WinDLL(path)
            self.lib.nvmlInit_v2()
            self.lib.nvmlDeviceGetHandleByIndex_v2(index, ctypes.byref(self.handle))
            buf = ctypes.create_string_buffer(96)
            self.lib.nvmlDeviceGetName(self.handle, buf, 96)
            self.gpu_name = buf.value.decode(errors="replace")
        except Exception:
            self.lib = None

    def available(self) -> bool:
        return self.lib is not None

    def read(self) -> SensorSnapshot:
        if not self.lib:
            raise RuntimeError("NVML 不可用")
        t = ctypes.c_uint()
        p = ctypes.c_uint()
        c = ctypes.c_uint()
        temp = power = clock = None
        try:
            self.lib.nvmlDeviceGetTemperature(self.handle, 0, ctypes.byref(t))
            temp = float(t.value)
        except Exception:
            pass
        try:
            self.lib.nvmlDeviceGetPowerUsage(self.handle, ctypes.byref(p))
            power = p.value / 1000.0
        except Exception:
            pass
        try:
            self.lib.nvmlDeviceGetClockInfo(self.handle, 0, ctypes.byref(c))
            clock = float(c.value)
        except Exception:
            pass
        return SensorSnapshot(ts=time.time(), temp_c=temp, power_w=power, clock_mhz=clock, provider=self.id)

    def close(self) -> None:
        if self.lib:
            try:
                self.lib.nvmlShutdown()
            except Exception:
                pass
            self.lib = None
