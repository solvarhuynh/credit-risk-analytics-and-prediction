# TV2 Progress Log — Lending Club Dataset Reset

## Dataset Migration Reset — 2026-10-01

- Dataset cũ đã retired; Lending Club 2007–2018 được chọn.
- Lịch sử trước reset đã được loại khỏi working tree; có thể truy xuất qua Git history.
- Chưa chạy lại pipeline hoặc mô hình.
- Trạng thái: **RESET / NOT YET EXECUTED**.
- Bước tiếp theo: **DE-LC-01 — Raw inventory & schema profiling**.

## 2026-10-01 — Full dataset migration

- Trạng thái: **MIGRATED / NOT YET EXECUTED**.
- Đã đặt raw local tại `data/raw/accepted_loans.csv` và `rejected_loans.csv`; reset interim/processed; rewrite `src/data/`, `src/features/`, contracts, setup/task và synthetic tests.
- Đã thêm column leakage policy, business-table architecture, target policy, chunk loader, quality/leakage gate và EDA functions.
- Kiểm tra: destination size/hash khớp source; 151 accepted + 9 rejected raw columns đều được policy phân loại; compileall PASS; không chạy pipeline hoặc data-dependent tests.
- Next step: **DE-LC-01 — Raw inventory & schema profiling**.

## 2026-10-01 — TV2 execution interface / runbook preparation

- Task: stage runner hardening; trạng thái **PARTIAL / PYTEST BLOCKED BY ENVIRONMENT**.
- Đã tạo canonical gated runner `src/data/tv2_runner.py` cho DE-LC-01…DE-LC-10, marker PASS/FAIL/BLOCKED, dependency gates, chunk-safe raw handling và fixture overrides.
- Đã cập nhật `docs/setup/tv2_setup.md` thành runbook từng stage; đồng bộ `docs/tasks/thanh-vien-2-data-engineering.md`; thêm synthetic runner tests.
- Đã harden `src/data/quality_report.py`, `src/data/build_pipeline.py` và `src/data/cleaning.py` cho quality wording, optional dependency message, Parquet schema cast và employment parsing.
- Kiểm tra: `compileall src tests` PASS; CLI help/invalid-stage PASS; synthetic DE-LC-01…03 smoke PASS; duplicate-key/target-unresolved/leakage gates PASS. `python -m pytest tests/data tests/features -q` chưa chạy được vì môi trường thiếu `pytest`; không chạy raw stage/pipeline thật.
- Next step: **Run DE-LC-01 on the real Lending Club raw files.**

## 2026-10-01 — Team responsibility reorganization

- Task: reorganize workload cho Lending Club; trạng thái **PLANNED / NOT YET IMPLEMENTED**.
- TV2 giữ primary Data Engineering + technical EDA, nhận V07–V09 và primary data/preprocessing report; không nhận modeling implementation.
- Files: `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/thanh-vien-2-data-engineering.md`, `docs/tasks/dashboard-visual-plan.md`, `docs/tasks/report-writing-plan.md`.
- Kiểm tra: phân công giữ DE-LC-01–10, TV1 là cross reviewer; không chạy pipeline/EDA.
- Next step: **DE-LC-01 — Raw inventory & schema profiling**.

## 2026-10-03 — DE-LC-01 Raw Inventory & Schema Profiling

- Task: ghi nhận kết quả raw inventory và schema profiling Lending Club; trạng thái **DE-LC-01 = PASS**.
- Ownership: **TV2 = PRIMARY OWNER — Data Engineering**; DE-LC-01 remains a TV2 Data Engineering task.
- Executor / Supporting Contributor: **TV1** trực tiếp thực hiện và review DE-LC-01 để hỗ trợ Data Engineering, đặc biệt nhằm hiểu và xác minh handoff downstream `TV2 → TV1` cho modeling. Việc này không thay đổi ownership của TV2 hoặc thay thế đóng góp Data Engineering của TV2.
- ACCEPTED: `data/raw/accepted_loans.csv`, 1,675,133,810 bytes, 151 raw columns, sample 5 rows, date range `2007-06-01 → 2018-12-01`, 51 unique state codes, 33 missing state.
- REJECTED: `data/raw/rejected_loans.csv`, 1,782,281,620 bytes, 9 raw columns, sample 5 rows, date range `2007-05-26 → 2018-12-31`, 51 unique state codes, 22 missing state.
- Observed accepted `loan_status` counts: Fully Paid 1,076,751; Current 878,317; Charged Off 268,559; Late (31-120 days) 21,467; In Grace Period 8,436; Late (16-30 days) 4,349; Does not meet the credit policy. Status:Fully Paid 1,988; Does not meet the credit policy. Status:Charged Off 761; Default 40; missing 33.
- Observations: profiling được thực hiện theo chunk/sample-wise, không full-load dataframe; accepted và rejected có schema khác biệt đáng kể; rejected không có loan outcome nên tách khỏi target default; geography có state codes; cleaning chưa bắt đầu.
- Exact target mapping chưa được chốt ở stage này; thuộc phạm vi **DE-LC-05**.
- Files: `logs/log_tv2.md`.
- Kiểm tra: `git diff --check` PASS.
- Next step: **DE-LC-02 = NOT STARTED**; chưa chạy cleaning.

## 2026-10-03 — DE-LC-04 Business-table Normalization Hardening

- Task: harden validation cho business-table normalization; trạng thái **DE-LC-04 = PASS** sau targeted tests.
- Ownership: **TV2 = PRIMARY OWNER — Data Engineering**. **TV1 = Executor / Supporting Contributor**; TV1 đã manually audit stage, agent thực hiện targeted implementation/test hardening dưới review đó.
- Đã mở rộng `tests/data/test_aggregate.py` để kiểm tra đủ năm accepted tables (`loan_application`, `borrower_profile`, `credit_profile`, `loan_pricing`, `loan_outcome`): bảo toàn row count, `loan_id` tồn tại/non-null/unique và fail closed với duplicate/null `loan_id`.
- Rejected grain: giữ `rejected_applications` là business table riêng, bảo toàn rows/cột nguồn và không merge row-to-row với accepted. Contract không yêu cầu `rejected_application_id`, nên không tạo synthetic key; uniqueness cấp hồ sơ không thể kiểm chứng khi source không có key.
- Leakage separation: `loan_outcome` vẫn có thể giữ POST_LOAN; canonical join chỉ nhận `target`, còn `loan_pricing` vẫn nằm ngoài baseline modeling join.
- Files: `src/data/aggregate.py`, `docs/contracts/data_contract.md`, `tests/data/test_aggregate.py`, `logs/log_tv2.md`.
- Kiểm tra: `.venv\Scripts\python.exe -m pytest tests/data/test_aggregate.py -v` — 17 passed; `.venv\Scripts\python.exe -m pytest tests/data/test_cleaning.py tests/data/test_aggregate.py -v` — 20 passed; `git diff --check` PASS.
- Status: **DE-LC-01 = PASS; DE-LC-02 = PASS; DE-LC-03 = PASS; DE-LC-04 = PASS; DE-LC-05 = NOT STARTED**.
- Next step: **DE-LC-05 — Target derivation**; chưa triển khai hoặc chạy stage này.

## 2026-10-03 — DE-LC-05 Target Derivation Hardening

- Task: làm rõ và harden target derivation; trạng thái **DE-LC-05 = PASS** sau targeted tests.
- Ownership: **TV2 = PRIMARY OWNER — Data Engineering**. **TV1 = Executor / Supporting Contributor**; agent thực hiện targeted implementation/test hardening dưới review của TV1.
- Canonical target policy: `Fully Paid → target=0`; `Charged Off → target=1`; `Default → target=1`.
- Unresolved và loại khỏi `canonical_labeled`: `Current`, `Late (16-30 days)`, `Late (31-120 days)`, `In Grace Period`, missing `loan_status`, và mọi status không nằm trong allowlist.
- Legacy policy: `Does not meet the credit policy. Status:Fully Paid` và `Does not meet the credit policy. Status:Charged Off` không được map ngầm; giữ unresolved và loại khỏi labeled modeling set.
- Đã làm rõ allowlist trong `derive_target()`; `prepare_accepted_batch()` vẫn bảo toàn các accepted business tables, chỉ đưa target 0/1 vào `canonical_labeled`, giữ `loan_id` non-null/unique và không đưa `TARGET_SOURCE`/`POST_LOAN` vào canonical model features.
- Files: `src/data/cleaning.py`, `tests/data/test_cleaning.py`, `tests/data/test_build_pipeline.py`, `logs/log_tv2.md`.
- Kiểm tra: `.venv\Scripts\python.exe -m pytest tests/data/test_cleaning.py tests/data/test_build_pipeline.py -v` — 15 passed; regression `.venv\Scripts\python.exe -m pytest tests/data/test_aggregate.py tests/data/test_cleaning.py tests/data/test_build_pipeline.py -v` — 32 passed; `git diff --check` PASS.
- Status: **DE-LC-01 = PASS; DE-LC-02 = PASS; DE-LC-03 = PASS; DE-LC-04 = PASS; DE-LC-05 = PASS; DE-LC-06 = NOT STARTED**.
- Next step: **DE-LC-06 — Application-time features**; chưa triển khai hoặc chạy stage này.

## 2026-10-03 — DE-LC-06 Application-time Feature Engineering Hardening

- Task: harden deterministic application-time feature engineering; trạng thái **DE-LC-06 = PASS** sau targeted tests.
- Ownership: **TV2 = PRIMARY OWNER — Data Engineering**. **TV1 = Executor / Supporting Contributor**; agent thực hiện targeted implementation/test hardening dưới review của TV1.
- Feature logic: `fico_avg` là arithmetic mean của `fico_range_low` và `fico_range_high`, thiếu một component thì giữ missing; `loan_to_income_ratio = loan_amnt / annual_inc`, denominator `<= 0` hoặc invalid thì missing và không tạo infinity; `credit_history_months` là month difference giữa `issue_d` và `earliest_cr_line`, history âm hoặc thiếu date thì missing.
- Date logic: `issue_year`, `issue_quarter`, `issue_month` chỉ lấy từ `issue_d`; thiếu `issue_d` thì cả ba giá trị derived đều missing.
- Band logic: sửa `fico_band` sang interval left-closed `[650, 700, 750)` để `650 → 650-699`, `700 → 700-749`, `750 → 750+`; giữ nguyên labels và semantics hiện có của `loan_amount_band`, `income_band`, `dti_band`, đã kiểm tra boundaries.
- Leakage/policy validation: toàn bộ `ENGINEERED_FEATURES` được classify vào `APPLICATION_TIME` hoặc `CREDIT_SNAPSHOT`; không có `UNKNOWN_REVIEW_REQUIRED`, `POST_LOAN`, `TARGET_SOURCE` hoặc `POLICY_DERIVED`; không mở rộng `MODEL_ELIGIBLE_CLASSES`.
- Files: `src/features/engineering.py`, `tests/features/test_engineering.py`, `logs/log_tv2.md`.
- Kiểm tra: `.venv\Scripts\python.exe -m pytest tests/features/test_engineering.py -v` — 5 passed; regression `.venv\Scripts\python.exe -m pytest tests/data/test_cleaning.py tests/data/test_aggregate.py tests/data/test_build_pipeline.py tests/features/test_engineering.py -v` — 37 passed; `git diff --check` PASS.
- Status: **DE-LC-01 = PASS; DE-LC-02 = PASS; DE-LC-03 = PASS; DE-LC-04 = PASS; DE-LC-05 = PASS; DE-LC-06 = PASS; DE-LC-07 = NOT STARTED**.
- Next step: **DE-LC-07 — Join canonical dataset**; chưa triển khai hoặc chạy stage này.

## 2026-10-03 — DE-LC-07 Canonical Modeling Dataset and Leakage Gate Hardening

- Task: harden canonical labeled validation, baseline leakage gate và stage-only execution; trạng thái **DE-LC-07 IMPLEMENTATION = PASS; DE-LC-07 RUNTIME = NOT RUN**.
- Ownership: **TV2 = PRIMARY OWNER — Data Engineering**. **TV1 = Executor / Supporting Contributor** cho DE-LC-07 review/hardening; agent thực hiện targeted implementation/test hardening dưới review của TV1.
- Canonical validation: kiểm tra `loan_id` tồn tại/non-null/unique, `target` tồn tại/non-null và chỉ `{0,1}`, numeric không có infinity, labeled rows chỉ gồm resolved loans, và join không làm nhân bản dòng.
- `prepare_accepted_batch()` expose `canonical_audit` gồm input rows, joined rows, resolved/labeled rows, unresolved rows, unique/duplicate/null loan IDs, target counts, baseline features và leakage-gate result; không drop thêm rows ngoài unresolved target filtering.
- Baseline feature list được derive từ `approved_model_features()` của shared column policy. Chỉ `APPLICATION_TIME` và `CREDIT_SNAPSHOT` được phép; identifier, target source, post-loan, policy-derived, geography, text high-cardinality, analytics-only và unknown đều bị chặn.
- Stage separation: DE-LC-07 chỉ ghi `data/processed/cleaned_dataset.parquet`; test xác nhận không tạo `dim_date`, `dim_state`, dictionary hoặc manifest của DE-LC-08/09. Loader cho phép stage accepted-only không bắt buộc rejected raw.
- Parquet safety: kiểm tra schema ổn định qua empty→non-empty chunks và `close()` an toàn khi gọi lặp hoặc không có write.
- Files: `src/data/quality_report.py`, `src/data/build_pipeline.py`, `src/data/tv2_runner.py`, `src/data/load_data.py`, `tests/data/test_build_pipeline.py`, `logs/log_tv2.md`.
- Kiểm tra: `.venv\Scripts\python.exe -m pytest tests/data/test_build_pipeline.py -v --basetemp D:\ttdltq\.pytest-tmp-de07` — 12 passed; regression `.venv\Scripts\python.exe -m pytest tests/data/test_cleaning.py tests/data/test_aggregate.py tests/data/test_build_pipeline.py tests/features/test_engineering.py -v --basetemp D:\ttdltq\.pytest-tmp-de07-regression` — 47 passed; supporting tests quality/runner/loader — 10 passed; `git diff --check` PASS.
- Status: **DE-LC-01 = PASS; DE-LC-02 = PASS; DE-LC-03 = PASS; DE-LC-04 = PASS; DE-LC-05 = PASS; DE-LC-06 = PASS; DE-LC-07 IMPLEMENTATION = PASS; DE-LC-07 RUNTIME = NOT RUN; DE-LC-08 = NOT STARTED; DE-LC-09 = NOT STARTED**.
- Next step: **DE-LC-07 runtime on real raw accepted data**, only after explicit execution; chưa chạy full Lending Club raw pipeline.

## 2026-10-03 — DE-LC-04 Runtime Atomic-output and Interruption Hardening

- Incident: lần chạy DE-LC-04 trên raw thật trước đó bị **INTERRUPTED** bởi user `KeyboardInterrupt` trong lúc xử lý rejected data. Không có marker `DE-LC-04 PASS`; toàn bộ Parquet output từ lần interrupted được coi là **UNTRUSTED**.
- Hardening: runner ghi độc lập vào sáu `*.partial.parquet`, đóng sink, validate đủ file rồi mới promote bằng `os.replace` sang canonical names. Khi gặp `StageValidationError`, `ValueError`, `OSError`, `RuntimeError` hoặc `KeyboardInterrupt`, sink được đóng, partial artifacts được dọn, canonical outputs cũ được giữ; promotion lỗi có rollback các canonical cũ.
- Progress: thêm báo cáo nhẹ theo chunk/row cho accepted và rejected. Không in theo từng row.
- Rejected cleaning: không thay đổi `clean_rejected_loans()` hoặc semantics chuẩn hóa null-like strings; chưa có optimization được chứng minh an toàn nên giữ nguyên implementation.
- Ownership: **TV2 = PRIMARY OWNER — Data Engineering**. **TV1 = Executor / Supporting Contributor**; agent thực hiện targeted runtime hardening dưới review của TV1. DE-LC-04 vẫn là task của TV2, không chuyển ownership.
- Files: `src/data/tv2_runner.py`, `tests/data/test_tv2_runner.py`, `docs/setup/tv2_setup.md`, `logs/log_tv2.md`.
- Kiểm tra: `.venv\Scripts\python.exe -m pytest tests/data/test_tv2_runner.py tests/data/test_aggregate.py -v --basetemp D:\ttdltq\.pytest-tmp-de04` — **27 passed**; regression `.venv\Scripts\python.exe -m pytest tests/data/test_cleaning.py tests/data/test_aggregate.py tests/data/test_build_pipeline.py tests/data/test_tv2_runner.py tests/features/test_engineering.py -v --basetemp D:\ttdltq\.pytest-tmp-de04-regression` — **57 passed**; `git diff --check` — **PASS**.
- Status: **DE-LC-01 RUNTIME = PASS; DE-LC-02 RUNTIME = PASS; DE-LC-03 RUNTIME = PASS; DE-LC-04 IMPLEMENTATION = PASS; DE-LC-04 RUNTIME = INTERRUPTED / NOT PASS; DE-LC-05 = NOT RUN**.
- Next step: rerun DE-LC-04 trên raw thật chỉ sau khi owner chủ động xác nhận; không chạy DE-LC-05+ trong task này.

## 2026-10-03 — Data Artifacts Guide for Lending Club Pipeline

- Task: tạo hướng dẫn beginner-friendly cho raw, interim business tables, DE-LC-08 dimensions/mart, processed handoff và stage evidence; trạng thái **PASS**.
- File: `docs/data/data_artifacts.md`.
- Đã đối chiếu artifact names và semantics với `src/data/aggregate.py`, `src/data/tv2_runner.py`, `src/data/build_pipeline.py`, `docs/contracts/data_contract.md` và `docs/setup/tv2_setup.md`.
- Guide ghi rõ grain, mục đích, consumer, model/dashboard usage và caution cho từng artifact; nhấn mạnh `POST_LOAN`, `POLICY_DERIVED`, rejected-data separation và canonical modeling handoff.
- Evidence hiện có: `reports/tv2_stages/de-lc-07.md` xác nhận `1,345,350` resolved labeled rows và leakage gate `PASS`; `reports/tv2_stages/de-lc-08.md` xác nhận outputs dimensions/mart. Guide không tự thêm số liệu chưa có trong stage reports.
- Discrepancy cần theo dõi: log cũ vẫn ghi DE-LC-07 runtime `NOT RUN`, trong khi stage reports hiện có `de-lc-07` và `de-lc-08` `PASS`; task này chỉ ghi nhận trong guide/log, không tự sửa lịch sử status.
- `BAO_CAO_MIGRATION_LENDING_CLUB.md` đang ở trạng thái deleted trong working tree của task trước; đã đọc bản tracked bằng read-only để đối chiếu, không khôi phục hoặc chỉnh file đó.
- Kiểm tra: `git diff --check` — pending sau khi ghi entry này.
- Next step: TV2 reconcile stage-status log với reports/markers trước khi dùng làm official runtime history.

## 2026-10-03 — DE-LC-10 Static EDA Redesign and Runtime Rerun

- Task: thay bộ static EDA cũ bằng đúng 5 chart đa dạng, có business question/visual rationale/candidate insight/story connection; trạng thái **DE-LC-10 RUNTIME = PASS**.
- Ownership: **DE-LC-10 vẫn là TV2 Data Engineering stage** và TV2 vẫn là **PRIMARY OWNER** của canonical EDA source/module. **TV1 = Executor / Supporting Contributor** cho phần refinement/interpreting static EDA; agent thực hiện targeted implementation/test hardening dưới review của TV1. Ownership này không chuyển Data Engineering sang TV1.
- Bộ chart mới: histogram loan amount; boxplot DTI by target; ordered FICO default-rate bar; FICO × DTI default-rate heatmap; chronological loan-volume/default-rate line chart.
- EDA-01/02 dùng plotting sample deterministic tối đa 200,000 rows. EDA-03/04/05 aggregate từ toàn bộ canonical labeled dataset theo chunk. DTI display cap là 99th percentile `38.35`, không mutate canonical data. Heatmap minimum cell count là `100`.
- Funnel audit: **FAIL / discrepancy detected**. Expected từ DE-LC-02: accepted `2,260,701`, rejected `27,648,741`; actual `application_funnel.parquet`: accepted `2,260,701`, rejected `55,197,482`; rejected difference `+27,548,741`. Không sửa DE-LC-08 trong task này; discrepancy được ghi trong report để follow-up riêng.
- Files/code: `src/data/tv2_runner.py`, `tests/data/test_eda.py`, `docs/tasks/thanh-vien-2-data-engineering.md`, `docs/setup/tv2_setup.md`, `logs/log_tv2.md`.
- Generated reports: `reports/eda_report.md`, `reports/tv2_stages/de-lc-10.md`, `reports/tv2_stages/state/de-lc-10.json`.
- Generated figures: `reports/figures/eda/eda_01_loan_amount_distribution.png`, `eda_02_dti_by_target.png`, `eda_03_default_by_fico.png`, `eda_04_fico_dti_heatmap.png`, `eda_05_loan_volume_default_rate_over_time.png`. Old annual-income, purpose và accepted/rejected EDA images đã được retire; underlying data/mart không bị xóa.
- Kiểm tra: focused EDA + runner tests — **15 passed**; targeted regression data/features/EDA suite — **62 passed**; full `tests/data tests/features` regression — **65 passed**; real command `.venv\Scripts\python.exe -m src.data.tv2_runner --stage de-lc-10` — **PASS**, đúng 5 PNG non-empty; `git diff --check` — **PASS**.
- Limitations: observed default rate chỉ mô tả association, không phải causation. Các tháng gần đây có thể có resolved-outcome coverage khác nhau vì canonical chỉ chứa final outcomes đã resolve.
- Next step: xử lý discrepancy của `application_funnel.parquet` trong một task DE-LC-08 riêng; không sửa ngầm logic DE-LC-08 trong DE-LC-10.

## 2026-10-03 — Beginner Data Documentation Learning Path

- Task: tạo hai tài liệu học nhanh bằng tiếng Việt để giải thích workflow và quy tắc chọn dữ liệu cho người mới; trạng thái **PASS**.
- Files: `docs/data/DATA_WORKFLOW.md`, `docs/data/DATA_RULES.md`, `docs/overview/overview.md`, `logs/log_tv2.md`.
- `DATA_WORKFLOW.md` tóm tắt luồng RAW → cleaning → INTERIM → target/features → `cleaned_dataset.parquet` → safe columns → model, nhánh INTERIM → dimensions/marts → dashboard, ba lớp dữ liệu, nhóm business tables, DE-LC-01 đến DE-LC-10 và sự khác nhau giữa model với dashboard.
- `DATA_RULES.md` giải thích ba nhóm thông tin, `X`/`y`, target 0/1, leakage qua `recoveries`/`total_pymnt`, đường đi thực tế từ interim đến safe `X` và ví dụ cột được dùng hoặc loại bỏ. Tên policy kỹ thuật được đặt sau khái niệm đơn giản để người mới dễ học.
- `docs/overview/overview.md` có mục **Bắt đầu từ đây** trỏ tới hai tài liệu học nhanh và `docs/data/data_artifacts.md`.
- Không sửa code/data và giữ nguyên `docs/data/data_artifacts.md` cùng các tài liệu kỹ thuật/contracts hiện có.
- Kiểm tra: `git diff --check` — pending sau khi hoàn tất chỉnh sửa; chưa commit/push.
- Next step: review nội dung beginner docs và reconcile các status lịch sử trong log/stage reports nếu cần; không thay đổi technical history trong task này.

## 2026-10-03 — Finalize DE-LC-10 EDA and Fix DE-LC-08 Funnel Duplication

- Task: sửa duplication logic trong `application_funnel.parquet`, harden DE-LC-08 rerun/atomic outputs và hoàn thiện bộ static EDA; trạng thái **DE-LC-08 RUNTIME = PASS; DE-LC-10 RUNTIME = PASS**.
- Ownership: **TV2 = PRIMARY OWNER — Data Engineering**. **TV1 = Executor / Supporting Contributor**; agent thực hiện targeted implementation/test hardening dưới review của TV1.
- Root cause DE-LC-08: `row_ids` của rejected funnel được tạo với RangeIndex bắt đầu từ 0, trong khi các Series lấy từ pandas chunk giữ global chunk index. Khi dựng `DataFrame`, pandas union hai index khác nhau, làm các rejected chunk sau chunk đầu bị nở thành hai lần số dòng (và tạo null-aligned rows). Vì vậy `rejected_applications.parquet` vẫn đúng `27,648,741`, nhưng funnel cũ ghi `55,197,482` rejected rows.
- Fix DE-LC-08: tạo `row_ids` với `index=cleaned.index`, assert mỗi funnel table bảo toàn số dòng source, ghi `dim_date`, `dim_state` và funnel vào `*.partial.parquet`, validate decision counts/total, rồi atomic promote có rollback. Rerun bắt đầu từ partial sạch và không append vào canonical funnel cũ.
- Funnel trước: accepted `2,260,701`; rejected `55,197,482`; total `57,458,183`.
- Funnel sau: accepted `2,260,701`; rejected `27,648,741`; total `29,909,442`; decision counts khớp DE-LC-02; không còn partial output.
- DE-LC-10 refinement: giữ EDA-01 histogram loan amount và EDA-04 FICO × DTI heatmap; EDA-02 dùng nhãn trục `DTI (%)` với P99 display cap `38.35`; EDA-03 giữ FICO order và mask group < `100` bằng NA/Insufficient sample; EDA-05 đổi thành single-axis `Accepted Loan Volume Over Time` từ toàn bộ `loan_application.parquet`, không vẽ resolved-only default-rate trend.
- Files/code: `src/data/tv2_runner.py`, `tests/data/test_tv2_runner.py`, `tests/data/test_eda.py`, `docs/setup/tv2_setup.md`, `docs/tasks/thanh-vien-2-data-engineering.md`, `logs/log_tv2.md`.
- Reports/markers: `reports/tv2_stages/de-lc-08.md`, `reports/tv2_stages/state/de-lc-08.json`, `reports/tv2_stages/de-lc-10.md`, `reports/tv2_stages/state/de-lc-10.json`, `reports/eda_report.md`.
- Figures: `reports/figures/eda/eda_01_loan_amount_distribution.png`, `eda_02_dti_by_target.png`, `eda_03_default_by_fico.png`, `eda_04_fico_dti_heatmap.png`, `eda_05_accepted_loan_volume_over_time.png`; đúng 5 PNG và đều non-empty.
- Kiểm tra: focused DE-LC-08 + EDA — **20 passed**; regression `tests/data tests/features` — **70 passed**; real `python -m src.data.tv2_runner --stage de-lc-08` — **PASS**; funnel audit exact counts — **PASS**; real `python -m src.data.tv2_runner --stage de-lc-10` — **PASS**; `git diff --check` — pending sau log entry này.
- Method limitation: EDA-05 chỉ mô tả accepted volume; default rate theo origination time cố ý không đưa vào static chart vì canonical chỉ gồm resolved outcomes và các vintage gần đây có maturity/selection bias. Không thay đổi raw data, target policy hoặc canonical modeling dataset.
- Next step: TV3 có thể dùng funnel đã sửa và bộ 5 EDA mới; chưa commit/push.

## 2026-10-03 — Repository Cleanup and Documentation Consolidation

- Task: gom nhóm tài liệu, loại bỏ file cũ/cache và sửa các đường dẫn bị stale; không thay đổi logic pipeline hoặc dữ liệu nguồn.
- Giữ nguyên các bảng `data/interim/` vì mỗi file có grain và consumer riêng theo data contract; `target_audit.csv` là audit artifact, không phải bản trùng của business tables.
- Đã xóa các tài liệu reset/archive không còn là nguồn hiện hành: `docs/architecture/note.md` và ba log archive `logs/log_tv1_old.md`, `logs/log_tv2_old.md`, `logs/log_tv3_old.md`. Lịch sử vẫn có thể xem qua Git history.
- Đã xóa `.gitkeep` dư trong các thư mục đã có source/output thật: `notebooks/`, `src/dashboard/`, `src/data/`, `src/features/`, `src/models/`, `reports/figures/eda/`.
- Đã dọn các thư mục cache/test tạm không tracked: `.audit_tmp/`, `.pytest_cache/`, toàn bộ thư mục root `.pytest_tmp*`, và `__pycache__/` dưới `src/`/`tests/`.
- Đã cập nhật `docs/data/tv2_data_handoff.md` từ trạng thái NOT YET GENERATED sang bộ artifact thực tế đã tạo và gate PASS; sửa link `data_artifacts.md` trong README, overview, DATA_WORKFLOW và log hiện hành.
- Kiểm tra: `git diff --check` và kiểm tra link/path stale sau cleanup.
- Next step: review diff, stage từng nhóm đường dẫn cụ thể rồi commit/push theo quy trình branch; chưa commit/push trong task này.

## 2026-10-03 — Beginner EDA Presentation Guide

- Task: tạo tài liệu học nhanh bằng tiếng Việt cho năm biểu đồ EDA cuối cùng; trạng thái **PASS**.
- File: `reports/figures/eda/EDA_PRESENTATION_GUIDE.md`.
- Bổ sung ngay đầu tài liệu đường dẫn tới `reports/eda_report.md`; nội dung bám theo năm PNG hiện hành, P99 DTI = 38.35, minimum group/cell count = 100 và nguồn EDA-05 là toàn bộ accepted loans trong `loan_application.parquet`.
- Guide gồm câu hỏi business, lý do chọn chart, cách đọc trục/màu, insight có giới hạn, script thuyết trình, điểm cần cẩn thận, Q&A, thuật ngữ, memory sequence, câu không nên nói và cheat sheet.
- Không sửa chart, code, data hoặc report runtime.
- Kiểm tra: xác nhận đủ 5 PNG tồn tại; kiểm tra link tới `reports/eda_report.md`; `git diff --check` PASS.
- Next step: TV1/TV3 review guide khi chuẩn bị oral presentation; chưa commit/push.

## 2026-10-03 — Final End-to-end TV2 Handoff Audit

- Task: audit độc lập toàn bộ DE-LC-01 → DE-LC-10 trước TV1 Modeling; trạng thái cuối **TV2_HANDOFF_FAIL**.
- Ownership: **TV2 = PRIMARY OWNER — Data Engineering**. Audit này không chuyển ownership sang TV1; TV1 Modeling chưa được bắt đầu.
- Stage evidence: cả 10 marker hiện là `PASS`; canonical dataset, leakage gate, interim business tables, funnel và 5 EDA figures đều đạt independent runtime/artifact checks. DE-LC-09 bị đánh dấu **FAIL ở final audit** vì artifact handoff chưa đáp ứng đủ contract.
- Blocker 1: `data/processed/cleaned_dataset_manifest.json` thiếu accepted rows, rejected rows, unresolved rows và run status/provenance đầy đủ theo `docs/contracts/data_contract.md`; hiện chỉ ghi `accepted_labeled_rows` và quality/leakage status.
- Blocker 2: `reports/data_quality_report.md` ghi unresolved count là `None`, trong khi evidence DE-LC-02/07 và canonical audit xác nhận **915,351** unresolved accepted rows. Nguyên nhân được định vị tại `_stage_09` trong `src/data/tv2_runner.py`.
- Canonical evidence: `1,345,350` rows, `113` columns, `loan_id` unique/non-null, target `0 = 1,076,751`, target `1 = 268,599`, null target `0`, infinity `0`, baseline features `106`, forbidden baseline `[]`.
- Funnel evidence: accepted `2,260,701`, rejected `27,648,741`, total `29,909,442`; no `*.partial.parquet` remains and rerun/atomic promotion checks pass.
- Tests: `.venv\Scripts\python.exe -m pytest tests/data tests/features -q --basetemp D:\ttdltq\.pytest_tmp_final_audit` — **70 passed, 3 warnings**. `git diff --check` — **PASS**; Git chỉ báo line-ending warnings cho hai file đã có thay đổi trước đó.
- Files: `reports/tv2_final_handoff_audit.md`, `reports/tv2_final_handoff_audit.json`, `logs/log_tv2.md`.
- Next step/blocker: TV2 bổ sung row counts/provenance vào manifest, ghi unresolved `915,351` vào quality report, chạy lại DE-LC-09 rồi thực hiện final handoff audit lần nữa; **không commit, không push** trong task này.

## 2026-10-04 — Repair DE-LC-09 and Re-open TV2 Handoff Gate

- Task: sửa integrity của DE-LC-09 handoff artifacts sau final audit `TV2_HANDOFF_FAIL`; trạng thái cuối **TV2_HANDOFF_PASS**.
- Ownership: **TV2 = PRIMARY OWNER — Data Engineering**. **TV1 = Executor / Supporting Contributor / Cross-reviewer**; agent thực hiện targeted implementation/test hardening dưới review của TV1. TV1 Modeling không được tự động chạy trong task này.
- Root cause đã xác nhận từ audit trước: `_stage_09` ghi `excluded_unresolved_status_rows = None`; manifest chỉ có `accepted_labeled_rows`, thiếu accepted/rejected/labeled/unresolved counts, run/stage status và provenance.
- Repair: `_stage_09` derive accepted/rejected rows từ Parquet business-table metadata, tính `unresolved_rows = accepted_rows - labeled_rows`, ghi target counts, canonical/dictionary counts, baseline feature count, leakage status, artifact paths và provenance. `validate_handoff_manifest()` fail-closed khi thiếu field, count reconciliation sai, dictionary coverage không đủ, leakage/forbidden list hoặc status không PASS.
- Quality report sau repair: accepted `2,260,701`; rejected `27,648,741`; canonical labeled `1,345,350`; unresolved `915,351`; null/duplicate key `0 / 0`; infinity `0`; dictionary coverage `1.0`; `LEAKAGE GATE = PASS`.
- Focused tests: `.venv\Scripts\python.exe -m pytest tests/data/test_quality_report.py tests/data/test_tv2_runner.py tests/data/test_build_pipeline.py -q --basetemp D:\ttdltq\.pytest_tmp_de09_focused` — **31 passed, 4 warnings**.
- Regression tests: `.venv\Scripts\python.exe -m pytest tests/data tests/features -q --basetemp D:\ttdltq\.pytest_tmp_de09_regression` — **75 passed, 4 warnings**.
- Real runtime: `.venv\Scripts\python.exe -m src.data.tv2_runner --stage de-lc-09` — **PASS**; marker `reports/tv2_stages/state/de-lc-09.json` và report được cập nhật với manifest/quality evidence mới.
- Read-only canonical re-audit: `1,345,350` rows, `113` columns, unique/non-null `loan_id`, target `0 = 1,076,751`, target `1 = 268,599`, target null `0`, infinity `0`, baseline `106`, forbidden `[]`; funnel accepted `2,260,701`, rejected `27,648,741`, total `29,909,442`; không có partial output.
- Final audit outputs: `reports/tv2_final_handoff_audit.md` và `.json` đã cập nhật từ evidence hiện tại; **10/10 stage audit PASS**, final gate **TV2_HANDOFF_PASS**.
- Documentation: cập nhật `docs/data/tv2_data_handoff.md` với manifest counts/provenance và `docs/tasks/thanh-vien-2-data-engineering.md` để bỏ stale `Next step: DE-LC-01`; không rewrite các log lịch sử cũ.
- Kiểm tra: `git diff --check` — **PASS**; `compileall src tests` — **PASS**; Git chỉ báo line-ending warnings cho hai file đã có thay đổi trước đó. **Không commit, không push**.
- Next step: TV1 có thể bắt đầu Model Input Gate/Modeling sau khi review handoff; TV2 tiếp tục cross-review data semantics.
