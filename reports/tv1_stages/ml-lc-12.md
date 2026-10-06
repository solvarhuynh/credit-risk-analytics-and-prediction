# ML-LC-12 — Full-data Refit

## 1. Vì sao refit?

Candidate và operating threshold đã được chọn trước đó; frozen test đã cung cấp đánh giá không thiên lệch ở ML-LC-08. Bước này fit cấu hình đã khóa trên toàn bộ labeled canonical rows để tạo artifact demo/inference dùng nhiều dữ liệu hơn.

## 2. Model đã đánh giá và model refit

- **Evaluated model:** `D:\ttdltq\data\processed\modeling\xgboost_candidate.joblib`; chỉ model này gắn với metrics frozen-test ML-LC-08.
- **Full-data refit model:** `D:\ttdltq\data\processed\modeling\xgboost_full_refit.joblib`; được fit trên toàn bộ labeled canonical population. Đây là model khác, không có unbiased test score mới.
- ML-LC-08 test metrics không được tính lại hoặc gán cho full-data refit.

## 3. Cấu hình đã khóa

| Parameter | Value |
|---|---:|
| `n_estimators` | `200` |
| `max_depth` | `4` |
| `learning_rate` | `0.05` |
| `subsample` | `0.8` |
| `colsample_bytree` | `0.8` |
| `random_state` | `42` |
| `objective` | `binary:logistic` |
| `eval_metric` | `logloss` |
| `tree_method` | `hist` |
| `n_jobs` | `4` |

Approved features: 106; actual model inputs: 103; transformed inputs: 151.
Preprocessing được fit trên `full_labeled_canonical`; feature list giữ nguyên từ ML-LC-05.

## 4. Toàn bộ labeled data

Rows used: 1,345,350. Target 0 (non-default): 1,076,751; target 1 (default): 268,599.
Fit duration: 79.12 seconds.

## 5. Threshold carried forward

Threshold `0.22009515762329102` được chọn từ validation của evaluated candidate tại ML-LC-07. Không tìm hoặc tái xác nhận threshold trên full-data refit; score distribution của refit có thể khác.

## 6. Output scores

`D:\ttdltq\data\processed\modeling\ml_lc_12_full_refit_scores.parquet` có một hàng mỗi loan_id, PD, predicted class, risk score, project credit score, risk tier và context dashboard được duyệt.
Đây là **full-data refit scores / deployment-demo scoring output**, là dự đoán in-sample trên population đã dùng fit; không phải unbiased test predictions hay final evaluation predictions.

## 7. Giới hạn quan trọng

ML-LC-08 vẫn là nguồn duy nhất cho unbiased performance evidence: ROC-AUC 0.723186, PR-AUC 0.400000, precision 0.345877, recall 0.602960, F1 0.439590, accuracy 0.693065 trên frozen test của `xgboost_candidate`. Không diễn giải các chỉ số này như kết quả của refit.
Không chọn lại model, không đổi features/hyperparameters/threshold, không dùng frozen test để select và không tính metrics trên full-refit in-sample scores.

## 8. Tiếp theo

ML-LC-13 — audit handoff sang dashboard/inference contract.
