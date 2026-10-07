# Audit sửa measure Huy trong PBIP Nghia

Ngày cập nhật: 2026-10-08. Trạng thái: **tham chiếu tĩnh và DAX chạy trong Power BI Desktop PASS; render từng visual vẫn cần nghiệm thu**.

Đính chính audit trước: các trang Huy **đã được chuyển thủ công** vào `nghia.Report/definition/pages/`. Vì vậy `Huydepzai.Report/definition/pages/` trống là trạng thái mong đợi, không phải lý do chặn việc sửa measure. Bản audit trước đã kết luận sai điểm này.

## 1. Source / Target

- Source công thức: `Huydepzai.SemanticModel/definition/tables/%2AMeasure table.tmdl`.
- Master được sửa: `nghia.pbip` → `nghia.Report` → `nghia.SemanticModel`.
- Backup mới trước sửa: `_merge_backup/20261008-003435/` gồm `nghia.Report`, `nghia.SemanticModel` và `nghia.pbip`. Backup trước đó được giữ nguyên.
- Power BI Desktop đã đóng khi sửa PBIR/TMDL.

## 2. Pages imported

Không nhập lại trang. Master vẫn có 12 page entries và 81 visual JSON. Các trang chứa binding Huy được sửa tại chỗ: Portfolio Overview, Portfolio Trends & Purpose, Borrower Risk Profile và TT_V11.

## 3. Tables imported

Không tạo/copy bảng dữ liệu. Master đã có `application_funnel`, `cleaned_dataset`, `dim_date`, `dim_state` cùng `fact_evaluated_loan` và ba bảng ML-LC-09. Không chép nguyên `*Measure table` vì sẽ trùng `Total Loans` và xung đột `Observed Default Rate`.

## 4. Measures imported / reused

Tất cả measure mới nằm trong bảng `cleaned_dataset`:

- `Observed Default Rate — Portfolio`: giữ DAX Huy, đếm default trên `cleaned_dataset[target]`, N < 100 trả BLANK; đổi tên để phân biệt với TV1.
- `Total Funded Amount` = `SUM(cleaned_dataset[loan_amnt])`.
- `Average FICO Score` = `AVERAGE(cleaned_dataset[fico_avg])`.
- `Average Loan Amount` = `AVERAGE(cleaned_dataset[loan_amnt])`.
- `Top Purpose` = `"Debt Consolidation"` (hằng số gốc của Huy).
- `Peak Year` = `2015` (hằng số gốc của Huy).
- `Label Peak Year`: giữ `IF(SELECTEDVALUE(dim_date[year]) = 2015, FORMAT([Total Loans], "0.00M") & " (Peak)", BLANK())`; hiện không thấy visual dùng measure này.

`Total Loans` của Huy và Nghia đều là `COUNTROWS(cleaned_dataset)` với format `0`; dùng lại measure đã có trong `cleaned_dataset`. Các format string gốc của bảy measure được giữ, kể cả định dạng tiền `\$` của Huy. Đây là format trình bày nguồn, không xác nhận đơn vị tiền của dữ liệu.

## 5. Calculated columns imported

Không thêm calculated column. Những field cần cho DAX mới (`target`, `loan_amnt`, `fico_avg`, `dim_date[year]`) đã có trong target.

## 6. Relationships imported

Không thay relationship. Các trang Huy đã sử dụng các bảng trong model target; task này chỉ sửa measure binding.

## 7. Resources / bookmarks imported

Không thêm resource hoặc bookmark. Target không có `definition/bookmarks/` và không thấy action bookmark trong imported pages. Bookmark nguồn Huy không được nhập trong task này; không còn bookmark nào ở target tham chiếu `*Measure table`.

## 8. Conflicts và visual binding

`Observed Default Rate` của TV1 trên `fact_evaluated_loan` giữ nguyên. Version Portfolio dùng `cleaned_dataset` và có gate N ≥ 100, vì vậy visual Huy được chuyển sang `cleaned_dataset[Observed Default Rate — Portfolio]`. Các measure Huy còn lại trỏ về `cleaned_dataset`; `Total Loans` trỏ về bản canonical sẵn có.

Trước sửa có 18 visual JSON chứa `*Measure table`; trong đó 20 expression Measure thực sự thiếu bảng nguồn, và một card (`e85f9955dcdae194e6fa`) chỉ có selector metadata cũ. Các visual đã sửa:

- Portfolio Overview: `13521b87db3056e4279f` (Total Loans + Observed Default Rate dùng tô màu bản đồ); `5dc5245623a5789431a8` (Average FICO Score); `99fbfeb01668ee67e68d` (Total Loans); `acf45ee8b7a3a5bd3086` (Total Funded Amount); `c2644a24da8debd50f6f` (Observed Default Rate).
- Portfolio Trends & Purpose: `109f3649907db9bb50bb` (Observed Default Rate); `1eb081856520dcc85b12` (Total Loans); `25151bed10a138d36846` (Peak Year và metadata Total Funded Amount); `311442f8ad8c8d8ac47a` (Observed Default Rate + Total Loans); `8c1bfb565c7c639ac05f` (Total Funded Amount); `dd52aed9c09245a16822` (Top Purpose + sort/metadata Total Funded Amount).
- Borrower Risk Profile: `607c325aca8984020df8` (Total Loans); `31ee08e9be5979bf1b63` (Observed Default Rate); `e85f9955dcdae194e6fa` (Average Loan Amount); `9f46a614a7ecfc316174` (Average Loan Amount); `7c128f7b69e10f4fae3c` (Average FICO Score).
- TT_V11: `634f279d1172c8298a40` (Total Loans); `3f7bcf1c6e9c79858b0a` (Observed Default Rate).

Card `e85f9955dcdae194e6fa` trước đó ghi “GIÁ TRỊ VAY TRUNG BÌNH” nhưng query lấy `annual_inc` và selector lại chỉ `Average Loan Amount`. Query/sort nay dùng đúng measure Average Loan Amount, phù hợp nhãn card. Các property/queryRef/metadata/sort/conditional-color bindings cũ của 18 visual được đồng bộ theo measure mới.

## 9. Validation results

- Quét 93 file page/visual JSON: 89 field references phân biệt theo file/kind/table/name, **0 missing table/field/measure** sau sửa; trước sửa có 20 missing expression references tới `*Measure table`.
- Không còn chuỗi `*Measure table` trong target report/model; không có source path `D:\Huy\...` trong target.
- Không đổi số trang/visual; không sửa các trang TV1 V02–V06 và `4. Annalysis RISK` (so hash với backup).
- `fact_evaluated_loan.tmdl` và measure TV1 không đổi. `nghia.pbip` và binding `definition.pbir` vẫn dùng master.
- Parse 101 file JSON/PBIR/PBIP, kiểm tra cấu trúc và DAX dependencies tĩnh: PASS. Mở master bằng Power BI Desktop, model local load được; truy vấn DAX gọi cả 8 measure Huy (kể cả `Total Loans` dùng lại), thêm `fact_evaluated_loan[Observed Default Rate]` của TV1: PASS. Kết quả smoke: Total Loans 1.345.350, Portfolio default rate khoảng 0,19965, Average FICO 698,185, Average Loan Amount 14.420, Top Purpose “Debt Consolidation”, Peak Year 2015; `Label Peak Year` trả BLANK khi không chọn năm, đúng DAX nguồn. Desktop đã đóng sau kiểm tra, không Save lại PBIR.
- Chưa kiểm tra screenshot/render của từng visual, refresh mọi data source hoặc đối chiếu aggregate với parquet; không gọi các bước đó PASS.

## 10. Remaining manual checks

Mở `D:/ttdltq/reports/figures/dashboard/nghia.pbip` trong Power BI Desktop. Kiểm tra KPI cards, xu hướng, mục đích vay, bản đồ và TT_V11; đặc biệt màu bản đồ theo Portfolio default rate và card Average Loan Amount. Đối chiếu số liệu từng visual với source population trước khi diễn giải. `Top Purpose` và `Peak Year` là hằng số Huy, không tự đổi theo filter; cần giữ giới hạn này khi trình bày. Nếu Desktop báo lỗi DAX/visual, dùng backup mới và không coi nghiệm thu runtime là PASS.
