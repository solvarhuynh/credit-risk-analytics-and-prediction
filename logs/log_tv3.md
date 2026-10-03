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

## 2026-10-01 — Team responsibility reorganization

- Task: reorganize workload cho Lending Club; trạng thái **PLANNED / NOT YET IMPLEMENTED**.
- TV3 giữ primary Master Power BI integration, nhận V10–V12 và dashboard report/demo; tích hợp V01–V09 từ các owner khác.
- Files: `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/thanh-vien-3-dashboard.md`, `docs/tasks/dashboard-visual-plan.md`, `docs/tasks/report-writing-plan.md`, `docs/tasks/defense-knowledge-matrix.md`.
- Kiểm tra: PBIX single integration owner và 5-page plan được ghi rõ; chưa build dashboard/DAX.
- Next step: review visual specifications khi TV2 bàn giao usable schema.
