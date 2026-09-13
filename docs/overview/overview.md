# Tổng quan Đồ án: Phân tích Rủi ro Tín dụng & Khả năng Vỡ nợ Khách hàng Cá nhân

**Môn học:** Tương tác Dữ liệu Trực quan
**Dataset:** Home Credit Default Risk (Kaggle)
**Mục tiêu điểm:** 9/10 (A+)
**Dashboard:** Power BI (Python dùng cho pipeline và mô hình)
**Model:** Logistic Regression + XGBoost

---

## 1. Bối cảnh & Bài toán kinh doanh

Trong hoạt động cho vay tiêu dùng, việc đánh giá sai rủi ro tín dụng dẫn đến hai loại tổn thất:
- **Duyệt nhầm khách hàng xấu** → nợ xấu, mất vốn
- **Từ chối oan khách hàng tốt** → mất doanh thu

Đồ án xây dựng một hệ thống phân tích và dự báo rủi ro tín dụng khách hàng cá nhân, đóng vai trò như một **Data Analyst / Risk Analyst** trình bày kết quả cho bộ phận quản trị rủi ro của tổ chức tín dụng.

**Mục tiêu cốt lõi:** Xây dựng pipeline hoàn chỉnh từ dữ liệu thô → mô hình dự báo xác suất vỡ nợ (Probability of Default) → hệ thống điểm tín dụng (Credit Score) → dashboard trực quan hỗ trợ ra quyết định duyệt vay theo thời gian thực.

### Điểm khác biệt so với đồ án thông thường

- Credit Scoring 300–850
- Expected Loss / Lợi nhuận
- XGBoost + SHAP
- Xử lý Imbalanced Data
- Fairness Check
- What-if Simulator
- Storytelling 3 lớp

---

## 2. Dataset

| Bảng dữ liệu | Nội dung | Vai trò |
| --- | --- | --- |
| `application_train/test` | Hồ sơ vay chính (~307,000 dòng): thu nhập, nghề nghiệp, tình trạng gia đình, loại vay... | Bảng trung tâm |
| `bureau` | Lịch sử tín dụng của khách hàng tại các tổ chức tín dụng khác | Join theo SK_ID_CURR |
| `bureau_balance` | Lịch sử trả nợ hàng tháng theo từng khoản vay bên ngoài | Aggregate → bureau |
| `previous_application` | Lịch sử các khoản vay trước đó tại chính tổ chức | Join theo SK_ID_CURR |
| `installments_payments` | Lịch sử trả góp thực tế so với kế hoạch | Feature hành vi trả nợ |
| `credit_card_balance` / `POS_CASH_balance` | Số dư thẻ tín dụng & khoản vay trả góp theo tháng | Feature bổ sung |

**Nguồn:** Kaggle — Home Credit Default Risk. Thỏa mãn yêu cầu ≥5,000 dòng và ≥3 bảng liên kết qua khóa chính `SK_ID_CURR`.

---

## 3. Pipeline tổng thể

```
1. Thu thập & Tiền xử lý → 2. Khám phá dữ liệu (EDA) → 3. Dashboard tương tác → 4. Insight & Dự báo (ML)
```

### 3.1 Thu thập & Tiền xử lý

- Join/Merge các bảng theo `SK_ID_CURR`, aggregate bảng phụ (mean/max/count theo nhóm)
- Xử lý missing values, outlier (VD: `DAYS_EMPLOYED` có giá trị bất thường 365243)
- Tạo calculated fields: DTI (Debt-to-Income), tỷ lệ Credit/Annuity, số năm làm việc, nhóm tuổi, số lần trễ hạn trong quá khứ

### 3.2 Khám phá dữ liệu (EDA)

- Phân phối thu nhập theo Target (default/non-default)
- Tỷ lệ vỡ nợ theo nhóm tuổi, nghề nghiệp, loại hợp đồng vay
- Correlation heatmap giữa các biến số & Boxplot outlier trước/sau xử lý

### 3.3 Dashboard trực quan hóa tương tác

- **Công cụ:** Power BI (Python xử lý pipeline và mô hình)
- **8+ loại biểu đồ:** Bar, Line, Pie/Donut, Scatter, Heatmap, Treemap, Boxplot, và **Map** (phân bố rủi ro theo vùng)
- **Tính năng:** Filter nhiều cấp, Drill-down, Tooltip, Cross-filtering giữa các biểu đồ
- **Điểm nhấn:** What-if Simulator — nhập thông tin khách hàng, hệ thống trả về risk score tức thì

### 3.4 Insight & Mô hình dự báo

- Logistic Regression (baseline bắt buộc theo đề) + XGBoost/LightGBM (nâng cao)
- Xử lý mất cân bằng dữ liệu bằng SMOTE / class weighting
- SHAP values giải thích đóng góp từng đặc trưng vào dự đoán
- Quy đổi xác suất vỡ nợ → Credit Score (thang 300–850) & phân lớp Risk Tier (Low/Medium/High)

---

## 4. Các điểm nhấn nâng cao (mục tiêu vượt barem)

1. **Credit Scoring System** — Quy đổi xác suất vỡ nợ (log-odds) thành thang điểm tín dụng chuẩn ngành (300–850, tương tự FICO), thay vì chỉ xuất nhãn 0/1.

2. **Expected Loss & Phân tích lợi nhuận** — Ước tính nếu ngân hàng áp dụng mô hình, giảm bao nhiêu % nợ xấu / tăng bao nhiêu % lợi nhuận cho vay — gắn kết quả kỹ thuật với giá trị kinh doanh cụ thể.

3. **XGBoost/LightGBM + SHAP** — So sánh với Logistic Regression baseline, dùng SHAP để giải thích model ở mức từng khách hàng (explainable AI), thể hiện chiều sâu kỹ thuật khi vấn đáp.

4. **Xử lý Imbalanced Data** — Chủ động phát hiện và xử lý mất cân bằng lớp (tỷ lệ vỡ nợ thực tế thường chỉ 5–8%) bằng SMOTE/class weighting, tránh đánh giá sai lệch bằng accuracy.

5. **Fairness Check & Model Validation** — Kiểm tra model có thiên lệch (bias) theo giới tính/độ tuổi không; phân tích trade-off giữa False Positive và False Negative theo các ngưỡng (threshold) khác nhau, gắn với chi phí kinh doanh thực tế.

---

## 5. Đối chiếu với Barem chấm điểm (10 điểm)

| Hạng mục Barem | Điểm | Cách đồ án đáp ứng / vượt yêu cầu |
| --- | --- | --- |
| Thu thập & Tiền xử lý dữ liệu | 2.5 | Multi-table Home Credit, xử lý missing/outlier triệt để, calculated fields có ý nghĩa nghiệp vụ (DTI, tỷ lệ vay/thu nhập) |
| Thiết kế & Xây dựng Dashboard | 3.5 | 8+ loại biểu đồ, bản đồ rủi ro theo vùng, filter/drill-down/cross-filtering, **+ What-if Simulator** |
| Phân tích Insight & Dự báo | 2.0 | Logistic Regression đúng yêu cầu, **+ XGBoost/SHAP, Credit Scoring, Expected Loss** |
| Báo cáo khoa học & Demo | 2.0 | Chuẩn IEEE, storytelling 3 lớp (Overview→Diagnostic→Prescriptive), demo đóng vai Risk Analyst |
| **Tổng** | **10.0** | Các điểm nhấn ở mục 4 nhằm đảm bảo phần vấn đáp giữ trọn điểm, không bị trừ |

**Lưu ý về vấn đáp:** Theo barem, điểm có thể bị trừ tối đa 4.0 nếu nhóm không hiểu rõ source code hoặc logic tính toán. Do đó mỗi thành viên cần nắm vững toàn bộ pipeline, không chỉ riêng phần mình phụ trách (chi tiết phân công xem các file `thanh-vien-1-modeling.md`, `thanh-vien-2-data-engineering.md`, `thanh-vien-3-dashboard.md`).

**Lưu ý về Video Demo:** Barem yêu cầu bắt buộc có Video backup tóm tắt kèm báo cáo — đây là việc làm chung của cả 3 thành viên, không được bỏ.

**Lưu ý về Map:** Dataset Home Credit Default Risk không có tọa độ địa lý/tên tỉnh thật, chỉ có mã vùng (`REGION_RATING_CLIENT`). Dashboard vẫn phải có Map theo đúng barem, nhưng cần ghi chú rõ đây là bản đồ minh họa theo Region Rating nội bộ của dataset, không phải vị trí địa lý thực tế (chi tiết xử lý xem mục 2.3.1 trong `thanh-vien-3-dashboard.md`).

---

## 6. Công nghệ sử dụng

| Nhóm | Công cụ / Thư viện |
| --- | --- |
| Ngôn ngữ & xử lý dữ liệu | Python (Pandas, NumPy) |
| Trực quan hóa tĩnh (EDA) | Matplotlib, Seaborn |
| Machine Learning | Scikit-learn (Logistic Regression), XGBoost/LightGBM, imbalanced-learn (SMOTE), SHAP |
| Dashboard tương tác | Power BI |
| Báo cáo & thuyết trình | Word/LaTeX (chuẩn IEEE), PowerPoint/Slide |

---

*Tài liệu tổng quan đồ án — Môn Tương tác Dữ liệu Trực quan | Đề tài: Phân tích rủi ro tín dụng & khả năng vỡ nợ khách hàng cá nhân*
