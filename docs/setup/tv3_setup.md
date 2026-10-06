# Thiết lập TV3 — Dashboard

Trạng thái: **PLAN ONLY**. Chưa build/review Power BI. Data/model sources có sẵn một phần nhưng integration chưa được khẳng định hoàn tất. Tham chiếu page/visual plan canonical: `docs/tasks/dashboard-visual-plan.md`.

Các bước **EXPECTED / NOT YET VERIFIED AFTER DATASET RESET**:

1. Đọc `docs/contracts/data_contract.md`, `model_contract.md` và task TV3.
2. Đọc lecturer visualization theory/materials trước khi chốt chart types; hiện tất cả chart types là provisional.
3. Theo provisional story pages: Portfolio & Application Overview (V01/V07/V08/V09); Borrower Risk Profile (V04/V10/V11/V12); Model Risk & Explainability (V02/V03/V05); Business Risk & Expected Loss (V06); Individual Prediction / Decision Support (planned, UI chưa quyết định).
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
