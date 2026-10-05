# ML-LC-04 — Imbalance Experiment

## Why this experiment exists

Target `default` không cân bằng (xấp xỉ 80/20) và baseline ở threshold
tham chiếu 0.5 có recall thấp. Stage này kiểm tra riêng liệu
`class_weight='balanced'` có thay đổi khả năng phát hiện default trên
**validation** hay không.

## Controlled experiment

- Baseline: ML-LC-03 Logistic Regression với `class_weight=None`.
- Weighted: Logistic Regression với `class_weight='balanced'`.
- Giữ nguyên train/validation membership, feature list, preprocessing,
  solver, penalty, `max_iter` và `random_state`.
- Không SMOTE, resampling, threshold search, XGBoost hoặc model selection
  bằng frozen test.

## Data

- Train: **807,210** dòng
- Validation: **269,070** dòng
- Frozen test: **269,070** dòng, sealed; không train,
  predict hoặc tính metric.
- Approved features: **106**
- Actual baseline/weighted input features: **103**
- Transformed features: **151**, sparse output:
  **True**

## Results

Reference threshold = **0.5**; đây không phải
threshold cuối và chưa có threshold nào được chọn.

| Metric | Baseline | Weighted | Difference (Weighted - Baseline) |
|---|---:|---:|---:|
| roc_auc | 0.714887 | 0.715097 | +0.000210 |
| pr_auc | 0.385307 | 0.384014 | -0.001292 |
| precision | 0.562454 | 0.322134 | -0.240319 |
| recall | 0.084494 | 0.655398 | +0.570905 |
| f1 | 0.146917 | 0.431958 | +0.285041 |
| accuracy | 0.804096 | 0.655852 | -0.148244 |

## Confusion matrix comparison

| Cell | Baseline | Weighted | Difference |
|---|---:|---:|---:|
| TN | 211819 | 141262 | -70557 |
| FP | 3531 | 74088 | +70557 |
| FN | 49181 | 18512 | -30669 |
| TP | 4539 | 35208 | +30669 |

Baseline matrix `[ [TN, FP], [FN, TP] ]`:
`[[211819, 3531], [49181, 4539]]`

Weighted matrix `[ [TN, FP], [FN, TP] ]`:
`[[141262, 74088], [18512, 35208]]`

## Weighted model

- Solver: `lbfgs`
- Penalty: `l2`
- `max_iter`: **1000**
- `class_weight`: **balanced**
- `random_state`: **42**
- Convergence: **True**, `n_iter=[74]`
- Preprocessing fit: **train only**

Weighted validation predictions:
`D:\ttdltq\data\processed\modeling\ml_lc_04_weighted_validation_predictions.parquet`

Weighted model artifact:
`D:\ttdltq\data\processed\modeling\logistic_weighted.joblib`

## Interpretation

Recall tăng +0.570905 trên validation. False negatives thay đổi -30669; false positives thay đổi +70557. Precision thay đổi -0.240319; F1 thay đổi +0.285041. ROC-AUC thay đổi +0.000210; PR-AUC thay đổi -0.001292. Trade-off quan sát được là weighted model nhạy hơn với default nhưng tạo thêm cảnh báo false positive.

Đây là trade-off quan sát được trên validation, không phải kết luận nhân quả.

## Decision

ML-LC-04 chỉ là experiment. Chưa tuyên bố weighted model là final model.
ML-LC-06 mới thực hiện candidate selection theo tiêu chí được khóa trước.

## Leakage and frozen-test safeguards

- Feature schema tiếp tục lấy từ ML-LC-01; không thêm feature mới.
- Raw date fields vẫn không được one-hot trực tiếp.
- `frozen_test_used_for_training = false`.
- `frozen_test_used_for_evaluation = false`.
- `frozen_test_used_for_selection = false`.
- `threshold_selected = false`.

## Limitations

- Threshold 0.5 chỉ là reference.
- Chưa threshold optimization, resampling, XGBoost, frozen-test evaluation,
  explainability hoặc scoring/risk tier.
- Kết quả validation không tự quyết định model cuối.
