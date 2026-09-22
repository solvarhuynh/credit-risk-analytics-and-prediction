# TV1 — Modeling setup & run guide

Owner: TV1 (Modeling & Machine Learning)

## Trạng thái hiện tại

TV1-MASTER đã hoàn thành một run gated trên canonical snapshot SHA-256
`6460999371297ff2f83418a8341b0c85d4a2e4dc6c29b29e793edd2a0c755c96`.
Model locked là `xgboost_depth6`, với frozen-test ROC-AUC `0.780060`, PR-AUC
`0.270385`, Precision `0.272622`, Recall `0.426586`, F1 `0.332653` tại
threshold kỹ thuật `0.16`. Chi tiết đầy đủ nằm trong `reports/model_card.md`.

## Chuẩn bị môi trường

Từ thư mục repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Input canonical bắt buộc

TV1 chỉ bắt đầu preprocessing/split sau khi TV2 bàn giao:

- `data/processed/cleaned_dataset.parquet`
- `data/processed/data_dictionary.csv`
- quality report chứng minh `SK_ID_CURR`, `TARGET`, missing/sentinel và leakage checks.

Script tự kiểm tra fingerprint, dictionary, manifest, khóa/nhãn, infinity và
chặn nếu frozen test của cùng snapshot/split đã được dùng. Không sửa raw data,
không dùng `application_test.csv`, và không dùng frozen test để chọn model hoặc
threshold.

## Lệnh modeling canonical

Từ repository root, chỉ dùng để tạo một modeling run mới trên snapshot chưa từng
được đánh giá frozen-test trong output namespace hiện hành:

```powershell
& .\.venv\Scripts\python.exe -m src.models.modeling_pipeline
```

Sau khi run hoàn tất, chỉ kiểm tra artifact mà không train/evaluate lại frozen test:

```powershell
& .\.venv\Scripts\python.exe -m src.models.modeling_pipeline --verify-only
```

Nếu canonical dataset đổi hoặc muốn thực hiện experiment mới, phải tạo run/output
namespace mới và ghi fingerprint/split mới trước khi chạy lại. Không xóa hay ghi đè
control record frozen-test để lặp evaluation.

## Output và consumer

- `models/full_inference_pipeline.joblib` — pipeline inference cuối, ignored; TV3/
  service consumer dùng `predict_proba` trên đúng 201 feature, không truyền
  `TARGET` hoặc `SK_ID_CURR` vào model.
- `data/processed/scored_dataset.parquet` — 1:1 với canonical dataset, gồm
  `SK_ID_CURR`, `TARGET`, `PREDICTED_PD`, `DECISION_THRESHOLD`,
  `RECOMMENDATION`, `MODEL_VERSION`, `CREDIT_SCORE`, `RISK_TIER`,
  `EXPECTED_LOSS`; ignored.
- `reports/model_card.md` — evidence về dataset/split/CV/frozen test, threshold,
  limits và giả định scoring/EL; consumer là TV1, TV2 fairness review và TV3.
- `reports/frozen_test_evaluation_record.json` — record versioned của frozen-test
  một lần, gồm split hashes, metrics và hashes của đúng artifact/model score đã
  xuất; TV1/handoff validation dùng để chặn đánh giá lặp hoặc artifact lệch.
- `reports/model_integration_profiles.csv` — hai profile ẩn danh với output Python
  kỳ vọng để TV3 đối chiếu Power Query/What-if integration.
- `reports/figures/modeling/` — ROC, PR và SHAP explanations. Không commit model/
  data lớn; theo workflow nhóm chỉ stage file report/source đã được review.

`CREDIT_SCORE`, `RISK_TIER` và `EXPECTED_LOSS` dùng giả định kỹ thuật đã nêu trong
model card, không phải business lending policy, realized loss hay profit.

## Validation bắt buộc

Chạy regression test suite cho các reusable modeling modules:

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\models -q
& .\.venv\Scripts\python.exe -m src.models.modeling_pipeline --verify-only
git diff --check
git status --short
```

Preprocessor (median imputation + scale cho Logistic; imputation + OneHotEncoder
cho categorical) nằm trong từng CV/model pipeline. SMOTE không được dùng cho run
này vì sparse one-hot categorical và class-weight comparison đã được kiểm soát;
không được áp dụng SMOTE lên full data hoặc validation/test.

## Giới hạn quan trọng

- Threshold `0.16` tối ưu F1 trên development out-of-fold probabilities, không tối
  ưu business cost và không được đổi sau frozen test.
- LGD 45% và `AMT_CREDIT` làm EAD proxy chỉ là scenario minh bạch.
- SHAP/feature importance mô tả đóng góp cho dự báo, không chứng minh nhân quả.
