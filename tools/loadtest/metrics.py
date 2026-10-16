"""Small Windows/stdlib metrics helpers for the loopback-only load runner.

The Windows venv python.exe can be a launcher with the real interpreter below
it. Always include descendants, rather than reporting only that idle launcher.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import math
from pathlib import Path
import subprocess
import sys
from typing import Iterable


class _ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class _MemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _windows_api():
    if sys.platform != "win32":
        raise RuntimeError("Process metrics require Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
    kernel.Process32FirstW.restype = wintypes.BOOL
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_ProcessEntry)]
    kernel.Process32NextW.restype = wintypes.BOOL
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(_MemoryCounters), wintypes.DWORD
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    return kernel, psapi


def _process_tree(pid: int, kernel) -> list[tuple[int, int]]:
    """Return (PID, thread count), parents first, from one system snapshot."""
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    entries = {}
    try:
        entry = _ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        present = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while present:
            entries[int(entry.th32ProcessID)] = (
                int(entry.th32ParentProcessID), int(entry.cntThreads)
            )
            present = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    # Keep the root as a seed even if it exited before the snapshot, so any
    # remaining launcher children can still be measured and cleaned up.
    discovered = {pid}
    ordered = [(pid, entries[pid][1])] if pid in entries else []
    while True:
        children = [
            (child, threads)
            for child, (parent, threads) in entries.items()
            if child not in discovered and parent in discovered
        ]
        if not children:
            return ordered
        discovered.update(child for child, _ in children)
        ordered.extend(children)


def _filetime(value: wintypes.FILETIME) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def process_sample(pid: int) -> dict:
    """Sum live root/descendant CPU seconds, current RSS bytes and threads.

    CPU is cumulative kernel + user time since each live process started; RSS
    sums working sets (shared pages can count more than once). An exited child
    is absent in later samples, so callers should clamp negative CPU deltas.
    Missing/inaccessible PIDs are listed explicitly instead of silently zeroing
    their measurements. No PowerShell, WMI, psutil or network call is involved.
    """
    kernel, psapi = _windows_api()
    result = {
        "cpu_seconds": 0.0,
        "rss_bytes": 0,
        "threads": 0,
        "process_count": 0,
        "pids": [],
        "unavailable_pids": [],
    }
    for child, threads in _process_tree(int(pid), kernel):
        # PROCESS_QUERY_INFORMATION | PROCESS_VM_READ
        handle = kernel.OpenProcess(0x0400 | 0x0010, False, child)
        if not handle:
            result["unavailable_pids"].append(child)
            continue
        try:
            created, exited, system, user = (wintypes.FILETIME() for _ in range(4))
            memory = _MemoryCounters()
            memory.cb = ctypes.sizeof(memory)
            got_times = kernel.GetProcessTimes(
                handle, ctypes.byref(created), ctypes.byref(exited),
                ctypes.byref(system), ctypes.byref(user),
            )
            got_memory = psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb)
            if not got_times or not got_memory:
                result["unavailable_pids"].append(child)
                continue
            result["cpu_seconds"] += (_filetime(system) + _filetime(user)) / 10_000_000
            result["rss_bytes"] += int(memory.WorkingSetSize)
            result["threads"] += threads
            result["process_count"] += 1
            result["pids"].append(child)
        finally:
            kernel.CloseHandle(handle)
    return result


def stop_process_tree(process: subprocess.Popen) -> None:
    """Terminate the runner-owned Popen tree, including a venv launcher child.

    This is forced shutdown; take the final database/resource sample first.
    Open handles to the whole snapshot before termination, then stop children
    before parents so a disappearing launcher does not hide its interpreter.
    """
    kernel, _ = _windows_api()
    handles = []
    try:
        for pid, _ in reversed(_process_tree(process.pid, kernel)):
            # PROCESS_TERMINATE | SYNCHRONIZE
            handle = kernel.OpenProcess(0x0001 | 0x00100000, False, pid)
            if handle:
                handles.append(handle)
        for handle in handles:
            kernel.TerminateProcess(handle, 1)
        for handle in handles:
            kernel.WaitForSingleObject(handle, 5000)
    finally:
        for handle in handles:
            kernel.CloseHandle(handle)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def db_sizes(data_dir: str | Path) -> dict:
    """Return sizes of SQLite databases and their WAL/SHM files, in bytes."""
    result = {"db_bytes": 0, "wal_bytes": 0, "shm_bytes": 0, "total_bytes": 0, "files": {}}
    directory = Path(data_dir)
    if not directory.exists():
        return result
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        name = path.name.lower()
        base = name.removesuffix("-wal").removesuffix("-shm")
        if not base.endswith((".db", ".sqlite", ".sqlite3")):
            continue
        try:
            size = path.stat().st_size
        except FileNotFoundError:  # SQLite can checkpoint/remove its WAL mid-sample.
            continue
        key = "wal_bytes" if name.endswith("-wal") else "shm_bytes" if name.endswith("-shm") else "db_bytes"
        result[key] += size
        result["total_bytes"] += size
        result["files"][path.relative_to(directory).as_posix()] = size
    return result


def percentile(values: Iterable[float], p: float) -> float | None:
    """Nearest-rank percentile for p in [0, 100]; empty input returns None."""
    if not 0 <= p <= 100:
        raise ValueError("percentile must be between 0 and 100")
    ordered = sorted(values)
    if not ordered:
        return None
    return ordered[max(0, math.ceil(len(ordered) * p / 100) - 1)]
