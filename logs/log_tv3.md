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

## 2026-10-01 — Team responsibility reorganization

- Task: reorganize workload cho Lending Club; trạng thái **PLANNED / NOT YET IMPLEMENTED**.
- TV3 giữ primary Master Power BI integration, nhận V10–V12 và dashboard report/demo; tích hợp V01–V09 từ các owner khác.
- Files: `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/thanh-vien-3-dashboard.md`, `docs/tasks/dashboard-visual-plan.md`, `docs/tasks/report-writing-plan.md`, `docs/tasks/defense-knowledge-matrix.md`.
- Kiểm tra: PBIX single integration owner và 5-page plan được ghi rõ; chưa build dashboard/DAX.
- Next step: review visual specifications khi TV2 bàn giao usable schema.
