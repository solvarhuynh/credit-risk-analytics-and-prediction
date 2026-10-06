# Phân tích Rủi ro Tín dụng & Dự báo Khả năng Vỡ nợ

**Retail Credit Risk Analytics & Default Prediction Dashboard**

Đồ án xây dựng một quy trình phân tích rủi ro tín dụng bán lẻ từ dữ liệu Lending Club giai đoạn **2007–2018**. Dự án kết hợp Data Engineering, phân tích khám phá, mô hình dự báo và Power BI để trả lời các câu hỏi: hồ sơ nào có nguy cơ vỡ nợ cao, rủi ro phân bố như thế nào trong danh mục, và kết quả mô hình có thể hỗ trợ quyết định tín dụng ra sao.

Raw data được quản lý cục bộ vì dung lượng lớn và không đưa lên Git. Nguồn dữ liệu chính gồm:

- `accepted_loans.csv`: các khoản vay đã được cấp, có kết quả trả nợ để phân tích default và huấn luyện mô hình.
- `rejected_loans.csv`: các đơn đăng ký bị từ chối, dùng cho phân tích nhu cầu, funnel và cơ cấu hồ sơ; không dùng để huấn luyện default vì không có kết quả trả nợ tương lai.

## Mục tiêu dự án

1. Xây dựng pipeline dữ liệu có grain rõ ràng, kiểm soát chất lượng và tránh nhân bản dòng khi kết hợp các bảng nghiệp vụ.
2. Chuẩn hóa target vỡ nợ và tạo bộ dữ liệu đầu vào an toàn cho mô hình.
3. Phân tích đặc điểm khách hàng, khoản vay và các mẫu hình liên quan đến rủi ro tín dụng.
4. Huấn luyện mô hình Logistic Regression làm baseline; có thể dùng XGBoost như mô hình so sánh.
5. Giải thích kết quả bằng feature importance/SHAP, PD, risk tier và Expected Loss.
6. Trình bày kết quả qua dashboard Power BI có tương tác, lọc, drill-down và hỗ trợ phân tích địa lý theo bang.

## Kiến trúc tổng thể

```text
accepted + rejected raw
        ↓ TV2 — Data Engineering
business tables + dimensions + canonical labeled dataset
        ↓ TV1 — Modeling
Logistic baseline + optional XGBoost + scored outputs
        ↓ TV3 — Dashboard
Power BI: risk, portfolio, funnel, trend và geographic views
```

TV2 chuẩn hóa dữ liệu từ raw thành các bảng nghiệp vụ, dimension và bộ dữ liệu canonical. TV1 nhận đầu vào đã qua data contract để xây dựng mô hình và các trường chấm điểm. TV3 tích hợp các đầu ra thành một báo cáo Power BI thống nhất.

## Quy tắc dữ liệu và mô hình

- Khóa canonical là `loan_id`, được chuẩn hóa từ trường `id` của raw data.
- `Fully Paid` được mã hóa `target = 0`.
- `Charged Off` và `Default` được mã hóa `target = 1`.
- Trạng thái chưa có kết quả cuối cùng bị loại khỏi supervised modeling, không tự động gán thành không vỡ nợ.
- Các trường payment, recovery, hardship, settlement và thông tin phát sinh sau khoản vay không được đưa vào feature dự báo tại thời điểm cấp tín dụng.
- Các trường policy-derived, định danh, văn bản có cardinality cao và trường chưa phân loại được loại khỏi feature mặc định theo nguyên tắc fail-closed.
- Phân tích Map sử dụng `addr_state` chuẩn hóa thành `state_code` và `country = United States`. ZIP được giữ như chuỗi đã che; không tự tạo latitude/longitude.

Chi tiết được quy định tại [Data Contract](docs/contracts/data_contract.md) và [Feature Leakage Policy](docs/data/feature_leakage_policy.md).

## Các nhóm phân tích và dashboard

Dashboard được tổ chức theo ba lớp: tổng quan danh mục, chẩn đoán rủi ro và hỗ trợ quyết định.

- **Risk & Model Views:** Geographic Risk Map, PD Distribution, Risk Tier Distribution, FICO so với Risk/PD, Feature Importance/SHAP và Expected Loss/Risk Contribution.
- **Data & Portfolio Views:** Loan Volume và Default Rate theo thời gian, Accepted vs Rejected Funnel, Loan Purpose Analysis.
- **Business & Segment Views:** Loan Amount so với Annual Income, DTI/FICO Risk Matrix và Borrower Segment Composition.

Các thành phần được tích hợp với filter, cross-filtering, drill-down, tooltip, navigation và các quan hệ dữ liệu cần thiết trong Power BI.

## Cấu trúc repository

```text
ttdltq/
├── data/
│   ├── raw/                  # accepted/rejected raw, local-only
│   ├── interim/              # bảng trung gian sau làm sạch/tổng hợp
│   └── processed/            # dataset, dictionary và output dùng chung
├── dashboard/                # Power BI artifact và tài nguyên giao diện
├── docs/
│   ├── architecture/         # kiến trúc và quyết định kỹ thuật
│   ├── contracts/            # data contract và model contract
│   ├── data/                 # inventory, policy và data handoff
│   ├── setup/                # runbook của TV1, TV2 và TV3
│   └── tasks/                # phân công, visual plan và quy trình làm việc
├── logs/                     # nhật ký làm việc theo thành viên
├── models/                   # model artifacts và checkpoints
├── notebooks/                # các notebook phân tích
├── reports/                  # báo cáo, biểu đồ, slide và video demo
├── src/
│   ├── data/                 # loader, cleaning, aggregation và quality gate
│   ├── features/             # feature engineering an toàn
│   └── models/               # preprocessing, training, scoring và evaluation
├── tests/                    # kiểm thử pipeline và chất lượng dữ liệu
└── requirements.txt
```

## Phân công trách nhiệm

### TV1 — Modeling, Storytelling & Report

TV1 là chủ trì mô hình hóa: xây dựng Logistic Regression baseline, mô hình so sánh tùy chọn, đánh giá, scoring, SHAP, risk tier và Expected Loss. TV1 phụ trách các visual V02–V06: PD, risk tier, FICO/PD, SHAP và Expected Loss; đồng thời giữ vai trò Storytelling Lead, Report Coordinator và Defense Coordinator. V01 Geographic Risk Map thuộc TV3.

### TV2 — Data Engineering & Technical EDA

TV2 là chủ trì Data Engineering: kiểm kê raw, profiling schema, cleaning, aggregate, join/merge, data quality gate, data dictionary và canonical handoff cho TV1/TV3. TV2 phụ trách các visual V07–V09: trend theo thời gian, accepted/rejected funnel và loan purpose; đồng thời là primary author của các phần dataset, preprocessing, Join/Merge, calculated fields, quality và technical EDA.

### TV3 — Master Power BI & Integration

TV3 là chủ trì artifact Power BI tổng thể, layout, theme, relationships, filters, drill-down, tooltip, cross-filtering, navigation và demo. TV3 sở hữu trực tiếp V01 Geographic Risk Map và các visual V10–V12: loan amount/annual income, DTI/FICO risk matrix và borrower segment composition; đồng thời tích hợp V01–V09 vào Master PBIX duy nhất.

Mỗi phần báo cáo có primary author và cross reviewer. Tất cả thành viên cần hiểu luồng end-to-end, còn TV3 là đầu mối duy nhất quản lý bản Master PBIX.

## Tài liệu tham chiếu

- [Kiến trúc repository và liên kết dữ liệu](docs/architecture/repo_structure_and_linkages.md)
- [Data Contract](docs/contracts/data_contract.md)
- [Model Contract](docs/contracts/model_contract.md)
- [Chính sách Feature Leakage](docs/data/feature_leakage_policy.md)
- [Data Workflow](docs/data/DATA_WORKFLOW.md)
- [Data Rules](docs/data/DATA_RULES.md)
- [Data Artifacts Guide](docs/data/data_artifacts.md)
- [TV2 Data Handoff](docs/data/tv2_data_handoff.md)
- [Phân công nhiệm vụ và RACI](docs/tasks/phan-cong-nhiem-vu.md)
- [Kế hoạch visual dashboard](docs/tasks/dashboard-visual-plan.md)
- [Quy trình phối hợp và Git](docs/tasks/working-protocol.md)
