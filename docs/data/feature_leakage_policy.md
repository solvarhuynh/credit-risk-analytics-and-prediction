# Chính sách Feature Leakage — Lending Club

Mọi cột phải thuộc đúng một lớp trong `src/data/column_policy.py`:

- `IDENTIFIER`: chỉ định danh, không vào X.
- `APPLICATION_TIME`: có thể dùng nếu sẵn có lúc nộp/cấp vay.
- `CREDIT_SNAPSHOT`: có thể dùng khi semantics xác nhận snapshot tại origination.
- `POLICY_DERIVED`: pricing/grade/funded amount phản ánh quyết định lender; baseline loại mặc định.
- `GEOGRAPHY_ANALYTICS`: dùng Map/dashboard; baseline loại để giảm bias địa lý.
- `TEXT_HIGH_CARDINALITY`: loại khỏi baseline, có thể dùng analytics.
- `TARGET_SOURCE`: chỉ để derive target.
- `POST_LOAN`: tuyệt đối không làm model feature.
- `ANALYTICS_ONLY`: chỉ phục vụ báo cáo.
- `UNKNOWN_REVIEW_REQUIRED`: fail-closed, chặn model handoff.

Post-loan tối thiểu gồm `out_prncp*`, `total_pymnt*`, `total_rec_*`, `recoveries`, `collection_recovery_fee`, `last_pymnt_*`, `next_pymnt_*`, `last_credit_pull_*`, `last_fico_*`, `hardship_*`, `debt_settlement_*`, `settlement_*`.

Các cột raw vẫn được giữ nguyên để audit và phân tích lịch sử. Chúng bị tách ở layer nghiệp vụ/model, không bị xóa khỏi nguồn.

Policy-derived gồm tối thiểu `grade`, `sub_grade`, `int_rate`, `funded_amnt`, `funded_amnt_inv`, `installment`: có quanh origination nhưng mã hóa policy/underwriting của Lending Club.
