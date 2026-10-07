# Defense Knowledge Matrix — Lending Club

Trạng thái: **PLANNED / NOT YET REHEARSED**. TV1 điều phối question bank và rehearsal; ownership sâu không miễn cho thành viên khác khỏi hiểu phần còn lại. Dashboard page architecture và individual prediction demo plan nằm trong `docs/tasks/dashboard-visual-plan.md`; report/video flow nằm trong `docs/tasks/report-writing-plan.md`.

| Category | Tất cả thành viên phải giải thích được | TV1 deep knowledge | TV2 deep knowledge | TV3 deep knowledge |
|---|---|---|---|---|
| Data | Vì sao chọn Lending Club; accepted vs rejected; raw/interim/processed | Tác động dữ liệu lên model input | 151 accepted/9 rejected schema, chunking, missing/outlier | Cách data shape thành Power BI model |
| Model | Target, train/test, Logistic, PD, Precision/Recall/AUC, threshold | Split, preprocessing, imbalance, threshold, SHAP, Expected Loss | Vì sao chỉ final accepted rows vào default model; leakage inputs | Cách prediction output xuất hiện trên dashboard |
| Dashboard | Map, Filter, Drill-down, Tooltip, Cross-filter | Ý nghĩa V02–V06 và model caveat; cross-review V01 khi cần | Semantics V07–V09, date/state, funnel | V01 ownership, relationships, theme, 4 trang Power BI + Dash bên ngoài, interactions, PBIX integration |
| Insight | Observation vs interpretation; correlation không phải causation | Hợp nhất story applicant→risk→business | Data limitation/censoring và validity của claims | Trình bày insight bằng visual/UX rõ ràng |
| Business | PD vs default, risk tier, Expected Loss và assumptions | Policy/threshold/EL decision context | Portfolio/funnel/purpose/time context | Cách người dùng đọc và hành động trong dashboard |
| Integration | Handoff TV2→TV1→TV3 và trạng thái chưa chạy | Model/scored schema cho TV3 | Dictionary/manifest/quality gate | Master PBIX và single integration owner |

## Câu hỏi bắt buộc trong shared question bank

- Dataset Lending Club có những nguồn nào? Vì sao rejected không train default?
- `loan_id`, `loan_status`, `target` được tạo và kiểm tra thế nào?
- Vì sao payment/recovery/hardship/settlement là leakage nhưng vẫn giữ trong raw?
- Ba bảng nghiệp vụ chính được join thế nào và làm sao chứng minh one-to-one?
- Map dùng field nào? Vì sao không tạo tọa độ từ ZIP masked?
- Logistic Regression trả PD thế nào; threshold khác gì metric?
- Precision, Recall, ROC-AUC có ý nghĩa và hạn chế gì?
- Dashboard dùng filter, drill-down, tooltip và cross-filter ra sao?
- Insight nào là observation, insight nào chỉ là hypothesis cần kiểm chứng?
- Những limitation nào làm không được kết luận nhân quả hoặc fairness tuyệt đối?

Trước khi final, mỗi câu phải có người trả lời chính, người kiểm tra chéo và evidence path trong report/log.
