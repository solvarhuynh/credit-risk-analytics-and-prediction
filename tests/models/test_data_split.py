import pandas as pd

from src.models.data_split import create_development_split


def test_split_is_deterministic_and_excludes_id_target() -> None:
    frame = pd.DataFrame({"loan_id": [str(i) for i in range(100)], "target": [0, 1] * 50, "dti": list(range(100))})
    first = create_development_split(frame)
    second = create_development_split(frame)
    assert first.train.ids.tolist() == second.train.ids.tolist()
    assert "loan_id" not in first.train.X
    assert "target" not in first.train.X
    assert len(first.train.X) + len(first.validation.X) + len(first.test.X) == len(frame)
