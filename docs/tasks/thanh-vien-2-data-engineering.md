# NHIỆM VỤ CHI TIẾT — THÀNH VIÊN 2

**Đề tài:** Phân tích rủi ro tín dụng và khả năng vỡ nợ của khách hàng cá nhân
**Mảng phụ trách chính:** Data Engineering & Pipeline
**Mảng hỗ trợ:** Hỗ trợ Modeling (Fairness Check, Confusion Matrix theo threshold)

---

## 1. Mục tiêu tổng thể

Xây dựng toàn bộ tầng dữ liệu của dự án: từ thu thập, làm sạch, kết hợp nhiều bảng, đến tạo ra các đặc trưng (features) có ý nghĩa nghiệp vụ để phục vụ cho cả EDA và Modeling. Đây là nền tảng của toàn bộ pipeline — nếu dữ liệu đầu vào không tốt, model và dashboard phía sau đều bị ảnh hưởng.

---

## 2. Danh sách công việc (Main: Data Engineering & Pipeline)

### 2.1 Thu thập dữ liệu

- [ ] Tải dataset **Home Credit Default Risk** từ Kaggle
- [ ] Ghi chú rõ nguồn (link Kaggle) để trích dẫn trong báo cáo
- [ ] Kiểm tra số dòng, số bảng để xác nhận thỏa mãn yêu cầu đề (≥5,000 dòng, ≥3 bảng)
- [ ] Liệt kê các bảng sẽ dùng: `application_train/test`, `bureau`, `bureau_balance`, `previous_application`, `installments_payments`, `credit_card_balance`, `POS_CASH_balance`

### 2.2 Khám phá cấu trúc dữ liệu ban đầu

- [ ] Với mỗi bảng: kiểm tra shape, kiểu dữ liệu từng cột, tỷ lệ missing value
- [ ] Xác định khóa chính/khóa ngoại để join (`SK_ID_CURR`, `SK_ID_BUREAU`, `SK_ID_PREV`)
- [ ] Lập **Data Dictionary** — bảng mô tả ý nghĩa từng trường dữ liệu quan trọng sẽ dùng (bắt buộc có trong báo cáo)

### 2.3 Làm sạch dữ liệu (Data Cleaning)

- [ ] Xử lý missing values: quyết định impute (mean/median/mode) hay drop tùy theo % thiếu và ý nghĩa cột
- [ ] Xử lý outlier: đặc biệt chú ý `DAYS_EMPLOYED` (giá trị bất thường 365243 cần xử lý thành NaN hoặc flag riêng)
- [ ] Chuẩn hóa định dạng: các cột `DAYS_*` đang là số âm (ngày tính từ hiện tại) — cân nhắc quy đổi sang năm/tháng cho dễ hiểu
- [ ] Chuẩn hóa chuỗi ký tự (nếu có lỗi chính tả, khoảng trắng thừa trong các cột categorical)
- [ ] Kiểm tra và xử lý duplicate rows nếu có

### 2.4 Join/Merge dữ liệu

- [ ] Aggregate bảng phụ trước khi join vào bảng chính:
  - `bureau` + `bureau_balance` → tổng hợp theo `SK_ID_CURR` (số khoản vay ngoài, số lần trễ hạn, dư nợ trung bình...)
  - `previous_application` → tổng hợp theo `SK_ID_CURR` (số lần vay trước, tỷ lệ được duyệt...)
  - `installments_payments` → tổng hợp hành vi trả góp (số lần trả trễ, chênh lệch số tiền trả thực tế vs kế hoạch)
  - `credit_card_balance`, `POS_CASH_balance` → tổng hợp số dư trung bình/tối đa
- [ ] Join tất cả về bảng chính `application` theo `SK_ID_CURR`
- [ ] Kiểm tra sau khi join: không bị nhân bản dòng (duplicate do join sai khóa), không mất dữ liệu ngoài ý muốn

### 2.5 Tạo Calculated Fields (Feature Engineering)

- [ ] **DTI (Debt-to-Income ratio)** = khoản vay / thu nhập
- [ ] Tỷ lệ Credit Amount / Annuity (số tiền vay / số tiền trả góp hàng năm)
- [ ] Số năm làm việc (quy đổi từ `DAYS_EMPLOYED`)
- [ ] Nhóm tuổi (binning từ `DAYS_BIRTH`)
- [ ] Số lần trễ hạn trong quá khứ (từ `bureau`/`installments_payments`)
- [ ] Các field khác thấy có ý nghĩa nghiệp vụ, ghi rõ lý do tạo trong báo cáo

### 2.6 Khám phá dữ liệu (EDA)

- [ ] Vẽ 3-5 biểu đồ tĩnh bằng Matplotlib/Seaborn:
  - Phân phối thu nhập theo Target (default/non-default)
  - Tỷ lệ vỡ nợ theo nhóm tuổi, nghề nghiệp, loại hợp đồng vay
  - Correlation heatmap giữa các biến số quan trọng
  - Boxplot outlier trước/sau xử lý (minh chứng bước làm sạch có tác dụng)
- [ ] Rút ra 2-3 nhận xét ban đầu từ EDA để đóng góp cho phần Storytelling chung

### 2.7 Video Demo — phần quay của Thành viên 2 (việc chung, xem chi tiết ở `phan-cong-nhiem-vu.md`)

- [ ] Quay screen recording phần pipeline: chạy script clean_data, minh họa trước/sau xử lý missing/outlier, kết quả EDA
- [ ] Voice-over giải thích ngắn gọn nguồn dữ liệu và các bước xử lý chính
- [ ] Gửi clip cho người tổng hợp dựng video hoàn chỉnh

### 2.8 Bàn giao

- [ ] Xuất dataset đã làm sạch, đã join, đã có calculated fields (`cleaned_dataset.csv`)
- [ ] Gửi cho Thành viên 1 (để train model) và Thành viên 3 (để build dashboard)
- [ ] Viết script pipeline hoàn chỉnh (`clean_data_pipeline.py`) để tái tạo dataset từ đầu — có thể tham khảo cấu trúc pipeline dạng function theo từng bước
- [ ] Viết phần báo cáo "Giới thiệu dataset" + "Quy trình tiền xử lý & EDA" kèm Data Dictionary

---

## 3. Danh sách công việc hỗ trợ (Secondary: Hỗ trợ Modeling)

### 3.1 Fairness Check

- [ ] Sau khi Thành viên 1 có model, kiểm tra: tỷ lệ dự đoán "rủi ro cao" có chênh lệch bất thường giữa các nhóm giới tính không, giữa các nhóm tuổi không
- [ ] Tính các chỉ số công bằng cơ bản (VD: so sánh False Positive Rate giữa các nhóm)
- [ ] Ghi nhận kết quả và đề xuất nếu phát hiện thiên lệch (bias) rõ rệt

### 3.2 Confusion Matrix theo Threshold

- [ ] Vẽ Confusion Matrix ở nhiều ngưỡng xác suất khác nhau (VD: 0.3, 0.5, 0.7)
- [ ] Phân tích trade-off: ngưỡng thấp → duyệt ít hơn nhưng an toàn hơn (nhiều False Positive), ngưỡng cao → duyệt nhiều hơn nhưng rủi ro hơn (nhiều False Negative)
- [ ] Đề xuất ngưỡng phù hợp dựa trên chi phí kinh doanh giả định (VD: chi phí bỏ lỡ 1 khách tốt vs chi phí mất vốn 1 khách xấu)
- [ ] Review kết quả này cùng Thành viên 1 trước khi đưa vào báo cáo

---

## 4. Checklist chuẩn bị vấn đáp (bắt buộc tự luyện)

- [ ] Giải thích được lý do chọn từng phương pháp xử lý missing/outlier cho từng cột cụ thể
- [ ] Giải thích được logic join giữa các bảng, tại sao phải aggregate trước khi join
- [ ] Giải thích được ý nghĩa nghiệp vụ của từng calculated field đã tạo
- [ ] Giải thích được Fairness Check đo cái gì, tại sao quan trọng trong bài toán tín dụng
- [ ] Nắm cơ bản cách Thành viên 1 dùng dữ liệu này để train model (không cần chi tiết thuật toán, nhưng hiểu input/output)
- [ ] Nắm cơ bản cách dữ liệu hiển thị trên Dashboard của Thành viên 3

---

## 5. Deliverables cuối cùng

1. Script pipeline hoàn chỉnh (`clean_data_pipeline.py`)
2. Dataset đã làm sạch (`cleaned_dataset.csv`)
3. Data Dictionary (bảng mô tả các trường dữ liệu)
4. Bộ biểu đồ EDA (3-5 biểu đồ)
5. Kết quả Fairness Check + Confusion Matrix theo threshold
6. Phần báo cáo "Dataset" + "Tiền xử lý & EDA" (theo chuẩn IEEE)
7. Nội dung trình bày slide phần Data Pipeline
