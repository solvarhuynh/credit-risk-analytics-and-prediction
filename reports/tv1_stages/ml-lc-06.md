# ML-LC-06 — Model Comparison & Candidate Lock

## 1. Mục tiêu

ML-LC-03 tạo Logistic baseline bắt buộc; ML-LC-04 thử class weighting; ML-LC-05 thử XGBoost. Stage này so sánh công bằng ba candidate và khóa một candidate để chuyển sang chọn threshold.

## 2. Dữ liệu dùng

Chỉ dùng **269,070** dự đoán validation trên cùng loan_id/target. Frozen test vẫn sealed; chỉ xác nhận file test IDs tồn tại, không đọc nhãn hoặc features.

## 3. Tiêu chí chọn

ROC-AUC đo khả năng xếp người vỡ nợ cao hơn người không vỡ nợ; PR-AUC chú trọng lớp vỡ nợ ít gặp. Ưu tiên ROC-AUC; nếu chênh không quá 0.002, dùng PR-AUC; nếu PR-AUC cũng chênh không quá 0.005, ưu tiên model đơn giản hơn. Hai Logistic có cùng mức phức tạp thì xét Log Loss, rồi Brier Score.
Log Loss và Brier Score càng thấp càng tốt cho chất lượng xác suất PD; chỉ là chẩn đoán ở stage này. Metrics tại threshold 0.5 không quyết định model vì ML-LC-07 mới chọn threshold. Không kiểm định ý nghĩa thống kê.

## 4. Bảng so sánh

| Model | ROC-AUC | PR-AUC | Log Loss | Brier | Precision @0.5 | Recall @0.5 | F1 @0.5 | Accuracy @0.5 | TN | FP | FN | TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| logistic_baseline | 0.714887 | 0.385307 | 0.451609 | 0.144037 | 0.562454 | 0.084494 | 0.146917 | 0.804096 | 211819 | 3531 | 49181 | 4539 |
| logistic_weighted | 0.715097 | 0.384014 | 0.619602 | 0.215452 | 0.322134 | 0.655398 | 0.431958 | 0.655852 | 141262 | 74088 | 18512 | 35208 |
| xgboost_candidate | 0.724501 | 0.399256 | 0.447402 | 0.142595 | 0.598674 | 0.075614 | 0.134270 | 0.805326 | 212627 | 2723 | 49658 | 4062 |

Chênh lệch so với Logistic baseline (Log Loss/Brier âm nghĩa là tốt hơn):

| Model | Δ ROC-AUC | Δ PR-AUC | Δ Log Loss | Δ Brier | Δ Precision @0.5 | Δ Recall @0.5 |
|---|---:|---:|---:|---:|---:|---:|
| logistic_baseline | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 | +0.000000 |
| logistic_weighted | +0.000210 | -0.001292 | +0.167993 | +0.071415 | -0.240319 | +0.570905 |
| xgboost_candidate | +0.009614 | +0.013949 | -0.004207 | -0.001442 | +0.036220 | -0.008879 |

## 5. Diễn giải

Logistic baseline đơn giản, dễ giải thích và là baseline bắt buộc. Weighted Logistic nhạy hơn với default tại ngưỡng 0.5 nhưng tạo nhiều false positives; recall cao tại ngưỡng này không đồng nghĩa ranking hay PD tốt hơn. XGBoost có thể học quan hệ phi tuyến/tương tác, nhưng phức tạp và khó giải thích trực tiếp hơn Logistic.

## 6. Candidate đã khóa

**`xgboost_candidate`** — Theo quy tắc đã ghi trong model contract: ROC-AUC 0.724501 (so với baseline +0.009614), PR-AUC 0.399256 (so với baseline +0.013949); ngưỡng gần nhau lần lượt 0.002/0.005. Quyết định dựa trên validation point estimates, chưa có kiểm định ý nghĩa thống kê.

Model artifact: `D:\ttdltq\data\processed\modeling\xgboost_candidate.joblib`. Validation predictions: `D:\ttdltq\data\processed\modeling\ml_lc_05_xgboost_validation_predictions.parquet`.

## 7. Vì sao hai candidate còn lại không được chọn

- `logistic_baseline`: ROC-AUC 0.714887 (candidate khóa trừ model này: +0.009614); PR-AUC 0.385307 (candidate khóa trừ model này: +0.013949). Model đơn giản, dễ giải thích và vẫn là baseline bắt buộc.
- `logistic_weighted`: ROC-AUC 0.715097 (candidate khóa trừ model này: +0.009403); PR-AUC 0.384014 (candidate khóa trừ model này: +0.015242). Recall @0.5 0.655398 đi kèm 74,088 false positives; ngưỡng tham chiếu không được dùng để chọn model.

## 8. Những việc chưa thực hiện

Chưa chọn threshold, chưa đánh giá frozen test, chưa công bố final model hoặc fit calibration. Chênh lệch validation là point estimates, không khẳng định có ý nghĩa thống kê.

## 9. Bước tiếp theo

ML-LC-07 — Threshold Selection trên validation cho duy nhất candidate đã khóa.
