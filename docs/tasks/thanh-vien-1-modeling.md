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
| ML-LC-12 Full-data refit | Locked config + labeled set | Production pipeline | Không thay hyperparameter/threshold sau test |
| ML-LC-13 TV3 handoff | Model + scored data + contract | Integration package | Schema/model version và validation cases có thật |

## DASHBOARD VISUALS V01–V06 — PRIMARY

TV1 chuẩn bị visual specification, required fields, measures, interpretation và prototype nếu cần. TV3 tích hợp vào Master PBIX; TV3 là reviewer cho nhóm này.

- V01 Geographic Risk Map.
- V02 PD Distribution.
- V03 Risk Tier Distribution.
- V04 FICO vs Risk/PD.
- V05 Model Feature Importance / SHAP.
- V06 Expected Loss / Risk Contribution.

Mỗi visual phải có business question, source table, fields, measure, filter, interaction, tooltip, candidate insight và limitation. Status hiện tại: `PLANNED / WAITING FOR DATA`.

## STORYTELLING LEAD

TV1 kết hợp insight từ cả ba thành viên thành narrative: applicant → decision/funnel → temporal/geographic portfolio → borrower risk → PD/prediction → explanation → Expected Loss. TV1 kiểm tra các câu chữ không biến correlation thành causation và chuẩn bị executive summary.

## REPORT COORDINATOR

TV1 điều phối cấu trúc và consistency của scientific report tối thiểu 40 trang; primary author cho problem framing, modeling, prediction, evaluation, geographic interpretation, Storytelling, Expected Loss và conclusions. TV3 cross-review readability/dashboard consistency; TV2 review data claims khi cần.

## DEFENSE COORDINATOR

TV1 tạo shared question bank, kiểm tra rehearsal và bảo đảm ba thành viên giải thích được flow, preprocessing, dashboard calculations và limitations. TV1 không độc quyền kiến thức: TV2 đi sâu data, TV3 đi sâu Power BI.

## CROSS-REVIEW TASKS

- Review TV2 processed-data handoff, V07–V09 và data/EDA report sections.
- Review TV3 dashboard structure, V10–V12, interaction và final report consistency.
- Đọc toàn bộ defense matrix trước khi sign-off.

Trạng thái: **PLANNED / WAITING FOR TV2 LENDING CLUB HANDOFF**. Không train hoặc tạo model artifact trong task phân công này.
