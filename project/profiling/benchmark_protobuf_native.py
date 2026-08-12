"""Measure direct C++ loading and querying of a Protobuf corpus."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.autocomplete import select_native_completions
from src.native_index import NativeIndex


class ProcessMemoryCountersEx(ctypes.Structure):
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
        ("PrivateUsage", ctypes.c_size_t),
    ]


def memory_bytes() -> tuple[int, int, int]:
    counters = ProcessMemoryCountersEx()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCountersEx),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    if not psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(),
        ctypes.byref(counters),
        counters.cb,
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    return counters.WorkingSetSize, counters.PrivateUsage, counters.PeakWorkingSetSize


def mib(value: int) -> float:
    return value / 1024**2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protobuf_directory")
    arguments = parser.parse_args()

    before_working, before_private, _ = memory_bytes()
    started = perf_counter()
    native_index = NativeIndex.from_protobuf_directory(
        arguments.protobuf_directory
    )
    load_seconds = perf_counter() - started
    after_working, after_private, peak_working = memory_bytes()

    print(f"sentences={len(native_index):,}")
    print(f"load_seconds={load_seconds:.3f}")
    print(f"added_working_mib={mib(after_working - before_working):.1f}")
    print(f"added_private_mib={mib(after_private - before_private):.1f}")
    print(f"peak_working_mib={mib(peak_working):.1f}")

    queries = [
        "a",
        "th",
        "the",
        "flows across a network once the osi model is understood",
        "xlows across a network once the osi model is understood",
        "flows across a network once the osi model is understoox",
        "this phrase should not occur anywhere in the complete archive xyzq",
    ]
    try:
        for query in queries:
            started = perf_counter()
            results = select_native_completions(query, native_index)
            elapsed_ms = (perf_counter() - started) * 1000
            print(
                f"query_ms={elapsed_ms:.3f} results={len(results)} "
                f"chars={len(query)} query={query!r}"
            )
    finally:
        native_index.close()


if __name__ == "__main__":
    main()
