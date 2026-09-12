# NHIỆM VỤ CHI TIẾT — THÀNH VIÊN 1 (LEAD)

**Đề tài:** Phân tích rủi ro tín dụng và khả năng vỡ nợ của khách hàng cá nhân
**Vai trò:** Lead (quản lý tiến độ chung) — nhưng khối lượng công việc kỹ thuật như thành viên bình thường
**Mảng phụ trách chính:** Modeling & Machine Learning
**Mảng hỗ trợ:** Data Engineering

---

## 1. Mục tiêu tổng thể

Xây dựng toàn bộ tầng Machine Learning của dự án: từ mô hình dự báo xác suất vỡ nợ (baseline + nâng cao), xử lý dữ liệu mất cân bằng, giải thích mô hình, cho đến quy đổi ra hệ thống điểm tín dụng và ước tính tác động kinh doanh. Đây là phần "trọng tâm kỹ thuật" quyết định chiều sâu của đồ án, cần làm kỹ để tự tin trả lời vấn đáp.

---

## 2. Danh sách công việc (Main: Modeling & ML)

### 2.1 Chuẩn bị dữ liệu cho model (nhận từ Thành viên 2)

- [ ] Nhận dataset đã làm sạch (cleaned dataset) + data dictionary từ Thành viên 2
- [ ] Kiểm tra lại: không còn missing value quan trọng, kiểu dữ liệu đúng, không rò rỉ thông tin tương lai (data leakage) — đặc biệt chú ý các cột như `DAYS_*`
- [ ] Encode biến categorical (One-Hot / Label Encoding tùy loại biến)
- [ ] Chia tập Train/Test (hoặc Train/Validation/Test), giữ tỷ lệ Target hợp lý (stratified split)

### 2.2 Baseline Model — Logistic Regression (bắt buộc theo đề)

- [ ] Train Logistic Regression làm baseline
- [ ] Đánh giá bằng: AUC-ROC, Precision, Recall, F1-score (KHÔNG dùng Accuracy làm chỉ số chính vì dữ liệu mất cân bằng)
- [ ] Vẽ ROC Curve và Precision-Recall Curve
- [ ] Giải thích hệ số hồi quy (coefficient) — biến nào tăng/giảm khả năng vỡ nợ

### 2.3 Xử lý mất cân bằng dữ liệu (Imbalanced Data)

- [ ] Kiểm tra tỷ lệ Target (thường vỡ nợ chỉ chiếm 5–8%)
- [ ] Áp dụng SMOTE (Synthetic Minority Oversampling) hoặc class_weight='balanced'
- [ ] So sánh kết quả model trước/sau xử lý imbalance (bảng so sánh AUC, Recall của lớp thiểu số)
- [ ] Giải thích rõ trong báo cáo: tại sao Accuracy cao có thể gây hiểu lầm ở bài toán này

### 2.4 Model nâng cao — XGBoost / LightGBM

- [ ] Train XGBoost hoặc LightGBM trên cùng tập dữ liệu
- [ ] Tune hyperparameter cơ bản (n_estimators, max_depth, learning_rate) — có thể dùng GridSearch/RandomSearch đơn giản
- [ ] So sánh hiệu năng với Logistic Regression bằng bảng + biểu đồ (AUC, Precision, Recall)
- [ ] Kết luận: mô hình nào phù hợp hơn cho bài toán, đánh đổi giữa độ chính xác và khả năng giải thích

### 2.5 Giải thích mô hình — SHAP

- [ ] Tính SHAP values cho model XGBoost
- [ ] Vẽ Summary Plot (feature importance tổng thể)
- [ ] Vẽ Force Plot / Waterfall Plot cho 2-3 khách hàng cụ thể (ví dụ 1 khách rủi ro cao, 1 khách rủi ro thấp) để minh họa cách model ra quyết định
- [ ] Chuẩn bị sẵn phần giải thích bằng lời cho từng biểu đồ SHAP (rất hay bị hỏi khi vấn đáp)

### 2.6 Credit Scoring System

- [ ] Nghiên cứu công thức chuẩn: chuyển đổi log-odds (từ predicted probability) sang thang điểm tín dụng, ví dụ theo công thức PDO (Points to Double the Odds), tương tự FICO (300–850)
- [ ] Áp dụng công thức, tính điểm cho từng khách hàng trong tập test
- [ ] Phân nhóm Risk Tier: Low Risk / Medium Risk / High Risk theo ngưỡng điểm
- [ ] Vẽ phân phối điểm tín dụng theo Target để kiểm tra tính hợp lý (khách vỡ nợ nên có điểm thấp hơn rõ rệt)

### 2.7 Expected Loss & Phân tích lợi nhuận

- [ ] Ước tính Expected Loss = PD (xác suất vỡ nợ) × LGD (giả định tỷ lệ mất vốn, có thể lấy giả định hợp lý VD 45%) × EAD (số dư nợ)
- [ ] So sánh: nếu duyệt vay theo mô hình threshold mới thay vì duyệt toàn bộ, giảm được bao nhiêu % nợ xấu dự kiến
- [ ] Trình bày dưới dạng con số cụ thể (VD: "giảm X% expected loss, tương đương Y tỷ đồng") — đây là điểm nhấn giúp bài toán có giá trị kinh doanh rõ ràng

### 2.8 Video Demo — phần quay của Thành viên 1 (việc chung, xem chi tiết ở `phan-cong-nhiem-vu.md`)

- [ ] Quay screen recording phần Notebook: chạy qua các bước train model, kết quả AUC/SHAP, cách quy đổi Credit Score
- [ ] Voice-over giải thích ngắn gọn logic mô hình và Expected Loss
- [ ] Gửi clip cho người tổng hợp dựng video hoàn chỉnh

### 2.9 Bàn giao

- [ ] Export model đã train (pickle/joblib) kèm script load model
- [ ] Viết hướng dẫn ngắn cho Thành viên 3 cách gọi model để tích hợp What-if Simulator (input format, output format)
- [ ] Viết phần báo cáo "Mô hình dự báo" (mô tả thuật toán, kết quả, SHAP, Credit Scoring, Expected Loss)

---

## 3. Danh sách công việc hỗ trợ (Secondary: Data Engineering)

- [ ] Cùng Thành viên 2 review schema join giữa các bảng (`application`, `bureau`, `bureau_balance`, `previous_application`, `installments_payments`, `credit_card_balance`, `POS_CASH_balance`)
- [ ] Góp ý về các calculated fields nên tạo thêm để phục vụ model tốt hơn (VD: external source score, tỷ lệ thanh toán đúng hạn)
- [ ] Kiểm tra chất lượng dữ liệu đầu vào trước khi train model, phản hồi lại nếu phát hiện vấn đề (data leakage, outlier chưa xử lý...)

---

## 4. Checklist chuẩn bị vấn đáp (bắt buộc tự luyện)

- [ ] Giải thích được vì sao chọn Logistic Regression làm baseline (đúng yêu cầu đề + dễ giải thích + chuẩn ngành tín dụng)
- [ ] Giải thích được SMOTE hoạt động như thế nào, khác gì với việc duplicate dữ liệu đơn thuần
- [ ] Giải thích được ý nghĩa AUC-ROC, vì sao không dùng Accuracy
- [ ] Giải thích được logic quy đổi Credit Score, vì sao dùng thang 300-850
- [ ] Nắm cơ bản phần pipeline dữ liệu của Thành viên 2 (join bảng nào, tại sao)
- [ ] Nắm cơ bản cách Dashboard của Thành viên 3 hiển thị kết quả model (What-if Simulator hoạt động ra sao)

---

## 5. Deliverables cuối cùng

1. Notebook/script modeling hoàn chỉnh (`model_training.ipynb` hoặc `.py`)
2. File model đã train (`model.pkl`)
3. Bộ biểu đồ: ROC Curve, SHAP Summary Plot, SHAP Force Plot, phân phối Credit Score
4. Phần báo cáo "Mô hình dự báo" (theo chuẩn IEEE, có trích dẫn tham khảo)
5. Nội dung trình bày slide phần Modeling
