from __future__ import annotations

import ctypes
import sys
from pathlib import Path

from ctypes import wintypes


OFN_EXPLORER = 0x00080000
OFN_FILEMUSTEXIST = 0x00001000
OFN_PATHMUSTEXIST = 0x00000800


class OpenFileNameW(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", wintypes.LPVOID),
        ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", wintypes.LPVOID),
        ("dwReserved", wintypes.DWORD),
        ("FlagsEx", wintypes.DWORD),
    ]


def pick_mod_file(owner_hwnd: int | None = None) -> Path | None:
    if not sys.platform.startswith("win"):
        raise RuntimeError("The bundled file picker currently supports Windows only.")

    buffer = ctypes.create_unicode_buffer(32768)
    filters = "Minecraft mods (*.jar;*.mrpack)\0*.jar;*.mrpack\0All files (*.*)\0*.*\0\0"

    dialog = OpenFileNameW()
    dialog.lStructSize = ctypes.sizeof(OpenFileNameW)
    dialog.hwndOwner = owner_hwnd or None
    dialog.lpstrFilter = filters
    dialog.nFilterIndex = 1
    dialog.lpstrFile = ctypes.cast(buffer, wintypes.LPWSTR)
    dialog.nMaxFile = len(buffer)
    dialog.lpstrTitle = "Select Minecraft mod"
    dialog.Flags = OFN_EXPLORER | OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST

    if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(dialog)):
        return Path(buffer.value)

    error = ctypes.windll.comdlg32.CommDlgExtendedError()
    if error:
        raise RuntimeError(f"Windows file picker failed with error code {error}.")
    return None
