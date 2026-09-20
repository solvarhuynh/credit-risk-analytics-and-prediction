# Giao ước bàn giao dữ liệu & kết quả kỹ thuật — TV2 → TV1 & TV3

**Mã nhiệm vụ (Task ID):** TV2-DE-07 — Exploratory Data Analysis and Data Engineering Handoff
**Bên bàn giao (Producer):** Thành viên 2 (TV2) — Data Engineering & Data Pipeline
**Bên tiếp nhận (Consumers):**
- Thành viên 1 (TV1) — Modeling, Feature Selection & Evaluation
- Thành viên 3 (TV3) — Dashboard & Application Architecture
**Trạng thái bàn giao (Handoff Status):** **READY FOR HANDOFF (PENDING CONSUMER ACKNOWLEDGEMENT)**
**Mốc cam kết (Base Commit):** `704755a` (`feat(data): publish data dictionary and quality report`)
**Thời điểm lập (Timestamp UTC):** 2026-09-20T15:35:00Z

---

## 1. Mục đích văn bản

Tài liệu này xác lập biên bản bàn giao kỹ thuật chính thức từ TV2 (Data Engineering) cho TV1 (Modeling) và TV3 (Dashboard) sau khi hoàn tất toàn bộ chuỗi công việc tiền xử lý cốt lõi từ DE-01 đến DE-07. Tài liệu quy định chi tiết danh mục tạo tác chuẩn tắc (canonical artifacts), checksum bảo toàn, đặc tả dữ liệu, chính sách giá trị khuyết thiếu, các ràng buộc kỹ thuật bắt buộc để chống rò rỉ dữ liệu (data leakage) và phạm vi trách nhiệm của từng thành viên.

---

## 2. Danh mục tạo tác chuẩn tắc bàn giao (Artifact Inventory)

| STT | Tên tạo tác | Đường dẫn tệp | Kích thước | SHA-256 Checksum | Trạng thái Git |
| :---: | :--- | :--- | :---: | :--- | :---: |
| 1 | **Tập dữ liệu chuẩn tắc** | `data/processed/cleaned_dataset.parquet` | 64,213,549 B | `e3cbf594a5a0a072fc1625baa11563c323b8c392afc90cb46bb17bf48c12de75` | Gitignored (`*.parquet`) |
| 2 | **Manifest kiểm định xuất bản** | `data/processed/cleaned_dataset_manifest.json` | 17,082 B | `e633885a14ad70b7f153cc27587722c77ee6c5b73ac03495872755df7a73d3f7` | Tracked (`git show`) |
| 3 | **Từ điển dữ liệu chuẩn tắc** | `data/processed/data_dictionary.csv` | 124,732 B | `efd1d1e1ad268f12ee38a901602f707a76b07a3b581ba99c25df9f6bd188ec39` | Gitignored (`*.csv`) |
| 4 | **Báo cáo chất lượng dữ liệu** | `reports/data_quality_report.md` | 16,740 B | `6330015da3379aec03c650870d19f5e364cdb0260567bcbbca157239ac274017` | Tracked (DE-06 commit) |
| 5 | **Báo cáo phân tích khám phá** | `reports/eda_report.md` | 12,891 B | `688248918afc567e66cfeac5a1ce42a70ce85b4d35196a52e60047c24b96d2b5` | Output deliverable (DE-07) |
| 6 | **Biểu đồ EDA 01** | `reports/figures/eda/01_income_distribution_by_target.png` | 400,315 B | `263e84e199e9dc6cf8c2e26687c2cd636d7a9e527e439788d031f9a632b956e6` | Output deliverable (DE-07) |
| 7 | **Biểu đồ EDA 02** | `reports/figures/eda/02_default_rate_by_age_group.png` | 198,222 B | `3d1b4352beb8862d815ebbcd2c8ff8758ff3c4872c5228dbb5478608742fc7df` | Output deliverable (DE-07) |
| 8 | **Biểu đồ EDA 03** | `reports/figures/eda/03_default_rate_by_occupation_and_contract.png` | 462,301 B | `cb2826c968f08787e361b6cacf615552c4b6df7dca0947452fbf87e63eb88bb1` | Output deliverable (DE-07) |
| 9 | **Biểu đồ EDA 04** | `reports/figures/eda/04_key_numeric_spearman_heatmap.png` | 488,137 B | `a7914f619916e59b445382359b14bfc429bc6de9fc559552a0c18f651ce5858b` | Output deliverable (DE-07) |
| 10 | **Biểu đồ EDA 05** | `reports/figures/eda/05_days_employed_before_after.png` | 295,138 B | `d8a669f6094e8541002fc3babf88deae0860e0ca876c3b4a3ec2f696f4386315` | Output deliverable (DE-07) |

> [!WARNING]
> **Lưu ý về truyền tải tệp gitignored:** Tệp dữ liệu `cleaned_dataset.parquet` (64.2 MB) và từ điển `data_dictionary.csv` (124.7 KB) bị loại trừ khỏi Git theo `.gitignore` để giữ kho lưu trữ gọn nhẹ. Các thành viên hạ nguồn không tải tệp này từ `git pull` mà cần tự tái tạo cục bộ bằng lệnh chính thức hoặc tiếp nhận qua kênh chia sẻ tệp nội bộ đã phê duyệt.

---

## 3. Quy cách dữ liệu chuẩn tắc (Dataset Specifications)

- **Số dòng (Rows):** Đúng **307,511** dòng (khớp 100% số hồ sơ ứng viên trong `application_train.csv`).
- **Số cột (Columns):** Đúng **203** cột.
- **Khóa chính & Hạt dữ liệu (Primary Key & Grain):** Duy nhất cột `SK_ID_CURR`, đơn điệu tăng dần từ 100,002 đến 456,255. Mỗi dòng đại diện cho đúng một khách hàng ứng viên (`customer (SK_ID_CURR)`). Tuyệt đối không có dòng null hoặc trùng lặp.
- **Nhãn mục tiêu (TARGET):** Nhị phân `{0, 1}`, không có giá trị khuyết thiếu.
  * **Target = 0 (Khách hàng không vỡ nợ):** 282,686 hồ sơ (91.9271%).
  * **Target = 1 (Khách hàng gặp khó khăn trả nợ):** 24,825 hồ sơ (8.0729%).
  * **Tỷ lệ mất cân bằng (Imbalance Ratio):** Khoảng 11.39 : 1.
- **Phân nhóm 201 đặc trưng dự báo (Feature Groups):**
  1. `application_raw` (120 đặc trưng): Các trường thô sạch từ hồ sơ vay nộp lúc duyệt.
  2. `application_cleaning` (1 đặc trưng): Cờ dị biệt `DAYS_EMPLOYED_ANOM` đánh dấu giá trị sentinel 365243.
  3. `application_derived` (6 đặc trưng): `AGE_YEARS`, `AGE_GROUP`, `EMPLOYED_YEARS`, `CREDIT_TO_INCOME_RATIO`, `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_ANNUITY_RATIO`.
  4. `bureau` (20 đặc trưng): Tổng hợp từ `bureau.csv` và `bureau_balance.csv` (tiền tố `BUREAU_`).
  5. `previous_application` (15 đặc trưng): Tổng hợp từ `previous_application.csv` (tiền tố `PREV_`).
  6. `installments` (10 đặc trưng): Tổng hợp hành vi thanh toán trả góp từ `installments_payments.csv` (tiền tố `INSTAL_`).
  7. `pos_cash` (11 đặc trưng): Tổng hợp số dư POS/tiền mặt từ `POS_CASH_balance.csv` (tiền tố `POS_`).
  8. `credit_card` (18 đặc trưng): Tổng hợp thẻ tín dụng từ `credit_card_balance.csv` (tiền tố `CC_`).

---

## 4. Chính sách xử lý giá trị khuyết thiếu (Missingness Policy)

1. **Chính sách thiếu lịch sử (Missing-History Policy — 18 cột số đếm):**
   Khách hàng không có hồ sơ trong bảng lịch sử tương ứng được điền giá trị `0` (bảo toàn ngữ nghĩa nghiệp vụ: 0 lần vay, 0 hợp đồng phát sinh).
   - `BUREAU`: `BUREAU_CREDIT_COUNT`, `BUREAU_ACTIVE_COUNT`, `BUREAU_CLOSED_COUNT`, `BUREAU_BB_MONTH_COUNT`, `BUREAU_BB_DELINQUENT_MONTH_COUNT`, `BUREAU_BB_SEVERE_MONTH_COUNT`.
   - `PREV`: `PREV_APPLICATION_COUNT`, `PREV_APPROVED_COUNT`, `PREV_REFUSED_COUNT`.
   - `INSTAL`: `INSTAL_INSTALLMENT_COUNT`, `INSTAL_LATE_COUNT`, `INSTAL_UNDERPAYMENT_COUNT`.
   - `POS`: `POS_RECORD_COUNT`, `POS_CONTRACT_COUNT`, `POS_LATE_MONTH_COUNT`.
   - `CC`: `CC_RECORD_COUNT`, `CC_CONTRACT_COUNT`, `CC_LATE_MONTH_COUNT`.
2. **Bảo toàn giá trị khuyết thiếu tự nhiên (Rates, Amounts, Statistics):**
   Tất cả 56 cột tỷ lệ, số tiền nợ, và thống kê lịch sử (`_RATE`, `_MEAN`, `_MAX`, `_SUM`) giữ nguyên giá trị `NaN` thực tế nếu khách hàng không có lịch sử hoặc thiếu dữ liệu. Tuyệt đối không điền 0 giả tạo.
3. **Cột phân loại bị khuyết thiếu (Categorical Columns):**
   Cột nghề nghiệp `OCCUPATION_TYPE` có 96,391 giá trị khuyết thiếu (31.35%). TV1 và TV3 phải xử lý hoặc hiển thị nhóm này như một danh mục hợp lệ riêng biệt (`Missing/Unknown`), có tỷ lệ nợ xấu quan sát là 6.51% (thấp hơn trung bình danh mục). Tuyệt đối không được suy diễn hay gán ghép bất kỳ danh tính nhân khẩu/xã hội học nào (như người hưu trí, người thất nghiệp hay người phụ thuộc) cho nhóm thiếu thông tin nghề nghiệp chỉ dựa trên sự vắng mặt của dữ liệu.

---

## 5. Ràng buộc thời gian & Chống rò rỉ thông tin (As-Of-Time & Anti-Leakage Constraints)

- **Mốc thời gian quyết định:** Toàn bộ dữ liệu hồ sơ và tổng hợp lịch sử đều xảy ra trước hoặc tại thời điểm nộp đơn (`DAYS <= 0`, `MONTHS_BALANCE <= 0`).
- **Loại trừ tuyệt đối `application_test.csv`:** Tập dữ liệu kiểm thử (48,744 dòng, không có nhãn) tuyệt đối không được đưa vào tập huấn luyện hoặc dùng để tính toán phân phối dữ liệu.
- **Quy tắc Sentinel:** Giá trị 365,243 trong `DAYS_EMPLOYED` đã được chuyển thành `NaN` và lưu giữ trong cờ `DAYS_EMPLOYED_ANOM`. Cờ này là một chỉ báo chất lượng dữ liệu / bất thường; **tuyệt đối không diễn giải cờ này là người nghỉ hưu hay thất nghiệp**. Các giá trị hợp lệ khác của `DAYS_EMPLOYED` giữ nguyên biểu diễn số ngày có dấu (<=0).

---

## 6. Cảnh báo kỹ thuật & Giới hạn dữ liệu (Known Warnings & Limitations)

1. **16 đặc trưng gần như hằng số (Near-constant features >= 99.5%):**
   Gồm 14 cờ tài liệu `FLAG_DOCUMENT_*` và 2 cờ điện thoại `FLAG_MOBIL`, `FLAG_CONT_MOBILE`. TV1 có toàn quyền quyết định giữ lại hoặc loại bỏ các cột này trong bước lựa chọn đặc trưng (feature selection).
2. **Độ bao phủ thẻ tín dụng thấp (28.26%):**
   Bảng `credit_card_balance` chỉ có 86,905 khách hàng tham gia (chiếm 28.26%), dẫn đến 18 cột `CC_*` có tỷ lệ khuyết thiếu ~71.74%. Đây là đặc tính tiêu dùng tự nhiên của danh mục.
3. **Tương quan hạng Spearman mạnh giữa các biến quy mô tài chính:**
   `AMT_CREDIT` và `AMT_GOODS_PRICE` có hệ số tương quan hạng Spearman đạt 0.9849; `AMT_CREDIT` và `AMT_ANNUITY` đạt 0.8302. Ngưỡng $|\rho| \ge 0.70$ là ngưỡng mô tả báo cáo tương quan đơn điệu, không phải bằng chứng chứng minh đa cộng tuyến hay cơ sở để tự động loại bỏ đặc trưng. TV1 cần tự đánh giá độ dư thừa đặc trưng thông qua kiểm định trên fold huấn luyện, độ ổn định hệ số, VIF nếu phù hợp, kỹ thuật điều chuẩn (L2/Ridge), hoặc hiệu năng mô hình ngoại mẫu.
4. **Tính chất phi nhân quả của EDA:**
   Các biểu đồ và phân tích trong báo cáo EDA chỉ phản ánh mối liên hệ thống kê quan sát được trên tập dữ liệu lịch sử; tuyệt đối không diễn giải là quan hệ nhân quả.

---

## 7. Hướng dẫn chuyên biệt cho từng thành viên hạ nguồn

### 7.1. Hướng dẫn dành cho TV1 (Modeling & Machine Learning)

1. **Nguồn dữ liệu huấn luyện:** Đọc trực tiếp tệp `data/processed/cleaned_dataset.parquet`.
2. **Tách biệt định danh và nhãn:**
   - Cột `SK_ID_CURR` là khóa chính định danh (identifier), bắt buộc loại trừ khỏi ma trận đặc trưng `X`.
   - Cột `TARGET` là vector nhãn (label), tuyệt đối không đưa vào ma trận đặc trưng.
3. **Quy tắc phân tách tập dữ liệu (Train/Val/Test Split Rule):**
   - Phải thực hiện phân chia tập huấn luyện và kiểm thử (hoặc Stratified K-Fold CV) **trước khi fit bất kỳ bộ biến đổi nào** (SimpleImputer, StandardScaler, OneHotEncoder, TargetEncoder, SelectKBest, SMOTE).
   - Mọi bộ tiền xử lý chỉ được học tham số (fit) trên tập huấn luyện (`train fold`), sau đó chỉ thực hiện `transform` trên validation/test fold để chống rò rỉ thông tin phân phối (distribution leakage).
4. **Không sử dụng `application_test.csv`:** Tập dữ liệu kiểm thử cuộc thi không có nhãn chỉ dùng cho bước nộp bài cuối cùng (nếu có), không tham gia vào cross-validation.
5. **Coi kết quả DE-07 là mô tả thống kê:** Không tự động loại bỏ bất kỳ đặc trưng nào chỉ dựa trên hệ số tương quan cặp Spearman trong EDA.
6. **Bước tiếp theo cho TV2-DE-08:** TV2 cần nhận lại từ TV1 tệp dự báo xác suất (`y_pred_proba`) và nhãn thực tế trên validation/test folds sau khi huấn luyện xong mô hình để thực hiện kiểm định công bằng (Fairness Check) và ma trận nhầm lẫn theo ngưỡng (Threshold Confusion Matrix).

### 7.2. Hướng dẫn dành cho TV3 (Dashboard & Application)

1. **Nguồn dữ liệu hiển thị:** Đọc dữ liệu từ `data/processed/cleaned_dataset.parquet` và tra cứu mô tả từ `data/processed/data_dictionary.csv`.
2. **Bảo toàn hạt dữ liệu:** Giao diện dashboard phải giữ nguyên cấu trúc 1 dòng cho mỗi khách hàng `SK_ID_CURR`.
3. **Ngữ nghĩa giá trị khuyết thiếu:** Không tự ý chuyển đổi các giá trị thiếu thống kê thành 0 khi vẽ biểu đồ phân phối hoặc phân tích thuộc tính.
4. **Nhãn lịch sử so với Dự báo:** Cột `TARGET` hiện tại là kết quả quan sát lịch sử (khách hàng đã từng trễ hạn hay chưa), không phải là điểm số rủi ro dự báo thời gian thực của mô hình.
5. **Sử dụng trực tiếp đặc trưng chuẩn tắc `AGE_GROUP`:** `AGE_GROUP` đã được lưu trữ sẵn trong `cleaned_dataset.parquet` dưới dạng đặc trưng phái sinh chuẩn tắc (persisted canonical derived feature, thuộc nhóm `application_derived`). TV3 nên sử dụng trực tiếp cột `AGE_GROUP` chuẩn tắc này để phân nhóm hiển thị trên dashboard. Các ngưỡng phân nhóm được xây dựng từ `AGE_YEARS` theo quy tắc nửa mở `[0, 25, 35, 45, 55, 65, 120]` (với `right=False`, các nhãn `'Under 25'`, `'25-34'`, `'35-44'`, `'45-54'`, `'55-64'`, `'65+'`) là quy chuẩn cấu trúc có thẩm quyền (authoritative construction rule); việc tái phái sinh `AGE_GROUP` từ `AGE_YEARS` chỉ được phép dùng cho mục đích kiểm định tính nhất quán hoặc làm phương án dự phòng (fallback/validation), không phải là chỉ dẫn bàn giao chính.
6. **Không suy diễn nhân khẩu từ dữ liệu khuyết:** Nhóm nghề nghiệp bị thiếu (`Missing/Unknown`) tuyệt đối không được gán ghép danh tính xã hội suy diễn (như người hưu trí hay thất nghiệp).
7. **Tránh trình bày nhân quả:** Không trình bày các tương quan thống kê cấp nhóm như là quan hệ nhân quả.
8. **Các tính năng phụ thuộc model:** Các biểu đồ điểm số tín dụng (credit score), giải thích đóng góp đặc trưng (SHAP values), và bộ mô phỏng chấp thuận khoản vay (loan approval simulator) sẽ đợi kết quả xuất bản `data/processed/scored_dataset.parquet` từ TV1.

---

## 8. Lệnh tái tạo và Kiểm tra chất lượng (Verification Commands)

```powershell
# 1. Tái tạo toàn bộ pipeline dữ liệu chuẩn tắc (DE-05)
& .\.venv\Scripts\python.exe -m src.data.build_pipeline

# 2. Tái tạo từ điển dữ liệu và báo cáo chất lượng (DE-06)
& .\.venv\Scripts\python.exe -m src.data.quality_report

# 3. Tái tạo toàn bộ biểu đồ và báo cáo EDA (DE-07)
& .\.venv\Scripts\python.exe -m src.data.eda

# 4. Chạy kiểm thử tự động toàn diện
& .\.venv\Scripts\python.exe -m pytest tests -q
```
