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

Ý nghĩa các lệnh chuẩn bị:

- `python -m venv .venv`: tạo virtual environment riêng cho repository.
- `.\.venv\Scripts\Activate.ps1`: kích hoạt môi trường Python trên PowerShell.
- `pip install -r requirements.txt`: cài đúng các thư viện pipeline, modeling,
  giải thích mô hình và kiểm thử đã khóa trong repository.

## Input canonical bắt buộc

TV1 chỉ bắt đầu preprocessing/split sau khi TV2 bàn giao:

- `data/processed/cleaned_dataset.parquet`
- `data/processed/data_dictionary.csv`
- quality report chứng minh `SK_ID_CURR`, `TARGET`, missing/sentinel và leakage checks.

Script tự kiểm tra fingerprint, dictionary, manifest, khóa/nhãn, infinity và
chặn nếu frozen test của cùng snapshot/split đã được dùng. Không sửa raw data,
không dùng `application_test.csv`, và không dùng frozen test để chọn model hoặc
threshold.

## Quy trình chạy và ý nghĩa từng lệnh

Tất cả lệnh dưới đây chạy từ repository root và dùng Python trong `.venv` để
tránh chạy nhầm interpreter bên ngoài môi trường dự án.

### 1. Chạy gated modeling pipeline

```powershell
& .\.venv\Scripts\python.exe -m src.models.modeling_pipeline
```

Lệnh này thực hiện một modeling run đầy đủ:

1. Đọc và kiểm tra canonical dataset, manifest và data dictionary.
2. Kiểm tra fingerprint, khóa `SK_ID_CURR`, nhãn `TARGET`, infinity và ranh giới
   feature; loại `SK_ID_CURR`, `TARGET` cùng các cột output khỏi `X`.
3. Tạo development/frozen-test split phân tầng cố định theo seed trong pipeline.
4. Fit preprocessing và các candidate model chỉ trên development folds; so sánh
   bằng metric phát triển, không dùng frozen test để chọn model.
5. Khóa threshold từ development out-of-fold probabilities.
6. Đánh giá frozen test đúng một lần, tạo model card/biểu đồ, sau đó refit
   pipeline production trên toàn bộ labeled canonical dataset.
7. Xuất model inference, scored dataset và các hồ sơ tích hợp cho TV3.

Không chạy lại lệnh này trên cùng output namespace sau khi frozen-test record đã
tồn tại. Nếu cần experiment mới, phải tạo snapshot/namespace và control record
mới theo policy trong model card.

### 2. Chỉ xác minh artifact đã có

```powershell
& .\.venv\Scripts\python.exe -m src.models.modeling_pipeline --verify-only
```

Lệnh này chỉ load model/scored dataset hiện có và kiểm tra fingerprint, schema,
PD, threshold, recommendation, model version, tính deterministic và an toàn với
category chưa từng gặp. Lệnh **không train model** và **không đánh giá lại frozen
test**; dùng lệnh này cho kiểm tra sau checkout hoặc trước handoff.

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

### Kiểm thử modeling

```powershell
& .\.venv\Scripts\python.exe -m pytest tests\models -q
& .\.venv\Scripts\python.exe -m src.models.modeling_pipeline --verify-only
```

Ý nghĩa:

- `pytest tests\models -q`: chạy regression tests cho split, preprocessing,
  evaluation, scoring, expected loss và modeling pipeline; `-q` giữ output ngắn.
- `--verify-only`: kiểm tra artifact production mà không làm thay đổi model,
  scored dataset hoặc frozen-test record.

### Kiểm tra thay đổi trước commit

```powershell
git diff --check
git status --short
```

- `git diff --check`: phát hiện whitespace lỗi trong phần thay đổi.
- `git status --short`: xác nhận chỉ các file đúng scope được thay đổi và không
  vô tình stage dữ liệu, model lớn hoặc secret.

Kết quả validation đã xác nhận cho run hiện tại:

- Full test suite: **209 passed**.
- Model tests: **61 passed**.
- `--verify-only`: `SUCCESS`, `deterministic=true`,
  `unknown_category_safe=true`, 307,511 dòng được xác minh.

Preprocessor (median imputation + scale cho Logistic; imputation + OneHotEncoder
cho categorical) nằm trong từng CV/model pipeline. SMOTE không được dùng cho run
này vì sparse one-hot categorical và class-weight comparison đã được kiểm soát;
không được áp dụng SMOTE lên full data hoặc validation/test.

## Giới hạn quan trọng

- Threshold `0.16` tối ưu F1 trên development out-of-fold probabilities, không tối
  ưu business cost và không được đổi sau frozen test.
- LGD 45% và `AMT_CREDIT` làm EAD proxy chỉ là scenario minh bạch.
- SHAP/feature importance mô tả đóng góp cho dự báo, không chứng minh nhân quả.

## Trạng thái blocker

- Modeling pipeline TV1-MASTER: **đã hoàn tất và đã xác minh**.
- Canonical input: bắt buộc phải đúng fingerprint trong model card; không tự tạo
  dữ liệu thay thế khi thiếu hoặc lệch snapshot.
- Frozen-test: đã khóa; không được dùng để retune model hoặc threshold.
- Fairness/threshold analysis DE-08 của TV2: thuộc downstream, chưa nằm trong
  phạm vi lệnh modeling của TV1.
