# TV3 Progress Log — Lending Club Dataset Reset

## Dataset Migration Reset — 2026-10-01

- Dataset cũ đã retired; Lending Club 2007–2018 được chọn.
- Lịch sử trước reset đã được loại khỏi working tree; có thể truy xuất qua Git history.
- Chưa chạy lại pipeline, mô hình hoặc dashboard.
- Trạng thái: **RESET / NOT YET EXECUTED**.
- Dashboard design có thể bắt đầu từ contract; tích hợp data/model chờ TV2/TV1 outputs.

## 2026-10-01 — Dashboard contract migration

- Trạng thái: **MIGRATED CONTRACT / WAITING FOR DATA + MODEL**.
- Đã chuyển dashboard task/setup/architecture sang state-level Map, date drill-down, funnel, 8+ visual types và prediction contract.
- Simulator không tạo inference giả; khi thiếu model sẽ báo `BLOCKED / WAITING FOR TV1 ARTIFACT`.
- Kiểm tra cú pháp PASS; chưa chạy dashboard.
- Next step: thiết kế layout từ contract, chờ TV2 dimensions/marts và TV1 scored artifacts.

## 2026-10-06 — V01 Geographic Risk Map ownership

- Task/status: **DONE / OWNERSHIP UPDATED**. TV3 nhận primary ownership của V01 Geographic Risk Map; TV1 trực tiếp phụ trách V02–V06.
- TV3 vẫn là Master Power BI integration owner và trực tiếp sở hữu V10–V12; V01 dùng `state_code`/`country` theo visual plan, không bịa location.
- Files: `README.md`, `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/thanh-vien-3-dashboard.md`, `docs/setup/tv3_setup.md`, `docs/tasks/dashboard-visual-plan.md`.
- Validation: kiểm tra chéo ownership bằng `rg`; chưa build hoặc thay đổi PBIX, code hay data.
- Next step: tích hợp V01 vào Master PBIX khi data/model dependencies usable.

## 2026-10-06 — Course visualization theory review V01–V12

- Task/status: **DESIGN REVIEW COMPLETE / POWER BI BUILD NOT STARTED**. `docs/tasks/dashboard-visual-plan.md` now records theory-based review before any chart lock or PBIX work.
- TV3 ownership remains V01 Geographic Risk Map, V10 Loan Amount vs Annual Income, V11 DTI/FICO Risk Matrix, V12 Borrower Segment Analysis and Master Power BI integration. V01 uses verified state-level `state_code`/`country`; no location is fabricated from masked ZIP.
- Review recommendation: V01 map remains a provisional candidate pending Power BI recognition; V10 should use binned heatmap or sampled detail instead of plotting the full raw population; V11 heatmap remains suitable with cell count/sparse-cell handling; V12 is **NEEDS MORE DATA** until segment dimension, measure and decision question are specified.
- Provisional five-page architecture and Individual Prediction / Decision Support page remain unchanged. Chart types, interactions and measures are not final until lecturer-material review and data-model sign-off.
- No PBIX, dataset, code or model changed; no commit/push. Next step: receive complete lecturer materials and then review TV3 visual specifications/data-model choices before integration.

## 2026-10-01 — Team responsibility reorganization

- Task: reorganize workload cho Lending Club; trạng thái **PLANNED / NOT YET IMPLEMENTED**.
- TV3 giữ primary Master Power BI integration, nhận V10–V12 và dashboard report/demo; tích hợp V01–V09 từ các owner khác.
- Files: `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/thanh-vien-3-dashboard.md`, `docs/tasks/dashboard-visual-plan.md`, `docs/tasks/report-writing-plan.md`, `docs/tasks/defense-knowledge-matrix.md`.
- Kiểm tra: PBIX single integration owner và 5-page plan được ghi rõ; chưa build dashboard/DAX.
- Next step: review visual specifications khi TV2 bàn giao usable schema.

## 2026-10-06 — Power BI Phase 2 data-model architecture

- Task/status: **ARCHITECTURE DOCUMENTED / POWER_BI_DATA_MODEL_BLOCKED**. V01–V12 visual families and five-page architecture remain locked; no visual selection, ownership or workload was changed.
- Updated canonical `docs/tasks/dashboard-visual-plan.md` with import manifest, source populations/grains, fact/dimension model, relationships, measure definitions/DAX proposals, slicers/interactions, tooltips/drill paths, Page 5 inference contract, provenance, performance and readiness gate.
- Reconciled `docs/tasks/thanh-vien-1-modeling.md`, `docs/tasks/thanh-vien-2-data-engineering.md`, `docs/tasks/thanh-vien-3-dashboard.md`, `docs/tasks/phan-cong-nhiem-vu.md`, and `docs/setup/tv3_setup.md` so none reopens locked chart families. TV2 remains PRIMARY OWNER of Data Engineering; V07–V09 ownership unchanged.
- Source checks: application funnel 29,909,442 rows (accepted 2,260,701; rejected 27,648,741); canonical labeled 1,345,350, target 0=1,076,751 and target 1=268,599; unresolved accepted 915,351; frozen-test scored/EL populations 269,070 with exact 1:1 loan_id match. All 269,070 scored IDs matched canonical context 1:1; all had state/FICO/loan/income bands; 80 had missing DTI band and must remain missing. State dimension 51; date dimension 4,238. SHAP sample 75,000 long rows from 5,000 validation loans; local table 30 rows (3 examples × 10 features).
- Reconciled ML-LC-10 threshold `0.22009515762329102`, tier counts 66,275 / 109,146 / 80,423 / 13,226; ML-LC-11 baseline EAD proxy 3,878,248,925, EL45 372,579,342.19, EL rate 9.6069%, LGD scenario totals 248,386,228.13 / 372,579,342.19 / 496,772,456.26. No model or test rerun.
- Blockers: application aggregation must preserve distinct accepted `issue_d` vs rejected `application_date` and accepted `purpose` vs rejected `loan_title`; create evaluated-score context mart for state and canonical bands; smoke-test Power BI state map recognition; Page 5 has no inference service/UI. Do not build visuals until gates in canonical plan pass.
- Validation: read-only artifact inspection and exact keyed join/control-total checks PASS; `git diff --check` PASS. No code/data/model/PBIX changed; existing untracked `reports/figures/dashboard/nghia.pbix` left untouched; no commit/push.
- Next step: TV2/TV3 review ownership and create/validate the specified marts through approved DE workflow; TV3 then smoke-tests model imports/Map in PBIX.

## 2026-10-07 — Chốt dashboard thành 4 trang Power BI + Plotly Dash companion

- **Status: FINAL STORYTELLING SPEC UPDATED; no Power BI/Dash implementation changed.** Viết lại `docs/tasks/dashboard-visual-plan.md` thành specification cuối cùng: bốn trang Power BI; Individual Prediction là ứng dụng Plotly Dash bên ngoài, không tính là trang report.
- Cập nhật phân trang/điều hướng, Big Idea/story flow từng trang và records V01–V12 theo cùng hợp đồng câu hỏi, bằng chứng/quan sát, insight, kết nối story, filter, nguồn/grain và limitation. Page 4 ghi V02 Histogram, V03 100% stacked horizontal bar, V05 Top-10 SHAP lollipop và V06 Expected Loss donut; không tuyên bố đã dựng các loại visual này trong PBIX.
- Giữ accepted/rejected, resolved outcome, frozen-test evaluated cohort, validation SHAP và Dash inference thành các population/ranh giới riêng. Những insight V01, V07, V09, V10, V11, V12 chưa có final evidence được ghi PENDING thay vì bịa.
- Condense design-decision diary; bỏ kiến trúc cũ sáu trang, speculative chart comparisons và Page 6 CSV-refresh assumptions khỏi nội dung canonical. Không sửa TV2/TV3 task/setup/PBIX/Dash, data, model; không commit/push/publish.
- Validation: checked exact page map, V01–V12 record headings, obsolete architecture phrases and `git diff --check`; kết quả closeout ghi trong phản hồi task.
- Next step: TV3 xác nhận cập nhật này với các owner và tiếp tục data-model/build gate theo final 4-page architecture.

## 2026-10-07 — Đồng bộ tài liệu TV3 và kiểm soát PBIP local cache trước khi publish mã nguồn

- **Status: DOC CONSISTENCY PASS.** Sau khi canonical `docs/tasks/dashboard-visual-plan.md` đã chốt 4 trang Power BI + Dash bên ngoài, đồng bộ `docs/setup/tv3_setup.md`, `docs/tasks/thanh-vien-3-dashboard.md`, `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/defense-knowledge-matrix.md` để không còn mô tả Master 5/6 trang. Working PBIP của TV1 được phân biệt rõ với Master TV3 chưa build. Không đổi ownership V01–V12 hoặc chart/data policy.
- Dọn khoảng trắng ở `docs/tasks/dashboard-visual-plan.md` để `git diff --check` PASS. Bổ sung `.gitignore` cho thư mục Power BI Desktop `.pbi/` chứa cache/local settings (đặc biệt `cache.abf` khoảng 33,8 MB); giữ các file định nghĩa PBIP/PBIR/TMDL có thể review, không xóa cache trên máy.
- Kiểm tra: toàn bộ `tests` **246 passed**, 7 warnings date parser/SHAP deprecation; 46 file JSON/PBIP/PBIR/PBISM parse PASS; `compileall -q src apps tests` PASS; `git diff --check` PASS. Không sửa dữ liệu/model hay nội dung Power BI report.
- Next step: TV3 kiểm tra file Master sau khi marts/map gate được đóng; tài liệu hiện dùng final 4-page architecture. Không tuyên bố Master đã hoàn tất.
