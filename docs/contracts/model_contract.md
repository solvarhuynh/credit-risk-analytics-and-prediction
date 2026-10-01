# Model Contract — Lending Club

Trạng thái: **CURRENT = NOT YET TRAINED ON LENDING CLUB**.

TV1 chỉ nhận `cleaned_dataset.parquet`, dictionary và manifest khi TV2 quality/leakage gate PASS. `X` chỉ gồm cột đã duyệt thuộc `APPLICATION_TIME` hoặc `CREDIT_SNAPSHOT`; loại `loan_id`, `target`, `loan_status`, geography, policy-derived, post-loan, text cardinality cao và unknown.

Logistic Regression là baseline bắt buộc. XGBoost là so sánh tùy chọn và không thay thế yêu cầu Logistic. Split cố định, threshold chọn bằng development/validation; frozen test chỉ đánh giá cuối.

Output TV3 tương lai tối thiểu: `loan_id`, `target`, `predicted_pd`, `decision_threshold`, `recommendation`, `model_version`. Có thể bổ sung `state_code`, `issue_year`, `loan_amnt`, `annual_inc`, `fico_avg`, `dti`, `purpose`, `credit_score`, `risk_tier`, `expected_loss` cho dashboard.

Khi chưa có artifact thật, simulator phải trả trạng thái `BLOCKED / WAITING FOR TV1 ARTIFACT`; không suy luận giả.
