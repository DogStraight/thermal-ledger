"""Built-in GPU load: CUDA Driver PTX FMA kernel (no torch)."""

from __future__ import annotations

import ctypes
import threading

from .base import LoadProvider


PTX = r"""
.version 8.0
.target sm_89
.address_size 64

.visible .entry stress(.param .u64 p_out, .param .u32 p_iters)
{
    .reg .f32 %f<12>;
    .reg .b32 %r<8>;
    .reg .b64 %rd<4>;
    .reg .pred %p1;

    ld.param.u64 %rd1, [p_out];
    ld.param.u32 %r1, [p_iters];
    mov.u32 %r2, %tid.x;
    cvt.rn.f32.u32 %f1, %r2;
    mov.f32 %f2, 0f3F800000;
    mov.f32 %f3, 0f3F000000;
    mov.f32 %f4, 0f3E800000;
    mov.f32 %f5, 0f3D800000;
    mov.f32 %f6, 0f3D000000;
    mov.f32 %f7, 0f3C800000;
    mov.f32 %f8, 0f3C000000;

L:
    fma.rn.f32 %f1, %f1, %f2, %f3;
    fma.rn.f32 %f3, %f3, %f2, %f4;
    fma.rn.f32 %f4, %f4, %f2, %f5;
    fma.rn.f32 %f5, %f5, %f2, %f1;
    fma.rn.f32 %f6, %f6, %f2, %f7;
    fma.rn.f32 %f7, %f7, %f2, %f8;
    fma.rn.f32 %f8, %f8, %f2, %f6;
    fma.rn.f32 %f1, %f1, %f2, %f8;
    sub.u32 %r1, %r1, 1;
    setp.ne.u32 %p1, %r1, 0;
    @%p1 bra L;

    st.global.f32 [%rd1], %f1;
    ret;
}
"""


class CudaStress:
    def __init__(self, blocks: int = 12288, threads: int = 256, iters: int = 1000):
        self.lib = ctypes.WinDLL("nvcuda.dll")
        self.blocks, self.threads, self.iters = blocks, threads, iters
        self.ctx = ctypes.c_void_p()
        self.mod = ctypes.c_void_p()
        self.func = ctypes.c_void_p()
        self.dptr = ctypes.c_ulonglong()
        self._init()

    def _check(self, res, where):
        if res != 0:
            raise RuntimeError(f"{where} failed: CUDA error {res}")

    def _init(self):
        lib = self.lib
        self._check(lib.cuInit(0), "cuInit")
        dev = ctypes.c_int()
        self._check(lib.cuDeviceGet(ctypes.byref(dev), 0), "cuDeviceGet")
        self._check(lib.cuCtxCreate_v2(ctypes.byref(self.ctx), 0, dev), "cuCtxCreate")
        image = ctypes.create_string_buffer(PTX.encode() + b"\0")
        self._check(lib.cuModuleLoadDataEx(ctypes.byref(self.mod), image, 0, None, None), "cuModuleLoadData")
        self._check(lib.cuModuleGetFunction(ctypes.byref(self.func), self.mod, b"stress"), "cuModuleGetFunction")
        self._check(lib.cuMemAlloc_v2(ctypes.byref(self.dptr), 4), "cuMemAlloc")

    def launch(self):
        out = ctypes.c_ulonglong(self.dptr.value)
        args = (ctypes.c_void_p * 2)()
        args[0] = ctypes.cast(ctypes.pointer(out), ctypes.c_void_p)
        args[1] = ctypes.cast(ctypes.pointer(ctypes.c_uint(self.iters)), ctypes.c_void_p)
        self._check(self.lib.cuLaunchKernel(self.func, self.blocks, 1, 1, self.threads, 1, 1,
                                           0, None, args, None), "cuLaunchKernel")

    def sync(self):
        self._check(self.lib.cuCtxSynchronize(), "cuCtxSynchronize")

    def close(self):
        try:
            self.lib.cuMemFree_v2(self.dptr)
            self.lib.cuModuleUnload(self.mod)
            self.lib.cuCtxDestroy_v2(self.ctx)
        except Exception:
            pass


class BuiltinLoad:
    id = "builtin"
    name = "Built-in CUDA load"
    description = "PTX FMA kernel, ~50 W; no extra dependencies"

    def __init__(self):
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None

    def available(self) -> bool:
        try:
            ctypes.WinDLL("nvcuda.dll")
            return True
        except Exception:
            return False

    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        stress = None
        try:
            stress = CudaStress()
            while not self._stop.is_set():
                stress.launch()
                stress.sync()
        except Exception as exc:
            self.error = str(exc)
        finally:
            if stress:
                stress.close()

    def poll(self, stop: threading.Event) -> None:
        if self.error:
            stop.set()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
