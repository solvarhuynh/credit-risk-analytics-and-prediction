# ML-LC-03 Logistic Regression Baseline

## Purpose

Huấn luyện baseline Logistic Regression bắt buộc trên train partition đã frozen,
đánh giá một lần trên validation và giữ frozen test chưa mở cho đánh giá.

## Data used

- Canonical source: `D:\ttdltq\data\processed\cleaned_dataset.parquet`
- Train: **807,210** dòng
- Validation: **269,070** dòng
- Frozen test: **269,070** dòng chỉ ghi metadata; không dùng để train/evaluate
- Train/validation không overlap; frozen test evaluation rows: **0**

## Features

- ML-LC-01 approved model-safe features: **106**
- Actual Logistic baseline input features: **103**
- Forbidden feature list: `[]`
- Feature audit: `D:\ttdltq\data\processed\modeling\ml_lc_03_feature_audit.csv`

Các cột model-safe nhưng không đưa trực tiếp vào baseline:

- `issue_d`: Raw issue date is not one-hot encoded; issue_year/issue_quarter/issue_month are the deterministic application-time representation.
- `earliest_cr_line`: Raw credit-history date is not one-hot encoded; credit_history_months is the deterministic numeric representation.
- `sec_app_earliest_cr_line`: Raw secondary-applicant date is not one-hot encoded because it is date-like and sparsely observed; no post-loan information is added.

## Preprocessing

- Numeric: median imputation + `StandardScaler`.
- Categorical: most-frequent imputation + `OneHotEncoder(handle_unknown='ignore')`.
- Date-like raw fields không one-hot trực tiếp; dùng feature engineered số đã có hoặc loại khỏi baseline theo audit.
- Toàn bộ preprocessing được fit qua pipeline trên **train only**; không fit validation/test.
- Transformed feature count: **151**; sparse output: **True**.

## Model

- Model: Logistic Regression
- Solver: `lbfgs`
- Penalty: `l2`
- `class_weight`: **None**
- `random_state`: **42**
- `max_iter`: **1000**
- Convergence: **True**
- Fit duration: **38.67 seconds**

## Validation results

Reference threshold = **0.5**. Đây chưa phải final threshold; ML-LC-07 mới được chọn threshold.

- ROC-AUC: **0.714887**
- PR-AUC / Average Precision: **0.385307**
- Precision: **0.562454**
- Recall: **0.084494**
- F1: **0.146917**
- Accuracy: **0.804096**
- Confusion matrix `[ [TN, FP], [FN, TP] ]`: `[[211819, 3531], [49181, 4539]]`

Validation predictions: `D:\ttdltq\data\processed\modeling\ml_lc_03_validation_predictions.parquet`

## Leakage safeguards

- Feature list lấy từ `build_feature_schema()` và shared column policy của ML-LC-01.
- Không dùng `loan_id`, `target`, `loan_status`, policy-derived, geography hoặc POST_LOAN fields.
- Không dùng frozen-test outcomes/probabilities.
- Không resampling, không `class_weight='balanced'`, không XGBoost và không threshold search.

## Limitations

- Đây chỉ là untreated Logistic Regression baseline, chưa phải model cuối.
- Chưa có imbalance treatment hoặc threshold optimization.
- Frozen test vẫn sealed cho các stage sau.
- Association/prediction không phải causal effect.
