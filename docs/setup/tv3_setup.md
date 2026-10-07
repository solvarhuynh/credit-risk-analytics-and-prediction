# Thiết lập TV3 — Dashboard

Trạng thái Master TV3: **POWER_BI_DATA_MODEL_BLOCKED / BUILD NOT STARTED**. Kiến trúc Power BI 4 trang + ứng dụng Dash bên ngoài và visual families V01–V12 đã chốt; Master Power BI chưa build/review. Working PBIP của TV1 có các visual/model demo riêng nhưng không phải Master TV3. Nguồn/model artifacts có sẵn một phần nhưng các dashboard marts và map-recognition check còn thiếu. Tham chiếu canonical spec: `docs/tasks/dashboard-visual-plan.md`.

Các bước **EXPECTED / NOT YET VERIFIED AFTER DATASET RESET**:

1. Đọc `docs/contracts/data_contract.md`, `model_contract.md` và task TV3.
2. Không thay đổi visual families đã LOCKED; đọc Phase 2 sign-off và đóng các blocker data-model trước khi build.
3. Theo 4 trang trong plan: Tổng quan danh mục (KPI, V08, V01); Xu hướng & Mục đích vay (V07, V09); Hồ sơ người vay (V04, V11, V10, V12); Rủi ro & Expected Loss (KPI, V02, V03, V05, V06). Dự đoán cá nhân là ứng dụng Dash bên ngoài, không phải trang Power BI thứ năm.
4. Chỉ sau review mới thiết kế Power BI model với các fact/dimensions, relationships và measures thực sự cần; không import artifacts toàn bộ một cách máy móc.
5. Xác minh data types/mapping thực tế cho `state_code` và `country` trước map; tạo filters, tooltip, drill-down, cross-filter và navigation chỉ khi chúng giúp trả lời câu hỏi phân tích.
6. Dùng prediction sources sau khi TV1 handoff contract/artifacts; individual demo không phải official loan approval system.

Kiểm tra simulator contract:

```powershell
python -c "from src.dashboard.simulator_engine import simulator_status; print(simulator_status('models/full_inference_pipeline.joblib'))"
```

Ý nghĩa: hiện phải báo `BLOCKED / WAITING FOR TV1 ARTIFACT`; không phải lỗi migration.

## Phạm vi trách nhiệm sau reorganize

TV3 là primary owner của Master Power BI artifact, trực tiếp sở hữu V01 và V10–V12, đồng thời tích hợp V01–V12, relationships, layout, theme, slicers, filters, drill-down, tooltip, cross-filter, navigation và demo. TV1/TV2 có thể gửi prototype/spec local; chỉ TV3 tích hợp Master PBIX. TV1 cross-review V01 và các model-facing visuals khi cần; TV2 review data semantics.
