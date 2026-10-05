"""Cấu hình đường dẫn chuẩn cho bộ dữ liệu Lending Club 2007–2018."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MODELING_DIR = PROCESSED_DIR / "modeling"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

ACCEPTED_RAW_PATH = RAW_DIR / "accepted_loans.csv"
REJECTED_RAW_PATH = RAW_DIR / "rejected_loans.csv"
CANONICAL_DATASET_PATH = PROCESSED_DIR / "cleaned_dataset.parquet"
DATA_DICTIONARY_PATH = PROCESSED_DIR / "data_dictionary.csv"
DATASET_MANIFEST_PATH = PROCESSED_DIR / "cleaned_dataset_manifest.json"
LOGISTIC_BASELINE_PATH = MODELING_DIR / "logistic_baseline.joblib"
ML_LC_03_VALIDATION_PREDICTIONS_PATH = MODELING_DIR / "ml_lc_03_validation_predictions.parquet"
ML_LC_03_MANIFEST_PATH = MODELING_DIR / "ml_lc_03_manifest.json"
ML_LC_03_FEATURE_AUDIT_PATH = MODELING_DIR / "ml_lc_03_feature_audit.csv"
LOGISTIC_WEIGHTED_PATH = MODELING_DIR / "logistic_weighted.joblib"
ML_LC_04_VALIDATION_PREDICTIONS_PATH = MODELING_DIR / "ml_lc_04_weighted_validation_predictions.parquet"
ML_LC_04_MANIFEST_PATH = MODELING_DIR / "ml_lc_04_manifest.json"

DATASET_ID = "lending_club_2007_2018"
ID_COLUMN = "loan_id"
TARGET_COLUMN = "target"
