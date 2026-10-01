# TV3 — Master Power BI Integration và Dashboard Roadmap

TV3 là **MASTER DASHBOARD INTEGRATOR**, không phải sole author của mọi visual. TV3 sở hữu PBIX/master artifact và tích hợp V01–V09 từ specification/prototype đã review.

## PRIMARY INTEGRATION

TV3 sở hữu data model và relationships, theme, page layout, slicers, filters, drill-down, tooltips, cross-filter behavior, navigation/bookmarks, visual consistency, final PBIX integration và demo readiness.

TV3 trực tiếp sở hữu:

- V10 Loan Amount vs Annual Income — scatter/bubble.
- V11 DTI/FICO Risk Matrix — heatmap.
- V12 Borrower Segment Composition — donut hoặc 100% stacked bar.

TV1 là reviewer chính cho V10 và model-facing visuals; TV2 review data inputs/measure semantics của V11–V12. Mọi visual có status `PLANNED / WAITING FOR DATA` cho tới khi usable schema/marts tồn tại.

## MASTER DASHBOARD — 5 PAGES

1. **Executive Overview:** KPI và visual risk/loan cấp cao.
2. **Application & Portfolio:** accepted/rejected, purpose, loan/income/borrower composition.
3. **Geographic & Temporal:** V01, V07, state/time filters.
4. **Credit Risk & Prediction:** V02, V03, V04, V11 và prediction outputs.
5. **Model & Business Impact:** V05, V06, model explanation và Expected Loss.

Không đặt 12 visual trên một trang. TV3 giữ navigation và consistency; visual owner giữ logic/interpretation.

## TÍCH HỢP V01–V09

TV1 cung cấp V01–V06 specification, fields, measures và caveats. TV2 cung cấp V07–V09 data semantics và EDA context. TV3 đưa các spec/prototype đó vào Master PBIX, kiểm tra interactions và ghi nguồn/reviewer.

Map dùng `state_code` + `country`; hierarchy thời gian là Year → Quarter → Month. Prediction/risk tier/Expected Loss chỉ bật khi TV1 bàn giao artifact thật. Thiếu model phải hiển thị `BLOCKED / WAITING FOR TV1 ARTIFACT`.

## REPORT VÀ DEMO

TV3 là primary author cho dashboard architecture, Power BI data model, UI/UX, Filter, Drill-down, Tooltip, Cross-filter, navigation, demo và user guide. TV1 là cross reviewer; TV2 review semantic correctness. TV3 phối hợp demo script nhưng cả ba phải hiểu và trình bày được project flow.

## POWER BI COLLABORATION POLICY

PBIX không phải file merge-friendly. Không cho ba người chỉnh một Master PBIX cùng lúc. TV1/TV2 có thể tạo local prototype PBIX hoặc screenshot nếu cần; TV3 là người tích hợp duy nhất. Prototype local phải được ghi rõ là local/optional và không thay Master artifact.

Trạng thái: **PLANNED / WAITING FOR DATA + MODEL**. Không mở/build Power BI hoặc viết DAX trong task phân công này.
