# NHIỆM VỤ CHI TIẾT — THÀNH VIÊN 3

**Đề tài:** Phân tích rủi ro tín dụng và khả năng vỡ nợ của khách hàng cá nhân
**Mảng phụ trách chính:** Dashboard (kỹ thuật)
**Mảng hỗ trợ:** Data Visualization hỗ trợ EDA

---

## 1. Mục tiêu tổng thể

Xây dựng Dashboard trực quan hóa tương tác hoàn chỉnh, biến kết quả từ dữ liệu (Thành viên 2) và mô hình (Thành viên 1) thành một công cụ trực quan, dễ thao tác, hỗ trợ ra quyết định thực tế — không chỉ là nơi "trưng" biểu đồ mà còn có tính năng mô phỏng (What-if Simulator) giúp dashboard trở thành công cụ ra quyết định thật sự.

---

## 2. Danh sách công việc (Main: Dashboard kỹ thuật)

### 2.1 Lựa chọn & chuẩn bị công cụ

- [ ] Quyết định dùng **Power BI** hay **Streamlit + Plotly** (cân nhắc: Power BI dễ đạt điểm UI/UX nhanh, Streamlit linh hoạt hơn để tích hợp model trực tiếp cho What-if Simulator)
- [ ] Cài đặt môi trường, kết nối với dataset đã làm sạch từ Thành viên 2
- [ ] Thiết kế wireframe/layout tổng thể trước khi build (mấy trang, mỗi trang có gì)

### 2.2 Giao diện & UI/UX

- [ ] Bố cục (layout) hợp lý: chia rõ khu vực filter, khu vực biểu đồ chính, khu vực chi tiết
- [ ] Chọn bảng màu hài hòa, nhất quán (nên thống nhất với màu dùng trong EDA của Thành viên 2)
- [ ] Đặt tiêu đề rõ ràng cho từng biểu đồ, có chú thích (Legend) dễ hiểu cho người dùng cuối không rành kỹ thuật

### 2.3 Đa dạng biểu đồ (tối thiểu 8 loại)

- [ ] **Bar chart** — tỷ lệ vỡ nợ theo nghề nghiệp/loại hợp đồng
- [ ] **Line chart** — xu hướng vay/vỡ nợ theo thời gian
- [ ] **Pie/Donut chart** — tỷ lệ loại hợp đồng vay
- [ ] **Scatter plot** — thu nhập vs credit amount, tô màu theo Target
- [ ] **Heatmap** — correlation giữa các biến, hoặc rủi ro theo 2 chiều (VD: tuổi x nghề nghiệp)
- [ ] **Treemap** — cơ cấu khách hàng theo ngành nghề/loại vay
- [ ] **Box plot** — phân phối thu nhập/khoản vay theo nhóm rủi ro
- [ ] **Map (bản đồ)** — phân bố tỷ lệ vỡ nợ theo vùng/khu vực địa lý (xem lưu ý xử lý kỹ thuật ở mục 2.3.1 bên dưới)

#### 2.3.1 Lưu ý quan trọng: Xử lý Map khi dataset không có tọa độ địa lý thật

Dataset Home Credit Default Risk **không có** tên tỉnh/thành hay tọa độ GPS thật — chỉ có các trường mã hóa vùng dạng số: `REGION_RATING_CLIENT`, `REGION_RATING_CLIENT_W_CITY`, `REGION_POPULATION_RELATIVE`. Để có Map hợp lệ, đúng khoa học (không "chế" dữ liệu không tồn tại), chọn 1 trong 2 phương án sau:

**Phương án A (khuyến nghị — an toàn, minh bạch):**
- Dùng **Choropleth Map dạng mô phỏng**: gán ngẫu nhiên có kiểm soát (hoặc theo phân phối hợp lý) các giá trị `REGION_RATING_CLIENT` (1/2/3) vào một bản đồ hành chính mẫu (VD: bản đồ các tỉnh Việt Nam hoặc các bang/vùng của một quốc gia bất kỳ dùng làm minh họa)
- **Bắt buộc ghi chú rõ trong dashboard và báo cáo**: "Bản đồ mang tính minh họa phân bố theo Region Rating nội bộ của dataset (không phải vị trí địa lý thực tế của khách hàng, vì dataset gốc không cung cấp thông tin này)"
- Đây là cách xử lý trung thực, thể hiện hiểu biết về hạn chế dữ liệu — điểm cộng khi vấn đáp thay vì bị trừ vì "bịa" dữ liệu

**Phương án B (nếu muốn địa lý thật):**
- Tìm thêm 1 dataset phụ có thật (VD: dataset tín dụng theo vùng của World Bank/quốc gia cụ thể) để bổ sung tọa độ, dùng làm ví dụ minh họa riêng, tách biệt rõ với phần phân tích chính trên Home Credit
- Rủi ro: tốn thời gian, dễ gây nhầm lẫn nguồn dữ liệu nếu trình bày không rõ ràng — chỉ làm nếu còn dư thời gian

→ **Quyết định:** Dùng Phương án A, ghi chú rõ ràng để tránh bị đánh giá là dữ liệu không trung thực khi vấn đáp.
- [ ] Đảm bảo mỗi loại biểu đồ chọn đúng loại dữ liệu phù hợp (không dùng Pie chart cho dữ liệu có quá nhiều category)

### 2.4 Tính năng tương tác

- [ ] **Filter nhiều cấp**: theo giới tính, độ tuổi, loại vay, vùng miền...
- [ ] **Drill-down**: từ tổng quan toàn bộ danh mục → chi tiết theo từng nhóm khi click vào
- [ ] **Tooltip**: hiển thị thông tin chi tiết khi hover chuột vào từng điểm/cột dữ liệu
- [ ] **Cross-filtering**: khi chọn 1 giá trị trên biểu đồ này, các biểu đồ khác tự động lọc theo (đây là phần chiếm điểm cao nhất trong barem — 1.5đ)
- [ ] Test kỹ toàn bộ tính năng để đảm bảo mượt mà khi demo trực tiếp

### 2.5 What-if Simulator (điểm nhấn quan trọng nhất)

- [ ] Nhận model đã train từ Thành viên 1 (file `.pkl` + hướng dẫn input/output)
- [ ] Thiết kế 1 trang/section riêng cho phép người dùng **nhập tay** thông số khách hàng giả định: thu nhập, tuổi, số năm làm việc, loại vay, số tiền vay...
- [ ] Khi nhấn "Tính toán" → gọi model → trả về ngay: xác suất vỡ nợ, Credit Score, Risk Tier (Low/Medium/High), khuyến nghị (Approve/Reject/Review)
- [ ] Nếu dùng Streamlit: tích hợp trực tiếp bằng Python (load pickle, predict ngay trong app)
- [ ] Nếu dùng Power BI: có thể cần dùng Power BI + Python script visual hoặc kết nối qua API đơn giản — bàn với Thành viên 1 về cách khả thi nhất
- [ ] Test với vài trường hợp thực tế từ tập test để đảm bảo kết quả hợp lý (khách rõ ràng rủi ro cao phải ra risk score cao)

### 2.6 Tích hợp kết quả dự báo lên Dashboard

- [ ] Thêm biểu đồ hiển thị đường xu hướng dự báo hoặc phân lớp rủi ro (risk tier) ngay trên dashboard tổng quan
- [ ] Đảm bảo người xem hiểu được: dashboard này không chỉ mô tả quá khứ mà còn hỗ trợ dự báo tương lai

### 2.7 Bàn giao

- [ ] Hoàn thiện file dashboard (`.pbix` cho Power BI hoặc app Streamlit deploy được/chạy local ổn định)
- [ ] Quay lại vài screenshot/GIF các tính năng chính để dùng trong báo cáo và slide
- [ ] Viết phần báo cáo "Thiết kế Dashboard" (giải thích layout, luồng tương tác, lý do chọn từng loại biểu đồ)

### 2.8 Video Demo — phần quay của Thành viên 3 (việc chung, xem chi tiết ở `phan-cong-nhiem-vu.md`)

- [ ] Quay screen recording thao tác trực tiếp trên Dashboard: filter, drill-down, cross-filtering, và đặc biệt phần What-if Simulator (nhập số liệu → ra kết quả ngay)
- [ ] Voice-over giải thích ngắn gọn từng tính năng khi quay
- [ ] Gửi clip cho người tổng hợp dựng video hoàn chỉnh

---

## 3. Danh sách công việc hỗ trợ (Secondary: Data Visualization hỗ trợ EDA)

- [ ] Hỗ trợ Thành viên 2 vẽ các biểu đồ tĩnh (Matplotlib/Seaborn) cho phần EDA — đặc biệt các biểu đồ cần kỹ thuật trực quan hóa tốt (heatmap, phân phối)
- [ ] Đề xuất bảng màu, style nhất quán để khi đưa lên Dashboard không bị "lệch tông" so với phần EDA trong báo cáo
- [ ] Góp ý cho Thành viên 2 loại biểu đồ nào nên dùng cho từng loại insight (kinh nghiệm từ việc build dashboard có thể áp dụng ngược lại cho EDA)

---

## 4. Checklist chuẩn bị vấn đáp (bắt buộc tự luyện)

- [ ] Giải thích được lý do chọn Power BI/Streamlit thay vì công cụ khác
- [ ] Giải thích được cách Cross-filtering hoạt động về mặt kỹ thuật
- [ ] Giải thích được What-if Simulator lấy model từ đâu, xử lý input/output như thế nào
- [ ] Giải thích được vì sao chọn field cụ thể để tô màu trên bản đồ (Map)
- [ ] Nắm cơ bản dữ liệu đến từ đâu, đã qua các bước xử lý nào (từ Thành viên 2)
- [ ] Nắm cơ bản model đứng sau dashboard hoạt động theo logic gì (từ Thành viên 1), dù không cần đi sâu vào thuật toán

---

## 5. Deliverables cuối cùng

1. File Dashboard hoàn chỉnh (`.pbix` hoặc Streamlit app)
2. Screenshot/GIF minh họa các tính năng chính (filter, drill-down, cross-filtering, What-if Simulator)
3. Phần báo cáo "Thiết kế Dashboard" (theo chuẩn IEEE)
4. Nội dung trình bày slide phần Dashboard + demo trực tiếp trong buổi bảo vệ
