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

## 2026-10-08 — Audit an toàn Huy PBIP → Nghia PBIP

- **Status: BLOCKED — SOURCE REPORT INCOMPLETE / SEMANTIC CONFLICTS.** Đã sao lưu `nghia.Report`, `nghia.SemanticModel`, `nghia.pbip` trước audit vào `reports/figures/dashboard/_merge_backup/20261008-001350/`. Power BI Desktop đóng. Không merge, không thay bất kỳ PBIR/TMDL/source file nào.
- Source `Huydepzai.Report` không có `definition/pages`, page/visual JSON; do đó không thể nhập trang hoặc kiểm tra visual dependencies. Bốn bảng trùng tên có TMDL khác nhau; source Power Query dùng absolute path `D:\Huy\...`; `Observed Default Rate` trùng tên nhưng khác population/logic; date relationships/bookmark cần review thêm.
- Tạo `reports/figures/dashboard/merge-huy-into-nghia-audit.md` lưu inventory, conflict, validation và điều kiện tiếp tục; cập nhật `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md` với hướng dẫn GUI tương đương và ghi rõ chưa thao tác GUI.
- Validation: source/target JSON/PBIR parse PASS; target binding vẫn trỏ tới `nghia.SemanticModel`; target 12 page entries/81 visuals giữ nguyên. `nghia.Report` backup 102 file, SHA-256 đối chiếu PASS. Visual dependency/render validation BLOCKED do source thiếu pages.
- Next step: yêu cầu source Huy đã Save đầy đủ (pages, visuals và dependencies); sau đó audit lại rồi xử lý conflicts được duyệt. Không commit/push/publish.

## 2026-10-08 — Sửa dependency measure Huy trong Nghia PBIP

- **Status: MEASURE_BINDING_STATIC_PASS / DAX_RUNTIME_PASS / VISUAL_RENDER_PENDING.** Đính chính entry audit trước: các trang Huy đã được người dùng đưa thủ công vào `nghia.Report/definition/pages/`; nguồn `Huydepzai.Report/definition/pages/` trống là mong đợi. Không nhập lại page.
- Backup mới trước sửa: `reports/figures/dashboard/_merge_backup/20261008-003435/` gồm `nghia.Report`, `nghia.SemanticModel`, `nghia.pbip`; backup cũ giữ nguyên. TV3 là owner tích hợp master.
- Sửa `reports/figures/dashboard/nghia.SemanticModel/definition/tables/cleaned_dataset.tmdl`: dùng lại `Total Loans = COUNTROWS(cleaned_dataset)`; thêm 7 measure gốc Huy, đổi tên đúng một measure thành `Observed Default Rate — Portfolio` để giữ riêng với `fact_evaluated_loan[Observed Default Rate]` của TV1. DAX/format source của cả 8 measure đối chiếu PASS; không tạo `*Measure table` trùng, không sửa data/relationship/model TV1.
- 18 visual JSON đã sửa binding (đường dẫn đầy đủ):
  - `reports/figures/dashboard/nghia.Report/definition/pages/ce7979183a9313cd4a54/visuals/13521b87db3056e4279f/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/ce7979183a9313cd4a54/visuals/5dc5245623a5789431a8/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/ce7979183a9313cd4a54/visuals/99fbfeb01668ee67e68d/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/ce7979183a9313cd4a54/visuals/acf45ee8b7a3a5bd3086/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/ce7979183a9313cd4a54/visuals/c2644a24da8debd50f6f/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/420bda4753cd633bcec7/visuals/109f3649907db9bb50bb/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/420bda4753cd633bcec7/visuals/1eb081856520dcc85b12/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/420bda4753cd633bcec7/visuals/25151bed10a138d36846/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/420bda4753cd633bcec7/visuals/311442f8ad8c8d8ac47a/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/420bda4753cd633bcec7/visuals/8c1bfb565c7c639ac05f/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/420bda4753cd633bcec7/visuals/dd52aed9c09245a16822/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/cebd7650a008a8c337e7/visuals/607c325aca8984020df8/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/cebd7650a008a8c337e7/visuals/31ee08e9be5979bf1b63/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/cebd7650a008a8c337e7/visuals/e85f9955dcdae194e6fa/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/cebd7650a008a8c337e7/visuals/9f46a614a7ecfc316174/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/cebd7650a008a8c337e7/visuals/7c128f7b69e10f4fae3c/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/6c440c0bbe572e288709/visuals/634f279d1172c8298a40/visual.json`
  - `reports/figures/dashboard/nghia.Report/definition/pages/6c440c0bbe572e288709/visuals/3f7bcf1c6e9c79858b0a/visual.json`
- Card `e85f9955dcdae194e6fa` trước ghi Average Loan Amount nhưng query `annual_inc`; nay Data/sort dùng đúng measure `Average Loan Amount`. Cập nhật `reports/figures/dashboard/merge-huy-into-nghia-audit.md` để sửa kết luận audit cũ; cập nhật `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md` với thao tác Desktop tương đương; cập nhật `docs/setup/tv3_setup.md` với cách mở, kiểm tra và giới hạn.
- Validation: 101 JSON/PBIR/PBIP parse PASS; 12 pages/81 visuals giữ nguyên; 89 field references phân biệt, 0 missing; không còn `*Measure table`/`D:\Huy\...` trong target; 8 DAX/format so với source PASS, 0 duplicate measure names; Desktop local model load và query 8 measure Huy + measure TV1 PASS; TV1 V02–V06/4. Annalysis RISK và `fact_evaluated_loan.tmdl` so hash với backup, không đổi; `nghia.pbip`/binding vẫn đúng. Agent mở Desktop chỉ để chạy DAX rồi đóng, không Save/publish.
- Next step: TV3 mở `nghia.pbip` để nghiệm thu render/map/KPI/trend/purpose/TT_V11 và đối chiếu số với nguồn trước khi chốt dashboard. Không commit/push/publish.

## 2026-10-08 — Rút Master còn bốn trang và sửa lỗi khoanh vùng

- **Trạng thái: PBIR/JSON STATIC PASS; DAX RUNTIME/RENDER PENDING; V01 MAP BLOCKED BY POWER BI SECURITY.** Người dùng chọn giữ Map và bật bằng Desktop/admin, không đổi sang chart khác. Desktop đã đóng trước khi chỉnh. Backup có thể khôi phục: `reports/figures/dashboard/_merge_backup/20261008-four-page-polish/` (report + semantic definition trước sửa, 8 trang rút khỏi Master và shape V04 cũ). Không xóa vĩnh viễn.
- `reports/figures/dashboard/nghia.Report/definition/pages/pages.json` và bốn `page.json` của `ce7979183a9313cd4a54`, `420bda4753cd633bcec7`, `cebd7650a008a8c337e7`, `3b1d1f6e1c7a4e64a853`: chỉ giữ các trang 01 Tổng quan, 02 Xu hướng, 03 Hồ sơ vay, 04 Rủi ro & EL; tên ngắn để page navigator không chồng/cắt; ba nền đầu đồng bộ màu `#C5D7E9` với trang 04. Đã rút `p4`, `P5`, `TT_V11`, V02/V03/V04/V05/V06 prototype thành 8 thư mục dưới `retired-pages` trong backup. Biểu đồ V02/V03/V05/V06 chính trên trang 04 giữ nguyên.
- Visual thay đổi (đường dẫn đều dưới `reports/figures/dashboard/nghia.Report/definition/pages/`): `ce7979183a9313cd4a54/visuals/13521b87db3056e4279f/visual.json` dùng count/default-rate trên evaluated fact, title trung tính; `ce7979183a9313cd4a54/visuals/b16b5dd10d775e4e00b1/visual.json` bỏ nhận định địa lý chưa nghiệm thu; `cebd7650a008a8c337e7/visuals/7fc46b23b3c2b1e32ff6/visual.json` điền KPI count; `cebd7650a008a8c337e7/visuals/e85f9955dcdae194e6fa/visual.json` chuyển card trùng loan amount sang annual income; `cebd7650a008a8c337e7/visuals/55990e0efc6d0e598c88/visual.json` phân biệt populations; `cebd7650a008a8c337e7/visuals/5289b1fa62556a58b95f/visual.json` chuyển V04 vào ô dưới bên phải thay placeholder; `cebd7650a008a8c337e7/visuals/31ee08e9be5979bf1b63/visual.json` đổi từ report-page tooltip sang default + N. Page navigator của trang 03/04 (`73cb2e456fb4e03dc872`, `ca4be020c31a2829a020`) bỏ các page-ID cũ.
- Model: `reports/figures/dashboard/nghia.SemanticModel/definition/relationships.tmdl` nối `dim_date.date → cleaned_dataset.issue_d` (one-to-many); `.../tables/cleaned_dataset.tmdl` bỏ `$` chưa có contract, thêm Average Annual Income và đổi Top Purpose/Peak Year từ hằng thành theo filter; `.../tables/dim_state.tmdl` gắn địa lý thật cho state/country. Không sửa dữ liệu, TV1 model output hoặc trang 04.
- Hướng dẫn GUI/cách chạy và cảnh báo: `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`, `docs/setup/tv3_setup.md`. Kiểm tra read-only: 76 JSON parse, 4 page entries = 4 page directories, 69 visual, V04 có mặt ở trang 03, không còn tham chiếu page-ID rút đi; MCP distill report cũng thấy 4/69. `cleaned_dataset` 1.345.350 rows, 12 năm; 2007=251 và 2015=375.546, default rate 17,93% vs 20,19%; `dim_date.date` 4.238 ngày unique, tất cả `issue_d` có match; 269.070 evaluated IDs đều nằm trong cleaned data. `git diff --check` PASS.
- **Giới hạn/next step:** agent thử mở Desktop ở chế độ ẩn để kiểm DAX nhưng chỉ nhận phiên `Untitled`, không có model/report để truy vấn; đã đóng phiên tạm không lưu. TV3 cần mở `nghia.pbip` trong Desktop, xác nhận TMDL/relationships, card/V04/tooltip/map render và số theo năm. Bật Map ở Desktop Security hoặc nhờ tenant admin; nếu V11 default tooltip không hiển thị N, khôi phục tooltip page từ backup trước khi coi hoàn thành. Không commit/push/publish.

## 2026-10-08 — Đính chính cardinality cho quan hệ ngày của Master

- **Status: DEFINITION ERROR IDENTIFIED AND PATCHED / DESKTOP REOPEN PENDING.** Người dùng mở `nghia.pbip` và cung cấp hộp thoại: `dim_date_to_cleaned_issue_d` bị Power BI hiểu One-to-One, trong khi CrossFilterDirection mặc định OneDirection; project không nạp được. Không Save phiên lỗi; Desktop đã đóng trước khi sửa.
- Sửa đúng một dòng trong `reports/figures/dashboard/nghia.SemanticModel/definition/relationships.tmdl`: thêm `toCardinality: many` cho `dim_date.date (1) → cleaned_dataset.issue_d (*)`. Nguồn xác minh: `dim_date.date` 4.238/4.238 unique; `cleaned_dataset.issue_d` 1.345.350 rows / 139 ngày unique, 0 ngày ngoài dim_date. Không đổi DAX/data hoặc relation khác.
- Đồng bộ GUI và trạng thái ở `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`, `docs/setup/tv3_setup.md`. `git diff --check` PASS; người dùng được yêu cầu mở lại Desktop. Chưa ghi runtime PASS cho tới khi project nạp được và biểu đồ năm được kiểm.

## 2026-10-08 — Sửa đúng hướng From/To của quan hệ ngày sau Frown feedback

- **Status: RELATIONSHIP DEFINITION PATCHED / DESKTOP REOPEN PENDING.** Feedback Power BI Desktop ngày 2026-10-08 01:40 local cho biết `dim_date_to_cleaned_issue_d` có **From end cardinality = One**, trong khi One-to-Many bắt buộc **From = Many**. Bản vá trước thêm `toCardinality: many` đã sai hướng kỹ thuật dù sơ đồ logic 1:* đúng; đây là lỗi agent, không phải dữ liệu nguồn.
- Sau khi xác nhận không còn process Power BI Desktop, sửa `reports/figures/dashboard/nghia.SemanticModel/definition/relationships.tmdl` thành `fromColumn: cleaned_dataset.issue_d` → `toColumn: dim_date.date`, bỏ hai dòng override cardinality, theo đúng convention của các relationship Many-to-One hiện có trong project. Trực quan GUI vẫn là dim_date (1) lọc cleaned_dataset (*). Dữ liệu nguồn đã kiểm: dim_date 4.238 ngày unique, cleaned_dataset 1.345.350 rows / 139 issue dates, 0 unmatched.
- Sửa lại hướng dẫn hiện hành ở `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md` và `docs/setup/tv3_setup.md`. Cần mở lại Desktop để xác nhận model load, DAX theo năm và render; không tự tuyên bố PASS. Không commit/push/publish.

## 2026-10-08 — Xác nhận model nạp được và DAX runtime sau sửa quan hệ

- **Status: MODEL_LOAD_PASS / DAX_RUNTIME_PASS / VISUAL_RENDER_PENDING.** Agent mở `reports/figures/dashboard/nghia.pbip` trong Power BI Desktop ở chế độ ẩn; cửa sổ có tiêu đề `nghia`, bridge nhận model ID và thực thi DAX thành công sau khi đổi TMDL sang `cleaned_dataset.issue_d` (Many) → `dim_date.date` (One). Không chỉnh visual hoặc Save trong Desktop.
- `SUMMARIZECOLUMNS(dim_date[year])` trả 12 năm với count khác nhau: 2007=251, 2015=375.546; observed default rate 2007=0,179283, 2015=0,20185. `Peak Year` toàn bộ=2015, khi filter 2007–2008 thì=2008; selected loans=1.813. Card measures: Total Loans=1.345.350, Average Loan Amount≈14.420, Average Annual Income≈76.247,6, Top Purpose=`debt_consolidation`, evaluated=269.070. Tổng evaluated theo 51 state = 269.070; ví dụ CA=39.472, NY=21.710. Không dùng số này để kết luận Map đã render.
- Đồng bộ trạng thái và GUI-check ở `docs/setup/tv3_setup.md`, `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`. Next step: TV3 mở giao diện để xác nhận 4 tab, V04, tooltip V11, chart năm, Map permission và tổng thể bố cục; không commit/push/publish.

## 2026-10-08 — Sửa V01 Geographic Risk Map

- **Status: DATA/BINDING PASS / PBIR STATIC PASS / MODEL-DAX PASS / DESKTOP VISUAL RENDER PENDING.** Backup trước sửa: `reports/figures/dashboard/_merge_backup/20261008-v01-map-audit/`. Desktop đã đóng trước khi sửa PBIR/TMDL.
- Audit nguồn: V01 dùng quan hệ `dim_state → cleaned_dataset ↔ fact_evaluated_loan`; DAX xác nhận **269.070 evaluated loans**, **51 state/state-equivalent có dữ liệu**, `country = United States`, tổng theo state khớp 269.070. Không có state bị thiếu trong evaluated context. `IA` có 1 loan, 0 default và là dữ liệu thật; blank referential member của dimension có 0 loan nên không được coi là state. Bảng đầy đủ ở `reports/figures/dashboard/v01_state_audit.md`.
- Lỗi cũ: visual ID `13521b87db3056e4279f` ở page `01 · Tổng quan` là **shapeMap**, dùng `Value` cho loan count và fill shape theo default rate. Shape map không thể biểu diễn đồng thời bubble size + bubble color. Fill rule cũ dùng `Observed Default Rate` chung và `asZero` cho null; vì vậy màu xám/xanh/pale trước đó không thể được đọc như một encoding rủi ro hợp lệ. IA còn bị BLANK rate do zero default. Static audit không cho thấy một state hợp lệ nào bị mất hoặc có category màu xanh riêng.
- Sửa `reports/figures/dashboard/nghia.Report/definition/pages/ce7979183a9313cd4a54/visuals/13521b87db3056e4279f/visual.json`: đổi `visualType` thành native `map`; bỏ shape-map GeoJSON; `Category` = `dim_state[state_code]` + `dim_state[country]`; `Size` = `[Evaluated Loan Count]`; thêm tooltip `[Evaluated Loan Count]`, `[Observed Default Count — State Map]`, `[Observed Default Rate — State Map]`, `[Mean PD]`; giữ gradient data-driven nhạt → cam → đỏ, null không còn ép thành zero, bật bubble settings/auto zoom/English-US geocoding.
- Sửa `reports/figures/dashboard/nghia.SemanticModel/definition/tables/fact_evaluated_loan.tmdl`: thêm hai measure chỉ phục vụ V01: `[Observed Default Count — State Map]` dùng `COALESCE(..., 0)` và `[Observed Default Rate — State Map]`. Không đổi raw data, frozen-test output, target, threshold, V02–V06 hoặc model artifact.
- Đổi title/subtitle trên visual thành `Rủi ro tín dụng phân bố khác nhau giữa các bang` và `Màu thể hiện tỷ lệ default quan sát · Kích thước thể hiện số khoản vay đánh giá`; cập nhật GUI-equivalent trong `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`, setup tại `docs/setup/tv3_setup.md`.
- Validation: JSON parse/PBIR distill **4 pages / 69 visuals PASS**; Desktop nạp model sau sửa và `describe_table` thấy hai measure mới; DAX state audit trả đúng count/rate. Ví dụ: CA 39.472 / 19,68%; TX 22.176 / 20,01%; NY 21.710 / 22,13%; MS 1.325 / 24,83%; OR 3.285 / 13,42%; IA 1 / 0,00%. `git diff --check` PASS.
- **Remaining check:** chưa có screenshot/render capture để xác nhận Map permission, bubble placement, Alaska/Hawaii và tooltip trên canvas. Mở Desktop, bật Map security nếu cần, hover tối thiểu CA/TX/NY/MS/OR/IA rồi kiểm tra Size/Color/Tooltip trước khi Save. Không commit/push/publish.

## 2026-10-08 — Xác nhận Map bị chặn ở cấp tenant

- **Status: TENANT POLICY BLOCKED / PBIR FIX RETAINED.** Người dùng mở lại `nghia.pbip` và cung cấp ảnh: mục **Current file → Use Map and Filled Map visuals** đã được bật, nhưng canvas vẫn báo *Map and filled map visuals aren't enabled for your org*.
- Kết luận: đây không còn là lỗi binding, dữ liệu, geocoding hay checkbox local. V01 vẫn là native bubble `Map` đúng thiết kế; Power BI tenant policy chưa cho phép visual Map. PBIR không thể tự ghi đè quyền tổ chức.
- Cách xử lý: tenant admin bật **Admin portal → Tenant settings → Map and filled map visuals** cho toàn tổ chức hoặc security group của tài khoản, bấm **Apply**, rồi người dùng đăng nhập lại và mở lại Desktop. Không tạo location giả và không đổi V01 sang chart khác khi chưa có chỉ đạo mới.
- Files cập nhật: `docs/setup/tv3_setup.md`, `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`. `git diff --check` cần chạy lại; không commit/push/publish.
