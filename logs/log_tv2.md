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

## 2026-09-20 — TV2-DE-01R: Restore raw Home Credit data and revalidate the existing raw-data preflight

- **Trạng thái:** PASS WITH WARNINGS
- **Tóm tắt đánh giá:**
  Raw-data authentication, restoration, schema preflight, key validation,
  and train/test separation passed.

  Post-cleaning and post-feature-engineering Data Contract gates remain
  PENDING for DE-02, DE-03, and DE-05.

  Warnings carried forward:
  1. bureau_balance contains 43,041 orphan SK_ID_BUREAU values.
  2. installments_payments contains 653,483 repeated installment-grain
     combinations representing possible split payments; do not blindly deduplicate.
- **Đã làm:**
  - Kiểm tra an toàn 4 archive ZIP gốc tại repository root (`data1_part1.zip`, `data1_part2.zip`, `data1_part3.zip`, `data2.zip`): kiểm tra tính toàn vẹn (integrity test pass), đường dẫn an toàn (không có directory traversal, symlink, absolute path, file thực thi), đối chiếu manifest nội bộ khớp hoàn toàn.
  - Giải nén an toàn vào thư mục staging tạm thời ngoài repository (`D:\Temp\credit-risk-tv2-staging-87952e8c-be1d-40e1-82b8-58cabb1599e5`).
  - Xác thực độc lập từng file trích xuất bằng streaming (byte size, SHA-256, physical lines, clean newline ending, header column count) đối chiếu với baseline xác thực: 10/10 file trùng khớp 100%.
  - Khôi phục nguyên trạng (không sửa đổi byte, loại bỏ thư mục ngoài thành đường dẫn phẳng) 8 file bắt buộc vào `data/raw/`: `application_train.csv`, `application_test.csv`, `bureau.csv`, `bureau_balance.csv`, `previous_application.csv`, `installments_payments.csv`, `credit_card_balance.csv`, `POS_CASH_balance.csv`.
  - Khôi phục 2 file bổ sung: `HomeCredit_columns_description.csv` và `sample_submission.csv`.
  - Giữ nguyên trạng thái untracked/ignored của toàn bộ dữ liệu thô (`data/raw/*.csv`) và 4 archive ZIP (thông qua `.git/info/exclude`).
  - Biên dịch và thực thi preflight nguyên bản `src/data/load_data.py` trên toàn bộ tập dữ liệu (không sampling).
- **Kết quả đo đạc:**
  - `application_train`: 307,511 dòng, 122 cột, 0 duplicate full rows, `SK_ID_CURR` duy nhất không null (307,511), `TARGET` chỉ gồm 2 giá trị phân loại [0, 1].
  - `application_test`: 48,744 dòng, 121 cột, 0 duplicate full rows, `SK_ID_CURR` duy nhất không null (48,744), không có cột `TARGET`.
  - Phân tách Train/Test: độ chồng lấn `SK_ID_CURR` = 0.
  - Khóa và hạt dữ liệu: `bureau` (1,716,428 dòng, `SK_ID_BUREAU` duy nhất), `bureau_balance` (27,299,925 dòng, hạt `(SK_ID_BUREAU, MONTHS_BALANCE)` duy nhất), `previous_application` (1,670,214 dòng, `SK_ID_PREV` duy nhất), `installments_payments` (13,605,401 dòng, 653,483 dòng trùng phiên bản/kỳ do tách thanh toán từng phần), `POS_CASH_balance` (10,001,358 dòng, hạt `(SK_ID_PREV, SK_ID_CURR, MONTHS_BALANCE)` duy nhất), `credit_card_balance` (3,840,312 dòng, hạt `(SK_ID_PREV, SK_ID_CURR, MONTHS_BALANCE)` duy nhất).
  - Độ phủ khóa ngoại: 100% `SK_ID_CURR` trong các bảng lịch sử đều tồn tại trong `application_train ∪ application_test` (0 orphan). `bureau_balance` khớp 94.73% `SK_ID_BUREAU` với `bureau` (43,041 orphan ngoài mẫu lịch sử, đúng đặc tính tập dữ liệu Home Credit).
- **Kiểm tra đã chạy:**
  - `python -m py_compile src\data\load_data.py`
  - `python -m src.data.load_data`
  - `git diff --check`
  - `git status --short`
- **File thay đổi:** `logs/log_tv2.md`.
- **Next step:** TV2-DE-02 — Data Cleaning & Sentinel/Missing Handling.
