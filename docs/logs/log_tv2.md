# Log công việc — TV2 (Data Engineering)

Chỉ append entry mới theo quy trình trong docs/tasks/working-protocol.md.

## 2026-09-13 — DE-01: Raw data loading & schema preflight

- **Trạng thái:** done - `tv1 đã làm giúp`
- **Đã làm:** hiện thực loader raw có kiểm tra 8 CSV bắt buộc và preflight đọc từng bảng để đo schema, duplicate, key/grain, train/test separation và foreign-key coverage; không clean, join hay aggregate.
- **File thay đổi:** `src/data/load_data.py`, `docs/logs/log_tv2.md`.
- **Kiểm tra đã chạy:** `python -m py_compile src\\data\\load_data.py`; đọc thử `application_train`; chạy full preflight trên toàn bộ raw CSV; kiểm tra thông báo khi thiếu file; đọc bảng mô tả optional bằng encoding phù hợp.
- **Next step:** DE-02 — Data Cleaning & Sentinel/Missing Handling.

## 2026-09-13 — Setup handoff guide

- **Trạng thái:** done
- **Đã làm:** tạo hướng dẫn chạy DE-01, raw prerequisites, validation và giới hạn output.
- **File thay đổi:** `docs/setup/tv2_setup.md`, `docs/logs/log_tv2.md`.
- **Kiểm tra:** đối chiếu command DE-01 đã chạy thực tế và canonical raw paths.
- **Next step:** Cập nhật guide cùng mỗi task DE-02 đến DE-06 khi có command/output mới.

## 2026-09-13 — DE-01 — Raw Data Loading & Schema Preflight (handoff sync)

- **Trạng thái:** done - `tv1 đã làm giúp`
- **Đã làm:**
  - Xác minh raw-data loader/preflight đã được hiện thực trong canonical `src/data/load_data.py`.
  - Xác minh đủ 8 raw tables; preflight đã kiểm tra schema, candidate grain/key, train/test separation và foreign-key coverage; chưa cleaning, aggregate, join hoặc feature engineering.
  - Ghi nhận handoff TV1: mọi bảng 1:N phải aggregate trước khi join application; historical feature phải có as-of-time/leakage validation.
  - Roadmap: DE-02 Cleaning → DE-03 Feature Engineering application-level → DE-04 Aggregation từng history source → DE-05 Join & canonical output → DE-06 Data Dictionary / quality report.
- **File thay đổi:** `src/data/load_data.py`, `docs/logs/log_tv2.md`.
- **Kiểm tra:** `python -m py_compile src\\data\\load_data.py`; load `application_train`; full preflight trên raw CSV; kiểm tra missing-file error; đọc optional columns description; `git diff --check`.
- **Next step:** DE-02 — Data Cleaning & Sentinel/Missing Handling.
