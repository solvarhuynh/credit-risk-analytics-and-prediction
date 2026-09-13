# Log công việc — TV1 (Modeling)

Chỉ append entry mới theo quy trình trong docs/tasks/working-protocol.md.

## 2026-09-13 — TV1-SEC-DE — Secondary Data Engineering review

- **Trạng thái:** blocked
- **Đã làm:**
  - Review schema/grain/cardinality và nguyên tắc aggregate-before-join cho các bảng application và history.
  - Review calculated fields contract và shortlist feature application/history phục vụ Modeling.
  - Chạy pre-training quality-gate review ở mức static; canonical model input chưa sẵn sàng.
  - Chốt nguyên tắc leakage: historical feature phải có source/formula/as-of-time; preprocessing statistic chỉ fit trên train fold.
- **File thay đổi:** `docs/logs/log_tv1.md`
- **Kiểm tra:** đối chiếu `data_contract.md`, task TV1/TV2 và trạng thái pipeline/canonical artifacts.
- **Blocker:** TV2 chưa bàn giao `data/processed/cleaned_dataset.parquet` và `data/processed/data_dictionary.csv` cùng join/quality audit.
- **Next step:** Chờ TV2 hoàn thành canonical Data Engineering handoff, sau đó chạy lại Join Review + Feature Review + Model Input Quality Gate trước khi Modeling.
