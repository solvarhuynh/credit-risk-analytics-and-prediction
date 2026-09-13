# PHÂN CÔNG NHIỆM VỤ ĐỒ ÁN

**Đề tài:** Phân tích rủi ro tín dụng và khả năng vỡ nợ của khách hàng cá nhân
**Môn học:** Tương tác Dữ liệu Trực quan
**Dataset:** Home Credit Default Risk (Kaggle)
**Mục tiêu điểm:** 9/10 (A+)
**Team:** 3 thành viên

---

## Nguyên tắc phân công

- Mỗi người có **1 nhiệm vụ Main** (chủ trì kỹ thuật) và **1 nhiệm vụ Secondary** (hỗ trợ mảng liên quan).
- **Storytelling & Insight tổng hợp** là việc **làm chung cả 3 người** — vì đây là nơi ráp nối kết quả từ dữ liệu, model và dashboard thành câu chuyện thống nhất.
- **Báo cáo IEEE** và **Slide thuyết trình** là việc chung, mỗi người viết/trình bày phần Main của mình.
- **Video Demo là việc làm chung** — barem yêu cầu bắt buộc phải có Video backup tóm tắt, nên không được bỏ. Mỗi người quay phần demo thuộc mảng mình phụ trách, ghép lại thành 1 video hoàn chỉnh.
- Vì phần vấn đáp có thể **trừ tối đa 4.0 điểm** nếu không hiểu rõ code/logic, mỗi người **bắt buộc hiểu cơ bản** phần Main của 2 người còn lại, không chỉ riêng phần mình.

---

## Thành viên 1

### 🎯 Main: Modeling & Machine Learning

| Việc | Chi tiết |
| --- | --- |
| Baseline model | Logistic Regression — đúng yêu cầu bắt buộc của đề |
| Model nâng cao | XGBoost / LightGBM — so sánh hiệu năng (AUC, Precision/Recall) với baseline |
| Xử lý mất cân bằng dữ liệu | SMOTE hoặc class weighting — vì tỷ lệ vỡ nợ thực tế thường chỉ 5–8% |
| Giải thích mô hình | SHAP values — feature importance tổng thể & theo từng khách hàng |
| Credit Scoring System | Quy đổi xác suất vỡ nợ (log-odds) → thang điểm 300–850 |
| Expected Loss | Tính toán ước lượng giảm nợ xấu / tăng lợi nhuận nếu áp dụng mô hình |

**Deliverable:** Notebook/script model hoàn chỉnh, file model đã train (pickle/joblib) để bàn giao cho Thành viên 3 tích hợp vào Dashboard, báo cáo phần "Mô hình dự báo".

### 🔧 Secondary: Data Engineering (hỗ trợ Thành viên 2)

- Hỗ trợ thiết kế schema join/merge giữa các bảng (`application`, `bureau`, `previous_application`...)
- Review và tối ưu pipeline tiền xử lý cùng Thành viên 2
- Đảm bảo các trường dữ liệu đưa vào model đã được tạo đúng và có ý nghĩa (calculated fields)

---

## Thành viên 2

### 🎯 Main: Data Engineering & Pipeline

| Việc | Chi tiết |
| --- | --- |
| Thu thập dữ liệu | Tải và tổ chức các bảng từ Home Credit Default Risk, ghi rõ nguồn/link |
| Làm sạch dữ liệu | Xử lý missing values, outlier (VD: `DAYS_EMPLOYED` = 365243), chuẩn hóa định dạng |
| Join/Merge | Kết hợp các bảng theo `SK_ID_CURR`, aggregate bảng phụ (mean/max/count) |
| Calculated fields | Tạo DTI, tỷ lệ Credit/Annuity, số năm làm việc, nhóm tuổi, số lần trễ hạn quá khứ |
| Data dictionary | Lập bảng mô tả ý nghĩa từng trường dữ liệu dùng trong dự án |

**Deliverable:** Script Python/R pipeline hoàn chỉnh (raw → cleaned dataset), file dataset đã xử lý sạch để bàn giao cho Thành viên 1 (model) và Thành viên 3 (dashboard), phần báo cáo "Tiền xử lý & EDA".

### 🔧 Secondary: Hỗ trợ Modeling

- Thực hiện **Fairness Check** — kiểm tra model có bias theo giới tính/độ tuổi không
- Vẽ **Confusion Matrix theo các ngưỡng (threshold) khác nhau**, phân tích trade-off giữa False Positive (từ chối oan khách tốt) và False Negative (duyệt nhầm khách xấu)
- Review kết quả model cùng Thành viên 1 trước khi đưa vào báo cáo

---

## Thành viên 3

### 🎯 Main: Dashboard (kỹ thuật)

| Việc | Chi tiết |
| --- | --- |
| Xây dựng Dashboard | Power BI, dùng dữ liệu sạch từ Thành viên 2 và bảng điểm từ Thành viên 1 |
| Đa dạng biểu đồ | Tối thiểu 8 loại: Bar, Line, Pie/Donut, Scatter, Heatmap, Treemap, Boxplot |
| Bản đồ (Map) | Biểu đồ địa lý thể hiện phân bố rủi ro vỡ nợ theo vùng |
| Tính tương tác | Filter nhiều cấp, Drill-down, Tooltip, Cross-filtering giữa các biểu đồ |
| What-if Simulator | Tích hợp model từ Thành viên 1 (qua pickle/API) — nhập tay thông tin khách hàng → trả về risk score/khuyến nghị ngay trên dashboard |

**Deliverable:** Dashboard Power BI hoàn chỉnh chạy được trực tiếp (file .pbix), phần báo cáo "Thiết kế Dashboard".

### 🔧 Secondary: Data Visualization hỗ trợ EDA

- Hỗ trợ Thành viên 2 vẽ các biểu đồ tĩnh (Matplotlib/Seaborn) cho phần Khám phá dữ liệu (EDA) trước khi đưa lên dashboard
- Đảm bảo tính nhất quán về màu sắc, phong cách trực quan giữa EDA và Dashboard

---

## Việc làm chung (cả 3 thành viên)

### 📖 Storytelling & Insight tổng hợp

Mỗi người đóng góp góc nhìn từ mảng mình phụ trách, sau đó cả nhóm ráp thành 1 câu chuyện thống nhất theo cấu trúc 3 lớp:

1. **Overview** — Toàn cảnh danh mục vay, tỷ lệ vỡ nợ tổng thể (dữ liệu từ Thành viên 2)
2. **Diagnostic** — Tại sao rủi ro tập trung ở đâu, nhóm khách hàng nào (model + dashboard, Thành viên 1 & 3)
3. **Prescriptive** — Đề xuất chính sách duyệt vay cụ thể, kèm ước tính tác động (Expected Loss, Thành viên 1)

### 📄 Báo cáo khoa học (chuẩn IEEE, tối thiểu 40 trang)

| Phần báo cáo | Người viết chính |
| --- | --- |
| Giới thiệu đề tài | Thành viên 1 |
| Mô tả dataset | Thành viên 2 |
| Quy trình tiền xử lý & EDA | Thành viên 2 |
| Thiết kế Dashboard | Thành viên 3 |
| Mô hình dự báo (Logistic/XGBoost, SHAP, Credit Scoring) | Thành viên 1 |
| Khai phá Insight (Storytelling) | Cả 3 — tổng hợp chung |
| Kết luận & Tài liệu tham khảo | Cả 3 — review chéo |

### 🎤 Slide thuyết trình

Làm chung, chia phần trình bày theo đúng phần Main của từng người — ai làm phần nào trình bày phần đó, phần Storytelling tổng kết trình bày chung.

### 🎬 Video Demo (bắt buộc theo barem — dùng làm bản backup)

- **Mục đích:** Phòng trường hợp lỗi kỹ thuật khi demo trực tiếp buổi bảo vệ (mất mạng, lỗi Power BI...), có sẵn video chạy mượt để trình chiếu thay thế.
- **Nội dung:** Quay màn hình theo kịch bản Data Analyst trình bày cho Risk Committee — mở đầu bài toán kinh doanh → pipeline dữ liệu (Thành viên 2) → mô hình dự báo (Thành viên 1) → thao tác trên Dashboard + What-if Simulator (Thành viên 3) → kết luận & khuyến nghị.
- **Độ dài:** 5–8 phút, súc tích, không lan man.
- **Phân công quay:** Mỗi người tự quay phần mình phụ trách (voice-over + screen recording), 1 người tổng hợp dựng/ghép video cuối cùng (có thể luân phiên hoặc người rành edit video nhất đảm nhận).
- **Nộp kèm:** Link video (Youtube unlisted/Google Drive) trong báo cáo, đúng yêu cầu "Hướng dẫn cài đặt/sử dụng & Link Video Demo".

### ✅ Buổi tổng duyệt trước khi bảo vệ (bắt buộc)

- Mỗi người phải trả lời được câu hỏi cơ bản về phần Main **của người khác**
- Diễn tập các câu hỏi phản biện có thể gặp (VD: "Tại sao chọn SMOTE thay vì undersampling?", "Vì sao dùng Logistic làm baseline?", "Bản đồ rủi ro dùng field nào để tô màu?")
- Rà lại toàn bộ để tránh tình trạng "hiểu chưa tốt" hoặc "ỷ lại thành viên khác" — vì đây là phần **quyết định điểm số cuối cùng** theo barem

---

## Timeline đề xuất (8 tuần)

| Tuần | Thành viên 1 | Thành viên 2 | Thành viên 3 |
| --- | --- | --- | --- |
| 1–2 | Hỗ trợ thiết kế schema | Thu thập, làm sạch dữ liệu | Nghiên cứu tool dashboard, layout |
| 3–4 | Xây Logistic + XGBoost | Join/merge, calculated fields, EDA | Hỗ trợ vẽ biểu đồ EDA |
| 5 | SMOTE, SHAP, Credit Scoring | Fairness check, confusion matrix | Bắt đầu build dashboard |
| 6 | Expected Loss, bàn giao model | Hoàn thiện data dictionary | Hoàn thiện biểu đồ + Map |
| 7 | Hỗ trợ tích hợp What-if Simulator | Viết phần báo cáo của mình | Tính năng tương tác + What-if Simulator |
| 8 | Storytelling + Báo cáo + Slide chung | Storytelling + Báo cáo + Slide chung | Storytelling + Báo cáo + Slide chung |

---

*Lưu ý: Timeline có thể điều chỉnh theo tiến độ thực tế, nhưng thứ tự bàn giao (Data → Model → Dashboard) cần được giữ để tránh nghẽn tiến độ.*
