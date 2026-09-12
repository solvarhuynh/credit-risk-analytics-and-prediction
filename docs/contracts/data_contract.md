# HỢP ĐỒNG DỮ LIỆU CHUẨN HÓA (DATA CONTRACT)
**Dự án:** Phân tích Rủi ro Tín dụng & Khả năng Vỡ nợ Khách hàng Cá nhân  
**Môn học:** Tương tác Dữ liệu Trực quan  
**Phiên bản Schema:** v1.0 (Official Release)  
**Ngày hiệu lực:** 2026-09-12  

---

## 1. CÁC BÊN THAM GIA & PHẠM VI TRÁCH NHIỆM
* **Bên phát hành (Data Producer):** Thành viên 2 — Phụ trách Data Engineering & Pipeline.
* **Bên tiếp nhận chính (Data Consumer - Modeling):** Thành viên 1 — Phụ trách Modeling & Machine Learning.
* **Bên tiếp nhận thứ cấp (Data Consumer - Visualization):** Thành viên 3 — Phụ trách Power BI Dashboard.
* **Mục đích:** Thiết lập giao ước kỹ thuật bất biến giữa tầng dữ liệu và tầng mô hình/trực quan hóa, ngăn chặn hiện tượng phá vỡ cấu trúc bảng (schema drift), sai lệch phân phối và rò rỉ dữ liệu (data leakage).

---

## 2. THÔNG SỐ TỆP BÀN GIAO & RÀNG BUỘC CỐT LÕI
* **Tệp bàn giao chính thức:** `data/processed/cleaned_dataset.csv`
* **Từ điển dữ liệu đi kèm:** `data/processed/data_dictionary.csv`
* **Định dạng:** CSV (Encoding UTF-8, phân cách bằng dấu phẩy `,`).
* **Đơn vị phân tích (Grain / Unit of Analysis):** Một dòng đại diện cho **duy nhất 1 hồ sơ đề nghị vay vốn** của khách hàng cá nhân tại thời điểm thẩm định.
* **Khóa chính duy nhất (Primary Key):** `SK_ID_CURR` (`int64`). Bắt buộc kiểm tra: `df['SK_ID_CURR'].is_unique == True`.
* **Kích thước dòng bắt buộc:** Chính xác **307,511 dòng** (bảo toàn 100% số lượng hồ sơ từ bảng `application_train.csv` gốc, tuyệt đối không bị nhân bản hay rơi rụng dòng qua các phép Join).
* **Biến mục tiêu (Target Variable):** `TARGET` (`int8`), giá trị nhị phân {0, 1}:
  * `0`: Non-default (Khách hàng trả nợ tốt, chiếm đa số ~91.93%).
  * `1`: Default (Khách hàng vỡ nợ/quá hạn nghiêm trọng, chiếm thiểu số ~8.07%).
  * Ràng buộc: `df['TARGET'].isna().sum() == 0`.

---

## 3. DANH MỤC SCHEMA CHI TIẾT TỪNG NHÓM ĐẶC TRƯNG

### Nhóm A: Đặc trưng định danh & Nhân khẩu học
| Tên cột | Kiểu dữ liệu | Bảng nguồn | Quy tắc xử lý làm sạch | Ý nghĩa nghiệp vụ |
| :--- | :---: | :--- | :--- | :--- |
| `SK_ID_CURR` | `int64` | `application_train` | Khóa chính duy nhất, không null | Mã định danh hồ sơ khách hàng |
| `CODE_GENDER` | `category` | `application_train` | Lọc bỏ 4 dòng mang giá trị 'XNA' | Giới tính khách hàng ('M', 'F') |
| `FLAG_OWN_CAR` | `category` | `application_train` | Mã hóa nhị phân ('Y', 'N') | Khách hàng có sở hữu xe ô tô không |
| `FLAG_OWN_REALTY` | `category` | `application_train` | Mã hóa nhị phân ('Y', 'N') | Khách hàng có sở hữu bất động sản không |
| `CNT_CHILDREN` | `int32` | `application_train` | Cắt tỉa ngoại lai > 10 | Số lượng con cái của khách hàng |
| `NAME_EDUCATION_TYPE` | `category` | `application_train` | Chuẩn hóa chuỗi danh mục | Trình độ học vấn cao nhất |
| `NAME_FAMILY_STATUS` | `category` | `application_train` | Chuẩn hóa chuỗi danh mục | Tình trạng hôn nhân |
| `NAME_HOUSING_TYPE` | `category` | `application_train` | Chuẩn hóa chuỗi danh mục | Loại hình nhà ở (Sở hữu/Thuê/Ở chung) |
| `REGION_RATING_CLIENT` | `int8` | `application_train` | Giá trị phân loại {1, 2, 3} | Đánh giá xếp hạng rủi ro vùng sinh sống |
| `AGE_YEARS` | `float32` | Derived (`DAYS_BIRTH`) | `= DAYS_BIRTH / -365.25` | Tuổi thực tế của khách hàng (theo năm) |
| `EMPLOYED_YEARS` | `float32` | Derived (`DAYS_EMPLOYED`) | Xử lý dị biệt 365243 -> NaN | Số năm thâm niên công tác thực tế |
| `DAYS_EMPLOYED_ANOM` | `int8` | Derived flag | `= 1` nếu `DAYS_EMPLOYED == 365243` | Cờ nhận diện khách nghỉ hưu/thất nghiệp |

### Nhóm B: Đặc trưng khoản vay & Năng lực tài chính
| Tên cột | Kiểu dữ liệu | Bảng nguồn | Ràng buộc giá trị | Ý nghĩa nghiệp vụ |
| :--- | :---: | :--- | :--- | :--- |
| `AMT_INCOME_TOTAL` | `float64` | `application_train` | > 0, xử lý ngoại lai cực trị | Tổng thu nhập hàng năm của khách hàng |
| `AMT_CREDIT` | `float64` | `application_train` | > 0 | Số tiền tín dụng được cấp theo hợp đồng |
| `AMT_ANNUITY` | `float64` | `application_train` | Impute median cho lượng nhỏ missing | Số tiền phải trả góp định kỳ hàng năm |
| `AMT_GOODS_PRICE` | `float64` | `application_train` | > 0 | Giá trị tài sản/hàng hóa tiêu dùng được tài trợ |
| `NAME_CONTRACT_TYPE` | `category` | `application_train` | Cash loans / Revolving loans | Loại hình hợp đồng tín dụng |

### Nhóm C: Chỉ số tài chính phái sinh (Domain Feature Engineering)
| Tên cột | Kiểu dữ liệu | Công thức tính toán | Ý nghĩa kinh tế & Quản trị rủi ro |
| :--- | :---: | :--- | :--- |
| `DEBT_TO_INCOME_RATIO` | `float32` | `AMT_CREDIT / AMT_INCOME_TOTAL` | Tỷ lệ đòn bẩy nợ trên thu nhập (DTI) |
| `ANNUITY_TO_INCOME_RATIO` | `float32` | `AMT_ANNUITY / AMT_INCOME_TOTAL` | Áp lực dòng tiền trả góp trên thu nhập hàng năm |
| `CREDIT_TO_GOODS_RATIO` | `float32` | `AMT_CREDIT / AMT_GOODS_PRICE` | Tỷ lệ tài trợ vốn tín dụng so với giá trị món hàng |
| `EMPLOYED_TO_AGE_RATIO` | `float32` | `EMPLOYED_YEARS / AGE_YEARS` | Tỷ lệ thời gian lao động tích lũy trên tuổi đời |
| `AGE_GROUP` | `category` | Binned: `<25`, `25-34`, `35-49`, `50-64`, `65+` | Nhóm tuổi nhân khẩu học phục vụ Slicers |

### Nhóm D: Điểm tín nhiệm bên ngoài (External Risk Scores)
| Tên cột | Kiểu dữ liệu | Bảng nguồn | Tỷ lệ khuyết thiếu | Giải pháp tiền xử lý cam kết |
| :--- | :---: | :--- | :---: | :--- |
| `EXT_SOURCE_1` | `float32` | `application_train` | ~56.4% | Giữ nguyên NaN, impute median trên Train fold |
| `EXT_SOURCE_2` | `float32` | `application_train` | ~0.2% | Giữ nguyên NaN, impute median trên Train fold |
| `EXT_SOURCE_3` | `float32` | `application_train` | ~19.8% | Giữ nguyên NaN, impute median trên Train fold |
| `EXT_SOURCES_MEAN` | `float32` | Derived | Tính trung bình các score khả dụng | Chỉ số tổng hợp sức mạnh tín nhiệm ngoài |

### Nhóm E: Đặc trưng lịch sử tổng hợp từ bảng phụ (Multi-Table Aggregates)
*Nguyên tắc: Toàn bộ bảng 1-nhiều được GroupBy theo `SK_ID_CURR` trước khi Left Join vào bảng chính.*
| Tên cột | Kiểu | Bảng nguồn gốc | Thuộc đo tổng hợp (Aggregation) | Ý nghĩa nghiệp vụ |
| :--- | :---: | :--- | :--- | :--- |
| `BUREAU_LOAN_COUNT` | `int32` | `bureau.csv` | `count(SK_ID_BUREAU)` (gán 0 nếu null) | Tổng số khoản vay tại các TCTD khác |
| `BUREAU_TOTAL_DEBT` | `float64` | `bureau.csv` | `sum(AMT_CREDIT_SUM_DEBT)` | Tổng dư nợ hiện tại tại các TCTD khác |
| `BUREAU_OVERDUE_COUNT` | `int32` | `bureau_balance.csv` | `sum(STATUS in ['1','2','3','4','5'])` | Số tháng phát sinh nợ quá hạn ngoài hệ thống |
| `PREV_APP_COUNT` | `int32` | `previous_application.csv` | `count(SK_ID_PREV)` (gán 0 nếu null) | Số lần từng nộp đơn vay tại Home Credit |
| `PREV_APPROVAL_RATE` | `float32` | `previous_application.csv` | `mean(NAME_CONTRACT_STATUS == 'Approved')` | Tỷ lệ hồ sơ được phê duyệt trong quá khứ |
| `INSTAL_LATE_PAY_COUNT` | `int32` | `installments_payments.csv` | `count(DAYS_ENTRY_PAYMENT > DAYS_INSTALMENT)` | Số lần thanh toán trễ hạn kỳ trả góp |
| `INSTAL_UNDERPAY_COUNT` | `int32` | `installments_payments.csv` | `count(AMT_PAYMENT < AMT_INSTALMENT)` | Số lần thanh toán thiếu tiền kế hoạch |
| `POS_DPD_MAX` | `int32` | `POS_CASH_balance.csv` | `max(SK_DPD)` | Số ngày quá hạn lớn nhất tại POS |

---

## 4. QUY CHUẨN KIỂM TOÁN CHẤT LƯỢNG (DATA QUALITY ASSERTIONS)
Trước khi bàn giao chính thức, Thành viên 2 phải xác thực 6 ràng buộc tự động:
1. `len(df) == 307511` (Toàn vẹn số dòng).
2. `df['SK_ID_CURR'].is_unique == True` (Không trùng lặp khóa chính).
3. `df['TARGET'].isin([0, 1]).all() and df['TARGET'].isna().sum() == 0` (Target sạch).
4. Không chứa chuỗi rác như 'NULL', 'None', '-999', ''. Giá trị thiếu mang dạng `np.nan`.
5. `(df['DAYS_EMPLOYED'] == 365243).sum() == 0` (Dị biệt đã bóc tách vào `DAYS_EMPLOYED_ANOM`).
6. `np.isinf(df.select_dtypes(include=np.number)).sum().sum() == 0` (Không có giá trị vô hạn).

---

## 5. CAM KẾT BẢO ĐẢM KHÔNG RÒ RỈ DỮ LIỆU (LEAKAGE WARRANTY)
* **Temporal Validity Check:** Thành viên 2 cam kết 100% các cột trong hợp đồng này chỉ đại diện cho thông tin có sẵn tại thời điểm khách hàng nộp đơn vay.
* Tuyệt đối không sử dụng thông tin phát sinh sau khi khoản vay hiện tại được giải ngân.

---

## 6. NÂNG CẤP PHIÊN BẢN & XỬ LÝ SỰ CỐ
* Mọi nhu cầu đổi tên cột, thêm feature hoặc đổi công thức phải nâng lên `schema_v1.1`.
* Nếu phát hiện lỗi cấu trúc, Thành viên 1 và Thành viên 3 có quyền từ chối tiếp nhận và yêu cầu sửa script `build_pipeline.py`.
