# Thiết lập TV1 — Lending Club Modeling

Trạng thái modeling: **ML-LC-01 đến ML-LC-13 PASS**. ML-LC-12 tạo model full-refit 103-input; model này vẫn là model chính. Dash demo đang dùng hai artifact phụ **6-input** (`xgboost_6input_demo.joblib`, `logistic_6input_demo.joblib`) theo quyết định validation-only; frozen test của hai candidate này **chưa được đánh giá**. Hai artifact 5-input và kết quả one-shot cũ chỉ còn là baseline lịch sử, không phải bản đang chạy. Frozen-test metrics gốc ML-LC-08 của `xgboost_candidate` giữ nguyên. Threshold `0.22009515762329102` được carry sang refit/demo, không retune. Power BI và Dash là hai ứng dụng khác nhau; Power BI do TV3 tích hợp.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Ý nghĩa: tạo môi trường Python độc lập, kích hoạt và cài dependency.

```powershell
Get-Item data/processed/cleaned_dataset.parquet,data/processed/data_dictionary.csv,data/processed/cleaned_dataset_manifest.json
```

Ý nghĩa: xác nhận đủ ba artifact TV2. Nếu thiếu thì dừng, không train.

```powershell
python -c "from src.models.modeling_pipeline import load_canonical_input,build_feature_schema; d,dd,m=load_canonical_input(); print(build_feature_schema(d,dd)); print(m)"
```

Ý nghĩa: chạy model input gate, kiểm tra dictionary coverage và chỉ chọn feature `APPLICATION_TIME`/`CREDIT_SNAPSHOT`.

```powershell
.venv\Scripts\python.exe -m pytest tests/models -q
```

Ý nghĩa: chạy focused/regression tests cho split, preprocessing, modeling, evaluation và runner. Baseline trước ML-LC-08 từng có 70 passed; kết quả mới nhất sau ML-LC-12/13 là **105 passed** (đã kiểm tra trong task closeout).

## ML-LC-03 — Logistic Regression baseline

Prerequisite: ba artifact TV2 (`cleaned_dataset.parquet`, `data_dictionary.csv`, `cleaned_dataset_manifest.json`) phải đạt PASS; frozen split ML-LC-02 phải tồn tại và đạt PASS.

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-03
```

Ý nghĩa: kiểm tra các gate đầu vào, lấy đúng train/validation từ frozen split, fit preprocessing và Logistic Regression chỉ trên train, đánh giá chỉ trên validation, rồi ghi baseline artifacts/report. Frozen test chỉ được kiểm tra membership, không tạo prediction/metric.

Input chính:

- `data/processed/cleaned_dataset.parquet`
- `data/processed/data_dictionary.csv`
- `data/processed/cleaned_dataset_manifest.json`
- `data/processed/modeling/{train_ids,validation_ids,test_ids}.parquet`
- `data/processed/modeling/split_manifest.json`

Output chính:

- `data/processed/modeling/logistic_baseline.joblib`
- `data/processed/modeling/ml_lc_03_validation_predictions.parquet`
- `data/processed/modeling/ml_lc_03_feature_audit.csv`
- `data/processed/modeling/ml_lc_03_manifest.json`
- `reports/tv1_stages/ml-lc-03.md`
- `reports/tv1_stages/state/ml-lc-03.json`

Validation bổ sung đã chạy:

```powershell
.venv\Scripts\python.exe -m pytest tests/data tests/features -q
.venv\Scripts\python.exe -m compileall -q src tests
git diff --check
```

Kết quả: `75 passed, 4 warnings` ở data/features; compileall PASS; diff check PASS. Warning là cảnh báo date parsing đã tồn tại ở test TV2, không làm test fail.

Giới hạn ML-LC-03: đây là untreated Logistic baseline với `class_weight=None`; chưa threshold optimization, chưa XGBoost, chưa explainability/scoring và chưa đánh giá frozen test. Threshold `0.5` chỉ là reference; ML-LC-07 mới chọn threshold cuối.

## ML-LC-04 — Logistic Regression imbalance experiment

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-04
```

Ý nghĩa: xác nhận ML-LC-03 PASS, giữ nguyên frozen train/validation và 103 feature thực tế, fit một Logistic Regression thứ hai với `class_weight="balanced"` chỉ trên train, rồi so sánh với baseline tại threshold tham chiếu `0.5` trên validation. Không chạy threshold search, không dùng frozen test để predict/metric/selection và không dùng resampling.

Output chính:

- `data/processed/modeling/logistic_weighted.joblib`
- `data/processed/modeling/ml_lc_04_weighted_validation_predictions.parquet`
- `data/processed/modeling/ml_lc_04_manifest.json`
- `reports/tv1_stages/ml-lc-04.md`
- `reports/tv1_stages/state/ml-lc-04.json`

Kết quả đã kiểm tra: weighted Logistic hội tụ; recall validation tăng nhưng false positives tăng mạnh và precision giảm. Đây là experiment, chưa khóa model cuối; ML-LC-06 mới thực hiện candidate selection.

## ML-LC-05 — XGBoost candidate

Đã huấn luyện đúng một XGBoost candidate trên cùng frozen train/validation split. Candidate dùng 103 feature đầu vào thực tế và tạo 151 feature sau preprocessing; tại thời điểm ML-LC-05, frozen test vẫn sealed và không được dùng để train, predict, evaluate hoặc select. Kết quả validation tại threshold tham chiếu `0.5`: ROC-AUC `0.724501`, PR-AUC `0.399256`, precision `0.598674`, recall `0.075614`, F1 `0.134270`, accuracy `0.805326`; confusion matrix `[[212627, 2723], [49658, 4062]]`. Tại stage này chưa chọn threshold và chưa chọn model cuối. Chi tiết tại `reports/tv1_stages/ml-lc-05.md` và `data/processed/modeling/ml_lc_05_manifest.json`.

## ML-LC-06 — So sánh model và khóa candidate

Prerequisite: ML-LC-02 đến ML-LC-05 đều PASS; có `split_manifest.json`, `validation_ids.parquet`, ba model artifacts, ba validation prediction files và các manifest/marker tương ứng trong `data/processed/modeling/` và `reports/tv1_stages/state/`.

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-06
```

Ý nghĩa: đối chiếu ba validation prediction files với frozen validation IDs/target, tính lại ROC-AUC, PR-AUC, Log Loss, Brier và các metrics tại ngưỡng tham chiếu `0.5`, so sánh theo quy tắc đã ghi trong `docs/contracts/model_contract.md`, rồi khóa đúng một candidate. Lệnh chỉ đọc metadata tồn tại của frozen test; không train lại model hoặc dự đoán trên test.

Output: `data/processed/modeling/ml_lc_06_manifest.json`, `reports/tv1_stages/ml-lc-06.md`, `reports/tv1_stages/state/ml-lc-06.json`. Manifest trỏ đến model/predictions đã có, không tạo bản sao model.

Validation đã chạy: focused tests `19 passed`, `tests/models` `65 passed`, `tests/data tests/features` `75 passed` (4 warning date parsing TV2), `compileall src tests` PASS, `git diff --check` PASS và runner ML-LC-06 PASS. Kết quả khóa: `xgboost_candidate`. Đây chỉ là candidate cho ML-LC-07; chưa chọn threshold, chưa có final model hay frozen-test metrics.

Workflow tiếp theo: ML-LC-07 chọn threshold trên validation → frozen test một lần → explainability/scoring/expected loss → full-data refit → TV3 handoff. Không dùng frozen test trước stage đánh giá cuối.

## ML-LC-07 — Chọn threshold trên validation

Prerequisite: ML-LC-06 PASS và khóa `xgboost_candidate`; prediction validation và validation IDs phải đủ, cùng population/target.

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-07
```

Ý nghĩa: dùng duy nhất `ml_lc_05_xgboost_validation_predictions.parquet`, tìm chính xác trên các score phân biệt để tối đa F1. F1 hòa trong `1e-12` được phân xử theo recall cao hơn, precision cao hơn, rồi threshold cao hơn. Lệnh không fit/retrain model và không đọc frozen test.

Output: `data/processed/modeling/ml_lc_07_threshold_table.csv` (toàn bộ thresholds đã xét và các mốc chẩn đoán), `data/processed/modeling/ml_lc_07_manifest.json`, `reports/tv1_stages/ml-lc-07.md`, `reports/tv1_stages/state/ml-lc-07.json`.

Runtime đã PASS trên `269,070` validation rows. Threshold được chọn: `0.2200951576`; F1 `0.439981`, precision `0.346453`, recall `0.602681`, accuracy `0.693693`. Tại ngưỡng tham chiếu `0.5`, F1 `0.134270`; frozen test vẫn sealed ở thời điểm ML-LC-07. Đây là operating threshold thống kê theo validation F1, không phải tối ưu Expected Loss/lợi nhuận/chi phí kinh doanh và chưa phải quyết định cuối.

Validation tại thời điểm ML-LC-07: focused `32 passed`, `tests/models` `70 passed`, `tests/data tests/features` `75 passed` (4 cảnh báo date parsing TV2), `compileall src tests` PASS, `git diff --check` PASS. Khi đó bước tiếp theo ML-LC-08; frozen test chưa được đánh giá trong stage đó. Trạng thái tổng thể hiện nay ở phần đầu guide.

## ML-LC-08 — Đánh giá frozen test đúng một lần

Prerequisite: ML-LC-06/07 PASS; candidate `xgboost_candidate` và threshold `0.22009515762329102` đã khóa, ba partition IDs, split manifest, TV2 canonical/dictionary/manifest và model fitted phải có đủ. Trước khi chạy test thật, phải chạy focused/model/data-feature tests, compileall và `git diff --check` thành công.

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-08
```

Ý nghĩa: kiểm tra khóa, membership/target và không overlap; lấy đúng 269,070 test rows theo thứ tự `test_ids.parquet`, dùng pipeline đã fit để `predict_proba`, áp dụng ngưỡng khóa và ghi metrics. Không fit, tìm threshold, so sánh model hoặc chỉnh feature bằng test. **Đã chạy thành công một lần; không chạy lại trên test thật.** Runner từ chối nếu prediction/manifest/report/state/one-shot lock đã tồn tại, kể cả output dở dang. Synthetic unit tests chỉ dùng dữ liệu tạm, không mở test thật.

Input: `data/processed/cleaned_dataset.parquet`, `data/processed/data_dictionary.csv`, `data/processed/cleaned_dataset_manifest.json`, `data/processed/modeling/{train_ids,validation_ids,test_ids}.parquet`, `split_manifest.json`, `ml_lc_05_manifest.json`, `ml_lc_06_manifest.json`, `ml_lc_07_manifest.json`, `xgboost_candidate.joblib` và state markers ML-LC-06/07.

Output: `data/processed/modeling/ml_lc_08_frozen_test_predictions.parquet`, `data/processed/modeling/ml_lc_08_manifest.json`, `reports/tv1_stages/ml-lc-08.md`, `reports/tv1_stages/state/ml-lc-08.json`; lock một lần tại `data/processed/modeling/ml_lc_08_one_shot.lock`.

Validation: focused synthetic **11 passed**, `tests/models` **81 passed**, `tests/data tests/features` **75 passed** (4 cảnh báo date parsing TV2), `compileall src tests` PASS, `git diff --check` PASS trước runtime. Sau runtime, artifact prediction có đúng 269,070 loan IDs unique/non-null, xác suất hữu hạn trong `[0,1]`, class khớp threshold; hashes model/ML-LC-06/07 không đổi. Metrics/test-vs-validation xem báo cáo ML-LC-08. Ở thời điểm ML-LC-08, ML-LC-09 là bước tiếp theo; kết quả hiện tại được ghi ở section ML-LC-09 bên dưới.

## ML-LC-09 — Explainability

Prerequisite: ML-LC-08 PASS; candidate/threshold locks, ML-LC-05–08 manifests và fitted model phải khớp. Explainability dùng validation IDs/predictions và các canonical rows thuộc validation; frozen test không được đọc lại.

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-09
```

Ý nghĩa: nạp pipeline XGBoost đã fit, khôi phục 151 tên transformed feature, chọn mẫu validation phân tầng cố định 5.000 dòng (`random_state=42`), tính gain/SHAP, gộp one-hot về feature gốc, tạo local examples và hình minh họa. Lệnh không gọi fit. SHAP cần package có sẵn trong môi trường; không tự cài. Nếu SHAP không hoạt động, stage ghi `BLOCKED` và chỉ giữ native gain.

Output: `data/processed/modeling/ml_lc_09_global_importance.csv` (dashboard V05, tên feature gốc, mean absolute SHAP, gain, hướng), `ml_lc_09_transformed_importance.csv`, `ml_lc_09_local_explanations.csv`, `ml_lc_09_shap_sample.parquet`, `ml_lc_09_manifest.json`, `reports/tv1_stages/ml-lc-09.md`, `reports/tv1_stages/state/ml-lc-09.json`, `reports/figures/modeling/ml_lc_09_global_importance.png`, `reports/figures/modeling/ml_lc_09_shap_summary.png`.

Validation trước runtime: focused **7 passed**, `tests/models` **88 passed**, `tests/data tests/features` **75 passed** (4 cảnh báo parse ngày TV2), `compileall src tests` PASS, `git diff --check` PASS. Runtime: validation `269,070`, SHAP sample `5,000` (`4,002` target 0; `998` target 1), original feature `103`, transformed `151`; SHAP PASS trong raw margin/log-odds, additivity max error `3.23e-06`. Model SHA-256 trước/sau không đổi. V05 source artifacts đã sẵn sàng; Power BI visual chưa được dựng/tích hợp. ML-LC-10 được ghi ở mục tiếp theo.

## ML-LC-10 — PD scoring và risk tier

Prerequisite: ML-LC-07/08/09 manifest và state đều PASS; candidate, threshold `0.22009515762329102`, model hash và frozen-test predictions phải khớp lock. Lệnh chỉ đọc predictions ML-LC-08 cùng 9 cột context mô tả cần cho dashboard; không load model, fit, gọi `predict_proba` hoặc chọn lại threshold/tier.

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-10
```

Ý nghĩa: xác thực `loan_id`, target, PD, predicted class; giữ nguyên một hàng cho mỗi loan; tính `risk_score = 100 × predicted_pd`, `credit_score = round(1000 × (1 − predicted_pd))` với round half-to-even, và bốn tier theo threshold đã khóa: A `< T/2`, B `[T/2,T)`, C `[T,2T)`, D `[2T,1]`. `credit_score` là điểm của project/model, không phải FICO. Observed default rate trong summary chỉ để mô tả test population, không tham gia tạo score/tier hoặc tuning.

Input: `data/processed/modeling/ml_lc_08_frozen_test_predictions.parquet` (269,070 dòng), `data/processed/data_dictionary.csv` để xác thực context chỉ thuộc `APPLICATION_TIME`/`CREDIT_SNAPSHOT`, và `data/processed/cleaned_dataset.parquet` (chỉ lấy `loan_id`, `fico_avg`, `dti`, `loan_amnt`, `annual_inc`, `loan_to_income_ratio`, `purpose`, `home_ownership`, `term_months`, `issue_year`).

Output: `data/processed/modeling/ml_lc_10_scored_frozen_test.parquet`, `ml_lc_10_risk_tier_summary.csv`, `ml_lc_10_score_summary.csv`, `ml_lc_10_manifest.json`, `reports/tv1_stages/ml-lc-10.md`, `reports/tv1_stages/state/ml-lc-10.json`.

Kết quả: **PASS**, đúng 269,070 rows; `risk_score` nằm trong [0,100], project `credit_score` trong [0,1000], source predictions và protected hashes giữ nguyên. Tier A/B/C/D lần lượt có 66,275 / 109,146 / 80,423 / 13,226 loans; mean predicted PD 7.73% / 16.03% / 30.15% / 51.79%; observed default rate 6.20% / 15.78% / 31.16% / 55.41%. Cả mean PD và observed rate tăng theo tier; đây là mô tả trên evaluated test population, không phải cam kết cho từng borrower.

V02 PD Distribution, V03 Risk Tier Distribution và V04 FICO vs Risk/PD có nguồn dữ liệu **READY**; TV3 vẫn cần tích hợp các visual vào Master PBIX. Validation: focused scoring **18 passed**, `tests/models` **96 passed**, `tests/data tests/features` **75 passed, 4 warnings** (date parsing trong TV2 tests), `compileall src tests` PASS, `git diff --check` PASS, runtime ML-LC-10 PASS. Model, ML-LC-07 manifest và ML-LC-08 manifest hashes trước/sau giống nhau; không retrain, candidate/threshold không đổi.

## ML-LC-11 — Expected Loss scenario analysis

Prerequisite: ML-LC-10 PASS, với candidate `xgboost_candidate`, threshold `0.22009515762329102` và scored population 269,070 dòng giữ nguyên. Stage chỉ đọc PD/risk tier/context đã tạo; không load/fit model, không gọi `predict_proba`, không tìm threshold mới.

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-11
```

Ý nghĩa: tính `EL = predicted_pd × LGD assumption × EAD proxy` trên dữ liệu ML-LC-10. Baseline LGD 45% và sensitivity 30/45/60% là scenario assumptions minh họa; `loan_amnt` là EAD proxy chứ không phải exposure thực tế tại default. Data dictionary không ghi currency unit, nên output/report giữ đơn vị nguồn thay vì tự ghi USD. `target` chỉ dùng trong observed default rate theo tier, không tham gia công thức EL.

Output: `data/processed/modeling/ml_lc_11_expected_loss.parquet`, `ml_lc_11_portfolio_el_summary.csv`, `ml_lc_11_risk_tier_el_summary.csv`, `ml_lc_11_manifest.json`, `reports/tv1_stages/ml-lc-11.md`, `reports/tv1_stages/state/ml-lc-11.json`. V06 là **DATA READY**; TV3 vẫn phải tích hợp visual vào Power BI.

Kết quả runtime: 269,070 loans; total EAD proxy 3,878,248,925 source units; baseline total EL 372,579,342.19; average EL 1,384.69; portfolio EL rate 9.61%. EL share theo A/B/C/D là 8.21% / 28.21% / 47.89% / 15.69%. LGD sensitivity total EL: 30% = 248,386,228.13; 45% = 372,579,342.19; 60% = 496,772,456.26. Đây là frozen-test scenario, không phải full portfolio hoặc realized loss.

Validation: focused expected-loss + cost-optimization tests **15 passed**; full `tests/models` **103 passed**; `tests/data tests/features` **75 passed, 4 warnings** (date parsing ở TV2 tests); `compileall src tests` PASS; `git diff --check` PASS; runtime ML-LC-11 PASS. Hash model, ML-LC-07/08/10 manifests không đổi; threshold/candidate không đổi; không retrain.

Historical note: dòng trạng thái khi ML-LC-11 được ghi là ML-LC-12 NOT STARTED. Trạng thái hiện tại được cập nhật ở đầu guide và trong phần ML-LC-12/13 bên dưới.

## ML-LC-12 — Full-data refit

Runtime đã PASS trên toàn bộ **1,345,350** labeled canonical rows. Runner:

```powershell
.venv\Scripts\python.exe -m src.models.tv1_runner --stage ml-lc-12
```

Lệnh fit full-data refit bằng cấu hình XGBoost/feature list đã khóa; không retrain candidate ML-LC-05 và không dùng frozen test để lựa chọn. Artifact: `data/processed/modeling/xgboost_full_refit.joblib`; demo/inference scores: `data/processed/modeling/ml_lc_12_full_refit_scores.parquet`; manifest/report/state tại `ml_lc_12_manifest.json`, `reports/tv1_stages/ml-lc-12.md`, `reports/tv1_stages/state/ml-lc-12.json`. Scores là in-sample, không phải unbiased evaluation. Threshold từ ML-LC-07 được carry forward, không retune hoặc revalidate.

## ML-LC-13 — Conditional handoff audit

Audit PASS — satisfied by existing handoff artifacts; không tạo duplicate combined parquet. Mapping nguồn V02–V04: `ml_lc_10_scored_frozen_test.parquet`; V05: ML-LC-09 global importance và explainability-specific local/sample artifacts; V06: ML-LC-11 Expected Loss summaries. Full-refit model pipeline có preprocessing và contract 103 input features cho inference một borrower. `individual_prediction_contract_ready=true`. Đây chỉ là modeling handoff/data readiness; không khẳng định Power BI đã được xây dựng, tích hợp hay review.

Modeling summary tổng hợp: `reports/tv1_stages/modeling_summary.md`.

## Phạm vi trách nhiệm sau reorganize

TV1 là primary owner của modeling, V02–V06, Storytelling, report coordination và defense coordination. V01 Geographic Risk Map thuộc TV3; TV1 chỉ cross-review khi cần. TV1 cross-review TV2 handoff/V07–V09 và TV3 dashboard structure. TV1 không tích hợp Master PBIX; TV3 giữ integration ownership.

## TV1 Power BI data preparation — V02–V06

Tạo một fact gọn cho năm visual TV1, không dựng visual/PBIX. Nguồn analytical chính là **269,070 ML-LC-08 frozen-test loans**; không dùng full-refit scores in-sample và không chạy lại model/test evaluation.

Prerequisite: `.venv` với requirements đã cài; ML-LC-10 và ML-LC-11 manifests phải ở trạng thái PASS; có scored test, Expected Loss và canonical parquet. Lệnh đã kiểm tra:

```powershell
.\.venv\Scripts\python.exe -m src.models.tv1_dashboard_data
```

Ý nghĩa: đọc đúng các cột cần từ `ml_lc_10_scored_frozen_test.parquet`, `ml_lc_11_expected_loss.parquet` và chỉ `loan_id`/`fico_band` từ canonical dataset; kiểm tra manifest/threshold, căn chỉnh IDs 1:1, tạo sort/bin fields; ghi Parquet qua file partial rồi đọc kiểm tra và promote atomically.

Output:

- `data/processed/dashboard/fact_evaluated_loan.parquet` — 269,070 dòng, một dòng mỗi `loan_id`, 27 cột cho V02/V03/V04/V06.
- ML-LC-09 giữ thành ba bảng riêng cho V05: `ml_lc_09_global_importance.csv`, `ml_lc_09_shap_sample.parquet`, `ml_lc_09_local_explanations.csv`. SHAP không được join vào loan fact vì population/grain khác.

Binning implementation:

- PD bins có độ rộng cố định 0.05: `[0.00,0.05)`, `[0.05,0.10)`, …, `[0.90,0.95)`, `[0.95,1.00]`; bin cuối gồm PD=1. `pd_bin` là cận dưới số học, `pd_bin_label` là nhãn hiển thị và `pd_bin_sort_order` từ 1 đến 20. Không tối ưu bin theo hình chart. Threshold line V02 vẫn là `0.22009515762329102`.
- `fico_band` được reuse nguyên từ canonical engineering: `<650`, `650-699`, `700-749`, `750+`; sort 1–4. Giá trị thiếu được gán `Missing`, sort 5; không có missing FICO band trong lần tạo hiện tại.
- `risk_tier` trong fact là mã `A/B/C/D`; `risk_tier_label` giữ label ML-LC-10, `tier_sort_order` là 1–4. Không tính lại tier boundary.

Power BI measures cần tạo trong build task (populations/filter context chỉ trong FactEvaluatedLoan):

```DAX
Evaluated Loan Count = COUNTROWS(FactEvaluatedLoan)
Mean PD = AVERAGE(FactEvaluatedLoan[predicted_pd])
Median PD = MEDIAN(FactEvaluatedLoan[predicted_pd])
Observed Default Count = SUM(FactEvaluatedLoan[target])
Observed Default Rate = DIVIDE([Observed Default Count], [Evaluated Loan Count])
Risk Tier Share = DIVIDE([Evaluated Loan Count], CALCULATE([Evaluated Loan Count], REMOVEFILTERS(FactEvaluatedLoan[risk_tier])))
Total EAD Proxy = SUM(FactEvaluatedLoan[ead_proxy])
Total Expected Loss = SUM(FactEvaluatedLoan[expected_loss])
Average Expected Loss = DIVIDE([Total Expected Loss], [Evaluated Loan Count])
Portfolio EL Rate = DIVIDE([Total Expected Loss], [Total EAD Proxy])
Expected Loss Contribution % = DIVIDE([Total Expected Loss], CALCULATE([Total Expected Loss], REMOVEFILTERS(FactEvaluatedLoan[risk_tier])))
High Risk Count = CALCULATE([Evaluated Loan Count], FactEvaluatedLoan[risk_tier] IN {"C", "D"})
High Risk Share = DIVIDE([High Risk Count], [Evaluated Loan Count])
```

EL mặc định là LGD 45%; `expected_loss_lgd_30/45/60` hỗ trợ selector ở bước build sau. Selector chỉ thay measure EL, tuyệt đối không thay `predicted_pd` hoặc `risk_tier`. Hiển thị EL/EAD theo source units, không tự gắn currency; EAD là `loan_amnt` proxy.

Focused tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/models/test_tv1_dashboard_data.py -v
```

Kết quả kiểm tra thực tế: **5 passed**; fact có 269,070 rows/27 columns, `loan_id` unique/non-null, A/B/C/D counts 66,275/109,146/80,423/13,226, expected loss IDs khớp 1:1 và baseline EL tổng `372,579,342.1934409`. V02 PD bins và V04 FICO bands exhaustive; current missing FICO band count = 0. Trạng thái build mới nhất nằm ở mục dưới.

## Power BI TV1 — V02–V06 core visuals

Mở `reports/figures/dashboard/nghia.pbip` trong Power BI Desktop để xem trang độc lập **TV1 - V06 Expected Loss Contribution**. Input đã nạp sẵn là `data/processed/dashboard/fact_evaluated_loan.parquet` (269,070 evaluated loans); không refresh/import bảng mới cho bước này. V06 dùng `risk_tier` và measure `[Total Expected Loss] = SUM(fact_evaluated_loan[expected_loss_lgd_45])`, sắp xếp giảm dần theo EL. Tooltip có `[EL Contribution %]`, `[Total EAD Proxy]`, `[Mean PD]`, `[Evaluated Loan Count]`. EL là scenario LGD 45%; EAD là `loan_amnt` proxy; số tiền giữ **đơn vị nguồn** và không gọi là realized loss.

Kiểm tra V06 trên Desktop: bốn thanh theo thứ tự **C → B → D → A**, không báo lỗi; tổng EL **372,579,342.1934409**, tổng EAD proxy **3,878,248,925**. Đã xem render trực tiếp: C ~178M, B ~105M, D ~58M, A ~31M. `V06_BUILD_PASS` cho core visual; trang tổng hợp và KPI cards thuộc giai đoạn sau.

V04 hiện đã có một trang Box & Whisker độc lập trong PBIP và đã render được ba FICO band có dữ liệu. `fico_band` được sort theo `fico_band_sort_order`; custom visual dùng `fico_band` ở Groups, `predicted_pd` ở Values và `loan_id` ở Samples để giữ grain từng khoản vay (mỗi `loan_id` chỉ có một dòng). Measures `[Median PD]`, `[PD Q1]`, `[PD Q3]`, `[Mean PD]`, `[Evaluated Loan Count]`, `[Observed Default Rate]` dùng để đối chiếu. Không thêm hộp cho band rỗng hoặc đổi Box Plot thành mean bar. Typography của visual được điều chỉnh và kiểm tra bằng ảnh Desktop ngày 2026-10-07. **Tooltip custom visual vẫn cần kiểm tra thủ công**: chưa xác nhận được cách thay built-in chart-specific tooltip bằng tooltip gọn mà không làm hỏng visual; cấu hình hiện tham chiếu trang `Page 2` trống. V02 cũng chưa có threshold line chính xác tại `0.22009515762329102` vì trục histogram là nhãn bin phân loại; không vẽ đường xấp xỉ.

Population V04: `650-699` **164,277**, `700-749` **83,552**, `750+` **21,241**; tổng **269,070**. `<650` và `Missing` có **0** dòng trong evaluated population hiện tại, nên không tạo hộp giả cho hai nhóm rỗng. PD nằm trong `[0.014859369, 0.803955436]`, không thiếu PD hoặc FICO band. Đối chiếu Q1/median/Q3 từ DAX: `650-699` = `0.145241 / 0.208485 / 0.301042`; `700-749` = `0.086702 / 0.127668 / 0.197087`; `750+` = `0.045053 / 0.067767 / 0.115688`. Đây là mẫu hình liên hệ với predicted PD, không phải bằng chứng FICO gây default.

### TV1 usability pass — slicer và tooltip (2026-10-07)

Mở `reports/figures/dashboard/nghia.pbip` trong Power BI Desktop. Các trang làm việc riêng vẫn có slicer mặc định **All**: Hạng rủi ro đồng bộ V02↔V04; Nhóm FICO đồng bộ V02↔V03. **Trang 3 final** ghép V02/V03/V05 và ba KPI, **không có slicer**; click tier A/B/C/D ở V03 lọc V02 và KPI, còn V05 không nhận filter từ V02/V03 vì SHAP thuộc validation sample. V05 giữ một Top-10 bar với mã feature gốc trên trục và chú giải tiếng Việt riêng (không sửa model). V06 có slicer Nhóm FICO **riêng, không đồng bộ**; task chốt Trang 3 không chỉnh V06. Không có LGD selector; V06 vẫn là giả định 45%.

Kiểm tra thủ công đã thực hiện: chọn Hạng C trên V02 làm PD histogram và V04 Box Plot đổi theo tier; V05 vẫn là Top-10 SHAP cũ. Chọn FICO `700-749` trên V02 làm histogram đổi và V03 còn 83,552 khoản vay với cơ cấu tier mới; V06 vẫn xếp C→B→D→A. Các lượt chọn thử được **Discard** khi đóng Desktop, nên file trên đĩa vẫn mở ở All.

Tooltip native đã kiểm tra bằng hover trên ảnh Power BI thật: V02 dùng Khoảng PD / Số khoản vay / Tỷ trọng; V03 dùng Hạng rủi ro / Số khoản vay / Tỷ trọng / PD trung bình / Tỷ lệ default thực tế; V05 dùng Đặc trưng / Mức quan trọng trung bình |SHAP| / Xếp hạng; V06 dùng Hạng rủi ro / Tổng Expected Loss / Tỷ trọng Expected Loss / Tổng EAD proxy / PD trung bình / Số khoản vay. EL/EAD chỉ là **đơn vị nguồn**, không gắn USD. Tooltip V04 vẫn là tooltip thống kê tiếng Anh do custom Box & Whisker tự ép hiển thị; trang report-tooltip `Page 2` không thay thế được khi thử hover. `# Samples` trong tooltip custom là số mẫu của visual, **không phải** `[Evaluated Loan Count]` của FICO band. Giữ nguyên Box Plot và ghi `V04_TOOLTIP_CUSTOM_VISUAL_LIMITATION`.

Hướng dẫn tái tạo/cập nhật các visual bằng thao tác Power BI Desktop: `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`. Trang 3 là **working PBIP của TV1**, chưa phải Master PBIX TV3. KPI gồm số khoản vay evaluated, PD dự đoán trung bình và tỷ lệ default quan sát; V05 vẫn là validation, không nối dữ liệu vào fact. V04 vẫn có giới hạn tooltip của custom visual; không đổi `loan_id` thành số khoản vay bằng cách gắn nhãn sai.

Chốt Trang 3: V02 giữ chart/bin/tooltip nhưng dùng phụ đề không ghi count cố định để đúng khi V03 lọc A/B/C/D; V03 giữ chart/tooltip; V05 giữ Top-10 mean |SHAP| và có chú giải tiếng Việt gọn bên phải theo lựa chọn **không sửa model/data**. Power BI Desktop render lại sạch; chọn thử từng tier A/B/C/D trên V03 làm V02 và ba KPI đổi, V05 không đổi, sau đó trả về baseline All. Hai slicer Trang 3 đã bỏ; slicer trên các trang độc lập khác giữ nguyên. Đây là `TRANG_3_MODEL_RISK_FINAL_PASS` cho bản TV1, chưa phải nghiệm thu Master TV3.

Input là `fact_evaluated_loan.parquet` và bảng SHAP đã import sẵn; không refresh dữ liệu hay sửa semantic model. Kiểm tra lại sau khi mở: baseline 269,070 loans, tier A/B/C/D = 66,275/109,146/80,423/13,226, EL ≈372,579,342.19 đơn vị nguồn; V05 vẫn Top-10. Nếu muốn trình bày tooltip V04 hoàn toàn bằng tiếng Việt, cần cấu hình trực tiếp trong custom visual hoặc thay tooltip/page binding sau một vòng review riêng; không coi là đã hoàn tất ở lượt này.

## Individual Prediction / What-if — prototype cục bộ

```powershell
.\run_prediction_app.bat
```

Launcher mặc định chạy phiên bản hiện tại của repo tại `http://127.0.0.1:8050/`. Mỗi port là một server/process riêng; launcher từ chối cổng đang dùng để tránh mở nhầm instance cũ. Nếu báo cổng bận, kiểm tra listener bằng `Get-NetTCPConnection -LocalPort 8050 -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress, LocalPort, OwningProcess`; nếu có PID, dừng đúng app cũ bằng `Ctrl+C` trong cửa sổ tương ứng rồi chạy lại. Nếu lệnh kiểm tra không trả dòng nào nhưng launcher vẫn báo bận, cập nhật/sửa launcher và thử lại; không tự kết thúc process không xác định. Chỉ dùng `$env:DASH_PORT = "<port trống>"` khi đã kiểm tra port chưa có listener. `Ctrl+F5` chỉ xóa cache trình duyệt; nó không nâng cấp code nằm trong một process Python đang chạy.

Threshold slider trong [0, 1] đổi kết luận Default/Non-default, đường/màu và hai số đếm trên visual, đối chiếu TP/TN/FP/FN cho preset nguyên bản, cùng ma trận/metrics Validation động ở mục riêng; PD, tier, mức rủi ro, điểm an toàn, EL và SHAP giữ nguyên. Nút Đặt lại dùng giá trị nội bộ chính xác `0.22009515762329102` (hiển thị `0.2201`). Chọn một trong tám hồ sơ Validation để điền sáu input, xem PD Validation của model đang chọn, rồi bấm DỰ ĐOÁN để suy luận. Chuyển model sau khi có kết quả sẽ chấm lại hồ sơ bằng model mới; chỉnh input sẽ xóa kết quả và ẩn đối chiếu nhãn lịch sử. Biểu đồ dùng 120 PD lấy mẫu cố định từ prediction Validation đã kiểm provenance, số đếm chỉ áp dụng cho các chấm đang hiển thị. Kiểm tra tập trung: `.\.venv\Scripts\python.exe -m pytest tests/apps/test_individual_prediction_dash.py -v`.

Trong khu vực **HIỆU NĂNG MÔ HÌNH · VALIDATION**, Brier Score/Log Loss và ROC-AUC/PR-AUC/F1 đọc từ manifest của model 6-input đang chọn. **Chi tiết mô hình** mặc định đóng, liệt kê model, hai ngưỡng, hai kết luận, cùng Recall/Precision/Accuracy của đúng model 6-input. Ba metric bổ sung và F1 ở đây là kết quả Validation tại ngưỡng đánh giá trong manifest, không đổi theo slider. Mở **ĐÁNH GIÁ PHÂN LOẠI THEO NGƯỠNG** để xem TN/FP/FN/TP, Precision/Recall/F1/Accuracy và số hồ sơ gắn cờ động trên toàn bộ 269.070 hồ sơ Validation có nhãn của model đang chọn. Visual PD chỉ dùng 120 chấm minh họa; không dùng 120 chấm để tính metric toàn tập. Dữ liệu động đọc `*_6input_demo_validation_predictions.parquet` sau kiểm hash model/split/prediction và so cả ID/target với `validation_ids.parquet`; không có dữ liệu hợp lệ thì hiển thị không khả dụng. Biểu đồ hiệu chuẩn cũ không còn trên UI chính. Khu EL có ba KPI, bar theo LGD và mục ⓘ mở để đọc công thức `PD × LGD × số tiền vay (EAD proxy)`.

Giải thích học thuật: Brier = trung bình `(PD − nhãn)²`, Log Loss phạt dự đoán xác suất quá chắc chắn nhưng sai; thấp hơn tốt hơn cho cả hai. Chúng là đánh giá tổng thể trên nhãn Validation, không phải khoảng sai số ± hay độ chính xác của hồ sơ đang nhập. Mỗi lần đổi model, metrics/chart đi theo manifest và validation predictions của đúng model. Metric nào thiếu trong manifest thì giao diện để `—`, không fallback sang model 103-feature hoặc frozen test.

## Reproduce model evaluation figures

Tạo bốn hình ROC, Precision–Recall, confusion matrix và calibration từ saved Validation predictions đã đối chiếu ID/target với frozen `validation_ids.parquet`:

```powershell
.\.venv\Scripts\python.exe -m src.models.evaluation_figures
```

Script không load model, không fit, không mở Frozen Test predictions và xác thực AUC/AP/confusion với ML-LC-03/04/05/07 manifests trước khi xuất PNG 300 DPI vào `reports/figures/modeling/`. Xem `reports/figures/modeling/README.md` và `figures_manifest.json` để biết nguồn, cohort, threshold, metrics và quy ước PR-AUC/AP.

## Render preparation

Hướng dẫn độc lập tại `apps/individual_prediction_dash/DEPLOY_RENDER.md`. Root Directory là `apps/individual_prediction_dash`; ứng dụng có runtime source mirror và bảy runtime artifacts cần thiết dưới thư mục này để không phụ thuộc source/dữ liệu bên ngoài root. Không có bước train khi start; giới hạn RAM Free chưa được xác nhận trên Linux và hiện là rủi ro cần theo dõi.

Ngưỡng phân loại tương tác chạy từ `0` đến `1`, bước `0.01`, ngay dưới sáu input và phía trên **DỰ ĐOÁN**. Mặc định/nút **Đặt lại** giữ chính xác `0.22009515762329102` (nhãn hiển thị `0.2201`); đây là ngưỡng chọn trên Validation của **mô hình chính 103-input**, chỉ được mang sang hai demo 6-input để tham chiếu, không phải optimum riêng của chúng. Giá trị người dùng chọn được giữ trong `sessionStorage` của tab hiện tại. Sau khi có PD, slider đổi kết luận theo `PD >= ngưỡng`, đường/màu visual và ma trận/metrics Validation động; không chạy lại inference, SHAP hay Expected Loss. Tier, mức rủi ro, PD, điểm an toàn và EL không đổi. Metrics Validation cố định ở khu hiệu năng vẫn gắn với ngưỡng đánh giá trong artifact. Kiểm tra: `.\.venv\Scripts\python.exe -m pytest tests/apps/test_individual_prediction_dash.py -v --basetemp .pytest_cache/threshold-tests`.
