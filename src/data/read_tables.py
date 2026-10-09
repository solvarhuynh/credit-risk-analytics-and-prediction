"""Tạo file CSV mẫu từ các bảng CSV/Parquet trong thư mục data.

Chạy từ thư mục gốc dự án:
    python -m src.data.read_tables
    python -m src.data.read_tables --rows 100 --output-dir data/sample_100_rows

Cũng có thể chạy trực tiếp file bằng nút Run Python File của VS Code.

Mặc định xuất mỗi bảng thành một CSV trong data/sample_100_rows,
gồm tối đa 100 dòng dữ liệu đầu tiên và một dòng tiêu đề.
Chạy lại sẽ cập nhật các CSV mẫu, không lấy bảng mẫu làm đầu vào.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

# Khi chạy trực tiếp, Python chỉ thêm src/data vào đường dẫn import.
# Thêm thư mục gốc để các import package src hoạt động như chế độ -m.
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.config import DATA_DIR
from src.data.load_data import load_csv

DEFAULT_OUTPUT_DIR = DATA_DIR / "sample_100_rows"


def list_tables(data_dir: str | Path = DATA_DIR) -> list[Path]:
    """Liệt kê các bảng, bao gồm bảng trong thư mục con."""
    directory = Path(data_dir)
    if not directory.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục dữ liệu: {directory}")
    return sorted(
        path for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in {".csv", ".parquet"}
    )


def read_table(
    table: str | Path,
    *,
    data_dir: str | Path = DATA_DIR,
    columns: list[str] | None = None,
    nrows: int | None = None,
) -> pd.DataFrame:
    """Đọc đường dẫn tuyệt đối hoặc đường dẫn tương đối tính từ data_dir.

    ``nrows=None`` đọc toàn bộ bảng; đặt nrows để giới hạn bộ nhớ.
    ``columns`` chỉ đọc những cột cần dùng. Giữ kiểu chuỗi ID/ZIP
    của hai bảng raw theo loader hiện có của dự án.
    """
    if nrows is not None and nrows < 0:
        raise ValueError("nrows phải >= 0 hoặc None.")
    path = Path(table)
    if not path.is_absolute():
        path = Path(data_dir) / path
    if not path.is_file():
        raise FileNotFoundError(f"Không tìm thấy bảng: {path}")

    if path.suffix.lower() == ".csv":
        raw_source = {
            "accepted_loans.csv": "accepted",
            "rejected_loans.csv": "rejected",
        }.get(path.name)
        if raw_source:
            return load_csv(
                raw_source, raw_dir=path.parent, usecols=columns, nrows=nrows,
            )
        return pd.read_csv(path, usecols=columns, nrows=nrows, low_memory=False)
    if path.suffix.lower() == ".parquet":
        if nrows is None:
            return pd.read_parquet(path, columns=columns)
        # Đọc batch đầu tiên, tránh nạp toàn bộ bảng chỉ để gọi head().
        with pq.ParquetFile(path) as parquet:
            if columns is not None:
                missing = sorted(set(columns) - set(parquet.schema_arrow.names))
                if missing:
                    raise ValueError(f"Cột không tồn tại: {missing}")
            schema = parquet.schema_arrow.empty_table()
            if columns is not None:
                schema = schema.select(columns)
            if nrows == 0:
                return schema.to_pandas()
            batch = next(
                parquet.iter_batches(batch_size=nrows, columns=columns), None,
            )
            return schema.to_pandas() if batch is None else batch.to_pandas()
    raise ValueError(f"Định dạng không hỗ trợ: {path.suffix}; dùng CSV hoặc Parquet.")


def export_tables(
    *,
    data_dir: str | Path = DATA_DIR,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    nrows: int = 100,
) -> list[Path]:
    """Xuất mỗi bảng sang CSV UTF-8 có BOM để mở tiếng Việt trong Excel."""
    if nrows < 0:
        raise ValueError("nrows phải >= 0.")
    directory = Path(data_dir).resolve()
    destination = Path(output_dir).resolve()
    if destination == directory:
        raise ValueError("Thư mục xuất phải khác thư mục dữ liệu đầu vào.")
    excluded = {destination, (directory / "sample_100_rows").resolve()}
    sources = [
        path for path in list_tables(directory)
        if not any(folder in path.resolve().parents for folder in excluded)
    ]
    targets = [destination / f"{source.stem}.csv" for source in sources]
    if len(targets) != len(set(targets)):
        raise ValueError("Có các bảng trùng tên; hãy dùng thư mục đầu vào riêng.")
    source_paths = {source.resolve() for source in sources}
    if any(target.resolve() in source_paths for target in targets):
        raise ValueError("Đường dẫn xuất trùng bảng nguồn; hãy chọn thư mục mới.")
    destination.mkdir(parents=True, exist_ok=True)
    for source, target in zip(sources, targets):
        frame = read_table(source, nrows=nrows)
        frame.to_csv(target, index=False, encoding="utf-8-sig")
        print(f"{target.name}: {len(frame):,} dòng dữ liệu, {len(frame.columns)} cột")
    print(f"Đã xuất {len(targets)} file CSV vào {destination}")
    return targets


def main() -> None:
    # Terminal Windows có thể mặc định dùng bảng mã không hỗ trợ tiếng Việt.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output-dir", type=Path, help="Thư mục xuất (mặc định: <data-dir>/sample_100_rows)")
    parser.add_argument("--rows", type=int, default=100, help="Số dòng tối đa mỗi file (mặc định: 100)")
    args = parser.parse_args()
    if args.rows < 0:
        parser.error("--rows phải >= 0")
    try:
        export_tables(
            data_dir=args.data_dir,
            output_dir=args.output_dir if args.output_dir is not None else args.data_dir / "sample_100_rows",
            nrows=args.rows,
        )
    except (FileNotFoundError, ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Lỗi xuất CSV: {exc}\n")


if __name__ == "__main__":
    main()
