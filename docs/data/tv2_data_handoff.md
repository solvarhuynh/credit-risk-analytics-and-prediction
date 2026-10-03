# TV2 Data Handoff — Lending Club

Trạng thái hiện tại: **GENERATED / QUALITY AND LEAKAGE GATE PASS**.

## Bộ artifact bàn giao

- [`data/processed/cleaned_dataset.parquet`](../../data/processed/cleaned_dataset.parquet): canonical labeled dataset, 1,345,350 accepted loans có outcome đã resolve.
- [`data/processed/data_dictionary.csv`](../../data/processed/data_dictionary.csv): dtype, policy class và model eligibility của các cột canonical.
- [`data/processed/cleaned_dataset_manifest.json`](../../data/processed/cleaned_dataset_manifest.json): dataset ID, trạng thái run/stage, accepted `2,260,701`, rejected `27,648,741`, labeled `1,345,350`, unresolved `915,351`, target counts, canonical/dictionary counts, leakage/quality status và provenance.
- [`reports/data_quality_report.md`](../../reports/data_quality_report.md): quality report với `LEAKAGE GATE = PASS`, key null/trùng bằng 0, infinity bằng 0 và unresolved count `915,351`.

## Bảng interim

DE-LC-04 đã tạo năm accepted business tables và một bảng rejected riêng:

- `loan_application.parquet`
- `borrower_profile.parquet`
- `credit_profile.parquet`
- `loan_pricing.parquet`
- `loan_outcome.parquet`
- `rejected_applications.parquet`

DE-LC-05 tạo [`target_audit.csv`](../../data/interim/target_audit.csv). DE-LC-08 tạo `dim_date.parquet`, `dim_state.parquet` và `application_funnel.parquet` cho dashboard. Rejected applications vẫn tách khỏi accepted và không được dùng để suy ra default target.

## Stage evidence và giới hạn sử dụng

- Marker và báo cáo DE-LC-01 đến DE-LC-10 nằm trong [`reports/tv2_stages/`](../../reports/tv2_stages/); các marker hiện tại đều `PASS`.
- [`data_artifacts.md`](data_artifacts.md) mô tả grain, consumer và giới hạn dùng của từng artifact.
- TV1 chỉ đưa các cột được policy cho phép vào baseline `X`; `POST_LOAN`, `POLICY_DERIVED`, target source và geography không tự động trở thành model features.
- TV3 có thể dùng dimensions/marts và các trường analytics phù hợp cho dashboard. Map dùng `state_code` thật ở cấp bang; không suy diễn tọa độ từ ZIP masked.
