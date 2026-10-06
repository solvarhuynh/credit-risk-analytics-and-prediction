# Thiết lập TV1 — Lending Club Modeling

Trạng thái modeling: **ML-LC-01 đến ML-LC-13 PASS**. ML-LC-12 tạo full-data refit và in-sample demo scores; ML-LC-13 là audit handoff, PASS nhờ artifacts/contracts hiện có. `xgboost_candidate` vẫn là evaluated model của ML-LC-08; frozen test không được chạy lại. Threshold `0.22009515762329102` được carry sang refit, không retune/revalidate. Chưa chọn lại final model/threshold; Power BI chưa được tích hợp hoặc review và vẫn thuộc TV3.

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
