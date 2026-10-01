# TV1 Progress Log — Lending Club Dataset Reset

## Dataset Migration Reset — 2026-10-01

- Dataset cũ đã retired; Lending Club 2007–2018 được chọn.
- Lịch sử trước reset được archive tại `logs/log_tv1_old.md`.
- Chưa chạy lại pipeline hoặc mô hình.
- Trạng thái: **RESET / NOT YET EXECUTED**.
- Bước tiếp theo: **WAITING FOR TV2 LENDING CLUB CANONICAL HANDOFF**.

## 2026-10-01 — Dataset migration implementation

- Trạng thái: **MIGRATED / NOT YET RETRAINED**.
- Đã chuyển `src/models/`, model contract, setup/task TV1 và synthetic model tests sang `loan_id`/`target` với Logistic bắt buộc và feature gate fail-closed.
- Đã xóa model/report/metric sinh từ dataset trước reset; `models/` chỉ còn `.gitkeep`.
- Kiểm tra: compileall PASS; legacy/old-result active search không còn exact match; không chạy training hoặc data-dependent tests.
- Next step: chờ TV2 hoàn tất DE-LC-01 đến DE-LC-10 và bàn giao canonical artifacts.

## 2026-10-01 — Team responsibility reorganization

- Task: reorganize workload cho Lending Club; trạng thái **PLANNED / NOT YET IMPLEMENTED**.
- TV1 nhận primary: modeling + V01–V06 + Storytelling/Report/Defense coordination; TV1 không phải PBIX integration owner.
- Files: `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/tasks/dashboard-visual-plan.md`, `docs/tasks/report-writing-plan.md`, `docs/tasks/defense-knowledge-matrix.md`.
- Kiểm tra: sẽ xác nhận 6 visual, report reviewer và defense matrix sau khi docs hoàn tất; không chạy pipeline/model/dashboard.
- Next step: TV1 chuẩn bị visual specifications sau khi TV2 có usable schema.
