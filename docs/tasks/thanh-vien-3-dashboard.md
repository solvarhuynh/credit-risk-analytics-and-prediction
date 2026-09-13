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

- [ ] Dùng **Power BI** làm dashboard chính: dựng Data Model, Power Query, DAX measures và cấu hình interaction/cross-filtering. Python chỉ tạo các bảng dữ liệu/model artifacts để Power BI tiêu thụ.
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

**Không dùng bản đồ mô phỏng bằng cách gán ngẫu nhiên khách hàng vào tỉnh/thành.** Cách đó không tạo dữ liệu địa lý thật.

- [ ] Hỏi giảng viên liệu biểu đồ phân bố theo Region Rating được chấp nhận thay bản đồ địa lý hay không.
- [ ] Nếu không, chỉ dùng Map khi có nguồn địa lý thật và khóa join hợp lệ; ghi rõ nguồn, cách join và giới hạn trong dashboard/báo cáo.
- [ ] Lưu quyết định trong tài liệu rủi ro/kiến trúc của dự án.
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
- [ ] Dashboard nạp bảng điểm do Python xuất. Không load model XGBoost trực tiếp trong Power BI.
- [ ] Nếu làm What-if Simulator, dùng Logistic Regression rút gọn đã chốt feature/hệ số và đối chiếu kết quả DAX với Python.
- [ ] Test với vài trường hợp thực tế từ tập test để đảm bảo kết quả hợp lý (khách rõ ràng rủi ro cao phải ra risk score cao)

### 2.6 Tích hợp kết quả dự báo lên Dashboard

- [ ] Thêm biểu đồ hiển thị đường xu hướng dự báo hoặc phân lớp rủi ro (risk tier) ngay trên dashboard tổng quan
- [ ] Đảm bảo người xem hiểu được: dashboard này không chỉ mô tả quá khứ mà còn hỗ trợ dự báo tương lai

### 2.7 Bàn giao

- [ ] Hoàn thiện file dashboard Power BI (`.pbix`) và hướng dẫn refresh dữ liệu.
- [ ] Quay lại vài screenshot/GIF các tính năng chính để dùng trong báo cáo và slide
- [ ] Viết phần báo cáo "Thiết kế Dashboard" (giải thích layout, luồng tương tác, lý do chọn từng loại biểu đồ)

### 2.8 Video Demo — phần quay của Thành viên 3 (việc chung, xem chi tiết ở `phan-cong-nhiem-vu.md`)

- [ ] Quay screen recording thao tác trực tiếp trên Dashboard: filter, drill-down, cross-filtering, và đặc biệt phần What-if Simulator (nhập số liệu → ra kết quả ngay)
- [ ] Voice-over giải thích ngắn gọn từng tính năng khi quay
- [ ] Gửi clip cho người tổng hợp dựng video hoàn chỉnh

---

## 3. Danh sách công việc hỗ trợ (Secondary: Data Visualization hỗ trợ EDA)

- [ ] Hỗ trợ Thành viên 2 vẽ các biểu đồ tĩnh (Matplotlib/Seaborn/Plotly) cho phần EDA — đặc biệt các biểu đồ cần kỹ thuật trực quan hóa tốt (heatmap, phân phối)
- [ ] Đề xuất bảng màu, style nhất quán để khi đưa lên Dashboard không bị "lệch tông" so với phần EDA trong báo cáo
- [ ] Góp ý cho Thành viên 2 loại biểu đồ nào nên dùng cho từng loại insight (kinh nghiệm từ việc build dashboard có thể áp dụng ngược lại cho EDA)

---

## 4. Checklist chuẩn bị vấn đáp (bắt buộc tự luyện)

- [ ] Giải thích được lý do chọn Power BI và sự phân tách Python pipeline/model với lớp dashboard
- [ ] Giải thích được cách Cross-filtering hoạt động về mặt kỹ thuật
- [ ] Giải thích được What-if Simulator lấy model từ đâu, xử lý input/output như thế nào
- [ ] Giải thích được vì sao chọn field cụ thể để tô màu trên bản đồ (Map)
- [ ] Nắm cơ bản dữ liệu đến từ đâu, đã qua các bước xử lý nào (từ Thành viên 2)
- [ ] Nắm cơ bản model đứng sau dashboard hoạt động theo logic gì (từ Thành viên 1), dù không cần đi sâu vào thuật toán

---

## 5. Deliverables cuối cùng

1. File Dashboard Power BI hoàn chỉnh (`.pbix`)
2. Screenshot/GIF minh họa các tính năng chính (filter, drill-down, cross-filtering, What-if Simulator)
3. Phần báo cáo "Thiết kế Dashboard" (theo chuẩn IEEE)
4. Nội dung trình bày slide phần Dashboard + demo trực tiếp trong buổi bảo vệ
