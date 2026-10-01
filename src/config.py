"""Cấu hình đường dẫn chuẩn cho bộ dữ liệu Lending Club 2007–2018."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

ACCEPTED_RAW_PATH = RAW_DIR / "accepted_loans.csv"
REJECTED_RAW_PATH = RAW_DIR / "rejected_loans.csv"
CANONICAL_DATASET_PATH = PROCESSED_DIR / "cleaned_dataset.parquet"
DATA_DICTIONARY_PATH = PROCESSED_DIR / "data_dictionary.csv"
DATASET_MANIFEST_PATH = PROCESSED_DIR / "cleaned_dataset_manifest.json"

DATASET_ID = "lending_club_2007_2018"
ID_COLUMN = "loan_id"
TARGET_COLUMN = "target"
