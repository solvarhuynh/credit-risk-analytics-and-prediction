# Credit Risk Analytics & Default Prediction

**Đồ án HCMUTE — Tương tác dữ liệu trực quan**
Phân tích rủi ro khoản vay Lending Club 2007–2018, kết hợp Data Engineering, mô hình dự báo và dashboard tương tác.

## Dự án làm gì?

Pipeline chuẩn hóa dữ liệu accepted/rejected, tạo bộ accepted loans có nhãn cuối cùng, xây dựng Logistic Regression baseline và so sánh với Weighted Logistic Regression/XGBoost. Kết quả được dùng để phân tích xác suất vỡ nợ dự đoán (PD), phân nhóm rủi ro, giải thích mô hình bằng SHAP và minh họa Expected Loss.

`Fully Paid → target 0`; `Charged Off` và `Default → target 1`. Trạng thái chưa có kết quả cuối cùng bị loại khỏi supervised modeling. Rejected applications không có kết quả trả nợ nên không tham gia target modeling. Đây là phân tích dữ liệu lịch sử, không phải hệ thống phê duyệt tín dụng thực tế.

## Dữ liệu và phương pháp

- Nguồn: Lending Club 2007–2018; raw CSV và processed/model artifacts dung lượng lớn nằm local dưới `data/` và không được Git theo dõi.
- TV2 sở hữu cleaning, business tables, canonical dataset, dictionary, quality gate và technical EDA.
- TV1 sở hữu modeling. Logistic Regression là baseline; XGBoost là candidate được chọn bằng validation. Frozen-test metrics chỉ thuộc `xgboost_candidate`, không thuộc full-data refit hoặc app demo 6-input.
- Kết quả frozen test đã ghi nhận: ROC-AUC 0.723186, PR-AUC 0.400000, Log Loss 0.447783, Brier 0.142643; tại threshold validation đã khóa 0.22009515762329102, F1 0.439590. Chi tiết, confusion matrix và giới hạn xem [modeling summary](reports/tv1_stages/modeling_summary.md).
- SHAP mô tả contribution của model, không chứng minh quan hệ nhân quả. Expected Loss dùng `PD × LGD × EAD`; LGD là giả định 30/45/60%, `loan_amnt` là EAD proxy và đơn vị tiền chưa được xác minh.

## Ứng dụng và dashboard

Ứng dụng Dash tại `apps/individual_prediction_dash/` là demo riêng dùng hai model 6-input đã đánh giá validation-only. Chúng không thay thế model chính 103-input và không có frozen-test evaluation mới. Hướng dẫn, giới hạn và lệnh chạy nằm trong [Dash README](apps/individual_prediction_dash/README.md) và [TV1 setup](docs/setup/tv1_setup.md).

Kế hoạch Power BI hiện định nghĩa bốn trang: Tổng quan; Xu hướng & Mục đích vay; Hồ sơ vay; Rủi ro & Expected Loss. Tuy nhiên, trạng thái PBIP trong worktree chưa qua kiểm tra mở/render ở lần audit này; không xem dashboard là đã nghiệm thu chỉ dựa trên file JSON/TMDL. Xem [TV3 setup](docs/setup/tv3_setup.md), [visual plan](docs/tasks/dashboard-visual-plan.md) và [repository audit](reports/repository_audit/repo_cleanup_audit.md) trước khi mở project.

## Bắt đầu

Từ PowerShell tại thư mục repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Chạy test:

```powershell
python -m pytest tests -v
```

Chạy Dash sau khi có các artifact model demo được nêu trong app guide:

```powershell
.\run_prediction_app.bat
```

Data Engineering pipeline cần raw CSV local `data/raw/accepted_loans.csv` và `data/raw/rejected_loans.csv`; xem [TV2 runbook](docs/setup/tv2_setup.md). Không có raw data/model artifacts thì việc cài package một mình chưa đủ để chạy pipeline hoặc inference. Mở Power BI chỉ sau khi xác nhận `.pbip` và semantic model tương ứng còn đủ; hiện trạng cần theo dõi tại audit.

## Cấu trúc

```text
apps/individual_prediction_dash/  Ứng dụng dự đoán Dash
data/                             Raw/interim/processed data và model artifacts local
docs/                             Contracts, setup, nhiệm vụ và kiến trúc
logs/                             Lịch sử TV1/TV2/TV3
notebooks/                        Danh mục; hiện chưa có notebook nghiên cứu hoàn chỉnh
reports/                          EDA, stage reports, figures và repository audit
src/data/                         Data loading, cleaning, stages và quality gates
src/features/                     Feature engineering
src/models/                       Split, modeling, evaluation, scoring và explainability
src/dashboard/                    Contract simulator TV3, chưa phải app inference
tests/                            Unit/regression tests
```

## Phân công

- **TV1:** modeling, evaluation, explainability, scoring/Expected Loss và ứng dụng Dash demo.
- **TV2:** PRIMARY OWNER của Data Engineering, canonical data handoff và technical EDA.
- **TV3:** PRIMARY OWNER Power BI master, dashboard integration và các visual theo phân công.

## Giới hạn và tái lập

Split model là stratified random split, không phải đánh giá out-of-time. Kết quả lịch sử Lending Club không đảm bảo hiệu năng hiện tại hay quyết định cho một cá nhân. Full-data refit scores là in-sample; chỉ frozen-test metrics của candidate được dùng làm bằng chứng đánh giá độc lập. SHAP/correlation không phải causality; Expected Loss là scenario, không phải realized loss.

Pipeline và tests có thể tái lập khi cung cấp đúng raw data, dependencies và các artifact theo từng stage. Raw data, model binaries và processed outputs không được lưu trong Git; báo cáo stage/manifests nhỏ ghi provenance và trạng thái hiện có. Cấu trúc chi tiết ở [repository structure](reports/repository_audit/repository_structure.md); contracts chuẩn là [data contract](docs/contracts/data_contract.md) và [model contract](docs/contracts/model_contract.md).
