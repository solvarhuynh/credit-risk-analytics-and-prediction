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

## 2026-09-20 — TV2-DE-05: Join and Canonical Dataset Publication (Updated TV2-DE-05C)

- **Trạng thái:** PASS WITH WARNINGS
- **Git history chuẩn xác:**
  - `6984c30` feat(data): aggregate historical credit records
  - `8c81727` feat(features): add application-level financial features
  - `4cabd50` feat(data): implement leakage-safe cleaning layer
  - `c51a511` docs(data): record raw preflight revalidation
  - `30659ab` feat(testing): establish regression test suite for modeling modules and normalize canonical logs
- **Đã làm:**
  - Hiện thực module điều phối và xuất bản tập dữ liệu chuẩn tắc `src/data/build_pipeline.py`.
  - Thiết lập hàm `join_customer_aggregates`: thực thi left join tuần tự 5 bảng aggregate trung gian (`BUREAU` $\rightarrow$ `PREV` $\rightarrow$ `INSTAL` $\rightarrow$ `POS` $\rightarrow$ `CC`) vào quần thể gắn nhãn `application_train`, kiểm định nghiêm ngặt lực lượng 1-to-1, ngăn ngừa nhân đôi dòng hoặc rơi rụng bản ghi.
  - Áp dụng chính sách xử lý khuyết thiếu lịch sử tín dụng (Missing-History Policy): chỉ điền giá trị `0` cho đúng 18 cột số đếm nghiệp vụ đã được phê duyệt (`BUREAU_CREDIT_COUNT`, `BUREAU_ACTIVE_COUNT`, `BUREAU_CLOSED_COUNT`, `BUREAU_BB_MONTH_COUNT`, `BUREAU_BB_DELINQUENT_MONTH_COUNT`, `BUREAU_BB_SEVERE_MONTH_COUNT`, `PREV_APPLICATION_COUNT`, `PREV_APPROVED_COUNT`, `PREV_REFUSED_COUNT`, `INSTAL_INSTALLMENT_COUNT`, `INSTAL_LATE_COUNT`, `INSTAL_UNDERPAYMENT_COUNT`, `POS_RECORD_COUNT`, `POS_CONTRACT_COUNT`, `POS_LATE_MONTH_COUNT`, `CC_RECORD_COUNT`, `CC_CONTRACT_COUNT`, `CC_LATE_MONTH_COUNT`); bảo toàn `NaN` cho các cột tỷ lệ, số tiền và thống kê.
  - Hiện thực cổng kiểm soát chất lượng dữ liệu `validate_canonical_dataset` với 28 quy tắc kiểm định toàn diện: bảo toàn số dòng (307,511), thứ tự cột chuẩn tắc (203 cột), tính duy nhất và đơn điệu tăng dần của `SK_ID_CURR`, tính bất biến của phân phối `TARGET` {0: 282,686; 1: 24,825}, không chứa giá trị vô cực (`inf`), tiền tố hợp lệ.
  - Bảo đảm đầy đủ các cột bắt buộc theo Data Contract (`AGE_YEARS`, `AGE_GROUP`, `EMPLOYED_YEARS`, `DAYS_EMPLOYED_ANOM`, `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_INCOME_RATIO`,...).
  - Chuẩn hóa kiểm định tỷ lệ: chỉ 10 cột tỷ lệ xác định (`BOUNDED_RATE_COLUMNS`) bị chặn trong `[0, 1]`; các tỷ lệ tài chính như `CREDIT_TO_INCOME_RATIO`, `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_ANNUITY_RATIO`, `PREV_CREDIT_TO_APPLICATION_RATIO_MEAN`, `INSTAL_PAYMENT_RATIO_MEAN`, `CC_UTILIZATION_MEAN/MAX` được phép lớn hơn 1 hợp lệ.
  - Hiện thực cơ chế xuất bản nguyên tử `write_canonical_dataset_atomic`: ghi tệp `.tmp`, thực hiện kiểm định đọc lại (read-back validation), hoán đổi an toàn bằng `os.replace`.
  - Tự động sinh tệp siêu dữ liệu kiểm định `cleaned_dataset_manifest.json` ghi nhận đầy đủ checksum, số liệu kiểm định join audit, phân phối nhãn và cảnh báo.
  - Cập nhật `.gitignore` loại trừ cục bộ `data/processed/cleaned_dataset_manifest.json`.
  - Viết bộ 22 unit tests cô lập trong `tests/data/test_build_pipeline.py` sử dụng dữ liệu giả lập (synthetic fixtures), kiểm thử toàn diện mọi tình huống biên, rò rỉ nhãn, tính bất biến, tỷ lệ không bị chặn và hợp đồng dữ liệu.
- **Đo đạc dữ liệu thực tế:**
  - `application_train` nạp vào: 307,511 dòng, 122 cột.
  - Sau làm sạch DE-02: 307,511 dòng, 123 cột.
  - Sau feature engineering DE-03: 307,511 dòng, 129 cột.
  - Sau left join `BUREAU`: 307,511 dòng, 149 cột.
  - Sau left join `PREV`: 307,511 dòng, 164 cột.
  - Sau left join `INSTAL`: 307,511 dòng, 174 cột.
  - Sau left join `POS`: 307,511 dòng, 185 cột.
  - Sau left join `CC`: 307,511 dòng, 203 cột.
  - Số dòng cuối cùng: 307,511 dòng (không mất dòng, không nhân đôi dòng).
  - Số cột cuối cùng: 203 cột (1 `SK_ID_CURR` + 1 `TARGET` + 120 cột thô sạch + 7 cột DE-02/DE-03 + 74 cột aggregate DE-04).
  - Số đặc trưng phục vụ mô hình: 201 đặc trưng (184 số trị, 17 phân loại/chuỗi).
  - Phân phối `TARGET`: {0: 282,686; 1: 24,825} (trùng khớp 100% so với dữ liệu gốc).
  - Số lượng khóa null: 0; Số lượng khóa trùng lặp: 0.
  - Số giá trị vô cực (`inf`): 0.
- **Độ bao phủ theo nguồn lịch sử (Per-Source Coverage):**
  - `BUREAU`: Khớp 263,491 (85.6851%), không khớp 44,020, chỉ có ở aggregate (test set) 42,320.
  - `PREV`: Khớp 291,057 (94.6493%), không khớp 16,454, chỉ có ở aggregate (test set) 47,800.
  - `INSTAL`: Khớp 291,643 (94.8399%), không khớp 15,868, chỉ có ở aggregate (test set) 47,944.
  - `POS`: Khớp 289,444 (94.1248%), không khớp 18,067, chỉ có ở aggregate (test set) 47,808.
  - `CC`: Khớp 86,905 (28.2608%), không khớp 220,606, chỉ có ở aggregate (test set) 16,653.
- **Bảo toàn checksum dữ liệu thô (SHA-256):**
  - `application_train.csv`: `52e96b895b1112e1c853f670e58372719c8441c5ed1c57ac2f7fad559d784f5f` (match)
  - `bureau.csv`: `9d799143423f280720cf51c1bfbbab2a0422da8ff2763335bb30bf43155494f7` (match)
  - `bureau_balance.csv`: `33e09f06174c26f0be6b8b7398886c69e7bf0abbb29b4122f7841ffe545729a9` (match)
  - `previous_application.csv`: `5046cd657ee04df2eaa6dc8308ae86be6b3b1763674a3f63574886a2f2896505` (match)
  - `installments_payments.csv`: `428c2e2496e4d6d697ee8270e98497e5213c41be16d882eed1bc95b133726797` (match)
  - `POS_CASH_balance.csv`: `0e13bc573ffa8fc29b3f00d975e557143193a405d675b0e4694b06fbdffcb0cd` (match)
  - `credit_card_balance.csv`: `a9cdc48900d55131c90f3128b991859aeb94ca1326fb5f4d1624b9fd03782247` (match)
- **Kiểm định checksum bảng tổng hợp trung gian (SHA-256):**
  - `bureau_aggregated.parquet`: `30aae00b224f8aea3d98d9cf5297bebc52881af40d257dbdf920552aecd2788f` (match)
  - `previous_application_aggregated.parquet`: `976189184db31c1b458c4460f3bce6ee7767652520657dd916405b9a26819ef8` (match)
  - `installments_payments_aggregated.parquet`: `9226525c74876d5b0171607728531e66619933ad14289aabe96a8cc1ce956041` (match)
  - `pos_cash_balance_aggregated.parquet`: `6437be29f54d0b3b73f77e306ba679d186f44d19528f9b903a697d61d7099d77` (match)
  - `credit_card_balance_aggregated.parquet`: `f4caaae57f25f0755eba7deb1e5c85b9f0ff42cd810d81bbeb5998a2dfe593cb` (match)
- **Tệp xuất bản chính thức (Published Output Artifacts):**
  - Parquet: `data/processed/cleaned_dataset.parquet` (64,213,549 bytes, SHA-256: `e3cbf594a5a0a072fc1625baa11563c323b8c392afc90cb46bb17bf48c12de75`).
  - Manifest: `data/processed/cleaned_dataset_manifest.json` (17,082 bytes, SHA-256: `e633885a14ad70b7f153cc27587722c77ee6c5b73ac03495872755df7a73d3f7`).
- **Lệnh thực thi & Kiểm thử:**
  - `python -m py_compile src\data\build_pipeline.py`: PASS (mã thoát 0)
  - `python -m pytest tests\data\test_build_pipeline.py -v`: 22/22 passed
  - `python -m pytest tests\data -v`: 67/67 passed
  - `python -m pytest tests\features -q`: 37/37 passed
  - `python -m pytest tests\models -q`: 53/53 passed
  - `python -m pytest tests -q`: 157/157 passed
  - `git diff --check`: PASS (không lỗi định dạng)
  - `python -m src.data.build_pipeline`: SUCCESS
- **Cảnh báo nghiệp vụ (Warnings):**
  1. Độ bao phủ lịch sử < 100% phản ánh đúng bản chất tín dụng khách hàng (đặc biệt `CC` chỉ đạt 28.26%).
  2. 43,041 mã mồ côi `bureau_balance` được loại trừ an toàn từ DE-04.
  3. 653,483 dòng trả góp từng phần được hợp nhất bảo toàn từ DE-04.
  4. Các đặc trưng tỷ lệ/thống kê của khách hàng không có lịch sử giữ nguyên `NaN` thực tế.
- **Trạng thái Git:**
  - DE-05 chưa được commit (`git commit` chưa chạy).
  - Không push lên bất kỳ remote repository nào.
- **Next step:** TV2-DE-06 — Data Dictionary and Data Quality Report.

## 2026-09-20 — TV2-DE-06: Data Dictionary and Data Quality Report (Updated TV2-DE-06C)

- **Trạng thái:** PASS WITH WARNINGS
- **Môi trường Python:** Python 3.13.5 (xác thực trực tiếp từ `& .\.venv\Scripts\python.exe --version`)
- **Git state:**
  - Branch: `tv2`
  - Base HEAD: `2999510` (`feat(data): publish canonical customer dataset`)
  - Tracked changes: Uncommitted for review (không commit, không push)
  - Trạng thái tệp báo cáo: `reports/data_quality_report.md` là sản phẩm bàn giao dự kiến theo dõi (intended tracked deliverable) nhưng hiện vẫn ở trạng thái untracked (`??`) cho đến khi hoàn thành commit đánh giá DE-06.
- **Đã làm:**
  - Hiện thực module kiểm định chất lượng và sinh siêu dữ liệu chuẩn tắc `src/data/quality_report.py`.
  - Tải và kiểm tra tính bất biến tuyệt đối của tập dữ liệu chuẩn tắc `data/processed/cleaned_dataset.parquet` và manifest `data/processed/cleaned_dataset_manifest.json` (SHA-256 hoàn toàn không đổi).
  - Tích hợp siêu dữ liệu đa tầng theo thứ tự ưu tiên: Handcrafted feature definitions từ DE-02, DE-03, DE-04 $\rightarrow$ Kaggle descriptions từ `data/raw/HomeCredit_columns_description.csv` $\rightarrow$ Structured fallback logic.
  - Xây dựng từ điển dữ liệu máy đọc `data/processed/data_dictionary.csv`:
    * Đúng 203 dòng (1 dòng cho mỗi cột chuẩn tắc, bảo toàn đúng thứ tự cột trong parquet).
    * Đúng 22 cột siêu dữ liệu theo quy định nghiêm ngặt của đề mục đã duyệt: `position`, `column_name`, `physical_dtype`, `logical_type`, `role`, `feature_group`, `source_table`, `source_columns`, `source_grain`, `canonical_grain`, `transformation_formula`, `unit`, `description`, `missing_value_meaning`, `valid_values_or_range`, `nullable`, `missing_count`, `missing_rate`, `unique_count`, `as_of_time_rule`, `leakage_note`, `modeling_note`.
    * 0 giá trị NaN, 0 chuỗi rỗng trên toàn bộ 22 cột; 100% cột có mô tả tiếng Anh, công thức phái sinh và ngữ nghĩa khuyết thiếu rõ ràng.
    * Phân nhóm vai trò chuẩn tắc (`role`): `identifier` (1), `target` (1), `feature` (201).
    * Phân nhóm đặc trưng (`feature_group`): `application_raw` (120), `bureau` (20), `credit_card` (18), `previous_application` (15), `pos_cash` (11), `installments` (10), `application_derived` (6), `identifier` (1), `target` (1), `application_cleaning` (1). Tổng: 203/203 cột.
    * Định dạng UTF-8 with BOM (`utf-8-sig`), kết thúc dòng LF (`\n`), kích thước 124,732 bytes, SHA-256: `efd1d1e1ad268f12ee38a901602f707a76b07a3b581ba99c25df9f6bd188ec39`.
    * Được loại trừ an toàn khỏi Git theo `.gitignore` (`data/processed/*.csv`).
  - Biên dịch báo cáo kiểm định chất lượng người đọc `reports/data_quality_report.md`:
    * Gồm đúng 19 phần Markdown chuẩn tắc được đánh số rõ ràng (từ 1 đến 19).
    * Loại bỏ hoàn toàn các phân tích tương quan với nhãn mục tiêu, xếp hạng dự báo và tương quan đa biến (chuyển về đúng phạm vi của nhiệm vụ DE-07 EDA).
    * Phân định chính xác vai trò các thành viên hạ nguồn: TV1 phụ trách Modeling, TV3 phụ trách Dashboard & Application.
    * Định dạng UTF-8, LF (`\n`), kích thước 16,740 bytes, SHA-256: `6330015da3379aec03c650870d19f5e364cdb0260567bcbbca157239ac274017`.
  - Cập nhật tài liệu hợp đồng dữ liệu `docs/contracts/data_contract.md` lên Phiên bản 1.1 (Version 1.1) phản ánh chính xác các sản phẩm bàn giao, 22 trường từ điển, vai trò TV1/TV3, 18 cột số đếm điền 0, quy tắc thời gian và cổng chất lượng.
  - Cập nhật hướng dẫn thiết lập kỹ thuật `docs/setup/tv2_setup.md` bổ sung tài liệu hướng dẫn vận hành, lược đồ và bàn giao hạ nguồn của DE-06.
  - Viết bộ 18 unit tests toàn diện trong `tests/data/test_quality_report.py` kiểm định toàn diện việc sinh từ điển, các cổng kiểm soát chất lượng, kiểm toán khuyết thiếu, kiểm tra biên độ phân tầng, phân định rõ all-null / constant / near-constant (99.5%), các quy tắc thời gian và xuất bản nguyên tử.
- **Bảo toàn checksum dữ liệu chuẩn tắc (SHA-256 Invariance):**
  - `cleaned_dataset.parquet`: `e3cbf594a5a0a072fc1625baa11563c323b8c392afc90cb46bb17bf48c12de75` (trước: `e3cbf594a5a0a072...`, sau: `e3cbf594a5a0a072...` — TRÙNG KHỚP 100%, 64,213,549 bytes)
  - `cleaned_dataset_manifest.json`: `e633885a14ad70b7f153cc27587722c77ee6c5b73ac03495872755df7a73d3f7` (trước: `e633885a14ad70b7...`, sau: `e633885a14ad70b7...` — TRÙNG KHỚP 100%, 17,082 bytes)
- **Đo đạc kiểm định chất lượng dữ liệu thực tế (Measured Audit Results):**
  - Quần thể: 307,511 dòng, 203 cột (1 `SK_ID_CURR`, 1 `TARGET`, 201 đặc trưng mô hình).
  - Khóa chính `SK_ID_CURR`: 0 null, 0 duplicate, đơn điệu tăng dần từ 100,002 đến 456,255.
  - Nhãn mục tiêu `TARGET`: 0 null, phân phối {0: 282,686, 1: 24,825}, tỷ lệ nợ xấu 8.0729%.
  - Kiểm định Missing-History Policy: Đúng 18/18 cột số đếm có 0 missing (100% tuân thủ chính sách điền 0).
  - Phân tầng ma trận giá trị khuyết thiếu (Missingness Buckets - 7 nhóm tất định, loại trừ lẫn nhau):
    * `exactly 0%`: 73 cột (bao gồm `SK_ID_CURR`, `TARGET`, 18 cột số đếm lịch sử, các trường định danh và thông tin ứng dụng cơ bản).
    * `greater than 0% and less than 5%`: 12 cột (`AMT_ANNUITY`, `AMT_GOODS_PRICE`, tỷ lệ tài chính DE-03).
    * `greater than or equal to 5% and less than 20%`: 48 cột (`EXT_SOURCE_3` 19.83%, `DAYS_EMPLOYED` / `EMPLOYED_YEARS` 18.01% do sentinel, độ bao phủ `BUREAU_` gap 14.31%).
    * `greater than or equal to 20% and less than 50%`: 9 cột (`OCCUPATION_TYPE` 31.35%, đặc tính tòa nhà).
    * `greater than or equal to 50% and less than 80%`: 61 cột (`EXT_SOURCE_1` 56.38%, `COMMONAREA_AVG` 69.87%, đặc trưng thẻ tín dụng `CC_*` 71.74% do độ bao phủ chỉ đạt 28.26%).
    * `greater than or equal to 80% and less than 100%`: 0 cột.
    * `exactly 100%`: 0 cột.
    * Tổng số cột phân tầng: Đúng 203/203 cột.
  - Phân loại đặc trưng đơn trị và gần như hằng số:
    * All-null (0 non-null values): 0 cột.
    * Constant (1 unique non-null value): 0 cột.
    * Near-constant (ngưỡng giá trị áp đảo >= 99.5%): Đúng 16 cột (14 cờ `FLAG_DOCUMENT_*`, `FLAG_MOBIL`, `FLAG_CONT_MOBILE`).
    * Cờ dị biệt `DAYS_EMPLOYED_ANOM` có tỷ lệ áp đảo 81.9928%, hoàn toàn không thuộc nhóm near-constant và được giữ nguyên là cờ chất lượng dữ liệu và dị biệt quan trọng.
  - Kiểm toán mốc thời gian: Toàn bộ các cột thời gian lịch sử (`DAYS_*`, `MONTHS_BALANCE_*`) đều bảo đảm giá trị `<= 0`, 0 rò rỉ tương lai.
- **Kết quả kiểm thử:**
  - `python -m py_compile src\data\quality_report.py`: PASS (mã thoát 0)
  - `python -m pytest tests\data\test_quality_report.py -v`: 18/18 passed
  - `python -m pytest tests\data -q`: 85/85 passed (18 quality_report + 22 build_pipeline + 23 aggregate + 22 cleaning)
  - `python -m pytest tests\features -q`: 37/37 passed
  - `python -m pytest tests\models -q`: 53/53 passed
  - `python -m pytest tests -q`: 175/175 passed
  - `git diff --check`: PASS (0 khoảng trắng thừa hoặc lỗi định dạng)
- **Cảnh báo nghiệp vụ (Warnings):**
  1. 16 đặc trưng gần như hằng số (tần suất giá trị phổ biến >= 99.5%) cần được TV1 xem xét khi lựa chọn mô hình dựa trên cây hoặc mô hình tuyến tính.
  2. 61 cột có tỷ lệ missing từ 50% đến 80% (chủ yếu là thông tin tòa nhà và thẻ tín dụng), yêu cầu chiến lược xử lý missing cẩn trọng trong pipeline tiền xử lý của TV1.
  3. Tỷ lệ thẻ tín dụng thấp (độ bao phủ 28.26%) phản ánh cấu trúc hành vi tiêu dùng tự nhiên của khách hàng.
- **Trạng thái Git:**
  - DE-06 chưa được commit (`git commit` chưa chạy).
  - Không push lên bất kỳ remote repository nào.
- **Next step:** TV2-DE-07 — Exploratory Data Analysis and Data Engineering Handoff.
