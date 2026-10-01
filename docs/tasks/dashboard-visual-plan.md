# Dashboard Visual Plan — Lending Club

Trạng thái toàn bộ: **PLANNED / WAITING FOR DATA**. Đây là specification để TV3 tích hợp Master PBIX; chưa viết DAX, chưa tạo visual và chưa đưa ra insight thực tế.

| ID / Visual | Primary | Reviewer | Page / chart | Business question; source; fields/measures | Filter / drill-down / tooltip | Candidate insight cần kiểm chứng; limitation | Status |
|---|---|---|---|---|---|---|---|
| V01 Geographic Risk Map | TV1 | TV3 | P3 / Map | Rủi ro phân bố theo bang? accepted canonical + `dim_state`; `state_code`, `country`, `target`, `predicted_pd` | Year/grade-independent filters; Year→Quarter→Month; state, loan count, default rate, PD | Có bang/cụm bang rủi ro cao hơn? Chỉ association; state-level không phải causal và không dùng ZIP masked | PLANNED / WAITING FOR DATA |
| V02 PD Distribution | TV1 | TV3 | P4 / Histogram/column | PD model phân bố thế nào? scored data; `predicted_pd`, risk bins | Model version, threshold, purpose; risk bin; loan_id, PD, target tooltip | Có đuôi PD cao cần review? Phụ thuộc model artifact và calibration | PLANNED / WAITING FOR DATA |
| V03 Risk Tier Distribution | TV1 | TV3 | P4 / Column/donut | Quy mô từng risk tier? scored data; `risk_tier`, count, share, default rate | threshold/model filters; tier; tier, PD range, count | Tier cao có default rate cao hơn không? Tier phải do TV1 định nghĩa | PLANNED / WAITING FOR DATA |
| V04 FICO vs Risk/PD | TV1 | TV3 | P4 / Scatter | FICO liên hệ thế nào với PD? canonical/scored; `fico_avg`, `predicted_pd`, `target`, loan amount | purpose, state, term; FICO band; loan_id, income, DTI, PD | FICO thấp có PD cao hơn không? Không kết luận nhân quả | PLANNED / WAITING FOR DATA |
| V05 Feature Importance / SHAP | TV1 | TV3 | P5 / Bar | Model dựa vào biến nào? TV1 explanation output; feature, importance/SHAP | model version, population; feature group; feature, direction, caveat | Feature ảnh hưởng dự đoán ra sao? SHAP là explanation, không phải causal effect | PLANNED / WAITING FOR DATA |
| V06 Expected Loss / Risk Contribution | TV1 | TV3 | P5 / Waterfall/bar | Rủi ro tiềm năng đóng góp bao nhiêu? scored + approved LGD/EAD; `expected_loss`, amount, tier | state/purpose/tier; portfolio→segment; loan/tier, PD, LGD/EAD assumptions | Segment nào đóng góp EL lớn? LGD/EAD là assumption nếu chưa observed | PLANNED / WAITING FOR DATA |
| V07 Loan Volume & Default Rate over Time | TV2 | TV1 | P3 / Line/combo | Danh mục và default thay đổi theo thời gian? canonical + `dim_date`; loan count, loan amount, default rate | state/purpose; Year→Quarter→Month; period, count, amount, rate | Trend/seasonality nào cần kiểm tra? Không suy ra nguyên nhân từ trend | PLANNED / WAITING FOR DATA |
| V08 Accepted vs Rejected Applications | TV2 | TV1 | P2 / Funnel | Funnel accepted/rejected ra sao? accepted + rejected funnel mart; decision, count, amount | date/state/purpose; Year→Quarter→Month; decision, amount, count | Nhu cầu và acceptance chênh lệch thế nào? Schema/date comparability phải được TV2 xác nhận | PLANNED / WAITING FOR DATA |
| V09 Loan Purpose Analysis | TV2 | TV1 | P2 / Treemap/bar | Purpose nào chiếm volume/risk? accepted canonical; `purpose`, count, amount, default rate | state/date/term; purpose; purpose, count, amount, rate | Purpose có volume/rate nổi bật? Nhóm nhỏ dễ dao động và không chứng minh causal | PLANNED / WAITING FOR DATA |
| V10 Loan Amount vs Annual Income | TV3 | TV1 | P2 / Scatter/bubble | Khoản vay và thu nhập phân bố thế nào? borrower/application; `loan_amnt`, `annual_inc`, size=count, color=purpose | state/purpose/target; income/amount band; loan, income, purpose, target | Segment amount/income nào đáng chú ý? Outlier và missing income cần nêu rõ | PLANNED / WAITING FOR DATA |
| V11 DTI/FICO Risk Matrix | TV3 | TV2 | P4 / Heatmap | DTI/FICO bands có pattern risk nào? canonical/scored; DTI band × FICO band, default/PD | state/purpose/time; FICO→DTI band; bands, count, rate, PD | Ô nào có rate cao? Bins cố định, sparse cells cần cảnh báo | PLANNED / WAITING FOR DATA |
| V12 Borrower Segment Composition | TV3 | TV2 | P2 / Donut/100% stacked | Thành phần home ownership/employment/verification ra sao? borrower; segment, count/share | state/purpose/issue period; ownership→verification; segment, count, income | Composition khác nhau theo segment? Không đại diện cho population ngoài dataset | PLANNED / WAITING FOR DATA |

## Definition of Done cho mọi visual

Visual chỉ được đánh dấu DONE khi có đủ business question, source table, required fields, calculated measure, chart type, filters, interaction, tooltip, owner, reviewer, candidate insight và limitation. Owner viết theo mẫu `OBSERVATION → WHAT IT MEANS → WHY IT MATTERS → POSSIBLE EXPLANATION → LIMITATION → BUSINESS FOLLOW-UP`; TV1 hợp nhất thành storytelling cuối.

## Integration policy

TV1/TV2 gửi specification hoặc prototype local; TV3 tích hợp vào đúng một Master PBIX. Không chỉnh PBIX đồng thời. Mọi insight là candidate cho tới khi dữ liệu đã được tạo và reviewer sign-off.
