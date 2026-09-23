# Báo cáo TV2 — Kết quả sửa lỗi handoff dữ liệu

## 1. Kết luận

TV2 đã đạt:

**MODEL_INPUT_GATE = PASS_WITH_WARNINGS**

Phần logic dữ liệu chính đã ổn: không mất dòng, không nhân dòng, không rò rỉ `TARGET`, dữ liệu canonical đủ điều kiện bàn giao cho TV1.

Tuy nhiên còn một cảnh báo về **metadata/provenance của manifest** cần chốt lại trước khi bàn giao chính thức.

## 2. Các lỗi đã phát hiện và đã sửa

| Vấn đề | Cách sửa | Kết quả |
|---|---|---|
| Xử lý nhầm toàn bộ `-999` như sentinel | Phân loại lại 474 giá trị `-999`; giữ nguyên vì chúng nằm trong các cột `DAYS_*` và có nghĩa là 999 ngày trước thời điểm nộp đơn. Chỉ xử lý `DAYS_EMPLOYED = 365243`. | Giữ đúng dữ liệu lịch sử; 55,374 sentinel `365243` được đổi thành `NaN` và giữ cờ `DAYS_EMPLOYED_ANOM`. |
| Tính sai `INSTAL_LATE_RATE` khi thiếu ngày | Chỉ tính kỳ trả góp khi có đủ `DAYS_INSTALMENT` và `DAYS_ENTRY_PAYMENT`. Kỳ thiếu ngày được coi là “không xác định”, không phải trả đúng hạn. | Không còn làm sai mẫu số tỷ lệ trễ hạn. |
| Kiểm tra ngày trả góp tạo lỗi giả | Sửa logic xử lý nhóm không có ngày đến hạn quan sát được. | Không còn báo xung đột giả trên nhóm thiếu toàn bộ mốc ngày. |
| Join `bureau_balance` chưa đủ chặt | Bổ sung kiểm tra null/unique và `validate="one_to_one"` khi nối `bureau_balance` với `bureau`. | Không nhân bản dòng; grain cuối vẫn là một dòng trên `SK_ID_CURR`. |
| Đường dẫn phụ thuộc thư mục chạy lệnh | Chuẩn hóa path theo repository root. | Có thể chạy pipeline từ vị trí khác mà vẫn tìm đúng dữ liệu. |
| Manifest ghi provenance chưa ổn định | Lấy branch/commit/trạng thái Git động; nếu không có Git thì ghi `null`; schema được đọc lại từ Parquet sau khi ghi. | Manifest phản ánh đúng artifact thực tế hơn. |
| Thiếu kiểm tra dataset cuối | Bổ sung quality gates về key, target, infinity, suffix, feature count, rate và row preservation. | Dataset đạt quality gate; report kết luận `PASS WITH WARNINGS`. |

Chi tiết log sửa lỗi: [logs/log_tv2.md:447](/D:/ttdltq/logs/log_tv2.md:447)

## 3. Các file đã sửa/liên quan

- [src/data/cleaning.py:160](/D:/ttdltq/src/data/cleaning.py:160) — xử lý sentinel và cleaning.
- [src/data/aggregate.py:833](/D:/ttdltq/src/data/aggregate.py:833) — aggregate bureau.
- [src/data/aggregate.py:1108](/D:/ttdltq/src/data/aggregate.py:1108) — aggregate installment payments.
- [src/data/build_pipeline.py:212](/D:/ttdltq/src/data/build_pipeline.py:212) — join và bảo toàn grain.
- [src/data/build_pipeline.py:455](/D:/ttdltq/src/data/build_pipeline.py:455) — canonical quality gate.
- [src/data/quality_report.py:2138](/D:/ttdltq/src/data/quality_report.py:2138) — dictionary và quality report.
- [docs/contracts/data_contract.md:1](/D:/ttdltq/docs/contracts/data_contract.md:1) — cập nhật data contract.
- [docs/setup/tv2_setup.md:240](/D:/ttdltq/docs/setup/tv2_setup.md:240) — cập nhật hướng dẫn chạy và kiểm tra.

## 4. Kết quả dataset sau khi sửa

| Hạng mục | Kết quả |
|---|---:|
| Số dòng | 307,511 |
| Số cột | 203 |
| Feature dự báo | 201 |
| Feature số | 184 |
| Feature categorical | 17 |
| `SK_ID_CURR` null | 0 |
| `SK_ID_CURR` duplicate | 0 |
| `TARGET` | `{0: 282,686; 1: 24,825}` |
| Infinity | 0 |
| Aggregate features | 74 |
| Application test đưa vào train | Không |
| Dataset SHA-256 | `6460999371297ff2f83418a8341b0c85d4a2e4dc6c29b29e793edd2a0c755c96` |

## 5. Artifact bàn giao

- [cleaned_dataset.parquet](/D:/ttdltq/data/processed/cleaned_dataset.parquet)  
  307,511 × 203, SHA-256 khớp canonical.
- [data_dictionary.csv](/D:/ttdltq/data/processed/data_dictionary.csv)  
  203 dòng × 22 cột metadata.
- [cleaned_dataset_manifest.json](/D:/ttdltq/data/processed/cleaned_dataset_manifest.json)
- [data_quality_report.md](/D:/ttdltq/reports/data_quality_report.md)  
  Kết luận: `PASS WITH WARNINGS`.
- [tv2_data_handoff.md](/D:/ttdltq/docs/data/tv2_data_handoff.md)

## 6. Kiểm tra đã chạy

Theo log TV2:

- Focused tests: **68 passed**.
- `pytest tests/data tests/features`: **147 passed**.
- `python -m src.data.build_pipeline --rebuild-aggregates`: **SUCCESS**.
- `python -m src.data.quality_report`: **PASS WITH WARNINGS**.
- Quality report ghi nhận 0 null key, 0 duplicate key, 0 infinity, 0 target mismatch, không có `_x`/`_y`, và không mất hoặc nhân dòng sau join.

## 7. Cảnh báo còn lại

Đây không phải lỗi làm hỏng dataset, nhưng TV1 cần biết:

- Một số tỷ lệ có đuôi dài hợp lệ: `CREDIT_TO_INCOME_RATIO` tối đa khoảng 84.74, `INSTAL_PAYMENT_RATIO_MEAN` tối đa khoảng 9,189.32, và `CC_UTILIZATION_MEAN` có 28 giá trị âm nhỏ.
- Lịch sử thiếu ở một số bảng là đặc tính coverage nguồn, không được tự động đổi toàn bộ thành 0.
- `bureau_balance` có 43,041 mã orphan đã được loại khỏi mapping khách hàng và ghi nhận trong manifest.
- Manifest local hiện có SHA-256 `33496d...`, trong khi contract/log TV2 ghi `d311f6...`; ngoài ra manifest local ghi branch `main` trong khi checkout hiện tại là `tv2`. Dataset SHA-256 vẫn đúng, nhưng provenance manifest cần được tái xác nhận trước handoff cuối.

## 8. Trạng thái hiện tại

**TV2 data logic: PASS.**  
**Canonical dataset: PASS.**  
**Quality gate: PASS WITH WARNINGS.**  
**Handoff TV1: Sẵn sàng về mặt dữ liệu, nhưng nên chốt lại provenance manifest trước khi tuyên bố hoàn toàn sạch.**
