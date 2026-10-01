"""Loader có giới hạn bộ nhớ cho hai nguồn raw Lending Club."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from src.config import ACCEPTED_RAW_PATH, REJECTED_RAW_PATH

RAW_PATHS = {"accepted": ACCEPTED_RAW_PATH, "rejected": REJECTED_RAW_PATH}


def validate_raw_files(raw_dir: str | Path | None = None) -> dict[str, Path]:
    directory = Path(raw_dir) if raw_dir is not None else ACCEPTED_RAW_PATH.parent
    paths = {
        "accepted": directory / ACCEPTED_RAW_PATH.name,
        "rejected": directory / REJECTED_RAW_PATH.name,
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Thiếu raw Lending Club: {', '.join(missing)}")
    return paths


def load_csv(
    source: str,
    *,
    raw_dir: str | Path | None = None,
    usecols: list[str] | None = None,
    dtype: dict[str, str] | None = None,
    chunksize: int | None = None,
    nrows: int | None = None,
    **kwargs: Any,
) -> pd.DataFrame | Iterator[pd.DataFrame]:
    """Đọc một nguồn; hỗ trợ ``usecols``, ``dtype`` và iterator theo chunk."""

    if source not in RAW_PATHS:
        raise ValueError("source phải là 'accepted' hoặc 'rejected'.")
    path = validate_raw_files(raw_dir)[source]
    defaults: dict[str, Any] = {"low_memory": False}
    defaults["dtype"] = (
        {"id": "string", "zip_code": "string"}
        if source == "accepted"
        else {"Zip Code": "string"}
    )
    if dtype:
        defaults["dtype"] = {**defaults["dtype"], **dtype}
    return pd.read_csv(
        path,
        usecols=usecols,
        chunksize=chunksize,
        nrows=nrows,
        **defaults,
        **kwargs,
    )


def load_accepted_loans(**kwargs: Any) -> pd.DataFrame | Iterator[pd.DataFrame]:
    return load_csv("accepted", **kwargs)


def load_rejected_loans(**kwargs: Any) -> pd.DataFrame | Iterator[pd.DataFrame]:
    return load_csv("rejected", **kwargs)


def inspect_raw_schema(raw_dir: str | Path | None = None, sample_rows: int = 5) -> dict[str, Any]:
    """Đọc header và mẫu nhỏ, tuyệt đối không nạp toàn bộ raw."""

    result: dict[str, Any] = {}
    for source, path in validate_raw_files(raw_dir).items():
        frame = pd.read_csv(path, nrows=sample_rows, low_memory=False)
        result[source] = {
            "path": str(path),
            "size_bytes": path.stat().st_size,
            "column_count": len(frame.columns),
            "columns": frame.columns.tolist(),
            "sample_rows_read": len(frame),
        }
    return result
