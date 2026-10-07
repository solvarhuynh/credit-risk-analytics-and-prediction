# TV1 — Modeling, Analytics và Coordination Roadmap

TV1 có workload lớn nhất theo phân công hiện tại. Điều kiện bắt đầu modeling vẫn là TV2 canonical handoff và `LEAKAGE GATE = PASS`.

## PRIMARY MODELING

| Stage | Input | Output | Definition of Done |
|---|---|---|---|
| ML-LC-01 Model Input Gate | Canonical + dictionary + manifest | Approved feature schema | Key/target/dictionary hợp lệ; không post-loan, policy, geo, unknown |
| ML-LC-02 Freeze split | Labeled accepted loans | Train/validation/frozen test IDs | Stratified, deterministic, không overlap |
| ML-LC-03 Logistic baseline | Development set | Logistic result | Logistic được báo cáo như model bắt buộc |
| ML-LC-04 Imbalance experiment | Logistic pipeline | Weighted/resampling comparison | Chỉ dùng development; metric phù hợp imbalance |
| ML-LC-05 Optional XGBoost | Same frozen split | Advanced candidate | Không thay thế Logistic |
| ML-LC-06 Model comparison | Validation/CV results | Locked candidate | Tiêu chí chọn được ghi trước, không nhìn frozen test |
| ML-LC-07 Threshold selection | OOF/validation PD | Decision threshold | Theo trade-off/business cost, không dùng test |
| ML-LC-08 Frozen test | Locked model/threshold | Final evaluation record | Đánh giá một lần, audit được |
| ML-LC-09 Explainability | Locked model | Global/local explanation | Không diễn giải leakage feature |
| ML-LC-10 Scoring | Predicted PD | Score/risk tier | Mapping và range được kiểm tra |
| ML-LC-11 Expected Loss | PD + approved LGD/EAD assumptions | EL analysis | Assumption minh bạch, không gọi là observed fact |
| ML-LC-12 Full-data refit | Locked config + labeled set | Full-refit demo/inference pipeline | Không thay hyperparameter/threshold sau test; không gán test metrics cho refit |
| ML-LC-13 TV3 handoff audit | Existing model/scoring artifacts + contract | Handoff audit evidence | Chỉ tạo phần còn thiếu; không trùng artifacts hoặc tuyên bố dashboard hoàn tất |

## Data Engineering Support / Cross-review

TV1 hỗ trợ TV2 ở các phần Data Engineering liên quan trực tiếp tới modeling:

- hiểu raw schema và business meaning của các field quan trọng;
- review target derivation;
- review leakage classification;
- review application-time/model-safe features;
- review calculated features phục vụ model;
- kiểm tra quality/leakage gate trước Model Input Gate;
- verify TV2 → TV1 handoff: `cleaned_dataset.parquet`, `data_dictionary.csv`, `cleaned_dataset_manifest.json`.

TV1 is **NOT the primary owner of Data Engineering**. TV2 remains the **PRIMARY OWNER** responsible for cleaning, normalization, joins, canonical dataset generation, dictionary, manifest, quality report and technical EDA pipeline. TV1's role is **SUPPORTING CONTRIBUTOR / CROSS-REVIEWER**.

## DASHBOARD VISUALS V02–V06 — PRIMARY

TV1 chuẩn bị visual specification, required fields, measures, interpretation và prototype nếu cần cho V02–V06. V01 Geographic Risk Map thuộc TV3; TV1 chỉ cross-review khi cần. TV3 tích hợp mọi visual vào Master PBIX và là reviewer cho nhóm V02–V06.

- V02 PD Distribution.
- V03 Risk Tier Distribution.
- V04 FICO vs Risk/PD.
- V05 Model Feature Importance / SHAP.
- V06 Expected Loss / Risk Contribution.

Mỗi visual phải có business question, source table, fields, measure, filter, interaction, tooltip, candidate insight và limitation. V05 đã có explainability source artifacts sau ML-LC-09; Power BI visual vẫn chờ TV3 tích hợp.

## STORYTELLING LEAD

TV1 kết hợp insight từ cả ba thành viên thành narrative: credit-risk problem → dataset/application flow → borrower risk → prediction/generalization → explainability → Expected Loss → individual prediction → limitations. Dashboard page story và V01–V12 visual families đã LOCKED trong `docs/tasks/dashboard-visual-plan.md`; TV1 giữ ownership V02–V06, không đổi chart selection hoặc workload ở phase data-model này. TV1 kiểm tra câu chữ không biến association thành causation và chuẩn bị executive summary.

## REPORT COORDINATOR

TV1 điều phối cấu trúc và consistency của full project report theo `docs/tasks/report-writing-plan.md`; primary author cho problem framing, modeling, prediction, evaluation, Storytelling, Expected Loss và conclusions. Báo cáo không phải dashboard-only. TV3 cross-review dashboard consistency; TV2 review data claims khi cần.

## DEFENSE COORDINATOR

TV1 tạo shared question bank, kiểm tra rehearsal và bảo đảm ba thành viên giải thích được flow, preprocessing, dashboard calculations và limitations. TV1 không độc quyền kiến thức: TV2 đi sâu data, TV3 đi sâu Power BI.

## CROSS-REVIEW TASKS

- Review TV2 processed-data handoff, V07–V09 và data/EDA report sections.
- Review TV3 dashboard structure, V10–V12, interaction và final report consistency.
- Đọc toàn bộ defense matrix trước khi sign-off.

Trạng thái hiện tại: **ML-LC-01 đến ML-LC-13 PASS**; ML-LC-13 PASS là handoff audit thỏa bằng artifacts hiện có, không có nghĩa Power BI đã hoàn thành. `xgboost_candidate` là model được đánh giá ở ML-LC-08; threshold `0.22009515762329102` được chọn trên validation. ML-LC-12 tạo model refit riêng trên 1,345,350 labeled rows và in-sample demo scores; không mang metrics frozen-test sang refit. Không chọn model/threshold lại. Dashboard integration và review Master PBIX vẫn thuộc TV3. Bản tổng hợp modeling: `reports/tv1_stages/modeling_summary.md`.
