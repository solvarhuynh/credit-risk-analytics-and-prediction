# Tổng quan đồ án

Đề tài: **Retail Credit Risk Analytics & Default Prediction** trên Lending Club 2007–2018.

Mục tiêu là xây dựng pipeline có thể audit, mô hình default có kiểm soát leakage và dashboard Power BI tương tác. Accepted loan cung cấp hồ sơ, credit snapshot, outcome và địa lý cấp bang. Rejected application bổ sung góc nhìn nhu cầu/funnel nhưng không có default label.

Sản phẩm phải thể hiện multi-table Join/Merge, EDA, Logistic Regression, so sánh mô hình nếu có, threshold/business cost, explainability, Map, ít nhất 8 loại biểu đồ, filter, drill-down, tooltip và cross-filtering.

Map dùng `addr_state → state_code` cùng `country = United States`. ZIP masked không đủ cho tọa độ chính xác và không được biến thành location giả.

Tài liệu đề bài gốc được giữ nguyên tại `Barem-TTDLTQ.docx` và `overview-du-an.pdf`.

## Bắt đầu từ đây

Nếu mới tìm hiểu pipeline dữ liệu, đọc theo thứ tự:

1. [DATA_WORKFLOW.md](../data/DATA_WORKFLOW.md) — workflow tổng thể và vai trò của raw, interim, processed.
2. [DATA_RULES.md](../data/DATA_RULES.md) — model được dùng gì, loại gì và cách tránh leakage.
3. [data_artifacts.md](../data/data_artifacts.md) — tham khảo chi tiết từng artifact khi cần.
