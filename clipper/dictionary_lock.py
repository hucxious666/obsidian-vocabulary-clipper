from __future__ import annotations

import ctypes
import hashlib
import os
from contextlib import contextmanager
from typing import Iterator


WAIT_OBJECT_0 = 0
WAIT_ABANDONED = 0x80


class DictionaryBusyError(RuntimeError):
    pass


def _mutex_name(pack_id: str) -> str:
    digest = hashlib.sha256(pack_id.encode("utf-8")).hexdigest()[:32]
    return f"Local\\ObsidianVocabularyClipper.Dictionary.{digest}"


@contextmanager
def installation_lock(pack_id: str) -> Iterator[None]:
    if os.name != "nt":
        yield
        return
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.ReleaseMutex.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.CreateMutexW(None, False, _mutex_name(pack_id))
    if not handle:
        raise DictionaryBusyError("无法创建词典安装锁")
    result = kernel32.WaitForSingleObject(handle, 0)
    acquired = result in (WAIT_OBJECT_0, WAIT_ABANDONED)
    try:
        if not acquired:
            raise DictionaryBusyError("该词典正在安装或更新，请稍后再试")
        yield
    finally:
        if acquired:
            kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)
