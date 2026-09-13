# TV3 — Dashboard setup & refresh guide

Owner: TV3 (Power BI Dashboard)

## Trạng thái hiện tại

Dashboard Power BI (`dashboard/Credit_Risk_Analytics.pbix`) và canonical scored
dataset chưa được bàn giao. Do đó chưa có file `.pbix` hoặc lệnh refresh tự động
để chạy trong repository.

## Chuẩn bị

1. Cài Power BI Desktop.
2. Nhận từ TV2 `data/processed/cleaned_dataset.parquet`.
3. Nhận từ TV1 `data/processed/scored_dataset.parquet` và model handoff.

## Refresh khi đã có dữ liệu

1. Mở `dashboard/Credit_Risk_Analytics.pbix`.
2. Cập nhật Power Query source tới các file Parquet trong `data/processed/`.
3. Chọn **Refresh**, kiểm tra row count, khóa `SK_ID_CURR` và các measure chính.
4. Kiểm tra filter, drill-down, tooltip, cross-filtering và What-if Simulator.

Lệnh refresh bằng Python: `PENDING` — Power BI là consumer desktop; chỉ thêm
lệnh khi nhóm thống nhất công cụ tự động hóa và đã kiểm tra trên máy demo.

## Validation / giới hạn

Không gán ngẫu nhiên khách hàng vào địa lý. Nếu dùng region rating thay bản đồ,
phải ghi rõ giới hạn theo `docs/architecture/decisions-and-risks.md`.
