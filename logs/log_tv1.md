# TV1 Progress Log — Lending Club Dataset Reset

## Dataset Migration Reset — 2026-10-01

- Dataset cũ đã retired; Lending Club 2007–2018 được chọn.
- Lịch sử trước reset đã được loại khỏi working tree; có thể truy xuất qua Git history.
- Chưa chạy lại pipeline hoặc mô hình.
- Trạng thái: **RESET / NOT YET EXECUTED**.
- Bước tiếp theo: **WAITING FOR TV2 LENDING CLUB CANONICAL HANDOFF**.

## 2026-10-01 — Dataset migration implementation

- Trạng thái: **MIGRATED / NOT YET RETRAINED**.
- Đã chuyển `src/models/`, model contract, setup/task TV1 và synthetic model tests sang `loan_id`/`target` với Logistic bắt buộc và feature gate fail-closed.
- Đã xóa model/report/metric sinh từ dataset trước reset; `models/` chỉ còn `.gitkeep`.
- Kiểm tra: compileall PASS; legacy/old-result active search không còn exact match; không chạy training hoặc data-dependent tests.
- Next step: chờ TV2 hoàn tất DE-LC-01 đến DE-LC-10 và bàn giao canonical artifacts.

## 2026-10-01 — Team responsibility reorganization

- Task: reorganize workload cho Lending Club; trạng thái **PLANNED / NOT YET IMPLEMENTED**.
- TV1 nhận primary: modeling + V01–V06 + Storytelling/Report/Defense coordination; TV1 không phải PBIX integration owner.
- Files: `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/tasks/dashboard-visual-plan.md`, `docs/tasks/report-writing-plan.md`, `docs/tasks/defense-knowledge-matrix.md`.
- Kiểm tra: sẽ xác nhận 6 visual, report reviewer và defense matrix sau khi docs hoàn tất; không chạy pipeline/model/dashboard.
- Next step: TV1 chuẩn bị visual specifications sau khi TV2 có usable schema.

## 2026-10-04 — ML-LC-02 Freeze deterministic split

- Task: implement và validate ML-LC-02 trên canonical Lending Club sau khi TV2 handoff đạt `TV2_HANDOFF_PASS`; trạng thái **ML-LC-02 = PASS**.
- Ownership: **TV1 = PRIMARY OWNER — Modeling**; **TV2 = upstream Data Engineering owner**; agent thực hiện targeted implementation/test hardening dưới TV1 review.
- Split policy: stratified by `target`, `random_state = 42`, train/validation/frozen test = `60% / 20% / 20%`. ML-LC-02 chỉ quyết định row membership; không fit preprocessing và không train model.
- Runtime source: `data/processed/cleaned_dataset.parquet`, `1,345,350` rows, approved ML-LC-01 feature schema `106` features. Exact partitions: train `807,210`, validation `269,070`, frozen test `269,070`.
- Target counts: full `0 = 1,076,751`, `1 = 268,599`; train `0 = 646,051`, `1 = 161,159`; validation `0 = 215,350`, `1 = 53,720`; frozen test `0 = 215,350`, `1 = 53,720`.
- Default rates: full `0.1996499052`; train `0.1996494097`; validation `0.1996506485`; frozen test `0.1996506485`; maximum absolute difference from full `7.43301e-07` under tolerance `0.005`.
- Integrity: train/validation overlap `0`, train/test `0`, validation/test `0`; union coverage `1,345,350`; partition IDs unique/non-null and targets preserved; no partial artifacts remain.
- Frozen artifacts: `data/processed/modeling/train_ids.parquet`, `validation_ids.parquet`, `test_ids.parquet`, `split_manifest.json`. Artifacts persist only `loan_id`, `target`, `split`; no 113-column copies.
- Rerun behavior: second real `ml-lc-02` run returned `PASS` with `reused_existing_artifacts = true`; membership was validated and not overwritten.
- Stage evidence: `reports/tv1_stages/ml-lc-02.md` and `reports/tv1_stages/state/ml-lc-02.json`.
- Tests: focused `18 passed`; full `tests/models` — **55 passed**; regression `tests/data tests/features` — **75 passed, 4 warnings**; `compileall src tests` — **PASS**; `git diff --check` — **PASS** with existing LF/CRLF warnings only.
- Scope boundary: ML-LC-03 chưa bắt đầu; không train Logistic/XGBoost, không fit StandardScaler/imputer/encoder, không tune threshold và không dùng frozen test để model selection.
- Next step: TV1 có thể mở ML-LC-03 Logistic baseline; giữ nguyên frozen split và chỉ dùng development split cho training/model selection.

## 2026-10-04 — ML-LC-03 Logistic Regression baseline

- Task/status: **ML-LC-03 = PASS**. TV1 là primary owner của modeling; agent thực hiện targeted implementation/test hardening dưới TV1 review. TV2 vẫn là upstream Data Engineering owner.
- Input/gate: TV2 handoff `TV2_HANDOFF_PASS`; canonical `data/processed/cleaned_dataset.parquet`; ML-LC-01 approved feature schema `106`; ML-LC-02 frozen split `train = 807,210`, `validation = 269,070`, `frozen test = 269,070`.
- Baseline: Logistic Regression `solver=lbfgs`, `penalty=l2`, `max_iter=1000`, `random_state=42`, **`class_weight=None`**. Không resampling, không imbalance treatment, không XGBoost và không threshold search.
- Feature audit: actual baseline dùng `103/106` feature. Loại raw date khỏi one-hot (`issue_d`, `earliest_cr_line`, `sec_app_earliest_cr_line`) vì đã có feature thời gian/credit-history deterministic hoặc date-like sparse representation; transformed output `151` features và giữ sparse.
- Preprocessing fit **train only**; validation chỉ dùng để `predict_proba`/đánh giá. Frozen test chỉ kiểm tra membership, `frozen_test_used_for_training = false`, `frozen_test_used_for_evaluation = false`, evaluation rows `0`.
- Convergence: **PASS**, `n_iter=[66]`, không có convergence warning. Validation predictions `269,070` dòng, `loan_id` unique/non-null, probability hữu hạn trong `[0,1]`.
- Validation metrics tại threshold reference `0.5` (chưa phải threshold cuối): ROC-AUC `0.7148869450`; PR-AUC `0.3853066510`; precision `0.5624535316`; recall `0.0844936709`; F1 `0.1469169769`; accuracy `0.8040955885`; confusion matrix `[[211819, 3531], [49181, 4539]]`.
- Artifacts/report: `data/processed/modeling/logistic_baseline.joblib`, `data/processed/modeling/ml_lc_03_validation_predictions.parquet`, `data/processed/modeling/ml_lc_03_feature_audit.csv`, `data/processed/modeling/ml_lc_03_manifest.json`, `reports/tv1_stages/ml-lc-03.md`, `reports/tv1_stages/state/ml-lc-03.json`.
- Validation: focused/full model tests **58 passed**; data/features regression **75 passed, 4 warnings**; `compileall src tests` **PASS**; `git diff --check` **PASS**. Real runner chạy lại lần hai vẫn **PASS**; validation probabilities/prediction artifact và metrics tương đương deterministic.
- Scope boundary: **ML-LC-04 = NOT STARTED**. Chưa chọn threshold cuối, chưa mở frozen test để đánh giá và chưa thực hiện imbalance experiment.
- Next step: review/sign-off ML-LC-03 rồi mới mở task ML-LC-04.

## 2026-10-05 — ML-LC-04 Logistic Regression imbalance experiment

- Task/status: **ML-LC-04 = PASS**. TV1 là primary owner của modeling; agent thực hiện targeted implementation/test hardening dưới TV1 review. TV2 vẫn là upstream Data Engineering owner.
- Controlled comparison: giữ nguyên frozen split, feature schema, 103 actual baseline features, preprocessing, `solver=lbfgs`, `penalty=l2`, `max_iter=1000` và `random_state=42`. Chỉ thay đổi treatment: baseline `class_weight=None` so với weighted `class_weight='balanced'`.
- Data: train `807,210`; validation `269,070`; frozen test `269,070`. Preprocessing weighted fit **train only**; transformed features `151`, sparse output. Frozen test chỉ được kiểm tra membership, không predict/metric/selection (`frozen_test_evaluation_rows = 0`).
- Weighted runtime: hội tụ **PASS**, `n_iter=[74]`, không có convergence warning. Weighted validation predictions `269,070` dòng, `loan_id` unique/non-null, probability hữu hạn trong `[0,1]`.
- Baseline tại threshold reference `0.5`: ROC-AUC `0.7148869450`; PR-AUC `0.3853066510`; precision `0.5624535316`; recall `0.0844936709`; F1 `0.1469169769`; accuracy `0.8040955885`; confusion `[[211819, 3531], [49181, 4539]]`.
- Weighted tại threshold reference `0.5`: ROC-AUC `0.7150973326`; PR-AUC `0.3840143077`; precision `0.3221343874`; recall `0.6553983619`; F1 `0.4319575993`; accuracy `0.6558516371`; confusion `[[141262, 74088], [18512, 35208]]`.
- Trade-off quan sát được: recall `+0.5709046910`, false negatives `-30,669`, nhưng precision `-0.2403191442`, false positives `+70,557`; ROC-AUC chỉ `+0.0002103876`, PR-AUC `-0.0012923433`. Weighted nhạy hơn với default tại threshold tham chiếu nhưng tạo nhiều false-positive alerts hơn; chưa phải kết luận causal hoặc model cuối.
- Files code/test/setup/status: `src/models/tv1_runner.py`, `src/config.py`, `tests/models/test_tv1_runner.py`, `docs/setup/tv1_setup.md`, `docs/tasks/thanh-vien-1-modeling.md`.
- Artifacts: `data/processed/modeling/logistic_weighted.joblib`, `data/processed/modeling/ml_lc_04_weighted_validation_predictions.parquet`, `data/processed/modeling/ml_lc_04_manifest.json`, `reports/tv1_stages/ml-lc-04.md`, `reports/tv1_stages/state/ml-lc-04.json`. `logistic_baseline.joblib` được hash trước/sau và giữ nguyên.
- Validation: focused runner test **3 passed**; full `tests/models` **59 passed**; regression `tests/data tests/features` **75 passed, 4 warnings**; `compileall src tests` **PASS**; `git diff --check` **PASS**. Real ML-LC-04 chạy **PASS hai lần** với probabilities/metrics tương đương; chưa thực hiện threshold optimization, resampling, XGBoost hoặc frozen-test evaluation.
- Scope boundary: **ML-LC-05 = NOT STARTED**. ML-LC-04 không tuyên bố weighted là final model; ML-LC-06 mới thực hiện candidate selection.
- Next step: review/sign-off ML-LC-04 trước khi mở ML-LC-05.

## 2026-10-05 — Modeling artifact deduplication

- Đã xác minh `data/processed/modeling/output/` là bản lặp của các artifact ML-LC-03 canonical ở `data/processed/modeling/`; không có source/doc nào tham chiếu thư mục lặp.
- Đã đưa thư mục lặp ra khỏi repository workspace: `D:\ttdltq\data\processed\modeling\output\` → `D:\ttdltq_archive\modeling-output-20261005\` để vẫn có thể khôi phục nếu cần.
- Giữ lại canonical artifacts trong `data/processed/modeling/`, gồm baseline, weighted experiment, manifests, predictions và frozen split IDs. Không xóa hoặc thay đổi canonical data/model.
- Kiểm tra: không còn thư mục `output/` dưới modeling; không còn reference tới path lặp; các binary/CSV/Parquet trùng khớp canonical theo SHA-256. Manifest cũ khác hash vì metadata thời gian chạy, không được dùng làm canonical.
- Next step: chỉ sử dụng `data/processed/modeling/` làm canonical modeling artifact directory.

## 2026-10-06 — ML-LC-05 documentation closeout

- Task/status: **ML-LC-05 = PASS**. TV1 = **PRIMARY OWNER — Modeling**. Đây là documentation closeout cho runtime đã PASS; không retrain và không bắt đầu ML-LC-06.
- Đã ghi nhận đúng một XGBoost candidate trên cùng frozen split: train `807,210`, validation `269,070`; frozen test `269,070` vẫn sealed. Candidate dùng `103` actual input features và `151` transformed features.
- Parameters: `n_estimators=200`, `max_depth=4`, `learning_rate=0.05`, `subsample=0.8`, `colsample_bytree=0.8`, `random_state=42`, `objective=binary:logistic`, `eval_metric=logloss`, `tree_method=hist`, `n_jobs=4`.
- Validation tại threshold tham chiếu `0.5`: ROC-AUC `0.724501`, PR-AUC `0.399256`, precision `0.598674`, recall `0.075614`, F1 `0.134270`, accuracy `0.805326`; confusion matrix `[[212627, 2723], [49658, 4062]]`.
- Runtime **PASS**; tests **PASS**: `tests/models` `61 passed`, `tests/data tests/features` `75 passed`; `compileall` và `git diff --check` PASS. Không chọn threshold, không chọn final model, và frozen test không được dùng để train, predict, evaluate hoặc select.
- Documentation changed: `docs/setup/tv1_setup.md`, `logs/log_tv1.md`. Canonical report/manifest: `reports/tv1_stages/ml-lc-05.md`, `reports/tv1_stages/state/ml-lc-05.json`, `data/processed/modeling/ml_lc_05_manifest.json`.
- Current status: **ML-LC-06 = NOT STARTED**. Next step chỉ là review/sign-off trước khi mở ML-LC-06.

## 2026-10-06 — ML-LC-06 Model Comparison & Candidate Lock

- Task/status: **ML-LC-06 = PASS**. TV1 = **PRIMARY OWNER — Modeling**. So sánh Logistic baseline, Logistic weighted và XGBoost candidate trên cùng `269,070` validation loan IDs/targets; alignment PASS. Frozen test `269,070` dòng vẫn sealed: chỉ kiểm tra file test IDs tồn tại, không đọc nhãn/features, train, predict, evaluate hoặc select trên test.
- Tiêu chí được ghi trong `docs/contracts/model_contract.md` trước runtime: ROC-AUC chính; nếu cách điểm cao nhất không quá `0.002`, xét PR-AUC; nếu PR-AUC cũng cách không quá `0.005`, ưu tiên model đơn giản, sau đó Log Loss/Brier. Log Loss/Brier là chẩn đoán chất lượng PD. Precision/recall/F1/accuracy/confusion tại `0.5` chỉ tham khảo; không dùng threshold này để chọn model. Không có kiểm định ý nghĩa thống kê.
- Validation metrics (ROC-AUC / PR-AUC / Log Loss / Brier): baseline `0.714887 / 0.385307 / 0.451609 / 0.144037`; weighted `0.715097 / 0.384014 / 0.619602 / 0.215452`; XGBoost `0.724501 / 0.399256 / 0.447402 / 0.142595`. Tính lại từ ba prediction artifacts và đối chiếu manifests gốc PASS. Weighted recall `0.655398` tại `0.5` đi kèm `74,088` false positives; không phải bằng chứng ranking tốt hơn.
- Candidate khóa: **`xgboost_candidate`** (`data/processed/modeling/xgboost_candidate.joblib` và `data/processed/modeling/ml_lc_05_xgboost_validation_predictions.parquet`). So với baseline, ROC-AUC `+0.009614`, PR-AUC `+0.013949`; Log Loss `-0.004207`, Brier `-0.001442`. Hai Logistic giữ vai trò baseline/experiment nhưng ranking validation thấp hơn theo quy tắc đã công bố. Đây là candidate cho ML-LC-07, chưa phải final model; `threshold_selected=false`, `final_model_selected=false`.
- Files changed: `src/config.py`, `src/models/evaluation.py`, `src/models/tv1_runner.py`, `tests/models/test_evaluation.py`, `tests/models/test_tv1_runner.py`, `docs/contracts/model_contract.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/setup/tv1_setup.md`, `logs/log_tv1.md`. Outputs: `data/processed/modeling/ml_lc_06_manifest.json`, `reports/tv1_stages/ml-lc-06.md`, `reports/tv1_stages/state/ml-lc-06.json`.
- Validation: focused `19 passed`; full `tests/models` `65 passed`; `tests/data tests/features` `75 passed, 4 warnings` (date parsing TV2); `compileall src tests` PASS; `git diff --check` PASS; real runner `ml-lc-06` PASS. Không retrain model.
- Next step: review/sign-off rồi mới bắt đầu **ML-LC-07 = NOT STARTED** để chọn threshold trên validation.

## 2026-10-06 — ML-LC-07 Validation Threshold Selection

- Task/status: **ML-LC-07 = PASS**. TV1 = **PRIMARY OWNER — Modeling**. Candidate ML-LC-06 `xgboost_candidate`; dùng `269,070` validation predictions đã đối chiếu loan_id/target với frozen validation IDs. Không đọc frozen-test rows/labels/probabilities.
- Selection rule đã ghi trước khi chạy: tối đa F1 chính xác trên prediction scores; F1 cách cực đại không quá `1e-12` là tie, rồi chọn recall cao hơn, precision cao hơn, cuối cùng threshold cao hơn. Đây là operating point thống kê trên validation; không gán business cost, Expected Loss hay lợi nhuận.
- Threshold khóa: **`0.22009515762329102`**. Precision `0.3464526485`, recall `0.6026805659`, F1 `0.4399809744`, accuracy `0.6936930910`; confusion `[[154276, 61074], [21344, 32376]]`.
- So với threshold tham chiếu `0.5`: precision `-0.252220897`, recall `+0.527066270`, F1 `+0.305711079`, accuracy `-0.111632661`, FP `+58,351`, FN `-28,314`. Threshold `0.5` reference: precision `0.5986735446`, recall `0.0756142964`, F1 `0.1342698950`, FP `2,723`, FN `49,658`.
- Artifacts: `data/processed/modeling/ml_lc_07_threshold_table.csv`, `data/processed/modeling/ml_lc_07_manifest.json`, `reports/tv1_stages/ml-lc-07.md`, `reports/tv1_stages/state/ml-lc-07.json`. Model `xgboost_candidate.joblib`, ML-LC-05 predictions và ML-LC-06 manifest giữ nguyên SHA-256; không retrain, không đổi candidate. `threshold_selected=true`, `final_model_selected=false`; frozen-test threshold/evaluation rows bằng `0`.
- Files changed: `src/config.py`, `src/models/evaluation.py`, `src/models/tv1_runner.py`, `tests/models/test_evaluation.py`, `tests/models/test_tv1_runner.py`, `docs/contracts/model_contract.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/setup/tv1_setup.md`, `logs/log_tv1.md`.
- Validation: focused `32 passed`; full `tests/models` `70 passed`; `tests/data tests/features` `75 passed, 4 warnings` (date parsing TV2); `compileall src tests` PASS; `git diff --check` PASS; real `ml-lc-07` runner PASS. `cost_optimization.py` không bị sửa.
- Next step: **ML-LC-08 = NOT STARTED**; chỉ mở frozen test theo task riêng và quy trình đánh giá một lần.

## 2026-10-06 — ML-LC-08 One-shot Frozen Test Evaluation

- Task/status: **ML-LC-08 = PASS** (procedural final evaluation); **TV1 = PRIMARY OWNER — Modeling**. ML-LC-09 = NOT STARTED.
- Khóa trước test: ML-LC-06 chọn `xgboost_candidate` bằng validation; ML-LC-07 chọn threshold `0.22009515762329102` bằng validation F1. Đã xác nhận hai manifest/state PASS, model và lock hashes khớp. Test chỉ dùng cho đánh giá cuối, không fit/retrain, đổi feature, candidate, threshold hoặc selection/tuning.
- Frozen test: `269,070` dòng, `loan_id` unique/non-null, nhãn khớp canonical, không overlap train/validation, xác suất hữu hạn `[0,1]`; predicted class dùng đúng ngưỡng khóa. Runner thực hiện một lần và để one-shot lock; rerun/partial output bị từ chối. Synthetic unit tests không mở test thật.
- Test ROC-AUC `0.7231857765`, PR-AUC `0.3999998160`, Log Loss `0.4477829637`, Brier `0.1426432715`, precision `0.3458766244`, recall `0.6029597915`, F1 `0.4395904159`, accuracy `0.6930650017`; confusion `[[154092, 61258], [21329, 32391]]`.
- Test trừ validation: ROC-AUC `-0.0013150309`, PR-AUC `+0.0007439304`, precision `-0.0005760241`, recall `+0.0002792256`, F1 `-0.0003905585`, accuracy `-0.0006280893`. Hiệu năng khá gần validation; không dùng gap để retune.
- Protected SHA-256 trước/sau giống nhau: model `c1a0ddbff7d857c467553e2aa7260ffaab4a8e56fde106f4ae9b33ce52138d07`, ML-LC-06 `79eeb712131a6e36f9d7cf3889427b994ba42caa2b9679132182fd7e7fdd495d`, ML-LC-07 `f0181c9c7bf13434335074b9875058bc24ea472e8ac85cd2a3f7ae0b8bcf1df4`.
- Code/tests: `src/config.py`, `src/models/tv1_runner.py`, `src/models/frozen_test.py`, `tests/models/test_frozen_test.py`. Artifacts: `data/processed/modeling/ml_lc_08_frozen_test_predictions.parquet`, `ml_lc_08_manifest.json`, `ml_lc_08_one_shot.lock`, `reports/tv1_stages/ml-lc-08.md`, `reports/tv1_stages/state/ml-lc-08.json`. Docs: `docs/setup/tv1_setup.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/contracts/model_contract.md`, `logs/log_tv1.md`.
- Validation trước runtime: focused `11 passed`; full model `81 passed`; data/features `75 passed, 4 warnings` (date parsing TV2); `compileall src tests` PASS; `git diff --check` PASS. Runtime PASS, post-run schema/probability/threshold/hash audit PASS. Không commit/push/chuyển branch.
- Next step: ML-LC-09 Explainability chỉ sau khi review/sign-off; không sửa cấu hình đã khóa theo test.

## 2026-10-06 — ML-LC-09 Model Explainability

- Task/status: **ML-LC-09 = PASS**. TV1 = **PRIMARY OWNER — Modeling**. Dùng cấu hình đã khóa `xgboost_candidate` + threshold `0.22009515762329102`; không retrain, đổi candidate/threshold hoặc quay lại sửa ML-LC-06/07/08.
- Explainability dùng riêng **269,070 validation rows**, stratified sample **5,000** (`random_state=42`, 4,002 target 0 / 998 target 1). Frozen test không được mở/dùng lại. Feature names đã khôi phục và đối chiếu: **103 original / 151 transformed**.
- SHAP **PASS**, `TreeExplainer`, output raw margin/log-odds; additivity max absolute error `3.23e-06`. Model SHA-256 trước/sau bằng nhau: `c1a0ddbff7d857c467553e2aa7260ffaab4a8e56fde106f4ae9b33ce52138d07`. Không diễn giải SHAP như causal effect hoặc điểm phần trăm PD.
- Top 10 original features theo mean absolute SHAP: `term_months`, `loan_to_income_ratio`, `fico_range_low`, `dti`, `issue_year`, `acc_open_past_24mths`, `home_ownership`, `mths_since_recent_inq`, `tot_hi_cred_lim`, `mort_acc`. Hướng numeric được ghi là association với raw-margin contribution; categorical/ít biến thiên ghi rõ không có chiều chung đủ chắc.
- Artifacts: `data/processed/modeling/ml_lc_09_manifest.json`, `ml_lc_09_global_importance.csv` (V05 source với feature gốc), `ml_lc_09_transformed_importance.csv`, `ml_lc_09_local_explanations.csv` (3 validation examples, 30 contributions), `ml_lc_09_shap_sample.parquet` (75,000 long rows cho top 15 features); figures `reports/figures/modeling/ml_lc_09_global_importance.png` và `ml_lc_09_shap_summary.png`; report/state `reports/tv1_stages/ml-lc-09.md`, `reports/tv1_stages/state/ml-lc-09.json`.
- Code/test/docs: `src/models/explainability.py`, `src/models/tv1_runner.py`, `tests/models/test_explainability.py`, `docs/setup/tv1_setup.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/tasks/dashboard-visual-plan.md`, `docs/contracts/model_contract.md`, `logs/log_tv1.md`. V05 source artifacts sẵn sàng; TV3 chưa dựng/integrate visual PBIX.
- Validation trước runtime: focused **7 passed**; full `tests/models` **88 passed**; `tests/data tests/features` **75 passed, 4 warnings** (TV2 date parsing); `compileall src tests` PASS; `git diff --check` PASS. Runtime ML-LC-09 PASS; artifacts/hashes audited. No commit/push/branch switch.
- Next step: **ML-LC-10 NOT STARTED** — chỉ bắt đầu theo task riêng; chưa tạo score/risk tier, EL hoặc final TV3 scoring handoff.

## 2026-10-06 — Dashboard ownership clarification

- Task/status: **DONE**. Ownership của V01 Geographic Risk Map đã chuyển sang TV3; TV1 hiện trực tiếp phụ trách V02–V06.
- TV1 vẫn có thể cross-review V01 khi cần, nhưng không phải primary owner của V01 và không sở hữu Master PBIX.
- Files: `README.md`, `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/tasks/working-protocol.md`, `docs/setup/tv1_setup.md`, `docs/tasks/dashboard-visual-plan.md`.
- Validation: kiểm tra chéo ownership bằng `rg`; chưa thay đổi code, data hoặc model artifacts.
- Next step: TV3 tích hợp V01 vào Master PBIX theo visual plan.

## 2026-10-06 — ML-LC-10 PD Scoring & Risk Tier

- Task/status: **ML-LC-10 = PASS**. TV1 = **PRIMARY OWNER — Modeling**. Dùng 269,070 frozen-test predictions đã đánh giá ở ML-LC-08 để hậu xử lý/reporting; không dùng kết quả test để tune.
- Policy đã ghi trong model contract: `risk_score = 100 * predicted_pd`; `credit_score = round_half_to_even(1000 * (1 - predicted_pd))`, project/model-derived và **không phải FICO**. Tier A/B/C/D lần lượt dùng `< T/2`, `[T/2,T)`, `[T,2T)`, `[2T,1]` với `T=0.22009515762329102`; boundaries `0.11004757881164551`, `0.22009515762329102`, `0.44019031524658203`.
- Kết quả tier (count; mean PD; observed default rate): A **66,275; 7.73%; 6.20%**, B **109,146; 16.03%; 15.78%**, C **80,423; 30.15%; 31.16%**, D **13,226; 51.79%; 55.41%**. Observed rate chỉ là mô tả và không tham gia mapping. V02/V03/V04 data sources READY; Power BI visuals chưa tích hợp.
- Files: `src/config.py`, `src/models/scoring.py`, `src/models/tv1_runner.py`, `tests/models/test_scoring.py`, `docs/contracts/model_contract.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/tasks/dashboard-visual-plan.md`, `docs/setup/tv1_setup.md`, `reports/tv1_stages/ml-lc-10.md`, `reports/tv1_stages/state/ml-lc-10.json`, `data/processed/modeling/ml_lc_10_scored_frozen_test.parquet`, `ml_lc_10_risk_tier_summary.csv`, `ml_lc_10_score_summary.csv`, `ml_lc_10_manifest.json`.
- Validation: focused scoring **18 passed**; `tests/models` **96 passed**; `tests/data tests/features` **75 passed, 4 date-parsing warnings**; `compileall src tests` PASS; `git diff --check` PASS; runner runtime PASS. Hash SHA-256 của model, ML-LC-07/08 manifests và source predictions giữ nguyên. Không retrain; candidate/threshold không đổi. Data dictionary cũng chặn context nếu policy class không thuộc `APPLICATION_TIME`/`CREDIT_SNAPSHOT`.
- Next step: **ML-LC-11 NOT STARTED**; chỉ bắt đầu khi LGD/EAD assumptions được duyệt.

## 2026-10-06 — ML-LC-11 Expected Loss Scenario Analysis

- Task/status: **ML-LC-11 = PASS**; TV1 = **PRIMARY OWNER — Modeling**. Đã dùng PD/risk tier đã khóa từ ML-LC-10 trên 269,070 frozen-test-scored loans; không load/train model, không gọi `predict_proba`, không đổi `xgboost_candidate` hoặc threshold `0.22009515762329102`, không tối ưu threshold theo EL.
- Policy: `EL = predicted_pd × LGD assumption × EAD proxy`. EAD proxy là `loan_amnt` (principal tại application/origination), không phải outstanding exposure thực tế. Baseline LGD 0.45; sensitivity 0.30/0.45/0.60. Đây là **illustrative/project assumptions**, không phải LGD empirical Lending Club, regulatory hoặc bank-policy estimate. Dictionary không xác định currency; các amount giữ nguyên `loan_amnt` source units, không gọi là USD. `target` không tham gia EL formula; chỉ dùng cho observed default rate hồi cứu theo tier.
- Kết quả baseline: total EAD proxy **3,878,248,925** source units; total Expected Loss **372,579,342.19**; average EL **1,384.69/loan**; portfolio EL rate (total EL / total EAD) **9.6069%**. LGD 30/45/60% cho total EL lần lượt **248,386,228.13 / 372,579,342.19 / 496,772,456.26**.
- Theo A/B/C/D: loan count **66,275 / 109,146 / 80,423 / 13,226**; exposure share **22.80% / 37.33% / 33.42% / 6.46%**; EL share **8.21% / 28.21% / 47.89% / 15.69%**. Tier C đóng góp phần EL lớn nhất; Tier D có mean PD cao nhất (51.79%) nhưng EL share 15.69%. Đây là mô tả scenario trên evaluated frozen-test population, không full portfolio hoặc causal claim.
- Artifacts: `data/processed/modeling/ml_lc_11_expected_loss.parquet`, `ml_lc_11_portfolio_el_summary.csv`, `ml_lc_11_risk_tier_el_summary.csv`, `ml_lc_11_manifest.json`; report/state: `reports/tv1_stages/ml-lc-11.md`, `reports/tv1_stages/state/ml-lc-11.json`. V06 đánh dấu DATA READY; Power BI vẫn chờ TV3 integration.
- Code/tests/docs: `src/models/expected_loss.py`, `src/config.py`, `src/models/tv1_runner.py`, `tests/models/test_expected_loss.py`, `docs/contracts/model_contract.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/tasks/dashboard-visual-plan.md`, `docs/setup/tv1_setup.md`, `logs/log_tv1.md`.
- Protected SHA-256 trước/sau giống nhau: model `c1a0ddbff7d857c467553e2aa7260ffaab4a8e56fde106f4ae9b33ce52138d07`; ML-LC-07 manifest `f0181c9c7bf13434335074b9875058bc24ea472e8ac85cd2a3f7ae0b8bcf1df4`; ML-LC-08 manifest `7cc7c453e4af0eedd62ee56f51fd710c8cdf595f11d35acf748e1afcb9d1a188`; ML-LC-10 manifest `270eb7502ed17c0a6192330a040bf6ccdf19fb895d790c12033ff9a311e53099`.
- Validation: focused EL + cost optimization **15 passed**; `tests/models` **103 passed**; `tests/data tests/features` **75 passed, 4 date-parsing warnings** (TV2 existing tests); `compileall src tests` PASS; `git diff --check` PASS; runtime `--stage ml-lc-11` PASS. Determinism, row formula, target isolation, tier/portfolio reconciliation, monotonic LGD sensitivity, and protected hashes checked.
- Next step at that time: ML-LC-12 had not started. No commit/push; current branch was `main`.

## 2026-10-06 — ML-LC-12/13 closeout and canonical modeling summary

- Task/status: **ML-LC-12 = PASS; ML-LC-13 = PASS — satisfied by existing handoff artifacts**. TV1 remains PRIMARY OWNER — Modeling. Current branch `main`; no branch switch, commit or push.
- ML-LC-12: refit locked XGBoost configuration on all **1,345,350** labeled canonical rows (target 0: 1,076,751; target 1: 268,599). Retained 106 approved / exact 103 actual features / 151 transformed features. Configuration unchanged: n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, random_state=42, objective=binary:logistic, eval_metric=logloss, tree_method=hist, n_jobs=4. Fit 79.12 seconds; full-refit SHA-256 `00fbab68eef6a5f5d75b1c6933d6843123c2038613eea327cc30c3851643796e`.
- Artifacts: `data/processed/modeling/xgboost_full_refit.joblib`, `ml_lc_12_full_refit_scores.parquet`, `ml_lc_12_manifest.json`, `reports/tv1_stages/ml-lc-12.md`, `reports/tv1_stages/state/ml-lc-12.json`. The score file is in-sample deployment/demo output. `xgboost_candidate.joblib` and ML-LC-05–11 protected inputs/manifests remained unchanged. Carried-forward threshold `0.22009515762329102` comes from ML-LC-07 validation; no threshold retuning/revalidation. No model selection change and no ML-LC-08 rerun; unbiased metrics remain attached only to evaluated candidate.
- ML-LC-13 audit found existing sources sufficient; no duplicate combined handoff parquet created. V02–V04: ML-LC-10 scored frozen-test artifact; V05: ML-LC-09 global/local/SHAP-specific artifacts; V06: ML-LC-11 Expected Loss sources. Individual prediction contract is ready for 103 named features with preprocessing in the refit pipeline; one-row canonical inference smoke check passed. Power BI is not built/reviewed; handoff readiness is not dashboard completion.
- Consolidated human-readable report: `reports/tv1_stages/modeling_summary.md`; includes 18 requested sections, validation comparison, frozen-test confusion matrix and deltas, SHAP sample/top 10/direction/limitations, scoring tiers, EL scenarios, refit distinction, artifact map and defense Q&A.
- Docs updated: `docs/setup/tv1_setup.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/contracts/model_contract.md`. Modeling roadmap now records ML-LC-01–13 PASS, with explicit handoff-only qualification for ML-LC-13 and TV3 Power BI ownership.
- Validation evidence: focused ML-LC-12/13 tests **2 passed**; `tests/models` **105 passed**; `tests/data tests/features` **75 passed, 4 existing date-parsing warnings**; `python -m compileall src tests` **PASS**; `git diff --check` **PASS**. Compile generated bytecode only; no source/data changes from validation.

## 2026-10-06 — Rewrite dashboard/report/video/storytelling plan

- Task/status: documentation-only planning rewrite; TV1 coordinates storytelling/report, TV2 remains Data Engineering + V07–V09 owner, TV3 remains V01/V10–V12 owner and Master PBIX integrator. No Power BI build/import, visual creation, data/model/code changes, commit or push.
- Rewrote canonical `docs/tasks/dashboard-visual-plan.md`: provisional five-page analytical story, V01–V12 questions/owners/data needs and provisional chart choices, required course-theory review before chart lock, per-visual documentation template, interaction rules, seven-phase build workflow, storytelling spine and observation/interpretation/business implication/limitation standard. Added the required Individual Prediction / Decision Support page without claiming UI exists.
- Rewrote existing `docs/tasks/report-writing-plan.md` as a full-project report plan (front matter and chapters 1–16), report/dashboard/video/defense distinction, 5–8 minute main presentation and narrative/time allocation, and defense preparation. No new planning file created.
- Consistency updates: `docs/tasks/phan-cong-nhiem-vu.md`, `docs/tasks/thanh-vien-1-modeling.md`, `docs/tasks/thanh-vien-3-dashboard.md`, `docs/tasks/defense-knowledge-matrix.md`, `docs/setup/tv3_setup.md`. V01 is TV3-owned; TV1 owns V02–V06; TV2 owns V07–V09; TV3 owns V10–V12 and integrates all visuals. Chart types explicitly remain provisional until lecturer theory review.
- Validation: final repo search found no remaining old Executive Overview/Geographic & Temporal five-page grouping or assignment claiming TV1 owns V01. `git diff --check` result recorded after closeout. No code/data/model artifacts touched.

## 2026-10-06 — Course visualization theory review V01–V12

- Task/status: **DESIGN REVIEW COMPLETE / POWER BI BUILD NOT STARTED**. Review áp dụng message/context/audience, Less is More, data type, granularity/LOD, aggregation, distribution, heatmap, treemap, map, reference line, tooltip, trend và calculated-measure principles từ lecturer theory brief.
- Updated canonical `docs/tasks/dashboard-visual-plan.md` với compact V01–V12 review table, detailed question/source/grain/variables/candidates/pros-cons/recommendation/aggregation/interaction/insight/limitation/story role, page interaction review, storytelling review và unresolved build gates.
- Ownership giữ nguyên: TV1 V02–V06; TV2 V07–V09; TV3 V01 và V10–V12, đồng thời là Master Power BI integrator. Five-page architecture và Individual Prediction / Decision Support page vẫn provisional.
- Review outcome: V01/V02/V03/V05/V06/V09/V11 giữ hướng provisional; V04 cần đổi khỏi raw scatter sang binned/box/violin direction; V07 cần coordinated time views thay combo mặc định; V08 cần grouped/100% stacked bar thay funnel hiện tại vì accepted/rejected là outcome song song; V10 cần binned heatmap/sampled detail thay raw scatter; V12 NEEDS MORE DATA để chốt segment dimension và measure.
- Chưa khóa chart type. Còn chờ lecturer materials đầy đủ, binning/sampling/denominator policy, V08 process semantics, V12 segment specification, V01 map recognition và TV2/TV3 data-model sign-off.
- Validation: review lại canonical docs/contract/reports/artifact semantics và `git diff --check` PASS. Không sửa PBIX, dataset, measure, code hoặc model; không commit/push.
