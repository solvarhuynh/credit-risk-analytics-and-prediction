# TV3 — Master Power BI Integration và Dashboard Roadmap

TV3 là **MASTER DASHBOARD INTEGRATOR**, không phải sole author của mọi visual. TV3 sở hữu PBIX/master artifact, trực tiếp sở hữu V01 và V10–V12, đồng thời tích hợp toàn bộ V01–V12 từ specification/prototype đã review.

## PRIMARY INTEGRATION

TV3 sở hữu data model và relationships, theme, page layout, slicers, filters, drill-down, tooltips, cross-filter behavior, navigation/bookmarks, visual consistency, final PBIX integration và demo readiness.

TV3 trực tiếp sở hữu:

- V01 Geographic Risk Map.
- V10 Loan Amount vs Annual Income — binned heatmap.
- V11 DTI/FICO Risk Matrix — heatmap.
- V12 Borrower Segment — bar/stacked bar; segment đề nghị: `home_ownership`, evaluated frozen-test population, stack composition theo canonical risk tier.

TV1 là reviewer chính cho V10 và model-facing visuals; TV2 review data inputs/measure semantics của V11–V12. Mọi visual có status `PLANNED / WAITING FOR DATA` cho tới khi usable schema/marts tồn tại.

## MASTER DASHBOARD — 4 TRANG POWER BI + DASH BÊN NGOÀI / DATA MODEL BLOCKED

Kế hoạch trang và visual families hiện hành được khóa trong `docs/tasks/dashboard-visual-plan.md`; chart selection không mở lại trong Power BI Phase 2. Trạng thái data model là `POWER_BI_DATA_MODEL_BLOCKED`, không được bắt đầu build visuals trước khi blockers trong plan được đóng.

1. **Tổng quan danh mục:** KPI, V08, V01.
2. **Xu hướng & Mục đích vay:** V07, V09.
3. **Hồ sơ người vay:** V04, V11, V10, V12.
4. **Rủi ro & Expected Loss:** KPI, V02, V03, V05, V06.

Dự đoán cá nhân dùng ứng dụng Dash bên ngoài Power BI; không thêm trang thứ năm vào Master.

Không đặt 12 visual trên một trang. TV3 giữ navigation và consistency; visual owner giữ logic/interpretation. Mọi interaction phải trả lời câu hỏi phân tích, không trang trí.

## TÍCH HỢP V01–V09

TV1 cung cấp V02–V06 specification, fields, measures và caveats; có thể cross-review V01 khi cần. TV3 trực tiếp sở hữu V01 và V10–V12. TV2 cung cấp V07–V09 data semantics và EDA context. TV3 đưa các spec/prototype đã review vào Master PBIX, kiểm tra interactions và ghi nguồn/reviewer.

V01 dùng `state_code` + `country` nhưng cần smoke-test Power BI map recognition. Time hierarchy dùng đúng date role: accepted `issue_d`, rejected `application_date`; không coi chúng là cùng một event date. Prediction/risk tier/Expected Loss artifacts đã có, nhưng evaluated score context mart còn thiếu state/bands; hiển thị readiness blocked cho tới khi được enrich/validated. V08 không tính default rate rejected.

## REPORT VÀ DEMO

TV3 là primary author cho dashboard architecture, Power BI data model, UI/UX, Filter, Drill-down, Tooltip, Cross-filter, navigation, demo và user guide. TV1 là cross reviewer; TV2 review semantic correctness. TV3 phối hợp demo script nhưng cả ba phải hiểu và trình bày được project flow.

## POWER BI COLLABORATION POLICY

PBIX không phải file merge-friendly. Không cho ba người chỉnh một Master PBIX cùng lúc. TV1/TV2 có thể tạo local prototype PBIX hoặc screenshot nếu cần; TV3 là người tích hợp duy nhất. Prototype local phải được ghi rõ là local/optional và không thay Master artifact.

Trạng thái: **PLANNED / WAITING FOR DATA + MODEL**. Không mở/build Power BI hoặc viết DAX trong task phân công này.
