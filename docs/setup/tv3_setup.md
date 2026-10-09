# Thiết lập TV3 — Dashboard

## Trạng thái hiện tại — kiểm tĩnh đã sửa, Desktop còn BLOCKED (2026-10-09)

`reports/figures/dashboard/nghia.pbip` hiện là entry trỏ đến **hai thư mục hiện có** `credit_risk_master_dashboard.Report` và `credit_risk_master_dashboard.SemanticModel`; `definition.pbir` trỏ đúng semantic model này. Tám partition M đã được đổi từ nguồn cũ `D:\Huy\...` sang tám file thực có dưới `D:\ttdltq\data\...`. Ba measure `Top Purpose`, `Peak Year`, `Label Peak Year` đã bỏ giá trị cố định để tính theo filter. Đây là sửa ở PBIP/PBIR/TMDL, **chưa phải nghiệm thu Power BI Desktop**: chưa mở, chưa Refresh, chưa chạy DAX hoặc xem render sau sửa.

PBIR hiện liệt kê **10 page IDs** (gồm một tooltip page), không phải bốn trang của plan. Không có bằng chứng đủ để xác định sáu trang nào được TV3 duyệt là staging hoặc có thể xóa/ẩn, nên chưa sửa page order/visibility. Các ghi nhận Desktop PASS bên dưới thuộc phiên trước; TV3 phải mở entry mới, refresh và nghiệm thu lại, rồi quyết định trang nào giữ trong master.

## Mở và nghiệm thu bản bốn trang

1. Mở `D:/ttdltq/reports/figures/dashboard/nghia.pbip` bằng Power BI Desktop khi không có phiên Desktop khác đang giữ project. **Hiện có 10 page IDs**, nên chưa kỳ vọng chỉ thấy bốn tab; đối chiếu từng trang với plan 4 trang cùng TV3 trước khi ẩn/xóa staging. Nếu Desktop báo lỗi, không lưu phiên lỗi và ghi lại thông báo nguyên văn.
2. Nếu Map V01 báo *Map and filled map visuals aren't enabled for your org*: vào **File → Options and settings → Options → Global → Security → Use Map and Filled Map visuals**, bật và khởi động lại Desktop. Checkbox này chỉ là cài đặt local của file/ứng dụng; nếu đã có dấu kiểm mà canvas vẫn báo lỗi như ảnh kiểm tra ngày 2026-10-08, chính sách tenant vẫn đang chặn. Khi đó nhờ Power BI/Fabric tenant admin vào **Admin portal → Tenant settings → Map and filled map visuals**, bật cho toàn tổ chức hoặc security group của tài khoản rồi **Apply**; sau đó đăng xuất/đăng nhập và mở lại Desktop. Không có quyền admin thì V01 còn BLOCKED; không dùng vị trí giả.
3. Trong **Model view → Manage relationships**, xác nhận `dim_date.date (1) → cleaned_dataset.issue_d (*)`, một chiều. TMDL dùng đúng hướng kỹ thuật `fromColumn: cleaned_dataset.issue_d` (Many), `toColumn: dim_date.date` (One), không ghi cardinality override. Sau đó trên trang 02, chọn các năm khác nhau trong slicer: tổng khoản vay và tỷ lệ default phải đổi; đối chiếu nguyên dữ liệu `cleaned_dataset` ở dưới. Kiểm tra Top Purpose và Peak Year không còn là hằng số khi filter thay đổi.
4. Trên trang 03, xác nhận bốn KPI không rỗng/trùng logic. Bốn visual phân tích theo lưới là V11 heatmap và V12 donut ở hàng trên, V04 box plot và V13 line chart có marker ở hàng dưới. V11/V12 dùng `cleaned_dataset`; V04/V13 dùng `fact_evaluated_loan` (tối đa 269.070, trước khi chọn năm).
5. Kiểm tra V13 dùng Loan-to-Income Ratio trên trục X số liên tục và Mean PD trên Y; 9 bins phải có tổng N=268.991 (79 dòng ratio thiếu do annual income không hợp lệ), min N=222 trước filter. Tooltip có khoảng, N, observed default rate, chênh lệch grouped observed−predicted và cờ N<100. Chọn năm/bang để xác nhận các giá trị thay đổi. Kiểm tra tooltip V11 có N và V02–V06 ở trang 04 còn nguyên. Lưu bằng **File → Save** chỉ sau khi tự kiểm tra render. GUI tương đương mọi thay đổi ghi tại `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`.

Audit V01 lịch sử bằng DAX đã ghi nhận 51 state/state-equivalent có dữ liệu, 269.070 evaluated loans và tổng theo state khớp population; IA có 1 khoản vay/0 default, không phải missing state. File `v01_state_audit.md` cũ không còn trong repo; phải đối chiếu lại các số trên bản PBIP hiện tại trước khi dùng để nghiệm thu. Không coi blank referential member của dimension (0 loan) là state.

Đối chiếu dữ liệu read-only đã chạy: `cleaned_dataset` có 1.345.350 khoản vay, 12 năm 2007–2018; năm 2015 có 375.546 khoản vay, năm 2007 có 251, tỷ lệ default theo năm khác nhau. `dim_date.date` có 4.238 ngày duy nhất và bao phủ toàn bộ `issue_d`. Kiểm tra này **không thay thế** DAX/render validation trong Desktop.

Các bước **EXPECTED / NOT YET VERIFIED AFTER DATASET RESET**:

1. Đọc `docs/contracts/data_contract.md`, `model_contract.md` và task TV3.
2. Không thay đổi visual families đã LOCKED; đọc Phase 2 sign-off và đóng các blocker data-model trước khi build.
3. Theo 4 trang trong plan: Tổng quan danh mục (KPI, V08, V01); Xu hướng & Mục đích vay (V07, V09); Hồ sơ vay (V11, V12, V04, V13; V10 đã rời trang nhưng giữ model); Rủi ro & Expected Loss (KPI, V02, V03, V05, V06). Dự đoán cá nhân là ứng dụng Dash bên ngoài, không phải trang Power BI thứ năm.
4. Chỉ sau review mới thiết kế Power BI model với các fact/dimensions, relationships và measures thực sự cần; không import artifacts toàn bộ một cách máy móc.
5. Xác minh data types/mapping thực tế cho `state_code` và `country` trước map; tạo filters, tooltip, drill-down, cross-filter và navigation chỉ khi chúng giúp trả lời câu hỏi phân tích.
6. Dùng prediction sources sau khi TV1 handoff contract/artifacts; individual demo không phải official loan approval system.

Simulator TV3 chưa có model adapter đã được nghiệm thu. Không dùng đường dẫn cũ `models/full_inference_pipeline.joblib`: root `models/` không còn là nơi lưu artifact và simulator không tự chuyển đổi model TV1. Contract hiện tại nằm ở `src/dashboard/simulator_engine.py`; trạng thái tích hợp được theo dõi tại `reports/tv1_stages/ml-lc-13.md` và `reports/tv2_final_handoff_audit.md`. Chỉ bổ sung lệnh chạy simulator sau khi adapter/model schema được thống nhất và có test.

## Phạm vi trách nhiệm sau reorganize

TV3 là primary owner của Master Power BI artifact, trực tiếp sở hữu V01 và V10–V13, đồng thời tích hợp visual hiện hành, relationships, layout, theme, slicers, filters, drill-down, tooltip, cross-filter, navigation và demo. TV1/TV2 có thể gửi prototype/spec local; chỉ TV3 tích hợp Master PBIX. TV1 cross-review model-facing visuals khi cần; TV2 review data semantics.

## Mở và kiểm tra measure Huy trong master

- **Mục đích:** kiểm tra 7 measure Portfolio mới và 18 visual Huy đã đổi binding trong `reports/figures/dashboard/nghia.pbip`.
- **Điều kiện:** có Power BI Desktop; tám source trong semantic model hiện trỏ tới `D:/ttdltq/data/`. Measure nằm trong `reports/figures/dashboard/credit_risk_master_dashboard.SemanticModel/definition/tables/%2AMeasure table.tmdl`; không dùng đường dẫn thư mục `Huydepzai.SemanticModel`/`nghia.SemanticModel` cũ.
- **Thao tác:** mở `D:/ttdltq/reports/figures/dashboard/nghia.pbip` bằng Power BI Desktop. Kiểm tra Model/Data pane có `cleaned_dataset[Total Loans]`, `cleaned_dataset[Observed Default Rate — Portfolio]` và sáu measure Portfolio khác; kiểm tra Portfolio Overview, Portfolio Trends & Purpose, Borrower Risk Profile và TT_V11 không còn dấu field lỗi. Hướng dẫn tạo/đổi field bằng GUI ở `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`.
- **Output:** master entry là `nghia.pbip`, dùng Report/SemanticModel `credit_risk_master_dashboard.*` hiện có; không tạo artifact dự báo hay Parquet mới.
- **Validation/giới hạn:** đường dẫn/JSON kiểm tĩnh đã kiểm; DAX động mới, render từng visual và Refresh toàn bộ nguồn **chưa được xác nhận trong Desktop**. Không đánh đồng Portfolio default rate trên `cleaned_dataset` với observed default rate TV1 trên `fact_evaluated_loan`. `Top Purpose` và `Peak Year` hiện là measure tính theo filter trên nguồn code, không còn hằng số; cần chạy DAX thực tế để nghiệm thu.
