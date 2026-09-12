# HỢP ĐỒNG GIAO DIỆN MÔ HÌNH HÓA (MODEL INTERFACE CONTRACT)
**Dự án:** Phân tích Rủi ro Tín dụng & Khả năng Vỡ nợ Khách hàng Cá nhân  
**Môn học:** Tương tác Dữ liệu Trực quan  
**Phiên bản:** v1.0 (Official Release)  
**Ngày hiệu lực:** 2026-09-12  

---

## 1. CÁC BÊN THAM GIA & PHẠM VI TRÁCH NHIỆM
* **Bên phát hành (Model Producer):** Thành viên 1 — Phụ trách Modeling & Machine Learning.
* **Bên tiếp nhận chính (Model Consumer):** Thành viên 3 — Phụ trách Power BI Dashboard.
* **Bên thụ hưởng nghiệp vụ (Business Consumer):** Hội đồng Quản trị Rủi ro / Giảng viên hướng dẫn.
* **Mục đích:** Đặc tả chính xác các sản phẩm mô hình đóng gói, cấu trúc dữ liệu kết quả chấm điểm đưa vào Power BI, công thức quy đổi Credit Scorecard (300–850) và logic vận hành phân hệ What-if Simulator.

---

## 2. DANH MỤC MODEL ARTIFACTS BÀN GIAO
Thành viên 1 chịu trách nhiệm huấn luyện, kiểm định và bàn giao các tệp sau vào thư mục `models/`:

| Tên tệp Model | Định dạng | Thuật toán / Thành phần | Mục đích sử dụng |
| :--- | :---: | :--- | :--- |
| `baseline_logistic.pkl` | Joblib / Pickle | Penalized Logistic Regression (L2) | Benchmark đối chuẩn và giải thích hệ số Odds Ratio |
| `final_model_xgboost.pkl`| Joblib / Pickle | Tuned XGBoost Classifier (scale_pos_weight) | Mô hình phân loại tối ưu hiệu năng ROC-AUC / PR-AUC |
| `full_inference_pipeline.pkl`| Joblib / Pickle | `sklearn.pipeline.Pipeline`: ColumnTransformer + XGBoost | Pipeline hoàn chỉnh phục vụ suy luận What-if Simulator |

---

## 3. ĐẶC TẢ DỮ LIỆU CHẤM ĐIỂM CHO POWER BI (`scored_dataset.csv`)
Để Power BI tải mượt mà và trực quan hóa toàn bộ danh mục, Thành viên 1 sau khi huấn luyện mô hình sẽ xuất ra tệp:
`data/processed/scored_dataset.csv`

### Cấu trúc Schema bắt buộc:
| Tên trường | Kiểu dữ liệu | Dải giá trị | Định nghĩa & Ý nghĩa nghiệp vụ |
| :--- | :---: | :---: | :--- |
| `SK_ID_CURR` | `int64` | Khóa chính | Khóa liên kết 1-1 với `cleaned_dataset.csv` trong Power BI Data Model |
| `TARGET` | `int8` | $\{0, 1\}$ | Nhãn thực tế (Dùng đối chứng ma trận nhầm lẫn Confusion Matrix) |
| `PREDICTED_PD` | `float32` | $[0.0000, 1.0000]$ | Xác suất vỡ nợ dự báo từ mô hình XGBoost ($PD = P(Y=1|X)$) |
| `CREDIT_SCORE` | `int32` | $[300, 850]$ | Điểm tín dụng chuẩn hóa theo phương pháp PDO |
| `RISK_TIER` | `string` | `'Low'`, `'Medium'`, `'High'` | Phân tầng cấp độ rủi ro danh mục |
| `RECOMMENDATION` | `string` | `'APPROVE'`, `'REVIEW'`, `'REJECT'` | Khuyến nghị thẩm định tự động theo chính sách cắt ngưỡng |
| `EXPECTED_LOSS` | `float64` | $\ge 0$ | Ước tính tổn thất kỳ vọng theo kịch bản: $EL = PD 	imes 45\% 	imes 	ext{AMT\_CREDIT}$ |
| `AMT_CREDIT` | `float64` | $>0$ | Số tiền vay (dùng làm trục phân tích dư nợ trong Power BI) |
| `AMT_INCOME_TOTAL` | `float64` | $>0$ | Thu nhập khách hàng (dùng làm trục phân tích) |
| `AGE_GROUP` | `string` | Danh mục 5 nhóm | Phục vụ Slicers lọc đa cấp trên Dashboard |
| `REGION_RATING_CLIENT`| `int8` | $\{1, 2, 3\}$ | Dùng tô màu Choropleth Map phân bố rủi ro |
| `OCCUPATION_TYPE` | `string` | Danh mục nghề | Phục vụ Bar Chart xếp hạng nợ xấu |

---

## 4. CÔNG THỨC TOÁN HỌC & LOGIC QUY ĐỔI NGHIỆP VỤ

### 4.1. Chuyển đổi Thang điểm Tín dụng (Credit Scorecard Scaling via PDO)
Không gán điểm tùy tiện; bắt buộc áp dụng công thức Scorecard chuẩn ngành (Siddiqi, 2006):
$$	ext{Score} = 	ext{Offset} + 	ext{Factor} 	imes \ln\left(rac{1 - PD}{PD}ight)$$

* **Các tham số thiết lập:**
  * $	ext{Base Score} = 600$ điểm tại $	ext{Base Odds} = 50:1$ (tương đương xác suất vỡ nợ $PD = rac{1}{1 + 50} pprox 1.96\%$).
  * $	ext{PDO (Points to Double the Odds)} = 20$ (điểm tăng 20 khi tỷ lệ cược tốt/xấu tăng gấp đôi).
* **Tính toán hằng số:**
  $$	ext{Factor} = rac{	ext{PDO}}{\ln(2)} = rac{20}{0.693147} pprox 28.8539$$
  $$	ext{Offset} = 	ext{Base Score} - 	ext{Factor} 	imes \ln(	ext{Base Odds}) = 600 - 28.8539 	imes \ln(50) pprox 487.123$$
* **Ràng buộc chặn biên:** $	ext{Score} = \max(300, \min(850, 	ext{round}(	ext{Score})))$.

### 4.2. Phân nhóm Cấp độ Rủi ro (Risk Tier Boundaries)
Thành viên 3 cấu hình phân tầng trên Power BI theo đúng quy ước:
* **Low Risk (Rủi ro Thấp):** Điểm $701 - 850$ (Xác suất vỡ nợ thấp, khách hàng tín nhiệm cao).
* **Medium Risk (Rủi ro Trung bình):** Điểm $581 - 700$ (Cần kiểm soát hồ sơ hoặc yêu cầu bảo lãnh).
* **High Risk (Rủi ro Cao):** Điểm $300 - 580$ (Nguy cơ nợ xấu cao, hạn chế phê duyệt).

### 4.3. Chính sách Quyết định Tín dụng (Automated Decision Policy)
Dựa trên ngưỡng cắt tối ưu chi phí kinh doanh $th^*$ (do Thành viên 2 và 1 tính toán tại Task CR-11.2, dự kiến $th^* pprox 0.18 - 0.22$):
* **AUTO APPROVE (Duyệt tự động):** Khi $PD < th^*$ VÀ $	ext{Risk Tier} == 	ext{'Low Risk'}$.
* **MANUAL REVIEW (Thẩm định thủ công / Bổ sung tài liệu):** Khi $th^* \le PD < 0.35$ HOẶC $	ext{Risk Tier} == 	ext{'Medium Risk'}$.
* **AUTO REJECT (Từ chối tự động):** Khi $PD \ge 0.35$ HOẶC $	ext{Risk Tier} == 	ext{'High Risk'}$.

---

## 5. GIAO THỨC TÍCH HỢP POWER BI DASHBOARD
Thành viên 3 triển khai Dashboard theo 2 cơ chế phối hợp:

### Cơ chế 1: Phân tích Toàn cảnh Danh mục (Portfolio BI)
* Power BI nạp trực tiếp `data/processed/scored_dataset.csv`.
* Tạo Relationship 1-1 với `cleaned_dataset.csv` theo khóa `SK_ID_CURR`.
* Hiển thị các visual bắt buộc: Donut (hợp đồng), Bar (ngành nghề), Line (thâm niên), Scatter (thu nhập vs khoản vay), Heatmap (tuổi x học vấn), Treemap (cơ quan), Boxplot (DTI), Choropleth Map (`REGION_RATING_CLIENT`).
* Cấu hình tính năng **Cross-filtering** (1.5đ barem): chọn một ngành trên Bar chart sẽ tự động lọc động toàn bộ các biểu đồ còn lại.

### Cơ chế 2: Phân hệ What-if Simulator trong Power BI
* **Tùy chọn A (Power BI Native - Khuyến nghị):** Tạo bảng **What-if Parameters** cho các biến đầu vào chính (Thu nhập, Số tiền vay, Kỳ hạn, Tuổi). Viết công thức **DAX Measure** ánh xạ hàm hồi quy Logistic / cây điểm từ `models/scoring.py` để khi người dùng kéo thanh trượt, thẻ KPI lập tức hiển thị động Điểm tín dụng và Khuyến nghị đổi màu.
* **Tùy chọn B (Python Visual):** Nhúng mã nguồn Python trực tiếp vào visual của Power BI:
  ```python
  import joblib, pandas as pd
  model = joblib.load(r'd:\ttdltq\models\full_inference_pipeline.pkl')
  ```

---

## 6. KIỂM THỬ TÍCH HỢP & XỬ LÝ LỖI ĐẦU VÀO (ERROR HANDLING)
* Thành viên 1 cung cấp tệp test mẫu `sample_applicant.json` chứa 1 hồ sơ tốt và 1 hồ sơ xấu.
* Nếu người dùng nhập thiếu dữ liệu trên Simulator: Pipeline tự động gán giá trị Median/Mode đã học lúc huấn luyện, tuyệt đối không được làm sập ứng dụng Dashboard.
