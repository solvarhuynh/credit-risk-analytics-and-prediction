"""Contract suy luận cho TV3; không giả lập dự đoán khi chưa có model."""

from __future__ import annotations

from pathlib import Path
from typing import Any

MODEL_REQUIRED_FIELDS = (
    "loan_id", "predicted_pd", "target", "state_code", "issue_year", "loan_amnt",
    "annual_inc", "fico_avg", "dti", "purpose", "risk_tier", "credit_score",
    "expected_loss", "recommendation",
)


def simulator_status(model_path: str | Path) -> dict[str, Any]:
    path = Path(model_path)
    if not path.is_file():
        return {
            "status": "BLOCKED / WAITING FOR TV1 ARTIFACT",
            "model_path": str(path),
            "required_output_fields": list(MODEL_REQUIRED_FIELDS),
        }
    return {
        "status": "READY FOR INTEGRATION VALIDATION",
        "model_path": str(path),
        "required_output_fields": list(MODEL_REQUIRED_FIELDS),
    }
