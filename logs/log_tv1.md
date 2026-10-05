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
