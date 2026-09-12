# Giao ước mô hình — TV1 → TV3

## Bàn giao

- `models/full_inference_pipeline.joblib`: `sklearn` Pipeline nhận DataFrame feature đúng tên và hỗ trợ `predict_proba`.
- `data/processed/scored_dataset.parquet`: dữ liệu portfolio cho dashboard.
- `reports/model_card.md`: split, seed, features, metric, threshold, giới hạn và phiên bản thư viện.

## Schema scored dataset

| Cột | Ý nghĩa |
| --- | --- |
| `SK_ID_CURR` | khóa 1–1 với cleaned dataset |
| `TARGET` | chỉ để đánh giá/trực quan, không là model input |
| `PREDICTED_PD` | xác suất default trong [0, 1] |
| `DECISION_THRESHOLD` | ngưỡng chọn từ validation |
| `RECOMMENDATION` | `APPROVE`, `REVIEW`, hoặc `REJECT` |
| `MODEL_VERSION` | artifact đã tạo bản score |

`CREDIT_SCORE`, `RISK_TIER`, `EXPECTED_LOSS` chỉ thêm khi model card có công thức, giả định và cách chặn biên.

## Integration test

TV1 bàn giao hai hồ sơ ẩn danh cùng output kỳ vọng. TV3 kiểm tra Power Query refresh được bảng điểm, relationship theo `SK_ID_CURR` là 1–1 và `PREDICTED_PD` luôn thuộc [0, 1]. Nếu làm What-if bằng DAX, kiểm thử kết quả của hai hồ sơ này với output Python trước khi demo.
