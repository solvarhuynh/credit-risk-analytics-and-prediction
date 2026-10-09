from __future__ import annotations

import hashlib
from pathlib import Path

from src.config import (
    LOGISTIC_6INPUT_DEMO_MANIFEST_PATH,
    LOGISTIC_6INPUT_DEMO_PATH,
    LOGISTIC_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
    MODELING_DIR,
    XGBOOST_6INPUT_DEMO_MANIFEST_PATH,
    XGBOOST_6INPUT_DEMO_PATH,
    XGBOOST_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH,
)


ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "apps" / "individual_prediction_dash"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_bundled_runtime_modules_match_canonical_source() -> None:
    """Render-only src package stays byte-identical to canonical runtime code."""
    modules = (
        "__init__.py",
        "config.py",
        "data/__init__.py",
        "data/column_policy.py",
        "models/__init__.py",
        "models/cost_optimization.py",
        "models/demo_5input.py",
        "models/demo_6input.py",
        "models/modeling_pipeline.py",
        "models/preprocess_pipeline.py",
        "models/risk_index.py",
        "models/scoring.py",
    )
    for relative in modules:
        assert (APP / "src" / relative).read_bytes() == (ROOT / "src" / relative).read_bytes()


def test_bundled_runtime_artifacts_match_canonical_artifacts() -> None:
    """Only required six-input models, validation references and IDs are bundled."""
    names = (
        XGBOOST_6INPUT_DEMO_PATH.name,
        XGBOOST_6INPUT_DEMO_MANIFEST_PATH.name,
        XGBOOST_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH.name,
        LOGISTIC_6INPUT_DEMO_PATH.name,
        LOGISTIC_6INPUT_DEMO_MANIFEST_PATH.name,
        LOGISTIC_6INPUT_DEMO_VALIDATION_PREDICTIONS_PATH.name,
        "validation_ids.parquet",
    )
    bundle = APP / "data" / "processed" / "modeling"
    for name in names:
        original = MODELING_DIR / name
        deployed = bundle / name
        assert original.is_file()
        assert deployed.is_file()
        assert _sha256(deployed) == _sha256(original)


def test_render_configuration_has_no_secret_environment_files() -> None:
    """Do not bake local credentials into the deploy bundle."""
    assert not (APP / ".env").exists()
    assert not (APP / ".env.production").exists()
