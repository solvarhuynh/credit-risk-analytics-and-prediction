# TV3 — Master Power BI Integration và Dashboard Roadmap

TV3 là **MASTER DASHBOARD INTEGRATOR**, không phải sole author của mọi visual. TV3 sở hữu PBIX/master artifact, trực tiếp sở hữu V01 và V10–V12, đồng thời tích hợp toàn bộ V01–V12 từ specification/prototype đã review.

## PRIMARY INTEGRATION

TV3 sở hữu data model và relationships, theme, page layout, slicers, filters, drill-down, tooltips, cross-filter behavior, navigation/bookmarks, visual consistency, final PBIX integration và demo readiness.

TV3 trực tiếp sở hữu:

- V01 Geographic Risk Map.
- V10 Loan Amount vs Annual Income — scatter/bubble.
- V11 DTI/FICO Risk Matrix — heatmap.
- V12 Borrower Segment Composition — donut hoặc 100% stacked bar.

TV1 là reviewer chính cho V10 và model-facing visuals; TV2 review data inputs/measure semantics của V11–V12. Mọi visual có status `PLANNED / WAITING FOR DATA` cho tới khi usable schema/marts tồn tại.

## MASTER DASHBOARD — CURRENT PROVISIONAL 5-PAGE STORY

Kế hoạch trang hiện hành được giữ chi tiết tại `docs/tasks/dashboard-visual-plan.md`. Đây là kiến trúc provisional; không quyết định chart type cho tới khi hoàn thành COURSE VISUALIZATION THEORY REVIEW.

1. **Portfolio & Application Overview:** V01, V07, V08, V09.
2. **Borrower Risk Profile:** V04, V10, V11, V12.
3. **Model Risk & Explainability:** V02, V03, V05.
4. **Business Risk & Expected Loss:** V06 cùng KPI/support khi phù hợp.
5. **Individual Prediction / Decision Support:** trang bắt buộc trong plan nhưng ngoài V01–V12; UI/implementation chưa quyết định và chưa được tuyên bố đã build.

Không đặt 12 visual trên một trang. TV3 giữ navigation và consistency; visual owner giữ logic/interpretation. Mọi interaction phải trả lời câu hỏi phân tích, không trang trí.

## TÍCH HỢP V01–V09

TV1 cung cấp V02–V06 specification, fields, measures và caveats; có thể cross-review V01 khi cần. TV3 trực tiếp sở hữu V01 và V10–V12. TV2 cung cấp V07–V09 data semantics và EDA context. TV3 đưa các spec/prototype đã review vào Master PBIX, kiểm tra interactions và ghi nguồn/reviewer.

Map dùng `state_code` + `country`; hierarchy thời gian là Year → Quarter → Month. Prediction/risk tier/Expected Loss chỉ bật khi TV1 bàn giao artifact thật. Thiếu model phải hiển thị `BLOCKED / WAITING FOR TV1 ARTIFACT`.

## REPORT VÀ DEMO

TV3 là primary author cho dashboard architecture, Power BI data model, UI/UX, Filter, Drill-down, Tooltip, Cross-filter, navigation, demo và user guide. TV1 là cross reviewer; TV2 review semantic correctness. TV3 phối hợp demo script nhưng cả ba phải hiểu và trình bày được project flow.

## POWER BI COLLABORATION POLICY

PBIX không phải file merge-friendly. Không cho ba người chỉnh một Master PBIX cùng lúc. TV1/TV2 có thể tạo local prototype PBIX hoặc screenshot nếu cần; TV3 là người tích hợp duy nhất. Prototype local phải được ghi rõ là local/optional và không thay Master artifact.

Trạng thái: **PLANNED / WAITING FOR DATA + MODEL**. Không mở/build Power BI hoặc viết DAX trong task phân công này.
