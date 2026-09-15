"""Environment fingerprint helpers."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def compute_environment_hash(workspace: str | Path | None = None) -> str:
    """Return a stable fingerprint for the local execution environment."""

    compilers: dict[str, str] = {}
    for name in ("g++", "clang++", "cl"):
        path = shutil.which(name)
        if path is None:
            continue
        compilers[name] = _command_version((path, "--version"))
    payload = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "total_memory_bytes": _total_memory_bytes(),
        "python": sys.version,
        "python_executable": sys.executable,
        "compilers": compilers,
        "dependency_lock_hash": _dependency_lock_hash(workspace),
        "sandbox_profile": "trusted-local",
    }
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _dependency_lock_hash(workspace: str | Path | None) -> str | None:
    if workspace is None:
        return None
    root = Path(workspace)
    names = (
        "pyproject.toml",
        "uv.lock",
        "poetry.lock",
        "requirements.txt",
    )
    digest = hashlib.sha256()
    found = False
    for name in names:
        path = root / name
        if not path.exists():
            continue
        found = True
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest() if found else None


def _total_memory_bytes() -> int | None:
    if sys.platform == "win32":

        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return int(status.ullTotalPhys)
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
    except (AttributeError, OSError, ValueError):
        return None
    return int(page_size * pages)


def _command_version(command: tuple[str, ...]) -> str:
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            timeout=5,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    output = (completed.stdout or completed.stderr).strip().splitlines()
    return output[0] if output else "unknown"
