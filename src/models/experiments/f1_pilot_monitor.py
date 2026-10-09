"""Giám sát tài nguyên Windows và chạy pilot trong process tree cô lập."""

from __future__ import annotations

import argparse
import base64
import ctypes
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence

from src.config import PROJECT_ROOT


AVAILABLE_STOP_BYTES = 5 * 1024**3
COMMIT_STOP_RATIO = 0.95
PROCESS_PRIVATE_STOP_BYTES = 16 * 1024**3
SEVERE_PAGING_PAGES_PER_SECOND = 1000.0
SEVERE_PAGING_MIN_AVAILABLE_BYTES = 8 * 1024**3
SEVERE_PAGING_SAMPLES = 5
PREFLIGHT_MAX_COMMIT_RATIO = 0.85
PREFLIGHT_MIN_AVAILABLE_BYTES = 7 * 1024**3
PREFLIGHT_SECONDS = 60
SAMPLE_SECONDS = 1.0


@dataclass(frozen=True)
class SystemSample:
    available_bytes: int
    committed_bytes: int
    commit_limit_bytes: int
    pages_input_per_sec: float | None
    page_reads_per_sec: float | None
    pages_output_per_sec: float | None
    page_writes_per_sec: float | None

    @property
    def commit_ratio(self) -> float:
        return self.committed_bytes / self.commit_limit_bytes if self.commit_limit_bytes else 1.0


@dataclass(frozen=True)
class ProcessSample:
    pid: int
    parent_pid: int | None
    executable_path: str
    working_set_bytes: int
    private_bytes: int
    cpu_seconds: float


def _windows_system_sample() -> SystemSample:
    if os.name != "nt":
        raise OSError("The pilot monitor requires Windows system counters.")

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    class PERFORMANCE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("CommitTotal", ctypes.c_size_t),
            ("CommitLimit", ctypes.c_size_t), ("CommitPeak", ctypes.c_size_t),
            ("PhysicalTotal", ctypes.c_size_t), ("PhysicalAvailable", ctypes.c_size_t),
            ("SystemCache", ctypes.c_size_t), ("KernelTotal", ctypes.c_size_t),
            ("KernelPaged", ctypes.c_size_t), ("KernelNonpaged", ctypes.c_size_t),
            ("PageSize", ctypes.c_size_t), ("HandleCount", ctypes.c_ulong),
            ("ProcessCount", ctypes.c_ulong), ("ThreadCount", ctypes.c_ulong),
        ]

    memory = MEMORYSTATUSEX()
    memory.dwLength = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
        raise ctypes.WinError()
    performance = PERFORMANCE_INFORMATION()
    performance.cb = ctypes.sizeof(performance)
    if not ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(performance), performance.cb):
        raise ctypes.WinError()
    paging = _windows_paging_counters()
    page_size = int(performance.PageSize)
    return SystemSample(
        available_bytes=int(memory.ullAvailPhys),
        committed_bytes=int(performance.CommitTotal * page_size),
        commit_limit_bytes=int(performance.CommitLimit * page_size),
        **paging,
    )


def _windows_paging_counters() -> dict[str, float | None]:
    counters = (
        "pages_input_per_sec", "page_reads_per_sec",
        "pages_output_per_sec", "page_writes_per_sec",
    )
    script = r"""
$paths = @('\Memory\Pages Input/sec', '\Memory\Page Reads/sec', '\Memory\Pages Output/sec', '\Memory\Page Writes/sec')
$samples = (Get-Counter -Counter $paths -ErrorAction Stop).CounterSamples
$result = [ordered]@{pages_input_per_sec=$null;page_reads_per_sec=$null;pages_output_per_sec=$null;page_writes_per_sec=$null}
foreach ($sample in $samples) {
  $counterName = ($sample.Path -split '\\')[-1].ToLowerInvariant()
  switch ($counterName) {
    'pages input/sec' {$result.pages_input_per_sec=[double]$sample.CookedValue}
    'page reads/sec' {$result.page_reads_per_sec=[double]$sample.CookedValue}
    'pages output/sec' {$result.pages_output_per_sec=[double]$sample.CookedValue}
    'page writes/sec' {$result.page_writes_per_sec=[double]$sample.CookedValue}
  }
}
[pscustomobject]$result | ConvertTo-Json -Compress
"""
    encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded_script],
            capture_output=True, text=True, timeout=8, check=True,
        )
        values = json.loads(completed.stdout.strip().splitlines()[-1])
        return {key: float(values[key]) for key in counters}
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError, json.JSONDecodeError):
        return {key: None for key in counters}


def _process_table() -> dict[int, int]:
    """Return PID -> parent PID from a Windows process snapshot."""
    if os.name != "nt":
        return {}

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
            ("th32ProcessID", ctypes.c_ulong), ("th32DefaultHeapID", ctypes.c_size_t),
            ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
            ("th32ParentProcessID", ctypes.c_ulong), ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_wchar * 260),
        ]

    kernel = ctypes.windll.kernel32
    kernel.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    kernel.CreateToolhelp32Snapshot.argtypes = [ctypes.c_ulong, ctypes.c_ulong]
    kernel.Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError()
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    result: dict[int, int] = {}
    try:
        more = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while more:
            result[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
            more = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return result


def descendant_pids(root_pid: int, process_table: dict[int, int]) -> list[int]:
    """Return root and descendants in parent-before-child order."""
    found = [root_pid]
    known = {root_pid}
    while True:
        children = sorted(pid for pid, parent in process_table.items() if parent in known and pid not in known)
        if not children:
            return found
        found.extend(children)
        known.update(children)


def _process_sample(pid: int, parent_pid: int | None) -> ProcessSample | None:
    if os.name != "nt":
        return None

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    ctypes.windll.kernel32.OpenProcess.restype = ctypes.c_void_p
    ctypes.windll.kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    ctypes.windll.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    ctypes.windll.psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), ctypes.c_ulong,
    ]
    ctypes.windll.kernel32.GetProcessTimes.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME), ctypes.POINTER(FILETIME),
    ]
    ctypes.windll.kernel32.QueryFullProcessImageNameW.argtypes = [
        ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong),
    ]
    handle = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x1000, False, pid)
    if not handle:
        return None
    try:
        memory = PROCESS_MEMORY_COUNTERS_EX()
        memory.cb = ctypes.sizeof(memory)
        if not ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(memory), memory.cb):
            return None
        created, exited, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if not ctypes.windll.kernel32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user)
        ):
            return None
        image_path = ctypes.create_unicode_buffer(32768)
        image_path_size = ctypes.c_ulong(len(image_path))
        if not ctypes.windll.kernel32.QueryFullProcessImageNameW(
            handle, 0, image_path, ctypes.byref(image_path_size)
        ):
            image = "<unavailable>"
        else:
            image = image_path.value
        ticks = lambda value: (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)
        return ProcessSample(
            pid=pid, parent_pid=parent_pid, executable_path=image,
            working_set_bytes=int(memory.WorkingSetSize),
            private_bytes=int(memory.PrivateUsage),
            cpu_seconds=(ticks(kernel) + ticks(user)) / 10_000_000,
        )
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def stop_reason(system: SystemSample, process_private_bytes: int, paging_streak: int) -> str | None:
    """Evaluate unchanged hard stop limits."""
    reasons = stop_reasons(system, process_private_bytes, paging_streak)
    return reasons[0] if reasons else None


def stop_reasons(system: SystemSample, process_private_bytes: int, paging_streak: int) -> list[str]:
    """Return every breached hard limit, not only the first one."""
    reasons = []
    if system.available_bytes < AVAILABLE_STOP_BYTES:
        reasons.append("STOP_AVAILABLE_RAM_BELOW_5_GIB")
    if system.commit_ratio >= COMMIT_STOP_RATIO:
        reasons.append("STOP_SYSTEM_COMMIT_AT_OR_ABOVE_95_PERCENT")
    if process_private_bytes > PROCESS_PRIVATE_STOP_BYTES:
        reasons.append("STOP_PROCESS_TREE_PRIVATE_COMMIT_ABOVE_16_GIB")
    if paging_streak >= SEVERE_PAGING_SAMPLES:
        reasons.append("STOP_SUSTAINED_SEVERE_PAGING")
    return reasons


def preflight_passes(samples: Sequence[SystemSample], minimum_samples: int = 60) -> bool:
    """Require a full sustained window below conservative commit/RAM guardrails."""
    if len(samples) < minimum_samples:
        return False
    window = samples[-int(PREFLIGHT_SECONDS / SAMPLE_SECONDS):]
    return all(
        sample.commit_ratio < PREFLIGHT_MAX_COMMIT_RATIO
        and sample.available_bytes >= PREFLIGHT_MIN_AVAILABLE_BYTES
        and sample.pages_input_per_sec is not None
        and sample.page_reads_per_sec is not None
        and sample.pages_output_per_sec is not None
        and sample.page_writes_per_sec is not None
        for sample in window
    )


def _append_jsonl(stream: Any, event: dict[str, Any]) -> None:
    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
    stream.flush()
    os.fsync(stream.fileno())


def _terminate_tree(root_pid: int, timeout_seconds: float = 5.0) -> list[int]:
    table = _process_table()
    pids = descendant_pids(root_pid, table)
    for pid in reversed(pids):
        ctypes.windll.kernel32.OpenProcess.restype = ctypes.c_void_p
        ctypes.windll.kernel32.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        ctypes.windll.kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        handle = ctypes.windll.kernel32.OpenProcess(0x0001 | 0x1000, False, pid)
        if handle:
            try:
                ctypes.windll.kernel32.TerminateProcess(handle, 124)
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        table = _process_table()
        if not any(pid in table for pid in pids):
            break
        time.sleep(0.1)
    return pids


def run_monitored(
    command: Sequence[str], log_path: Path, *, preflight_seconds: int = PREFLIGHT_SECONDS,
    sample_seconds: float = SAMPLE_SECONDS,
    progress_path: Path | None = None,
    system_sampler: Callable[[], SystemSample] = _windows_system_sample,
    process_sampler: Callable[[int, int | None], ProcessSample | None] = _process_sample,
    preflight_max_commit_ratio: float = PREFLIGHT_MAX_COMMIT_RATIO,
    preflight_min_available_bytes: int = PREFLIGHT_MIN_AVAILABLE_BYTES,
) -> int:
    """Preflight then launch/monitor one command; stop its entire process tree on breach."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    with log_path.open("a", encoding="utf-8") as stream:
        _append_jsonl(stream, {
            "event": "MONITOR_START", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "command": list(command), "interpreter": command[0],
        })
    samples: list[SystemSample] = []
    preflight_started = time.monotonic()
    while True:
        sample = system_sampler()
        samples.append(sample)
        index = len(samples) - 1
        breached_stops = stop_reasons(sample, 0, 0)
        if breached_stops:
            preflight_stop = breached_stops[0]
        elif sample.available_bytes < preflight_min_available_bytes:
            preflight_stop = "PREFLIGHT_AVAILABLE_RAM_BELOW_7_GIB"
        elif sample.commit_ratio >= preflight_max_commit_ratio:
            preflight_stop = "PREFLIGHT_COMMIT_NOT_BELOW_85_PERCENT"
        elif any(value is None for value in (
            sample.pages_input_per_sec, sample.page_reads_per_sec,
            sample.pages_output_per_sec, sample.page_writes_per_sec,
        )):
            preflight_stop = "PREFLIGHT_PAGING_COUNTERS_UNAVAILABLE"
        else:
            preflight_stop = None
        with log_path.open("a", encoding="utf-8") as stream:
            _append_jsonl(stream, {
                "event": "PREFLIGHT_SAMPLE", "sample": index + 1,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "elapsed_seconds": time.monotonic() - started,
                **asdict(sample), "commit_utilization": sample.commit_ratio,
            })
        if preflight_stop:
            last_completed = _last_completed_phase(progress_path)
            with log_path.open("a", encoding="utf-8") as stream:
                _append_jsonl(stream, {
                    "event": "STOP", "reason": preflight_stop,
                    "stop_reasons": breached_stops,
                    "elapsed_seconds": time.monotonic() - started,
                    "last_completed_phase": last_completed,
                })
            if progress_path is not None:
                with progress_path.open("a", encoding="utf-8") as stream:
                    _append_jsonl(stream, {
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                        "phase": "STOPPED_AT_PREFLIGHT", "stop_reason": preflight_stop,
                        "last_completed_phase": last_completed,
                    })
            return 2
        preflight_elapsed = time.monotonic() - preflight_started
        if preflight_elapsed >= preflight_seconds and len(samples) >= 2:
            break
        time.sleep(min(sample_seconds, max(0.0, preflight_seconds - preflight_elapsed)))

    if not preflight_passes(samples, minimum_samples=2):
        last_completed = _last_completed_phase(progress_path)
        with log_path.open("a", encoding="utf-8") as stream:
            _append_jsonl(stream, {
                "event": "STOP", "reason": "PREFLIGHT_NOT_SUSTAINABLY_SAFE",
                "elapsed_seconds": time.monotonic() - started,
                "last_completed_phase": last_completed,
            })
        if progress_path is not None:
            with progress_path.open("a", encoding="utf-8") as stream:
                _append_jsonl(stream, {
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "phase": "STOPPED_AT_PREFLIGHT", "stop_reason": "PREFLIGHT_NOT_SUSTAINABLY_SAFE",
                    "last_completed_phase": last_completed,
                })
        return 2

    child = subprocess.Popen(list(command), cwd=PROJECT_ROOT, shell=False)
    root_pid = child.pid
    peak_private = 0
    peak_working_set = 0
    peak_single_private = 0
    peak_single_working_set = 0
    previous_cpu: dict[int, float] = {}
    previous_time = time.monotonic()
    paging_streak = 0
    stop = None
    with log_path.open("a", encoding="utf-8") as stream:
        _append_jsonl(stream, {"event": "CHILD_STARTED", "pid": root_pid, "timestamp_utc": datetime.now(timezone.utc).isoformat()})
        try:
            while child.poll() is None:
                now = time.monotonic()
                system = system_sampler()
                table = _process_table()
                pids = descendant_pids(root_pid, table)
                process_samples = [s for pid in pids if (s := process_sampler(pid, table.get(pid))) is not None]
                private_total = sum(s.private_bytes for s in process_samples)
                working_total = sum(s.working_set_bytes for s in process_samples)
                peak_private = max(peak_private, private_total)
                peak_working_set = max(peak_working_set, working_total)
                peak_single_private = max(peak_single_private, max((s.private_bytes for s in process_samples), default=0))
                peak_single_working_set = max(peak_single_working_set, max((s.working_set_bytes for s in process_samples), default=0))
                elapsed = max(now - previous_time, 1e-6)
                cpu_delta = sum(max(0.0, s.cpu_seconds - previous_cpu.get(s.pid, s.cpu_seconds)) for s in process_samples)
                cpu_percent = cpu_delta / elapsed / (os.cpu_count() or 1) * 100
                previous_cpu = {s.pid: s.cpu_seconds for s in process_samples}
                previous_time = now
                pages_in = system.pages_input_per_sec
                if (pages_in is not None and pages_in >= SEVERE_PAGING_PAGES_PER_SECOND
                        and system.available_bytes < SEVERE_PAGING_MIN_AVAILABLE_BYTES):
                    paging_streak += 1
                else:
                    paging_streak = 0
                breached_stops = stop_reasons(system, private_total, paging_streak)
                stop = breached_stops[0] if breached_stops else None
                _append_jsonl(stream, {
                    "event": "RESOURCE_SAMPLE", "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "elapsed_seconds": now - started, "main_pid": root_pid,
                    "runtime_interpreter_pids": [
                        sample.pid for sample in process_samples
                        if sample.executable_path.lower().endswith("\\python.exe")
                        and "\\.venv\\scripts\\python.exe" not in sample.executable_path.lower()
                    ],
                    "tracked_pids": [asdict(s) for s in process_samples],
                    "process_tree_private_bytes": private_total,
                    "process_tree_working_set_bytes": working_total,
                    "peak_process_tree_private_bytes": peak_private,
                    "peak_process_tree_working_set_bytes": peak_working_set,
                    "peak_single_process_private_bytes": peak_single_private,
                    "peak_single_process_working_set_bytes": peak_single_working_set,
                    "cpu_percent_total_machine": cpu_percent,
                    **asdict(system), "commit_utilization": system.commit_ratio,
                    "paging_streak": paging_streak,
                })
                if stop:
                    _append_jsonl(stream, {
                        "event": "STOP", "reason": stop, "stop_reasons": breached_stops,
                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    })
                    _terminate_tree(root_pid)
                    last_completed = _last_completed_phase(progress_path)
                    if progress_path is not None:
                        with progress_path.open("a", encoding="utf-8") as progress_stream:
                            _append_jsonl(progress_stream, {
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "phase": "STOPPED_BY_MONITOR", "stop_reason": stop,
                                "last_completed_phase": last_completed,
                            })
                    _append_jsonl(stream, {"event": "LAST_COMPLETED_PHASE", "phase": last_completed})
                    break
                time.sleep(sample_seconds)
        except BaseException as exc:
            _append_jsonl(stream, {"event": "STOP", "reason": "MONITOR_EXCEPTION", "detail": repr(exc)})
            if child.poll() is None:
                _terminate_tree(root_pid)
            raise
        finally:
            if child.poll() is None:
                _terminate_tree(root_pid)
            child.wait(timeout=10)
            _append_jsonl(stream, {
                "event": "CHILD_EXIT", "return_code": child.returncode,
                "stop_reason": stop, "peak_process_tree_private_bytes": peak_private,
                "peak_process_tree_working_set_bytes": peak_working_set,
                "peak_single_process_private_bytes": peak_single_private,
                "peak_single_process_working_set_bytes": peak_single_working_set,
                "elapsed_seconds": time.monotonic() - started,
            })
    return child.returncode if stop is None else 124


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--preflight-seconds", type=int, default=PREFLIGHT_SECONDS)
    parser.add_argument("--sample-seconds", type=float, default=SAMPLE_SECONDS)
    args = parser.parse_args(argv)
    run_dir = PROJECT_ROOT / "data" / "processed" / "modeling_experiments" / "f1_improvement" / args.run_id
    protected = (run_dir / "xgboost_pilot.joblib", run_dir / "pilot_result.json")
    if run_dir.exists() or any(path.exists() for path in protected):
        raise FileExistsError(f"Refusing to reuse existing pilot directory/artifacts: {run_dir}")
    run_dir.mkdir(parents=True)
    log_path = run_dir / f"resource-monitor-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
    command = [
        str(PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"),
        "-u", "-m", "src.models.experiments.f1_pilot",
    ]
    if not Path(command[0]).is_file():
        raise FileNotFoundError(f"Verified venv interpreter missing: {command[0]}")
    os.environ["F1_PILOT_RUN_ID"] = args.run_id
    return run_monitored(
        command, log_path, preflight_seconds=args.preflight_seconds,
        sample_seconds=args.sample_seconds, progress_path=run_dir / "pilot-progress.jsonl",
    )


def _last_completed_phase(progress_path: Path | None) -> str:
    if progress_path is None or not progress_path.is_file():
        return "START_NOT_REACHED"
    completed_phases = {"START", "DATA_LOADED", "PREPROCESSING_COMPLETE", "FIT_COMPLETE", "ARTIFACT_SAVED"}
    last_completed = "START_NOT_REACHED"
    try:
        for line in progress_path.read_text(encoding="utf-8").splitlines():
            phase = json.loads(line).get("phase")
            if phase in completed_phases:
                last_completed = phase
    except (OSError, json.JSONDecodeError):
        return last_completed
    return last_completed


if __name__ == "__main__":
    raise SystemExit(main())
