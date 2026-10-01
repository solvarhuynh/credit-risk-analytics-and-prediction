# Thiết lập TV3 — Dashboard

Trạng thái: dashboard design có thể bắt đầu từ contract; data/model integration chờ TV2/TV1.

Các bước **EXPECTED / NOT YET VERIFIED AFTER DATASET RESET**:

1. Đọc `docs/contracts/data_contract.md`, `model_contract.md` và task TV3.
2. Thiết kế Power BI model với `dim_date`, `dim_state`, portfolio/funnel/scored fact.
3. Phân loại `state_code` là State/Province và `country` là Country/Region.
4. Tạo drill-down Year → Quarter → Month, filter, tooltip và cross-filter.
5. Chỉ kết nối prediction khi TV1 bàn giao model/scored output thật.

Kiểm tra simulator contract:

```powershell
python -c "from src.dashboard.simulator_engine import simulator_status; print(simulator_status('models/full_inference_pipeline.joblib'))"
```

Ý nghĩa: hiện phải báo `BLOCKED / WAITING FOR TV1 ARTIFACT`; không phải lỗi migration.

## Phạm vi trách nhiệm sau reorganize

TV3 là primary owner của Master Power BI artifact, integration V01–V09, V10–V12, relationships, layout, theme, slicers, filters, drill-down, tooltip, cross-filter, navigation và demo. TV1/TV2 có thể gửi prototype/spec local; chỉ TV3 tích hợp Master PBIX. TV1 cross-review model-facing visuals; TV2 review data semantics.
