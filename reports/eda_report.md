# Static EDA — Lending Club

## Output summary

Canonical source: `D:\ttdltq\data\processed\cleaned_dataset.parquet`. EDA-01 và EDA-02 dùng deterministic plotting sample tối đa `200,000` rows; EDA-03 và EDA-04 dùng aggregated metrics từ toàn bộ canonical labeled dataset theo chunk. EDA-05 dùng toàn bộ accepted loans từ `D:\ttdltq\data\interim\loan_application.parquet` theo chunk.

## Visual reasoning

### EDA-01 — Loan Amount Distribution (Histogram)
- BUSINESS QUESTION: Khoản vay tập trung ở những khoảng giá trị nào?
- WHY THIS VISUAL: Histogram phù hợp để xem phân bố và vùng loan amount phổ biến.
- INSIGHT: Candidate insight — kiểm tra vùng tập trung và độ lệch của loan amount; không suy ra nguyên nhân.
- STORY CONNECTION: Overview → portfolio composition → risk segmentation.

### EDA-02 — DTI by Target (Boxplot)
- BUSINESS QUESTION: Phân bố DTI của non-default và default khác nhau thế nào?
- WHY THIS VISUAL: Boxplot so sánh median, spread và outlier pattern giữa hai target group.
- INSIGHT: Candidate insight — kiểm tra association giữa DTI và observed target; không diễn giải thành causation.
- NOTE: Trục y dùng `DTI (%)`; display limited to valid DTI values up to P99 = 38.35 for readability; source values không đổi.
- STORY CONNECTION: Portfolio overview → borrower/credit segmentation → risk.

### EDA-03 — Default Rate by FICO Band (Bar chart)
- BUSINESS QUESTION: Observed default rate thay đổi thế nào theo FICO band?
- WHY THIS VISUAL: Bar chart giữ thứ tự FICO logic và cho phép so sánh rate giữa các band.
- INSIGHT: Candidate insight — kiểm tra association giữa FICO band và observed default rate; count được ghi trên chart.
- LIMITATION: FICO group có n < 100 được giữ category nhưng hiển thị NA/insufficient sample, không vẽ numerical rate.
- STORY CONNECTION: Credit segmentation → risk comparison → model feature context.

### EDA-04 — FICO × DTI Risk Matrix (Heatmap)
- BUSINESS QUESTION: Các tổ hợp FICO band và DTI band có observed default rate như thế nào?
- WHY THIS VISUAL: Heatmap cho thấy pattern hai chiều mà từng biểu đồ một chiều có thể bỏ sót.
- INSIGHT: Candidate insight — kiểm tra joint association; ô dưới minimum count được để trống để tránh diễn giải sparse cell.
- STORY CONNECTION: Segmentation → risk matrix → candidate dashboard drill-down.

### EDA-05 — Accepted Loan Volume Over Time (Line chart)
- BUSINESS QUESTION: Số khoản vay accepted/issued thay đổi theo tháng như thế nào?
- SOURCE / AGGREGATION: Toàn bộ accepted loans từ `loan_application.parquet`, group theo `issue_d` year-month, đếm accepted loan.
- WHY THIS VISUAL: Line chart thể hiện thứ tự thời gian và volume theo một trục y đơn giản.
- INSIGHT: Candidate insight — kiểm tra pattern volume theo thời gian; không suy ra nguyên nhân từ trend.
- LIMITATION: Đây chỉ là volume accepted; figure không vẽ default rate vì canonical labeled chỉ chứa resolved outcomes.
- STORY CONNECTION: Overview → temporal portfolio context → downstream risk analysis.

## Technical limits and audit

- DTI y-axis: `DTI (%)`; P99 visualization cap = `38.35`.
- FICO minimum group count: `100`; heatmap minimum cell count: `100`.
- FICO counts by band: `{"<650": 2, "650-699": 820825, "700-749": 417917, "750+": 106606}`.
- Accepted-volume aggregation: `2007-06` → `2018-12` from all rows in `loan_application.parquet`; it does not use resolved-only canonical rows.
- Default rate over origination time was intentionally not included in the canonical static time-series figure because the labeled canonical dataset contains only resolved outcomes; recent vintages have incomplete outcome resolution and would create maturity/selection bias.
- Funnel audit: `{"status": "PASS", "expected_raw_rows": {"accepted": 2260701, "rejected": 27648741}, "actual_funnel_rows": {"accepted": 2260701, "rejected": 27648741}, "difference": {"accepted": 0, "rejected": 0}, "note": "Funnel counts khớp DE-LC-02."}`.

## Canonical figures

- `D:\ttdltq\reports\figures\eda\eda_01_loan_amount_distribution.png`
- `D:\ttdltq\reports\figures\eda\eda_02_dti_by_target.png`
- `D:\ttdltq\reports\figures\eda\eda_03_default_by_fico.png`
- `D:\ttdltq\reports\figures\eda\eda_04_fico_dti_heatmap.png`
- `D:\ttdltq\reports\figures\eda\eda_05_accepted_loan_volume_over_time.png`
