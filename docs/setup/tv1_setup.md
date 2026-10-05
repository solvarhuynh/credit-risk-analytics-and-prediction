# Thiết lập TV1 — Lending Club Modeling

Trạng thái: **ML-LC-03 PASS / ML-LC-04 PASS / ML-LC-05 NOT STARTED**. Canonical handoff TV2 và frozen split ML-LC-02 đã được kiểm tra.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Ý nghĩa: tạo môi trường Python độc lập, kích hoạt và cài dependency.

```powershell
Get-Item data/processed/cleaned_dataset.parquet,data/processed/data_dictionary.csv,data/processed/cleaned_dataset_manifest.json
```

Ý nghĩa: xác nhận đủ ba artifact TV2. Nếu thiếu thì dừng, không train.

```powershell
python -c "from src.models.modeling_pipeline import load_canonical_input,build_feature_schema; d,dd,m=load_canonical_input(); print(build_feature_schema(d,dd)); print(m)"
```

Ý nghĩa: chạy model input gate, kiểm tra dictionary coverage và chỉ chọn feature `APPLICATION_TIME`/`CREDIT_SNAPSHOT`.

```powershell
.venv\Scripts\python.exe -m pytest tests/models -q
```

Ý nghĩa: chạy focused/regression tests cho split, preprocessing, modeling, evaluation và runner. Kết quả hiện tại: **59 passed**.

## ML-LC-03 — Logistic Regression baseline

Prerequisite: ba artifact TV2 (`cleaned_dataset.parquet`, `data_dictionary.csv`, `cleaned_dataset_manifest.json`) phải đạt PASS; frozen split ML-LC-02 phải tồn tại và đạt PASS.

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-03
```

Ý nghĩa: kiểm tra các gate đầu vào, lấy đúng train/validation từ frozen split, fit preprocessing và Logistic Regression chỉ trên train, đánh giá chỉ trên validation, rồi ghi baseline artifacts/report. Frozen test chỉ được kiểm tra membership, không tạo prediction/metric.

Input chính:

- `data/processed/cleaned_dataset.parquet`
- `data/processed/data_dictionary.csv`
- `data/processed/cleaned_dataset_manifest.json`
- `data/processed/modeling/{train_ids,validation_ids,test_ids}.parquet`
- `data/processed/modeling/split_manifest.json`

Output chính:

- `data/processed/modeling/logistic_baseline.joblib`
- `data/processed/modeling/ml_lc_03_validation_predictions.parquet`
- `data/processed/modeling/ml_lc_03_feature_audit.csv`
- `data/processed/modeling/ml_lc_03_manifest.json`
- `reports/tv1_stages/ml-lc-03.md`
- `reports/tv1_stages/state/ml-lc-03.json`

Validation bổ sung đã chạy:

```powershell
.venv\Scripts\python.exe -m pytest tests/data tests/features -q
.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

Kết quả: `75 passed, 4 warnings` ở data/features; compileall PASS; diff check PASS. Warning là cảnh báo date parsing đã tồn tại ở test TV2, không làm test fail.

Giới hạn ML-LC-03: đây là untreated Logistic baseline với `class_weight=None`; chưa threshold optimization, chưa XGBoost, chưa explainability/scoring và chưa đánh giá frozen test. Threshold `0.5` chỉ là reference; ML-LC-07 mới chọn threshold cuối.

## ML-LC-04 — Logistic Regression imbalance experiment

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-04
```

Ý nghĩa: xác nhận ML-LC-03 PASS, giữ nguyên frozen train/validation và 103 feature thực tế, fit một Logistic Regression thứ hai với `class_weight="balanced"` chỉ trên train, rồi so sánh với baseline tại threshold tham chiếu `0.5` trên validation. Không chạy threshold search, không dùng frozen test để predict/metric/selection và không dùng resampling.

Output chính:

- `data/processed/modeling/logistic_weighted.joblib`
- `data/processed/modeling/ml_lc_04_weighted_validation_predictions.parquet`
- `data/processed/modeling/ml_lc_04_manifest.json`
- `reports/tv1_stages/ml-lc-04.md`
- `reports/tv1_stages/state/ml-lc-04.json`

Kết quả đã kiểm tra: weighted Logistic hội tụ; recall validation tăng nhưng false positives tăng mạnh và precision giảm. Đây là experiment, chưa khóa model cuối; ML-LC-06 mới thực hiện candidate selection.

Workflow tiếp theo: ML-LC-05 optional XGBoost → ML-LC-06 chọn candidate → ML-LC-07 chọn threshold → frozen test một lần → explainability/scoring/expected loss → full-data refit → TV3 handoff. Không được dùng lại frozen test trước stage đánh giá cuối.

## Phạm vi trách nhiệm sau reorganize

TV1 là primary owner của modeling, V01–V06, Storytelling, report coordination và defense coordination. TV1 cross-review TV2 handoff/V07–V09 và TV3 dashboard structure. TV1 không tích hợp Master PBIX; TV3 giữ integration ownership.
