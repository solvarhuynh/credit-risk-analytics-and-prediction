"""Focused tests for the F1 pilot process and resource monitor."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from src.models.experiments import f1_pilot, f1_pilot_monitor as monitor


def _healthy_system() -> monitor.SystemSample:
    return monitor.SystemSample(
        available_bytes=12 * 1024**3,
        committed_bytes=35 * 1024**3,
        commit_limit_bytes=46 * 1024**3,
        pages_input_per_sec=0.0,
        page_reads_per_sec=0.0,
        pages_output_per_sec=0.0,
        page_writes_per_sec=0.0,
    )


def test_stop_rules_keep_required_limits() -> None:
    healthy = _healthy_system()
    assert monitor.stop_reason(healthy, 0, 0) is None
    assert monitor.stop_reason(
        monitor.SystemSample(4 * 1024**3, 30, 46, 0, 0, 0, 0), 0, 0
    ) == "STOP_AVAILABLE_RAM_BELOW_5_GIB"
    assert monitor.stop_reason(
        monitor.SystemSample(9 * 1024**3, 44, 46, 0, 0, 0, 0), 0, 0
    ) == "STOP_SYSTEM_COMMIT_AT_OR_ABOVE_95_PERCENT"
    assert monitor.stop_reason(healthy, 17 * 1024**3, 0) == "STOP_PROCESS_TREE_PRIVATE_COMMIT_ABOVE_16_GIB"
    assert monitor.stop_reason(healthy, 0, 5) == "STOP_SUSTAINED_SEVERE_PAGING"


def test_preflight_requires_full_sustained_safe_window() -> None:
    assert not monitor.preflight_passes([_healthy_system()] * 10)
    assert monitor.preflight_passes([_healthy_system()] * 60)
    unsafe = monitor.SystemSample(12 * 1024**3, 40 * 1024**3, 46 * 1024**3, 0, 0, 0, 0)
    assert not monitor.preflight_passes([_healthy_system()] * 59 + [unsafe])


def test_preflight_fails_closed_when_paging_counters_are_missing() -> None:
    missing_paging = monitor.SystemSample(
        available_bytes=12 * 1024**3,
        committed_bytes=35 * 1024**3,
        commit_limit_bytes=46 * 1024**3,
        pages_input_per_sec=None,
        page_reads_per_sec=None,
        pages_output_per_sec=None,
        page_writes_per_sec=None,
    )
    assert not monitor.preflight_passes([missing_paging] * 60)


def test_checkpoint_writes_and_flushes_jsonl(tmp_path: Path) -> None:
    progress = tmp_path / "pilot-progress.jsonl"
    for phase in (
        "START", "LOADING_DATA", "DATA_LOADED", "PREPROCESSING",
        "PREPROCESSING_COMPLETE", "FIT_START", "FIT_COMPLETE", "ARTIFACT_SAVED",
    ):
        f1_pilot.write_checkpoint(progress, phase)
    records = [json.loads(line) for line in progress.read_text(encoding="utf-8").splitlines()]
    assert [record["phase"] for record in records] == [
        "START", "LOADING_DATA", "DATA_LOADED", "PREPROCESSING",
        "PREPROCESSING_COMPLETE", "FIT_START", "FIT_COMPLETE", "ARTIFACT_SAVED",
    ]
    assert all(record["timestamp_utc"] for record in records)


def test_preflight_failure_never_launches_command(tmp_path: Path) -> None:
    marker = tmp_path / "should-not-run"
    log_path = tmp_path / "monitor.jsonl"
    progress_path = tmp_path / "pilot-progress.jsonl"
    unsafe = monitor.SystemSample(4 * 1024**3, 45 * 1024**3, 46 * 1024**3, 0, 0, 0, 0)
    code = monitor.run_monitored(
        [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
        log_path,
        preflight_seconds=0.1,
        sample_seconds=0.1,
        system_sampler=lambda: unsafe,
        preflight_max_commit_ratio=0.85,
        preflight_min_available_bytes=7 * 1024**3,
        progress_path=progress_path,
    )
    assert code == 2
    assert not marker.exists()
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    assert records[-1]["event"] == "STOP"
    assert records[-1]["reason"] == "STOP_AVAILABLE_RAM_BELOW_5_GIB"
    assert records[-1]["stop_reasons"] == [
        "STOP_AVAILABLE_RAM_BELOW_5_GIB",
        "STOP_SYSTEM_COMMIT_AT_OR_ABOVE_95_PERCENT",
    ]
    progress = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines()]
    assert progress[-1]["phase"] == "STOPPED_AT_PREFLIGHT"
    assert progress[-1]["last_completed_phase"] == "START_NOT_REACHED"
    assert progress[-1]["stop_reason"] == "STOP_AVAILABLE_RAM_BELOW_5_GIB"


@pytest.mark.skipif(os.name != "nt", reason="Windows process-tree API validation")
def test_tracks_and_terminates_synthetic_child_tree(tmp_path: Path) -> None:
    child_pid_file = tmp_path / "grandchild.pid"
    log_path = tmp_path / "monitor.jsonl"
    progress_path = tmp_path / "pilot-progress.jsonl"
    script = (
        "import subprocess,sys,time,pathlib; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
        f"pathlib.Path({str(child_pid_file)!r}).write_text(str(p.pid)); "
        "block=bytearray(16*1024*1024); "
        "[(block.__setitem__(i,1)) for i in range(0,len(block),4096)]; time.sleep(60)"
    )
    calls = 0

    def sampled_system() -> monitor.SystemSample:
        nonlocal calls
        calls += 1
        if calls <= 5:
            return _healthy_system()
        return monitor.SystemSample(4 * 1024**3, 35 * 1024**3, 46 * 1024**3, 0, 0, 0, 0)

    result = monitor.run_monitored(
        [sys.executable, "-c", script], log_path,
        preflight_seconds=0.1, sample_seconds=0.1,
        system_sampler=sampled_system, progress_path=progress_path,
    )
    assert result == 124
    assert child_pid_file.exists()
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    samples = [record for record in records if record["event"] == "RESOURCE_SAMPLE"]
    assert samples
    assert any(len(record["tracked_pids"]) >= 2 for record in samples)
    assert records[-1]["event"] == "CHILD_EXIT"
    assert records[-1]["peak_process_tree_private_bytes"] > 0
    progress = [json.loads(line) for line in progress_path.read_text(encoding="utf-8").splitlines()]
    assert progress[-1]["phase"] == "STOPPED_BY_MONITOR"
    assert progress[-1]["last_completed_phase"] == "START_NOT_REACHED"
    tracked = {pid for record in samples for pid in (item["pid"] for item in record["tracked_pids"])}
    tracked.add(int(child_pid_file.read_text(encoding="utf-8")))
    table = monitor._process_table()
    assert not tracked.intersection(table)


def test_run_id_guard_does_not_overwrite_existing_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_dir = tmp_path / "data" / "processed" / "modeling_experiments" / "f1_improvement" / "protected-run"
    run_dir.mkdir(parents=True)
    artifact = run_dir / "xgboost_pilot.joblib"
    artifact.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(monitor, "PROJECT_ROOT", tmp_path)
    with pytest.raises(FileExistsError):
        monitor.main(["--run-id", "protected-run"])
    assert artifact.read_text(encoding="utf-8") == "keep"
