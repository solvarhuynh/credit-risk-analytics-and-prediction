# TV2 Progress Log — Lending Club Dataset Reset

## Dataset Migration Reset — 2026-10-01

- Dataset cũ đã retired; Lending Club 2007–2018 được chọn.
- Lịch sử trước reset được archive tại `logs/log_tv2_old.md`.
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
