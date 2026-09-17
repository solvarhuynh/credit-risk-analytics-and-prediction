# Phân tích Rủi ro Tín dụng & Dự báo Khả năng Vỡ nợ Khách hàng Cá nhân
**(Retail Credit Risk Analytics & Default Prediction Dashboard)**

> Đồ án môn học: **Tương tác Dữ liệu Trực quan**  
> Bộ dữ liệu: [Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk/data)  
> Công nghệ cốt lõi: Python (Data Pipeline, Scikit-learn, XGBoost, SHAP) & Microsoft Power BI

---

## 1. Tổng quan Dự án

Dự án xây dựng một giải pháp hoàn chỉnh và có tính giải thích cao (Explainable AI) phục vụ công tác quản trị rủi ro tín dụng bán lẻ tại tổ chức tài chính. Quy trình bao gồm:
1. **Data Engineering:** Tiếp nhận, làm sạch và tổng hợp dữ liệu quan hệ đa bảng (7 bảng liên kết) theo nguyên tắc *Aggregate-first, Join-later* nhằm tránh nhân bản dòng và rò rỉ dữ liệu (leakage-free).
2. **Exploratory Data Analysis (EDA):** Phân tích tương quan, cấu trúc phân phối và mẫu hình hành vi của khách hàng tốt/xấu qua các biểu đồ thống kê chuyên sâu.
3. **Predictive Modeling:** Huấn luyện mô hình cơ sở (Logistic Regression) và mô hình phi tuyến nâng cao (XGBoost/LightGBM) với chiến lược xử lý mất cân bằng lớp (class weighting, SMOTE trên tập train) và đánh giá qua các thước đo bất biến với phân phối (ROC-AUC, PR-AUC, Brier Score).
4. **Model Interpretability (XAI):** Bóc tách cơ chế ra quyết định của mô hình thông qua giá trị SHAP ở cả cấp độ toàn danh mục (Global Beeswarm) và từng hồ sơ cá nhân (Local Waterfall).
5. **Credit Scoring & Cost Optimization:** Quy đổi xác suất vỡ nợ ($PD$) sang thang điểm tín dụng chuẩn ngành (300–850) bằng phương pháp PDO (Points to Double the Odds); xác định ngưỡng phê duyệt ($th^*$) tối ưu hóa hàm chi phí thiệt hại tài chính phi đối xứng; ước tính tổn thất kỳ vọng theo kịch bản ($EL = PD \times LGD \times EAD$).
6. **Decision Support Dashboard (Power BI):** Trực quan hóa tương tác đa chiều danh mục cho vay (≥ 8 loại biểu đồ, liên kết Cross-filtering, Drill-down) và tích hợp công cụ thẩm định động (What-if Simulator).

---

## 2. Kiến trúc Thư mục

```text
ttdltq/
├── data/                  # Quản lý dữ liệu đa tầng (local-only, được .gitignore bảo vệ)
│   ├── raw/               # 7 tệp CSV thô tải từ Kaggle Home Credit
│   ├── interim/           # Dữ liệu trung gian sau bước tổng hợp bảng phụ
│   └── processed/         # cleaned_dataset.parquet, scored_dataset.parquet, data_dictionary.csv
├── dashboard/             # Phân hệ Dashboard Power BI (.pbix) và assets giao diện
├── docs/                  # Tài liệu kiến trúc, giao ước kỹ thuật và phân công chi tiết
│   ├── architecture/      # Đặc tả kiến trúc repo, sơ đồ liên kết và quyết định kỹ thuật
│   ├── contracts/         # Data Contract (TV2 -> TV1/TV3) & Model Contract (TV1 -> TV3)
│   ├── overview/          # Đề bài, rubric barem chấm điểm và tổng quan đề tài
│   └── tasks/             # Bảng phân công chi tiết và quy trình làm việc (working-protocol)
├── logs/                  # Nhật ký tiến độ làm việc độc lập của từng thành viên (log_tv1..tv3)
├── models/                # Checkpoints và model artifacts đóng gói (.joblib / .pkl)
├── notebooks/             # 8 Jupyter Notebooks phân tích tuần tự (00_data_profiling -> 07_scoring)
├── reports/               # Báo cáo IEEE (>=40 trang), hình ảnh biểu đồ vector, slides, link video demo
├── src/                   # Mã nguồn Python dạng module chuẩn hóa
│   ├── config.py          # Hằng số toàn cục, đường dẫn và random seed
│   ├── data/              # Module load, clean, aggregate và pipeline thực thi
│   ├── features/          # Module xây dựng đặc trưng tài chính phái sinh (DTI, Annuity/Income)
│   ├── models/            # Module chia dữ liệu, tiền xử lý, huấn luyện, chấm điểm và đánh giá
│   └── dashboard/         # Backend adapter phục vụ suy luận What-if Simulator
├── requirements.txt       # Danh mục thư viện Python đồng bộ
└── README.md
```

---

## 3. Thiết lập Môi trường & Thực thi (Quickstart)

### Bước 1: Khởi tạo môi trường ảo Python (Yêu cầu Python 3.10 – 3.12)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

### Bước 2: Chuẩn bị Dữ liệu thô
Tải dataset [Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk/data) và giải nén các tệp CSV vào thư mục `data/raw/`:
* `application_train.csv`, `bureau.csv`, `bureau_balance.csv`
* `previous_application.csv`, `installments_payments.csv`, `POS_CASH_balance.csv`, `credit_card_balance.csv`

### Bước 3: Chạy Pipeline Xử lý Dữ liệu
```bash
python -m src.data.build_pipeline
```
Lệnh trên thực thi đọc dữ liệu thô, làm sạch dị biệt, aggregate các bảng quan hệ và xuất bản:
* `data/processed/cleaned_dataset.parquet`
* `data/processed/data_dictionary.csv`

### Bước 4: Chạy Luồng Huấn luyện & Chấm điểm Tín dụng
Thực thi các module mô hình hóa để huấn luyện và xuất bản:
* `models/full_inference_pipeline.joblib`
* `data/processed/scored_dataset.parquet`

### Bước 5: Khởi chạy Dashboard
Mở tệp `dashboard/Credit_Risk_Analytics.pbix` bằng **Power BI Desktop**, kết nối nguồn dữ liệu `data/processed/` đã tạo để xem báo cáo và kiểm thử tương tác.

---

## 4. Sản phẩm Đầu ra Chính (Deliverables)

| Sản phẩm | Vị trí / Định dạng | Mô tả kỹ thuật |
| :--- | :--- | :--- |
| **Cleaned Dataset** | `data/processed/cleaned_dataset.parquet` | Bảng hợp nhất cấp độ khách hàng (`SK_ID_CURR`), không trùng lặp dòng, tích hợp đầy đủ biến phái sinh |
| **Data Dictionary** | `data/processed/data_dictionary.csv` | Bảng mô tả chi tiết tên biến, kiểu dữ liệu, nguồn gốc và công thức tính |
| **Model Pipeline** | `models/full_inference_pipeline.joblib` | Scikit-learn Pipeline tích hợp trọn vẹn ColumnTransformer tiền xử lý và mô hình phân loại |
| **Scored Dataset** | `data/processed/scored_dataset.parquet` | Bảng dữ liệu tích hợp xác suất vỡ nợ ($PD$), điểm tín dụng (300–850), Risk Tier và khuyến nghị quyết định |
| **Interactive Dashboard** | `dashboard/Credit_Risk_Analytics.pbix` | Dashboard Power BI tương tác cao (≥ 8 biểu đồ, Cross-filtering, Drill-down, What-if Simulator) |
| **Báo cáo Khoa học** | `reports/Report_Credit_Risk_IEEE.docx` | Báo cáo định dạng chuẩn IEEE, dung lượng ≥ 40 trang, phân tích học thuật toàn diện |
| **Slide & Video Demo** | `reports/slides/`, `reports/video/` | Slide thuyết trình nghiệp vụ và Video Demo tóm tắt (5–8 phút) dự phòng |

---

## 5. Phân công Trách nhiệm Nhóm

* **Thành viên 1 — Modeling & Machine Learning:**
  * Chủ trì thiết kế kiến trúc mô hình, huấn luyện Baseline Logistic Regression và mô hình nâng cao (XGBoost).
  * Xử lý mất cân bằng mẫu, phân tích tầm quan trọng đặc trưng bằng SHAP, xây dựng công thức Credit Scorecard (PDO), tối ưu hóa ngưỡng cắt ($th^*$) và ước tính Expected Loss.
  * Hỗ trợ review schema và kiểm toán rò rỉ dữ liệu.
* **Thành viên 2 — Data Engineering & Pipeline:**
  * Chủ trì thu thập dữ liệu, kiểm toán schema thô, xử lý làm sạch ngoại lai (`DAYS_EMPLOYED = 365243`).
  * Thiết kế logic aggregate bảng phụ 1-nhiều về grain `SK_ID_CURR`, thực hiện join đa bảng không nhân bản dòng, tạo lập đặc trưng tài chính phái sinh, biên soạn Data Dictionary và vẽ biểu đồ EDA tĩnh.
  * Hỗ trợ chẩn đoán tính công bằng (Fairness Check).
* **Thành viên 3 — Dashboard & Visualization:**
  * Chủ trì thiết kế và xây dựng Dashboard tương tác trên Microsoft Power BI (≥ 8 loại biểu đồ, bản đồ rủi ro, liên kết Cross-filtering toàn diện).
  * Hiện thực hóa công cụ mô phỏng thẩm định thời gian thực (What-if Simulator).
  * Hỗ trợ chuẩn hóa bảng màu và phong cách trực quan cho các biểu đồ EDA.
* **Toàn bộ Thành viên:**
  * Phối hợp xây dựng câu chuyện dữ liệu 3 lớp (Overview → Diagnostic → Prescriptive).
  * Hoàn thiện Báo cáo khoa học chuẩn IEEE, slide thuyết trình, quay video demo dự phòng và diễn tập vấn đáp phản biện.

---

## 6. Tài liệu Tham chiếu Chi tiết

* [Kiến trúc Repository & Các luồng Liên kết](docs/architecture/repo_structure_and_linkages.md)
* [Sổ tay Quyết định Kỹ thuật & Quản trị Rủi ro Khoa học](docs/architecture/decisions-and-risks.md)
* [Hợp đồng Dữ liệu (Data Contract: TV2 → TV1, TV3)](docs/contracts/data_contract.md)
* [Hợp đồng Mô hình (Model Interface Contract: TV1 → TV3)](docs/contracts/model_contract.md)
* [Quy chế Phân công Trách nhiệm & Ma trận RACI](docs/tasks/phan-cong-nhiem-vu.md)
* [Quy trình Phối hợp Kỹ thuật & Quy ước Git](docs/tasks/working-protocol.md)
