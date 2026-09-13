# Phân tích rủi ro tín dụng và dự báo vỡ nợ

Đồ án môn **Tương tác Dữ liệu Trực quan**, dùng [Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk/data) hoặc [Driver](https://drive.google.com/file/d/1KACipCMMBQNzD53ozWCAQIDITlWIVugW/view?usp=drive_link): dữ liệu nhiều bảng → tiền xử lý/EDA → dự báo xác suất vỡ nợ → dashboard tương tác.

> Repository đang ở giai đoạn khởi tạo. Các file trong `src/` là skeleton; `docs/` quy định đầu ra và điểm bàn giao giữa các thành viên.

## Phạm vi

- Dùng tối thiểu ba bảng và hơn 5.000 dòng; làm sạch, aggregate theo `SK_ID_CURR`, tạo calculated fields.
- EDA với 3–5 biểu đồ tĩnh bằng Matplotlib/Seaborn.
- Dashboard chính dùng **Power BI**, có filter, drill-down, tooltip và cross-filtering; Python đảm nhiệm pipeline và mô hình.
- Logistic Regression là phần bắt buộc. XGBoost, SHAP, scorecard, Expected Loss và fairness chỉ thực hiện sau khi luồng tối thiểu chạy được.

## Khởi động

Yêu cầu Python 3.10–3.12. Tải CSV Kaggle vào `data/raw/` (không commit dữ liệu/model lớn).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.data.build_pipeline
```

Lệnh cuối là luồng chuẩn sau khi các module skeleton được hiện thực. Power BI Desktop nạp bảng điểm đã xuất để xây dashboard.

## Cấu trúc

```text
ttdltq/
├── data/          # raw, interim, processed (local-only)
├── dashboard/     # Power BI (.pbix), theme và assets
├── docs/          # architecture, contracts, overview, tasks
├── models/        # model artifacts (local-only)
├── notebooks/     # notebook 00–07; không là production source
├── reports/       # report, figures, slides, video
├── src/           # data, features, models, dashboard adapter
└── requirements.txt
```

Xem [kiến trúc](docs/architecture/repo_structure_and_linkages.md), [data contract](docs/contracts/data_contract.md), [model contract](docs/contracts/model_contract.md), [phân công](docs/tasks/phan-cong-nhiem-vu.md), và [quy trình làm việc/Git](docs/tasks/working-protocol.md).

## Lưu ý về Map

Home Credit không có tọa độ hoặc tên địa phương thật. Không được gán ngẫu nhiên khách hàng vào tỉnh/thành để tạo bản đồ. Nhóm cần xác nhận với giảng viên cách đáp ứng tiêu chí Map, hoặc dùng nguồn có khóa liên kết địa lý thật; xem [decision log](docs/architecture/decisions-and-risks.md).

## Đầu ra

- `data/processed/cleaned_dataset.parquet` và data dictionary
- `data/processed/scored_dataset.parquet`
- `models/full_inference_pipeline.joblib`
- `dashboard/Credit_Risk_Analytics.pbix`
- report IEEE, slide, video backup trong `reports/`

## Phân công

- **TV1:** baseline Logistic, đánh giá, export model/scored data.
- **TV2:** dữ liệu, aggregate, feature, EDA, data dictionary.
- **TV3:** Power BI, mô hình dữ liệu, DAX, UX, tương tác và dashboard demo.
- **Cả nhóm:** insight, báo cáo, slide, video, review chéo và vấn đáp.
