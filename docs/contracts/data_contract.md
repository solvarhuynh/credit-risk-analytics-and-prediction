# Giao ước dữ liệu — TV2 → TV1 và TV3 (Phiên bản 1.1 — DE-06)

## 1. Tệp bàn giao chính thức (Deliverables)

- `data/processed/cleaned_dataset.parquet`: Tập dữ liệu chuẩn tắc gắn nhãn phục vụ huấn luyện (307,511 dòng, 203 cột, 1 dòng trên 1 `SK_ID_CURR`).
  - SHA-256 (TV2-DE-FIX-01 rerun): `6460999371297ff2f83418a8341b0c85d4a2e4dc6c29b29e793edd2a0c755c96`
- `data/processed/data_dictionary.csv`: Từ điển dữ liệu chuẩn tắc (203 dòng, 22 cột) mô tả chi tiết toàn bộ đặc trưng.
  - SHA-256 (TV2-DE-FIX-01 rerun): `a588feff89b1e5be684fea77ce8add79b0caa27c4c8a87e41f3be3b711abc151`
- `reports/data_quality_report.md`: Báo cáo kiểm định chất lượng dữ liệu chuẩn tắc (19 phần toàn diện).
  - SHA-256 (TV2-DE-FIX-01 rerun): `2720572c74a48646412fc165c0ce46a9f56c81ac5c9b60361e1bb90157e0fd38`

## 2. Cột tối thiểu bắt buộc (Mandatory Columns)

| Nhóm | Cột |
| --- | --- |
| Khóa/nhãn | `SK_ID_CURR`, `TARGET` |
| Khoản vay | `AMT_INCOME_TOTAL`, `AMT_CREDIT`, `AMT_ANNUITY`, `AMT_GOODS_PRICE` |
| Nhân khẩu | `CODE_GENDER`, `NAME_CONTRACT_TYPE`, `AGE_YEARS`, `AGE_GROUP` |
| Derived | `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_INCOME_RATIO`, `EMPLOYED_YEARS`, `DAYS_EMPLOYED_ANOM` |
| Aggregate | 74 đặc trưng tiền tố nguồn: `BUREAU_`, `PREV_`, `INSTAL_`, `POS_`, `CC_` |

## 3. Cấu trúc từ điển dữ liệu (Data Dictionary Schema — 22 cột)

Toàn bộ 203 cột trong tập dữ liệu chuẩn tắc được mô tả tuần tự theo đúng 22 trường:
`position`, `column_name`, `physical_dtype`, `logical_type`, `role`, `feature_group`, `source_table`, `source_columns`, `source_grain`, `canonical_grain`, `transformation_formula`, `unit`, `description`, `missing_value_meaning`, `valid_values_or_range`, `nullable`, `missing_count`, `missing_rate`, `unique_count`, `as_of_time_rule`, `leakage_note`, `modeling_note`.

## 4. Vai trò và Nguồn gốc đặc trưng (Roles & Provenance)

- **Định danh (`role = identifier`):** Duy nhất `SK_ID_CURR`. Bắt buộc loại trừ khỏi ma trận đặc trưng huấn luyện `X`.
- **Nhãn mục tiêu (`role = target`):** Duy nhất `TARGET` ({0, 1}). Tuyệt đối không đưa vào ma trận đặc trưng.
- **Đặc trưng dự báo (`role = feature`):** Đúng 201 đặc trưng (120 thô, 1 cờ sentinel, 6 phái sinh hồ sơ, 74 tổng hợp lịch sử).
- **Hạt dữ liệu chuẩn tắc (`canonical_grain`):** Cấp khách hàng ứng viên `customer (SK_ID_CURR)`.

## 5. Xử lý khuyết thiếu lịch sử (Missing-History Semantics)

- **18 cột số đếm đã phê duyệt:** Khách hàng không có lịch sử được điền giá trị `0` (nghiệp vụ: 0 khoản vay/giao dịch phát sinh).
- **56 cột tỷ lệ, số tiền và thống kê:** Khách hàng không có lịch sử giữ nguyên giá trị khuyết thiếu thực tế `NaN`, tuyệt đối không điền 0 giả tạo.

## 6. Tính thời điểm và Chống rò rỉ (As-Of-Time & Leakage Prevention)

- Toàn bộ dữ liệu lịch sử phải phát sinh trước thời điểm nộp đơn xét duyệt (`DAYS <= 0`).
- Bảng `bureau_balance` được tổng hợp 2 tầng qua `SK_ID_BUREAU` trước khi kết nối vào khách hàng.
- Bảng `installments_payments` hợp nhất bảo toàn 653,483 dòng trả góp từng phần, không nhân đôi nghĩa vụ nợ.
- Tập dữ liệu kiểm thử `application_test.csv` (48,744 dòng) bị loại trừ tuyệt đối khỏi tập huấn luyện.

## 7. Cổng chất lượng dữ liệu (Quality Gates)

1. `SK_ID_CURR` không null và duy nhất (307,511 dòng); `TARGET` nhị phân {0: 282,686; 1: 24,825}.
2. Phép nối trái 1-to-1 tuần tự không làm mất hoặc nhân đôi dòng; không có cột hậu tố `_x`, `_y`.
3. `DAYS_EMPLOYED == 365243` được chuyển thành `NaN` và lưu giữ cờ bất thường `DAYS_EMPLOYED_ANOM`.
4. Tuyệt đối không chứa `+inf`, `-inf`, sentinel **dạng chuỗi** (`NULL`, `null`, `N/A`, `NA`, `-999`), hoặc cột trùng lặp. Giá trị số `-999` trong trường ngày tương đối hợp lệ (`DAYS_*`) được giữ nguyên với nghĩa 999 ngày trước thời điểm nộp đơn; đây không phải quy tắc sentinel số toàn cục.
5. Mẫu số bằng 0 trong các phép chia tỷ lệ cho kết quả `NaN`, không sinh vô cực.
6. 10 đặc trưng tỷ lệ có biên (`BOUNDED_RATE_COLUMNS`) được kiểm tra chặt trong `[0.0, 1.0]`. Các tỷ lệ tài chính không bị chặn trên (`CREDIT_TO_INCOME_RATIO`, `CC_UTILIZATION_MEAN`,...) được phép lớn hơn 1 hợp lệ.

## 7.1. Ngữ nghĩa thời điểm thanh toán trả góp

- `INSTAL_LATE_COUNT` chỉ đếm kỳ có đủ cả `DAYS_ENTRY_PAYMENT` và `DAYS_INSTALMENT`; kỳ thiếu một trong hai mốc thời gian là chưa biết trạng thái đúng hạn, không được coi là trả đúng hạn.
- `INSTAL_LATE_RATE` dùng mẫu số là số kỳ có đủ hai mốc thời gian. Nếu khách hàng không có kỳ nào quan sát được đầy đủ, tỷ lệ là `NaN`.
- `DAYS_EMPLOYED == 365243` là sentinel số đã được phê duyệt duy nhất trong cột `DAYS_EMPLOYED`: được chuyển thành `NaN` và giữ cờ `DAYS_EMPLOYED_ANOM`. Các sentinel ngày tài liệu đã định nghĩa riêng ở `previous_application` vẫn được xử lý theo DE-02.
## 8. Hướng dẫn tiền xử lý cho TV1 (Downstream Preprocessing Rule)

TV1 phải thực hiện fit toàn bộ các bộ biến đổi (`OneHotEncoder`, `OrdinalEncoder`, `SimpleImputer`, `StandardScaler`, v.v.) **duy nhất trên train fold** của từng fold cross-validation, sau đó mới transform trên validation/test folds để chống rò rỉ thông tin phân phối (data leakage).

## 9. Hướng dẫn cho TV3 (Dashboard & Application Handoff)

TV3 sử dụng `data/processed/cleaned_dataset.parquet` và `data/processed/data_dictionary.csv` để tra cứu nhãn hiển thị, phân loại, ngữ nghĩa đặc trưng và miền giá trị hợp lệ trên giao diện. Đối với các biểu đồ và tính năng liên quan đến điểm số dự báo rủi ro (risk score) và phân loại decile, TV3 sẽ đợi sản phẩm `data/processed/scored_dataset.parquet` từ TV1.
