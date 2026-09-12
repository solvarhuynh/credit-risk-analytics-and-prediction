# CẤU TRÚC TOÀN BỘ REPOSITORY VÀ KIỂU LIÊN KẾT HỆ THỐNG
> **Đề tài:** Phân tích rủi ro tín dụng và khả năng vỡ nợ của khách hàng cá nhân  
> **Môn học:** Tương tác Dữ liệu Trực quan  
> **Công cụ Dashboard:** Microsoft Power BI  
> **Mã nguồn Git:** [solvarhuynh/credit-risk-analytics-and-prediction](https://github.com/solvarhuynh/credit-risk-analytics-and-prediction)  
> **Quy mô nhóm:** 3 Thành viên

---

## 1. TOÀN BỘ CẤU TRÚC REPOSITORY (DIRECTORY TREE)

`	ext
ttdltq/
│
├── .git/                               # Quản trị phiên bản Git cục bộ (kết nối remote GitHub)
├── .gitignore                          # Cấu hình bỏ qua dữ liệu nặng, model, venv, cache
├── LICENSE                             # Giấy phép nguồn mở MIT (Copyright (c) 2026 Nghĩa Huỳnh)
├── README.md                           # Giới thiệu tổng quan, hướng dẫn thiết lập và tái lập kết quả
├── requirements.txt                    # Danh mục các thư viện Python cốt lõi cần cài đặt
├── note.md                             # Ghi chú định hướng công cụ (Power BI)
├── Barem-TTDLTQ.docx                   # Đề cương & Barem chấm điểm chính thức của Giảng viên
├── overview-du-an.pdf                  # Tài liệu PDF tổng quan ban đầu của dự án
│
├── docs/                               # TÀI LIỆU DỰ ÁN (CHIA THÀNH 4 THƯ MỤC CON CHUYÊN BIỆT)
│   ├── overview/                       # TỔNG QUAN ĐỒ ÁN & TÀI LIỆU CHỈ ĐẠO CỦA GIẢNG VIÊN
│   │   ├── overview.md                 # Tổng quan đề tài, bài toán kinh doanh, mục tiêu điểm 9.5+
│   │   ├── overview-du-an.pdf          # File PDF tổng quan chính thức
│   │   └── Barem-TTDLTQ.docx           # Đề cương & Barem chấm điểm chính thức của Giảng viên
│   ├── contracts/                      # HỢP ĐỒNG KỸ THUẬT & GIAO ƯỚC BÀN GIAO NỘI BỘ
│   │   ├── data_contract.md            # Giao ước schema bàn giao dữ liệu sạch: TV2 -> TV1 & TV3
│   │   └── model_contract.md           # Giao ước interface mô hình & Power BI: TV1 -> TV3
│   ├── architecture/                   # THIẾT KẾ KIẾN TRÚC & LIÊN KẾT HỆ THỐNG
│   │   ├── repo_structure_and_linkages.md # [FILE NÀY] Đặc tả toàn bộ repo và các luồng liên kết
│   │   └── note.md                     # Ghi chú định hướng công cụ Power BI
│   └── tasks/                          # PHÂN CÔNG NHIỆM VỤ CHI TIẾT 3 THÀNH VIÊN
│       ├── phan-cong-nhiem-vu.md       # Phân công tổng quan, timeline và kịch bản vấn đáp
│       ├── thanh-vien-1-modeling.md    # Chi tiết công việc Thành viên 1 (Modeling & ML)
│       ├── thanh-vien-2-data-engineering.md # Chi tiết công việc Thành viên 2 (Data Pipeline)
│       └── thanh-vien-3-dashboard.md   # Chi tiết công việc Thành viên 3 (Power BI Dashboard)
│
├── data/                               # QUẢN LÝ DỮ LIỆU ĐA TẦNG (ĐƯỢC .GITIGNORE BẢO VỆ)
│   ├── raw/                            # 7 bảng CSV thô tải từ Kaggle Home Credit Default Risk
│   │   ├── application_train.csv       # Bảng trung tâm (~307,000 dòng, chứa biến mục tiêu TARGET)
│   │   ├── bureau.csv                  # Lịch sử tín dụng tại các tổ chức khác (nhiều dòng/khách)
│   │   ├── bureau_balance.csv          # Lịch sử trả nợ hàng tháng theo từng khoản vay bên ngoài
│   │   ├── previous_application.csv    # Lịch sử các hợp đồng vay trước tại chính Home Credit
│   │   ├── installments_payments.csv   # Lịch sử trả nợ thực tế so với lịch trả góp
│   │   ├── credit_card_balance.csv     # Biến động số dư và hạn mức thẻ tín dụng
│   │   └── POS_CASH_balance.csv        # Số dư các khoản vay tiêu dùng trả góp qua điểm bán
│   ├── interim/                        # Lưu trữ dữ liệu trung gian sau khi aggregate các bảng phụ
│   └── processed/                      # Bộ dữ liệu hoàn chỉnh sẵn sàng cho mô hình và Power BI
│       ├── cleaned_dataset.csv         # Dữ liệu sạch hợp nhất cấp khách hàng SK_ID_CURR
│       ├── scored_dataset.csv          # Dữ liệu đã chấm điểm PD, Credit Score, Risk Tiers (cho Power BI)
│       └── data_dictionary.csv         # Từ điển dữ liệu mô tả chi tiết ngữ nghĩa từng trường
│
├── src/                                # MÃ NGUỒN PYTHON MODULE HÓA (DÙNG CHUNG)
│   ├── __init__.py
│   ├── config.py                       # Cấu hình đường dẫn toàn cục, random seed, tham số scorecard
│   ├── data/                           # [Thành viên 2 chủ trì]
│   │   ├── __init__.py
│   │   ├── load_data.py                # Hàm tải dữ liệu thô và tối ưu bộ nhớ RAM
│   │   ├── cleaning.py                 # Hàm làm sạch ngoại lai, dị biệt DAYS_EMPLOYED=365243
│   │   ├── aggregate.py                # Hàm rollup/aggregate bảng 1-nhiều về grain SK_ID_CURR
│   │   └── build_pipeline.py           # Pipeline tự động chạy toàn bộ từ Raw -> Processed
│   ├── features/                       # [Thành viên 2 & 1 cùng làm]
│   │   ├── __init__.py
│   │   └── engineering.py              # Hàm tính chỉ số tài chính (DTI, Annuity/Income, Ext_Source)
│   ├── models/                         # [Thành viên 1 chủ trì]
│   │   ├── __init__.py
│   │   ├── preprocess_pipeline.py      # ColumnTransformer độc lập fit trên Train set
│   │   ├── scoring.py                  # Công thức PDO quy đổi PD sang Credit Score 300-850
│   │   └── cost_optimization.py        # Hàm quét ma trận chi phí tìm ngưỡng cắt tối ưu th*
│   └── dashboard/                      # [Thành viên 3 chủ trì]
│       ├── __init__.py
│       └── simulator_engine.py         # Hàm kết nối suy luận điểm số phục vụ Power BI / Python
│
├── notebooks/                          # JUPYTER NOTEBOOKS PHÂN TÍCH TUẦN TỰ (00 -> 07)
│   ├── 00_data_profiling.ipynb         # [TV2] Đo missing, kiểm tra cấu trúc 7 bảng dữ liệu thô
│   ├── 01_data_cleaning_pipeline.ipynb # [TV2] Thực thi làm sạch, aggregate và join đa bảng
│   ├── 02_feature_engineering.ipynb    # [TV2 + TV1] Tạo các tỷ lệ tài chính phái sinh
│   ├── 03_eda_statistical.ipynb        # [TV2 + TV3] Phân phối, tương quan, trích xuất 3-5 hình tĩnh
│   ├── 04_baseline_and_imbalance.ipynb # [TV1] Baseline Logistic Regression, kiểm định SMOTE vs Weights
│   ├── 05_advanced_modeling.ipynb      # [TV1] Huấn luyện XGBoost, tinh chỉnh tham số qua CV
│   ├── 06_model_interpretability.ipynb # [TV1] Bóc tách mô hình qua SHAP Beeswarm & Waterfall
│   └── 07_scoring_and_fairness.ipynb   # [TV1 + TV2] Credit Score, Expected Loss, Fairness Check
│
├── models/                             # LƯU TRỮ MODEL ARTIFACTS ĐÃ HUẤN LUYỆN
│   ├── .gitkeep
│   ├── baseline_logistic.pkl           # Trọng số mô hình baseline hồi quy Logistic
│   ├── final_model_xgboost.pkl         # Trọng số mô hình nâng cao XGBoost tối ưu
│   └── full_inference_pipeline.pkl     # Pipeline trọn vẹn (ColumnTransformer + Model) cho suy luận
│
├── dashboard/                          # PHÂN HỆ DASHBOARD TƯƠNG TÁC POWER BI [Thành viên 3]
│   ├── Credit_Risk_Analytics.pbix      # Tệp báo cáo Power BI chính thức (>= 8 visual, Map, Cross-filter)
│   └── assets/                         # Ảnh nền, icon thẩm định, theme màu sắc chuẩn IEEE
│       └── .gitkeep
│
└── reports/                            # BÁO CÁO HỌC THUẬT, SLIDES & VIDEO DEMO CUỐI CÙNG
    ├── Report_Credit_Risk_IEEE.docx    # Báo cáo khoa học chuẩn IEEE (độ dài >= 40 trang)
    ├── figures/                        # Lưu trữ toàn bộ biểu đồ vector độ phân giải cao (300 DPI)
    │   ├── eda/                        # Biểu đồ phân phối, boxplot trước/sau làm sạch, tương quan
    │   ├── model/                      # Đường cong ROC, PR, SHAP Beeswarm, Waterfall plots
    │   └── dashboard/                  # Ảnh chụp các màn hình Power BI và phân hệ Simulator
    ├── slides/                         # Slide thuyết trình bảo vệ đồ án
    │   └── Slides_Credit_Risk.pptx     # File PowerPoint thuyết trình kịch bản Risk Analyst
    └── video/                          # Video Demo dự phòng (bắt buộc theo Barem)
        └── video_demo_link.txt         # Link lưu trữ Video Demo tóm tắt (5 - 8 phút)
`

---

## 2. CÁC KIỂU LIÊN KẾT TRONG HỆ THỐNG (SYSTEM LINKAGES & DATA FLOW)

### 2.1 Liên kết Luồng Dữ liệu (Data Pipeline Flow)
`
[data/raw/ (7 CSVs)]
       │
       ▼  (được gọi bởi src/data/load_data.py)
[src/data/cleaning.py] ──► Xử lý DAYS_EMPLOYED = 365243, chuẩn hóa kiểu
       │
       ▼
[src/data/aggregate.py] ──► Rollup bureau, prev_app, installments về SK_ID_CURR
       │
       ▼
[Multi-table Left Join] ──► Nối vào application_train theo khóa chính SK_ID_CURR
       │
       ▼
[src/features/engineering.py] ──► Tính DTI, Annuity/Income, Ext_Source composites
       │
       ▼
[data/processed/cleaned_dataset.csv]  <=== [DATA CONTRACT BÀN GIAO]
`

### 2.2 Liên kết Luồng Mô hình hóa & Chấm điểm (ML & Scoring Flow)
`
[data/processed/cleaned_dataset.csv]
       │
       ▼
[Stratified 80/20 Train-Test Split]
       │
       ├─► [Train Set (80%)] ──► [src/models/preprocess_pipeline.py] (Fit ColumnTransformer)
       │                                │
       │                                ▼
       │                         [Train Baseline Logistic & XGBoost via 5-Fold CV]
       │                                │
       │                                ▼
       │                         [Export: models/full_inference_pipeline.pkl]
       │
       └─► [Test Set (20%)]  ──► [Apply Transform & Predict Proba (PD)]
                                        │
                                        ▼
                                 [src/models/scoring.py (Công thức PDO)]
                                        │
                                        ▼
                                 [data/processed/scored_dataset.csv]
                                 (Chứa: SK_ID_CURR, TARGET, PD, Score 300-850, Risk Tier)
`

### 2.3 Liên kết Luồng Tích hợp Power BI (Power BI Integration Flow)
Vì dự án thống nhất dùng **Power BI**, liên kết kỹ thuật được thiết kế tối ưu như sau:
1. **Liên kết Báo cáo Tổng thể & Phân tích Đa chiều:**
   * Power BI (dashboard/Credit_Risk_Analytics.pbix) kết nối trực tiếp nguồn dữ liệu từ:
     * data/processed/cleaned_dataset.csv (dữ liệu đặc trưng nhân khẩu & hành vi).
     * data/processed/scored_dataset.csv (dữ liệu kết quả mô hình: xác suất $, Credit Score, Risk Tiers).
   * Cấu hình quan hệ 1-1 qua khóa chính SK_ID_CURR.
   * Vận hành $\ge 8$ loại biểu đồ: Donut (loại vay), Bar (nghề nghiệp), Line (thâm niên), Scatter (thu nhập vs khoản vay), Heatmap (tuổi x học vấn), Treemap (cơ quan), Boxplot (DTI), và **Choropleth Map** (phân bố theo REGION_RATING_CLIENT).
   * Bật liên kết **Cross-filtering** toàn diện giữa tất cả các biểu đồ.

2. **Liên kết Phân hệ What-if Simulator trong Power BI:**
   * *Cách 1 (Khuyến nghị):* Nhập thông số qua bảng tham số What-if Parameter của Power BI kết hợp DAX Scorecard Engine (triển khai trực tiếp công thức Scorecard PDO từ src/models/scoring.py vào công thức DAX).
   * *Cách 2:* Sử dụng Python Script Visual trong Power BI gọi models/full_inference_pipeline.pkl và hàm src/dashboard/simulator_engine.py để trả về xác suất và khuyến nghị thẩm định tức thì.

### 2.4 Liên kết Sang Báo cáo Khoa học & Đầu ra (Deliverables Flow)
`
[notebooks/03_eda_statistical.ipynb]      ──► Xuất ảnh EDA (300 DPI) ──┐
[notebooks/05_advanced_modeling.ipynb]    ──► Xuất ảnh ROC/PR Curves ──┼─► [reports/figures/]
[notebooks/06_model_interpretability.ipynb]──► Xuất ảnh SHAP plots   ──┤         │
[dashboard/Credit_Risk_Analytics.pbix]    ──► Screenshots Dashboard  ──┘         │
                                                                                 ▼
                                                      [reports/Report_Credit_Risk_IEEE.docx]
                                                      (Báo cáo chuẩn IEEE >= 40 trang)
                                                                                 │
                                                      [reports/slides/Slides_Credit_Risk.pptx]
                                                                                 │
                                                      [reports/video/video_demo_link.txt]
`

---

## 3. MA TRẬN LIÊN KẾT TRÁCH NHIỆM 3 THÀNH VIÊN

| Thành viên | Không gian làm việc chính trong Repo | Đầu vào tiêu thụ (Input) | Đầu ra sản sinh (Output) | Bàn giao cho ai (Handoff) |
| :--- | :--- | :--- | :--- | :--- |
| **Thành viên 2** (Data Engineering & Pipeline) | src/data/, src/features/, 
otebooks/00..03, data/processed/ | Dữ liệu thô tại data/raw/ | cleaned_dataset.csv, data_dictionary.csv, hình vẽ EDA | Bàn giao dữ liệu cho TV1 & TV3; hình vẽ cho Báo cáo |
| **Thành viên 1** (Modeling & Machine Learning) | src/models/, 
otebooks/04..07, models/ | cleaned_dataset.csv từ TV2 | models/full_inference_pipeline.pkl, scored_dataset.csv, hình SHAP/ROC | Bàn giao mô hình và số liệu điểm cho TV3; kết quả cho Báo cáo |
| **Thành viên 3** (Power BI Dashboard) | dashboard/, src/dashboard/, 
eports/figures/dashboard/ | cleaned_dataset.csv, scored_dataset.csv, model .pkl | File Credit_Risk_Analytics.pbix, ảnh chụp dashboard | Tích hợp vào Báo cáo IEEE, Slide thuyết trình và Video Demo |
| **Cả 3 Thành viên** | 
eports/, docs/ | Toàn bộ kết quả từ Data, Model và Dashboard | Báo cáo IEEE $\ge 40$ trang, Slide PPTX, Video Demo 5–8 phút | Giảng viên hướng dẫn & Hội đồng chấm bảo vệ |

---

## 4. LIÊN KẾT QUẢN TRỊ PHIÊN BẢN GIT (GIT REMOTE LINKAGE)

* **Repository Remote URL:** https://github.com/solvarhuynh/credit-risk-analytics-and-prediction.git
* **Nhánh chính (Trunk):** main
* **Quy tắc bảo toàn dữ liệu:**
  * File .gitignore bảo vệ nghiêm ngặt các thư mục data/raw/, data/interim/, data/processed/*.csv, models/*.pkl.
  * Các thư mục rỗng được giữ lại trên Git nhờ tệp giữ chỗ .gitkeep.
  * Mọi thành viên commit code, tài liệu và notebook sạch lên nhánh main (hoặc nhánh feature riêng trước khi merge).
