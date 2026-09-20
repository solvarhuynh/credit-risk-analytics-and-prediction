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

## 2026-09-20 — TV2-DE-02: Data Cleaning & Sentinel/Missing Handling

- **Trạng thái:** done
- **Đã làm:**
  - Hiện thực module làm sạch chuẩn tắc `src/data/cleaning.py` tuân thủ nguyên tắc không biến đổi (immutable) DataFrame đầu vào và chính sách chống rò rỉ (leakage-safe).
  - Áp dụng chính sách missing value: không suy diễn thống kê (mean/median/mode); giữ nguyên genuine missing values; các imputer mô hình dành riêng cho TV1 fit trên training fold sau split.
  - Cung cấp hàm `summarize_missingness` tóm tắt missing count và percentage cho mọi cột.
  - Xử lý sentinel `DAYS_EMPLOYED == 365243` trên `application_train` và `application_test`: chuyển thành missing (NaN) và tạo cờ bất thường `DAYS_EMPLOYED_ANOM` (`int8`, nhận 0 hoặc 1). Số cờ tạo ra khớp chính xác với số sentinel ban đầu.
  - Xử lý sentinel ngày trên `previous_application`: chuyển `365243` thành missing trên đúng 5 cột ngày theo thiết kế: `DAYS_FIRST_DRAWING`, `DAYS_FIRST_DUE`, `DAYS_LAST_DUE_1ST_VERSION`, `DAYS_LAST_DUE`, `DAYS_TERMINATION`.
  - Xử lý vô cực: nhận diện `+inf`/`-inf` trên các cột số và chuẩn hóa về NaN.
  - Chuẩn hóa chuỗi bảo toàn: cắt khoảng trắng đầu/cuối, giữ nguyên chữ hoa/thường và khoảng trắng nội bộ; chuỗi rỗng sau khi cắt chuyển thành missing; bảo toàn các nhãn nghiệp vụ `XNA` và `Unknown`.
  - Chính sách duplicate: phát hiện và báo cáo duplicate tuyệt đối, không xóa dòng tự động nhằm bảo toàn các giao dịch trả góp hợp lệ trong `installments_payments`.
  - Xác thực hợp đồng: kiểm tra khóa chính duy nhất không null (`SK_ID_CURR`, `SK_ID_BUREAU`, `SK_ID_PREV`), kiểm tra nhãn `TARGET` nhị phân {0, 1} trên train và không có `TARGET` trên test.
  - Tạo bộ unit test toàn diện 22 test cases trong `tests/data/test_cleaning.py`.
  - Thực hiện kiểm toán dữ liệu thực tế trên toàn bộ 3 bảng chứa sentinel (`application_train`, `application_test`, `previous_application`) thông qua hàm `audit_sentinel_bearing_raw_tables`.
- **Đo đạc dữ liệu thực tế:**
  - `application_train`: 307,511 dòng, 122 cột vào → 307,511 dòng, 123 cột ra; 0 duplicate; `DAYS_EMPLOYED` sentinel: 55,374 thay thế, 0 còn lại; cờ `DAYS_EMPLOYED_ANOM` = 55,374; trạng thái: VALIDATED.
  - `application_test`: 48,744 dòng, 121 cột vào → 48,744 dòng, 122 cột ra; 0 duplicate; `DAYS_EMPLOYED` sentinel: 9,274 thay thế, 0 còn lại; cờ `DAYS_EMPLOYED_ANOM` = 9,274; trạng thái: VALIDATED.
  - `previous_application`: 1,670,214 dòng, 37 cột vào → 1,670,214 dòng, 37 cột ra; 0 duplicate; sentinel thay thế: `DAYS_FIRST_DRAWING`: 934,444; `DAYS_FIRST_DUE`: 40,645; `DAYS_LAST_DUE_1ST_VERSION`: 93,864; `DAYS_LAST_DUE`: 211,221; `DAYS_TERMINATION`: 225,913; 0 sentinel còn lại trên cả 5 cột; trạng thái: VALIDATED.
- **Bảo toàn checksum dữ liệu thô (SHA-256):**
  - `application_train.csv`: `52e96b895b1112e1c853f670e58372719c8441c5ed1c57ac2f7fad559d784f5f` (trùng khớp 100%)
  - `application_test.csv`: `a36161331d839150a67b6216d4de066f543a3b01a34061507d40e76612e0dec8` (trùng khớp 100%)
  - `previous_application.csv`: `5046cd657ee04df2eaa6dc8308ae86be6b3b1763674a3f63574886a2f2896505` (trùng khớp 100%)
- **Kết quả kiểm thử:**
  - `python -m py_compile src\data\cleaning.py`: PASS (mã thoát 0)
  - `python -m pytest tests\data -v`: 22/22 passed
  - `python -m pytest tests\models -q`: 53/53 passed
  - `python -m src.data.cleaning`: PASS (toàn bộ 3 bảng được kiểm toán thành công)
- **Cảnh báo chuyển tiếp (Carried-forward warnings):**
  1. `bureau_balance` chứa 43,041 khóa ngoại `SK_ID_BUREAU` không tồn tại trong `bureau`.
  2. `installments_payments` chứa 653,483 tổ hợp lặp hạt trả góp thể hiện các đợt thanh toán từng phần; không được khử trùng lặp tùy tiện.
  3. Các tiêu chuẩn Data Contract sau khi tạo đặc trưng và kết nối bảng vẫn tiếp tục PENDING cho DE-03, DE-04 và DE-05.
- **File thay đổi:** `src/data/cleaning.py`, `tests/data/__init__.py`, `tests/data/test_cleaning.py`, `docs/setup/tv2_setup.md`, `logs/log_tv2.md`.
- **Next step:** TV2-DE-03 — Application-Level Feature Engineering.

## 2026-09-20 — TV2-DE-03: Application-Level Feature Engineering

- **Trạng thái:** PASS WITH WARNINGS
- **Đã làm:**
  - Hiện thực module tạo đặc trưng cấp hồ sơ ứng dụng `src/features/engineering.py` tuân thủ nguyên tắc không biến đổi (immutable) DataFrame đầu vào, thuần túy từng dòng (row-local) và chống rò rỉ (leakage-safe).
  - Định nghĩa metadata chuẩn tắc `APPLICATION_FEATURE_DEFINITIONS` cho 6 đặc trưng phái sinh bắt buộc:
    1. `AGE_YEARS`: Chuyển đổi `-DAYS_BIRTH / 365.25` (float64), phạm vi hợp lệ `[18, 100]`, giá trị < 18 hoặc > 100 chuyển thành missing (NaN).
    2. `AGE_GROUP`: Phân nhóm độ tuổi thành biến categorical có thứ tự theo các bin chuẩn `[18, 25, 35, 45, 55, 65, 101]` với nhãn chính xác `['Under 25', '25-34', '35-44', '45-54', '55-64', '65+']`.
    3. `EMPLOYED_YEARS`: Chuyển đổi `-DAYS_EMPLOYED / 365.25`, bảo toàn chính xác giá trị missing (NaN) xuất phát từ sentinel DE-02 và cờ bất thường `DAYS_EMPLOYED_ANOM`.
    4. `CREDIT_TO_INCOME_RATIO`: Tỷ lệ `AMT_CREDIT / AMT_INCOME_TOTAL`.
    5. `ANNUITY_TO_INCOME_RATIO`: Tỷ lệ `AMT_ANNUITY / AMT_INCOME_TOTAL`.
    6. `CREDIT_TO_ANNUITY_RATIO`: Tỷ lệ `AMT_CREDIT / AMT_ANNUITY`.
  - Hiện thực hàm `safe_ratio` xử lý an toàn mẫu số 0, missing và giá trị không hợp lệ; đảm bảo tuyệt đối không phát sinh giá trị vô cực `+inf`/`-inf` mà chuyển thành `NaN`.
  - Tuân thủ nghiêm ngặt nguyên tắc chống rò rỉ: không gộp train/test, không tính toán thống kê toàn cục hay theo nhóm (mean/median/std), không sử dụng biến mục tiêu `TARGET`, không thực hiện điền khuyết thống kê (imputation).
  - Bảo toàn tuyệt đối số lượng dòng, thứ tự dòng và tập khóa chính `SK_ID_CURR`.
  - Cung cấp hàm `validate_feature_parity` kiểm tra tính tương đồng giữa train và test: 128 đặc trưng chung có kiểu dữ liệu đồng nhất; `TARGET` chỉ xuất hiện trên `application_train`.
  - Xây dựng bộ unit test toàn diện 37 test cases trong `tests/features/test_engineering.py` (chứng minh tường minh 14 điều kiện biên tuổi và phân nhóm).
  - Thực hiện kiểm toán dữ liệu thực tế tuần tự trên toàn bộ `application_train` và `application_test` thông qua `audit_application_features`.
- **Đo đạc dữ liệu thực tế:**
  - `application_train`: 307,511 dòng, 123 cột vào (đã qua clean DE-02) → 307,511 dòng, 129 cột ra (thêm 6 đặc trưng); 0 infinity;
    * `AGE_YEARS`: min 20.50, max 69.07, median 43.14, 0 missing (0.0%), 0 giá trị nguồn không hợp lệ, 0 tuổi ngoài phạm vi [18, 100] (0 dưới 18, 0 trên 100).
    * `AGE_GROUP`: 0 missing (0.0%); phân bố: `Under 25`: 12,233; `25-34`: 72,429; `35-44`: 84,261; `45-54`: 70,190; `55-64`: 60,522; `65+`: 7,876.
    * `EMPLOYED_YEARS`: min 0.00, max 49.07, median 6.07, 55,374 missing (18.0072% — khớp chính xác 55,374 sentinel DE-02).
    * `CREDIT_TO_INCOME_RATIO`: min 0.048, max 84.74, median 3.27, 0 missing (0.0%).
    * `ANNUITY_TO_INCOME_RATIO`: min 0.0002, max 1.88, median 0.16, 12 missing (0.0039% — do thiếu `AMT_ANNUITY` gốc).
    * `CREDIT_TO_ANNUITY_RATIO`: min 2.00, max 43.08, median 20.00, 12 missing (0.0039% — do thiếu `AMT_ANNUITY` gốc).
  - `application_test`: 48,744 dòng, 122 cột vào (đã qua clean DE-02) → 48,744 dòng, 128 cột ra (thêm 6 đặc trưng); 0 infinity;
    * `AGE_YEARS`: min 20.09, max 68.98, median 43.10, 0 missing (0.0%), 0 giá trị nguồn không hợp lệ, 0 tuổi ngoài phạm vi [18, 100] (0 dưới 18, 0 trên 100).
    * `AGE_GROUP`: 0 missing (0.0%); phân bố: `Under 25`: 1,880; `25-34`: 11,288; `35-44`: 13,475; `45-54`: 11,322; `55-64`: 9,545; `65+`: 1,234.
    * `EMPLOYED_YEARS`: min 0.00, max 47.85, median 6.13, 9,274 missing (19.0259% — khớp chính xác 9,274 sentinel DE-02).
    * `CREDIT_TO_INCOME_RATIO`: min 0.17, max 38.89, median 3.14, 0 missing (0.0%).
    * `ANNUITY_TO_INCOME_RATIO`: min 0.0051, max 1.25, median 0.16, 24 missing (0.0492% — do thiếu `AMT_ANNUITY` gốc).
    * `CREDIT_TO_ANNUITY_RATIO`: min 2.18, max 39.88, median 20.00, 24 missing (0.0492% — do thiếu `AMT_ANNUITY` gốc).
  - Tính tương đồng Train/Test (Parity): PASS (128 cột chung, khớp 100% dtype, `TARGET` chỉ có trong train).
- **Bảo toàn checksum dữ liệu thô (SHA-256):**
  - `application_train.csv`: `52e96b895b1112e1c853f670e58372719c8441c5ed1c57ac2f7fad559d784f5f` (trùng khớp 100%)
  - `application_test.csv`: `a36161331d839150a67b6216d4de066f543a3b01a34061507d40e76612e0dec8` (trùng khớp 100%)
- **Kết quả kiểm thử:**
  - `python -m py_compile src\features\engineering.py`: PASS (mã thoát 0)
  - `python -m pytest tests\features -v`: 37/37 passed
  - `python -m pytest tests\data -q`: 22/22 passed
  - `python -m pytest tests\models -q`: 53/53 passed
  - `python -m pytest tests -q`: 112/112 passed
  - `python -m src.features.engineering`: PASS (toàn bộ kiểm toán train, test và parity thành công)
- **Cảnh báo chuyển tiếp (Carried-forward warnings):**
  1. `bureau_balance` chứa 43,041 khóa ngoại `SK_ID_BUREAU` không tồn tại trong `bureau`.
  2. `installments_payments` chứa 653,483 tổ hợp lặp hạt trả góp thể hiện các đợt thanh toán từng phần; không được khử trùng lặp tùy tiện.
  3. Các tiêu chuẩn Data Contract sau khi aggregate bảng lịch sử và kết nối bảng vẫn tiếp tục PENDING cho DE-04 và DE-05.
- **File thay đổi:** `src/features/engineering.py`, `tests/features/__init__.py`, `tests/features/test_engineering.py`, `docs/setup/tv2_setup.md`, `logs/log_tv2.md`.
- **Next step:** TV2-DE-04 — Historical Table Aggregation.

## 2026-09-20 — TV2-DE-04: Historical Table Aggregation

- **Trạng thái:** PASS WITH WARNINGS
- **Đã làm:**
  - Hiện thực module tổng hợp dữ liệu lịch sử chuẩn tắc `src/data/aggregate.py` chuyển đổi 6 bảng lịch sử 1:N thành 5 bảng tổng hợp cấp khách hàng (`SK_ID_CURR`) duy nhất, bảo toàn tính xác định (deterministic) và chống rò rỉ dữ liệu (leakage-safe).
  - Xuất khẩu từ điển metadata `AGGREGATE_FEATURE_DEFINITIONS` cho toàn bộ 74 đặc trưng phái sinh.
  - Hàm `validate_temporal_bounds` kiểm tra chặt chẽ điều kiện thời gian `<= 0` trên toàn bộ 6 bảng nguồn (0 vi phạm).
  - Hàm `validate_customer_aggregate` kiểm định hợp đồng dữ liệu: `SK_ID_CURR` duy nhất không null, không có `TARGET`, không trùng tên cột, không vô cực (`inf`), tiền tố cột đúng chuẩn (`BUREAU_`, `PREV_`, `INSTAL_`, `POS_`, `CC_`), số đếm không âm, tỷ lệ trong `[0, 1]`.
  - Tổng hợp `bureau` + `bureau_balance` (2 tầng): nhóm `bureau_balance` theo `SK_ID_BUREAU`, join vào `bureau`, nhóm theo `SK_ID_CURR`. Tỷ lệ trễ hạn được tính có trọng số; loại trừ an toàn 43,041 `SK_ID_BUREAU` mồ côi (3,120,184 dòng). Tạo 20 đặc trưng `BUREAU_`.
  - Tổng hợp `previous_application`: tính tỷ lệ hạn mức/đơn xin cấp dòng an toàn, nhóm theo `SK_ID_CURR`. Tạo 15 đặc trưng `PREV_`.
  - Tổng hợp `installments_payments`: hợp nhất bảo toàn 653,483 dòng trả góp từng phần trên hạt `(SK_ID_PREV, SK_ID_CURR, NUM_INSTALMENT_VERSION, NUM_INSTALMENT_NUMBER)`, không nhân đôi nghĩa vụ `AMT_INSTALMENT`, tính `delay_days` và `shortfall` chính xác. Tạo 10 đặc trưng `INSTAL_`.
  - Tổng hợp `POS_CASH_balance`: đếm hợp đồng duy nhất, đo lường DPD và tháng trễ hạn. Tạo 11 đặc trưng `POS_`.
  - Tổng hợp `credit_card_balance`: tính tỷ lệ sử dụng hạn mức (utilization) cấp dòng an toàn, đo lường dư nợ, hạn mức, DPD và thanh toán. Tạo 18 đặc trưng `CC_`.
  - Chiến lược an toàn bộ nhớ: xử lý tuần tự từng bảng, chỉ nạp các cột cần thiết (`usecols`), tối ưu dtypes, giải phóng bộ nhớ và `gc.collect()`, ghi nguyên tử (atomic write) qua file tạm và `os.replace`.
  - Viết bộ 23 unit tests toàn diện trong `tests/data/test_aggregate.py`.
- **Đo đạc dữ liệu thực tế:**
  - `bureau_aggregated.parquet`: 305,811 dòng, 21 cột (1 khóa + 20 đặc trưng), 12,825,653 bytes, SHA-256: `30aae00b224f8aea3d98d9cf5297bebc52881af40d257dbdf920552aecd2788f`.
  - `previous_application_aggregated.parquet`: 338,857 dòng, 16 cột (1 khóa + 15 đặc trưng), 19,539,477 bytes, SHA-256: `976189184db31c1b458c4460f3bce6ee7767652520657dd916405b9a26819ef8`.
  - `installments_payments_aggregated.parquet`: 339,587 dòng, 11 cột (1 khóa + 10 đặc trưng), 5,344,553 bytes, SHA-256: `9226525c74876d5b0171607728531e66619933ad14289aabe96a8cc1ce956041`.
  - `pos_cash_balance_aggregated.parquet`: 337,252 dòng, 12 cột (1 khóa + 11 đặc trưng), 5,244,997 bytes, SHA-256: `6437be29f54d0b3b73f77e306ba679d186f44d19528f9b903a697d61d7099d77`.
  - `credit_card_balance_aggregated.parquet`: 103,558 dòng, 19 cột (1 khóa + 18 đặc trưng), 5,639,629 bytes, SHA-256: `f4caaae57f25f0755eba7deb1e5c85b9f0ff42cd810d81bbeb5998a2dfe593cb`.
  - `aggregation_manifest.json`: Lưu trữ đầy đủ siêu dữ liệu tại `data/interim/aggregation_manifest.json`.
- **Chẩn đoán bản ghi mồ côi và trả góp:**
  - `bureau_balance`: 43,041 mã `SK_ID_BUREAU` mồ côi (3,120,184 dòng) được loại khỏi cấp khách hàng đúng thiết kế.
  - `installments_payments`: 13,605,401 dòng thô $\rightarrow$ 12,951,918 hạt trả góp duy nhất; 640,905 khóa lặp (1,294,388 dòng) được hợp nhất thành công.
- **Bảo toàn checksum dữ liệu thô (SHA-256):**
  - `bureau.csv`: `9d799143423f280720cf51c1bfbbab2a0422da8ff2763335bb30bf43155494f7` (match)
  - `bureau_balance.csv`: `33e09f06174c26f0be6b8b7398886c69e7bf0abbb29b4122f7841ffe545729a9` (match)
  - `installments_payments.csv`: `428c2e2496e4d6d697ee8270e98497e5213c41be16d882eed1bc95b133726797` (match)
  - `previous_application.csv`: `5046cd657ee04df2eaa6dc8308ae86be6b3b1763674a3f63574886a2f2896505` (match)
  - `POS_CASH_balance.csv`: `0e13bc573ffa8fc29b3f00d975e557143193a405d675b0e4694b06fbdffcb0cd` (match)
  - `credit_card_balance.csv`: `a9cdc48900d55131c90f3128b991859aeb94ca1326fb5f4d1624b9fd03782247` (match)
- **Kết quả kiểm thử:**
  - `python -m py_compile src\data\aggregate.py`: PASS (mã thoát 0)
  - `python -m pytest tests\data -v`: 45/45 passed
  - `python -m pytest tests\features -q`: 37/37 passed
  - `python -m pytest tests\models -q`: 53/53 passed
  - `python -m pytest tests -q`: 135/135 passed
  - `python -m src.data.aggregate`: PASS
- **Cảnh báo chuyển tiếp (Carried-forward warnings):**
  1. `bureau_balance` chứa 43,041 khóa ngoại `SK_ID_BUREAU` không tồn tại trong `bureau` (đã loại khỏi tổng hợp khách hàng).
  2. `installments_payments` chứa 653,483 tổ hợp lặp hạt trả góp thể hiện các đợt thanh toán từng phần (đã hợp nhất bảo toàn).
  3. Tiêu chuẩn Data Contract xuất bản tập dữ liệu hợp nhất cuối cùng tiếp tục PENDING cho DE-05.
- **File thay đổi:** `src/data/aggregate.py`, `tests/data/test_aggregate.py`, `docs/setup/tv2_setup.md`, `logs/log_tv2.md`.
- **Next step:** TV2-DE-05 — Join and Canonical Dataset Publication.
