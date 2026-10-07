# Thiết lập TV3 — Dashboard

Trạng thái Master PBIP làm việc: `nghia.pbip` chứa bảng dữ liệu TV2, model/visual TV1 và các trang Huy được chuyển thủ công. Ngày 2026-10-08 đã sửa measure dependency của Huy. Bản hiện tại đã rút còn **4 trang vật lý** theo `docs/tasks/dashboard-visual-plan.md`, sửa date relationship, KPI, V04 và **V01 từ Shape map sang native bubble Map**; kiểm tra cấu trúc PBIR **PASS**, model Desktop nạp được và DAX state audit **PASS**. **Render Map từng bubble và các visual khác vẫn cần nghiệm thu trực quan**. Map V01 vẫn phụ thuộc cài đặt Security của Desktop/tenant, không thể tự bật bằng PBIR.

## Mở và nghiệm thu bản bốn trang

1. Mở `D:/ttdltq/reports/figures/dashboard/nghia.pbip` bằng Power BI Desktop khi không có phiên Desktop khác đang giữ project; kiểm tra chỉ có bốn tab `01 · Tổng quan`, `02 · Xu hướng`, `03 · Hồ sơ vay`, `04 · Rủi ro & EL`. Backup trước dọn: `reports/figures/dashboard/_merge_backup/20261008-four-page-polish/` (gồm 8 trang cũ và placeholder V04 để khôi phục).
2. Nếu Map V01 báo *Map and filled map visuals aren't enabled for your org*: vào **File → Options and settings → Options → Global → Security → Use Map and Filled Map visuals**, bật và khởi động lại Desktop. Checkbox này chỉ là cài đặt local của file/ứng dụng; nếu đã có dấu kiểm mà canvas vẫn báo lỗi như ảnh kiểm tra ngày 2026-10-08, chính sách tenant vẫn đang chặn. Khi đó nhờ Power BI/Fabric tenant admin vào **Admin portal → Tenant settings → Map and filled map visuals**, bật cho toàn tổ chức hoặc security group của tài khoản rồi **Apply**; sau đó đăng xuất/đăng nhập và mở lại Desktop. Không có quyền admin thì V01 còn BLOCKED; không dùng vị trí giả.
3. Trong **Model view → Manage relationships**, xác nhận `dim_date.date (1) → cleaned_dataset.issue_d (*)`, một chiều. TMDL dùng đúng hướng kỹ thuật `fromColumn: cleaned_dataset.issue_d` (Many), `toColumn: dim_date.date` (One), không ghi cardinality override. Sau đó trên trang 02, chọn các năm khác nhau trong slicer: tổng khoản vay và tỷ lệ default phải đổi; đối chiếu nguyên dữ liệu `cleaned_dataset` ở dưới. Kiểm tra Top Purpose và Peak Year không còn là hằng số khi filter thay đổi.
4. Trên trang 03, xác nhận bốn KPI không rỗng/trùng logic: giá trị vay TB, số khoản vay có kết quả, thu nhập năm TB, FICO TB. V04 nằm góc dưới bên phải và dùng `fact_evaluated_loan`, không đọc như cùng population với các KPI `cleaned_dataset`.
5. Kiểm tra style/nền/trang điều hướng giống trang 04, tooltip V11 có số khoản vay, V02–V06 ở trang 04 còn nguyên. Lưu bằng **File → Save** chỉ sau khi tự kiểm tra render. GUI tương đương mọi thay đổi ghi tại `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`.

V01 state audit chi tiết: `reports/figures/dashboard/v01_state_audit.md`. Audit bằng DAX xác nhận 51 state/state-equivalent có dữ liệu, 269.070 evaluated loans, tổng theo state khớp tổng population; IA có 1 khoản vay/0 default và không phải missing state. Không coi blank referential member của dimension (0 loan) là state.

Đối chiếu dữ liệu read-only đã chạy: `cleaned_dataset` có 1.345.350 khoản vay, 12 năm 2007–2018; năm 2015 có 375.546 khoản vay, năm 2007 có 251, tỷ lệ default theo năm khác nhau. `dim_date.date` có 4.238 ngày duy nhất và bao phủ toàn bộ `issue_d`. Kiểm tra này **không thay thế** DAX/render validation trong Desktop.

Các bước **EXPECTED / NOT YET VERIFIED AFTER DATASET RESET**:

1. Đọc `docs/contracts/data_contract.md`, `model_contract.md` và task TV3.
2. Không thay đổi visual families đã LOCKED; đọc Phase 2 sign-off và đóng các blocker data-model trước khi build.
3. Theo 4 trang trong plan: Tổng quan danh mục (KPI, V08, V01); Xu hướng & Mục đích vay (V07, V09); Hồ sơ người vay (V04, V11, V10, V12); Rủi ro & Expected Loss (KPI, V02, V03, V05, V06). Dự đoán cá nhân là ứng dụng Dash bên ngoài, không phải trang Power BI thứ năm.
4. Chỉ sau review mới thiết kế Power BI model với các fact/dimensions, relationships và measures thực sự cần; không import artifacts toàn bộ một cách máy móc.
5. Xác minh data types/mapping thực tế cho `state_code` và `country` trước map; tạo filters, tooltip, drill-down, cross-filter và navigation chỉ khi chúng giúp trả lời câu hỏi phân tích.
6. Dùng prediction sources sau khi TV1 handoff contract/artifacts; individual demo không phải official loan approval system.

Kiểm tra simulator contract:

```powershell
python -c "from src.dashboard.simulator_engine import simulator_status; print(simulator_status('models/full_inference_pipeline.joblib'))"
```

Ý nghĩa: hiện phải báo `BLOCKED / WAITING FOR TV1 ARTIFACT`; không phải lỗi migration.

## Phạm vi trách nhiệm sau reorganize

TV3 là primary owner của Master Power BI artifact, trực tiếp sở hữu V01 và V10–V12, đồng thời tích hợp V01–V12, relationships, layout, theme, slicers, filters, drill-down, tooltip, cross-filter, navigation và demo. TV1/TV2 có thể gửi prototype/spec local; chỉ TV3 tích hợp Master PBIX. TV1 cross-review V01 và các model-facing visuals khi cần; TV2 review data semantics.

## Mở và kiểm tra measure Huy trong master

- **Mục đích:** kiểm tra 7 measure Portfolio mới và 18 visual Huy đã đổi binding trong `reports/figures/dashboard/nghia.pbip`.
- **Điều kiện:** có Power BI Desktop; các source của semantic model trỏ tới dữ liệu local trong `D:/ttdltq/data/`. Source DAX gốc là `reports/figures/dashboard/Huydepzai.SemanticModel/definition/tables/%2AMeasure table.tmdl`; target TMDL là `reports/figures/dashboard/nghia.SemanticModel/definition/tables/cleaned_dataset.tmdl`.
- **Thao tác:** mở `D:/ttdltq/reports/figures/dashboard/nghia.pbip` bằng Power BI Desktop. Kiểm tra Model/Data pane có `cleaned_dataset[Total Loans]`, `cleaned_dataset[Observed Default Rate — Portfolio]` và sáu measure Portfolio khác; kiểm tra Portfolio Overview, Portfolio Trends & Purpose, Borrower Risk Profile và TT_V11 không còn dấu field lỗi. Hướng dẫn tạo/đổi field bằng GUI ở `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`.
- **Output:** master PBIP vẫn là `nghia.pbip`; không tạo artifact dự báo hay parquet mới. Backup trước sửa: `reports/figures/dashboard/_merge_backup/20261008-003435/`.
- **Validation/giới hạn:** kiểm tra JSON/field references tĩnh PASS; truy vấn DAX trên model local trong Power BI Desktop PASS. Render từng visual và refresh tất cả nguồn chưa được kiểm tra. Không đánh đồng Portfolio default rate trên `cleaned_dataset` với observed default rate TV1 trên `fact_evaluated_loan`. Hai measure `Top Purpose` và `Peak Year` là hằng số theo source Huy.
