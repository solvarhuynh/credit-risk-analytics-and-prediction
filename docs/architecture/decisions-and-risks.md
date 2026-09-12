# Quyết định và rủi ro cần chốt

## ADR-001 — Dashboard theo thực tế doanh nghiệp

Dashboard chính dùng Power BI. TV3 bàn giao file `.pbix`, Power Query/DAX được mô tả trong tài liệu, nguồn dữ liệu refresh được và ảnh demo. Python tạo các bảng đã làm sạch/chấm điểm; Power BI không được tự train lại mô hình.

What-if Simulator chỉ dùng mô hình Logistic Regression rút gọn khi các biến đầu vào và hệ số được cố định, kiểm thử và chuyển sang DAX. Không cố chuyển XGBoost/SHAP sang DAX. Nếu chưa làm được simulator, vẫn ưu tiên hoàn thiện dashboard, filter, drill-down, cross-filtering và visual dự báo bắt buộc.

## RISK-001 — Map không tương thích dữ liệu hiện tại

`REGION_RATING_CLIENT` là mã/xếp hạng đã ẩn danh, không phải tọa độ hay tỉnh/thành. Không được tạo choropleth bằng cách gán ngẫu nhiên khách hàng vào bản đồ.

1. Hỏi giảng viên bằng văn bản liệu biểu đồ vùng theo `REGION_RATING_CLIENT` được thay cho geographic map hay không.
2. Nếu không, bổ sung/đổi sang nguồn có địa lý và khóa join thật; ghi nguồn, cách join và hạn chế.

Đây là blocker duy nhất để khẳng định đáp ứng trọn vẹn barem.

## RISK-002 — Leakage và scope

TV2/TV1 phải ghi nguồn và tính hợp lệ theo thời điểm của từng feature lịch sử. Logistic, EDA, dashboard và dự báo trên dashboard là việc bắt buộc; chỉ làm XGBoost, SHAP, SMOTE, PDO/EL và fairness sau khi luồng tối thiểu end-to-end hoàn chỉnh.
