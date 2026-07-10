from __future__ import annotations

import base64
import ctypes
import os
from ctypes import wintypes


class DpapiError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _blob_from_bytes(value: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(value, len(value))
    blob = _DataBlob(len(value), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    return blob, buffer


class DpapiProtector:
    _FLAGS = 0x01

    def __init__(self):
        if os.name != "nt":
            raise DpapiError("DPAPI 仅支持 Windows")
        self._crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._configure_signatures()

    def _configure_signatures(self) -> None:
        blob_pointer = ctypes.POINTER(_DataBlob)
        self._crypt32.CryptProtectData.argtypes = [
            blob_pointer,
            wintypes.LPCWSTR,
            blob_pointer,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            blob_pointer,
        ]
        self._crypt32.CryptProtectData.restype = wintypes.BOOL
        self._crypt32.CryptUnprotectData.argtypes = [
            blob_pointer,
            ctypes.POINTER(wintypes.LPWSTR),
            blob_pointer,
            ctypes.c_void_p,
            ctypes.c_void_p,
            wintypes.DWORD,
            blob_pointer,
        ]
        self._crypt32.CryptUnprotectData.restype = wintypes.BOOL
        self._kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self._kernel32.LocalFree.restype = ctypes.c_void_p

    def protect(self, value: str) -> str:
        encrypted = self._transform(value.encode("utf-8"), protect=True)
        return base64.b64encode(encrypted).decode("ascii")

    def unprotect(self, value: str) -> str:
        try:
            encrypted = base64.b64decode(value, validate=True)
            return self._transform(encrypted, protect=False).decode("utf-8")
        except (ValueError, UnicodeError) as error:
            raise DpapiError("无法解密本地凭据") from error

    def _transform(self, value: bytes, protect: bool) -> bytes:
        input_blob, input_buffer = _blob_from_bytes(value)
        output_blob = _DataBlob()
        if protect:
            ok = self._crypt32.CryptProtectData(
                ctypes.byref(input_blob),
                "Obsidian Vocabulary Clipper",
                None,
                None,
                None,
                self._FLAGS,
                ctypes.byref(output_blob),
            )
        else:
            ok = self._crypt32.CryptUnprotectData(
                ctypes.byref(input_blob),
                None,
                None,
                None,
                None,
                self._FLAGS,
                ctypes.byref(output_blob),
            )
        del input_buffer
        if not ok:
            raise DpapiError(f"Windows DPAPI 调用失败: {ctypes.get_last_error()}")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            self._kernel32.LocalFree(output_blob.pbData)
