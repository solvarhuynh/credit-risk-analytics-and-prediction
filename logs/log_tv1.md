# Log công việc — TV1 (Modeling)

Chỉ append entry mới theo quy trình trong docs/tasks/working-protocol.md.

## 2026-09-13 — TV1-SEC-DE — Secondary Data Engineering review

- **Trạng thái:** blocked
- **Đã làm:**
  - Review schema/grain/cardinality và nguyên tắc aggregate-before-join cho các bảng application và history.
  - Review calculated fields contract và shortlist feature application/history phục vụ Modeling.
  - Chạy pre-training quality-gate review ở mức static; canonical model input chưa sẵn sàng.
  - Chốt nguyên tắc leakage: historical feature phải có source/formula/as-of-time; preprocessing statistic chỉ fit trên train fold.
- **File thay đổi:** `docs/logs/log_tv1.md`
- **Kiểm tra:** đối chiếu `data_contract.md`, task TV1/TV2 và trạng thái pipeline/canonical artifacts.
- **Blocker:** TV2 chưa bàn giao `data/processed/cleaned_dataset.parquet` và `data/processed/data_dictionary.csv` cùng join/quality audit.
- **Next step:** Chờ TV2 hoàn thành canonical Data Engineering handoff, sau đó chạy lại Join Review + Feature Review + Model Input Quality Gate trước khi Modeling.

## 2026-09-13 — Setup handoff guide

- **Trạng thái:** done
- **Đã làm:** tạo hướng dẫn môi trường, prerequisite, trạng thái lệnh chạy và validation cho phần Modeling.
- **File thay đổi:** `docs/setup/tv1_setup.md`, `docs/logs/log_tv1.md`.
- **Kiểm tra:** đối chiếu model contract, trạng thái canonical input và rule setup/handoff.
- **Next step:** Cập nhật lệnh train ngay sau khi canonical model input và modeling script được bàn giao.

## 2026-09-14 — TV1-M01 — Modeling development/final refit policy

- **Trạng thái:** done
- **Đã làm:** Chốt fixed stratified development split với `random_state` tường minh và dùng cùng development population cho mọi candidate model; frozen test chỉ chạy một lần sau khi khóa model/features/hyperparameters/threshold để làm metric chính; cho phép final production refit trên toàn bộ labeled canonical dataset sau đánh giá; xác nhận `application_test` không phải training data và realtime inference tách biệt với retraining.
- **File thay đổi:** `logs/log_tv1.md`
- **Kiểm tra:** Đối chiếu task TV1-M01, `data_contract.md`, `model_contract.md`, architecture/risk docs và skeleton trong `src/models/`, `src/config.py`; không train, không fit preprocessing, không tạo data/metric giả.
- **Next step:** TV1-M02 — Preprocessing pipeline skeleton.

## 2026-09-14 — TV1-M02 — Preprocessing pipeline skeleton

- **Trạng thái:** done
- **Đã làm:** Tạo factory `build_preprocessor` và validation `validate_modeling_columns` nhận feature roles từ caller; numeric imputation/scaling có thể bật tắt, categorical imputation/OneHotEncoder an toàn với category mới; chặn TARGET, ID và các modeling output khỏi feature list. Transformer chỉ được build, không fit trong module.
- **File thay đổi:** `src/models/preprocess_pipeline.py`, `logs/log_tv1.md`
- **Kiểm tra:** Syntax/import, smoke build và tiny in-memory fit/transform bao gồm unknown category; không dùng canonical/raw project data, không train model.
- **Next step:** TV1-M03 — Split & reproducibility utilities.

## 2026-09-14 — TV1-M03 — Split & reproducibility utilities

- **Trạng thái:** done
- **Đã làm:** Tạo `create_development_split` cho fixed stratified Train/Validation/Test split với seed tường minh; tách `SK_ID_CURR` ra khỏi X để audit, trả metadata về số dòng/phân phối TARGET và chặn schema, target, ID hoặc split ratio không hợp lệ. Module không fit preprocessing và không train model.
- **File thay đổi:** `src/models/data_split.py`, `logs/log_tv1.md`
- **Kiểm tra:** Syntax/import và tiny in-memory fixture kiểm tra deterministic, union/no-overlap, stratification và validation errors; không dùng canonical/raw project data, không tạo model metric.
- **Next step:** TV1-M04 — Model evaluation utilities.

## 2026-09-14 — TV1-M04 — Binary classification evaluation utilities

- **Trạng thái:** done
- **Đã làm:** Tạo API đánh giá binary từ `y_true`, `y_proba` và threshold: ROC AUC, precision, recall, F1, accuracy bổ sung, confusion matrix và dữ liệu ROC/PR; thêm validation-only threshold table và helper so sánh model. Module không gọi model hoặc tối ưu threshold trên test.
- **File thay đổi:** `src/models/evaluation.py`, `logs/log_tv1.md`
- **Kiểm tra:** Syntax/import và tiny in-memory fixture cho perfect prediction, probability/threshold invalid, confusion matrix và metric keys; không dùng canonical/raw project data, không tạo model metric.
- **Next step:** TV1-M05 — Credit scoring utilities.

## 2026-09-14 — TV1-M05 — Credit scoring utilities

- **Trạng thái:** done
- **Đã làm:** Tạo utility validate PD, đổi PD/log bad-to-good odds, quy đổi score theo PDO scheme có cấu hình và gán risk tier theo threshold/label tường minh. Chưa chọn PDO, base odds, score bounds hay tier policy cuối; PD 0/1 được epsilon clipping để không sinh giá trị vô hạn.
- **File thay đổi:** `src/models/scoring.py`, `logs/log_tv1.md`
- **Kiểm tra:** Syntax/import và PD fixture kiểm tra chiều score, clipping/finite, score boundary, PD invalid và tier boundary; không dùng canonical/raw project data, không train model.
- **Next step:** TV1-M06 — Expected Loss & cost utilities.

## 2026-09-14 — TV1-M06 — Expected Loss & cost utilities

- **Trạng thái:** done
- **Đã làm:** Tạo utility vectorized tính Expected Loss (PD × LGD × EAD), tổng EL danh mục và đánh giá một threshold policy đã chọn. LGD/EAD luôn là input explicit, Series alignment/missing/range được kiểm tra; module không coi EL là profit và không tối ưu threshold trên test.
- **File thay đổi:** `src/models/cost_optimization.py`, `logs/log_tv1.md`
- **Kiểm tra:** Syntax/import và tiny numeric fixture kiểm tra công thức, zero PD/LGD/EAD, range invalid và finite output; không dùng canonical/raw project data, không tạo business result.
- **Next step:** WAIT FOR TV2 CANONICAL DATA → rerun Model Input Quality Gate.

## 2026-09-18 — TTD-WF-01 — Canonical log path normalization

- **Trạng thái:** done
- **Đã làm:** chuẩn hóa canonical owner logs thành logs/log_tv*.md; cập nhật .cursor/rules/02-quan-ly-file-va-log.mdc và docs/setup/tv2_setup.md; bảo toàn nguyên vẹn các entry lịch sử trong logs/.
- **File thay đổi:** `.cursor/rules/02-quan-ly-file-va-log.mdc`, `docs/setup/tv2_setup.md`, `logs/log_tv1.md`.
- **Kiểm tra đã chạy:** ripgrep kiểm tra toàn repo xác nhận không còn active reference nào trỏ tới docs/logs/; git diff --check; git status --short.
- **Next step:** TTD-WF-02 — Establish regression tests for implemented reusable modules.

## 2026-09-18 — TTD-WF-02 — TV1 regression test suite

- **Trạng thái:** done
- **Đã làm:**
  - Thiết lập regression test suite độc lập với canonical dataset cho 5 reusable modeling modules trong `tests/models/`: `test_preprocess_pipeline.py`, `test_data_split.py`, `test_evaluation.py`, `test_scoring.py`, `test_cost_optimization.py`.
  - Thêm dependency `pytest>=7.4,<9` vào `requirements.txt`.
  - Giữ nguyên 100% production source logic trong `src/models/`, không đổi business/model policy.
  - Cập nhật lệnh validation `pytest tests/models -q` vào `docs/setup/tv1_setup.md`.
- **File thay đổi:** `requirements.txt`, `docs/setup/tv1_setup.md`, `tests/__init__.py`, `tests/models/__init__.py`, `tests/models/test_preprocess_pipeline.py`, `tests/models/test_data_split.py`, `tests/models/test_evaluation.py`, `tests/models/test_scoring.py`, `tests/models/test_cost_optimization.py`, `logs/log_tv1.md`.
- **Kiểm tra đã chạy:**
  - `python -m pytest tests/models -v`: 53/53 tests passed (0 failed).
  - `python -m py_compile` kiểm tra cú pháp toàn bộ file test và source.
  - `git diff --check` và `git status --short`.
- **Next step:** WAIT FOR TV2 CANONICAL DATA → Model Input Quality Gate.

## 2026-09-22 — TV1-AUDIT-DE — Review TV2 canonical data handoff

- **Trạng thái:** done with FAIL gate / HIGH review items
- **Git range reviewed:** merge `6749975` (`Merge pull request #1 from solvarhuynh/tv2`), TV2 first parent `30659ab`, TV2 range `30659ab..22b9fc6`; 27 files changed, no processed Parquet committed.
- **Đã làm:** reviewed source-of-truth docs, rules, TV1/TV2 logs, TV2 diff, loader/cleaning/features/aggregation/build/quality-report code, join grain, temporal constraints, canonical Parquet, data dictionary and manifest. The supplied `data/processed.zip` was preserved; its artifact was compared with a fresh pipeline regeneration.
- **Kết quả:** canonical pipeline command succeeded (`307,511 x 203`, target `{0: 282,686; 1: 24,825}`, unique `SK_ID_CURR`, no null/duplicate key, no infinity). Regenerated output was semantically equivalent to the supplied artifact; byte hash differed because Parquet serialization changed. Data dictionary had 203/203 entries, 22 metadata columns, no duplicates or measured metadata mismatches. `-999` remains in 474 numeric cells without documented sentinel semantics; `DAYS_REGISTRATION` and `DAYS_ID_PUBLISH` dictionary entries incorrectly report no missing values. Manifest row/column/hash/size cross-checks passed, but its serialized schema labels differ from read-back pandas dtypes and it omits self-hash/version fields; branch/base commit are hard-coded historical provenance.
- **File thay đổi:** `logs/log_tv1.md`; ignored regenerated artifacts under `data/interim/` and `data/processed/` are local validation outputs; untracked `data/processed.zip` was not modified or removed.
- **Kiểm tra đã chạy:** `python -m pytest tests/data tests/features -q` → 142 passed; `python -m src.data.build_pipeline` → SUCCESS; `python -m src.data.quality_report` → PASS WITH WARNINGS; `git diff --check` (no whitespace errors, line-ending warning only). No model training, SMOTE, model preprocessing fit, dashboard change, commit or push.
- **MODEL_INPUT_GATE:** FAIL until the unresolved `-999` sentinel semantics/handling and related dictionary documentation are reviewed; grain, target and pipeline reproducibility gates pass.
- **Next step:** Fix the highest-severity Data Engineering blocker and rerun this gate.

## 2026-09-22 — TV1-AUDIT-DE re-review decision

- **Trạng thái:** `MODEL_INPUT_GATE = PASS_WITH_WARNINGS`.
- **Quyết định:** re-review xác nhận `-999` là giá trị ngày tương đối hợp lệ trong 8 cột được phát hiện, không phải sentinel cần thay thế. Sau khi TV2 sửa ngữ nghĩa `INSTAL_LATE_RATE`, integrity merge bureau, path/provenance manifest và tái tạo artifacts, dataset đạt grain/target/schema/dictionary/infinity gates.
- **Kiểm tra chứng cứ:** 147 tests data/features passed; canonical rebuild và quality report hoàn tất; 307,511 × 203, `SK_ID_CURR` unique/non-null, TARGET `{0: 282686, 1: 24825}`, dictionary 203/203 thống kê khớp và manifest current run chứa `main`/HEAD động.
- **Cảnh báo giao cho Modeling:** review bằng pipeline chỉ fit trên train fold các phân phối đuôi dài hợp lệ (`CREDIT_TO_INCOME_RATIO`, `INSTAL_PAYMENT_RATIO_MEAN`, một số ít `CC_UTILIZATION_MEAN` âm); không phải blocker Data Engineering.
- **Ownership:** implementation fixes do TV2 thực hiện; entry này chỉ ghi nhận quyết định re-review của TV1.
- **Next step:** bắt đầu TV1 modeling theo `model_contract.md`.

## 2026-09-22 — TV1-MASTER Gates A–B — Canonical input and leakage-safe feature boundary

- **Trạng thái:** done.
- **Đã làm:** tái kiểm tra trực tiếp canonical snapshot TV2 và chấp nhận dataset 307,511 × 203, SHA-256 `6460999371297ff2f83418a8341b0c85d4a2e4dc6c29b29e793edd2a0c755c96`; định nghĩa `y=TARGET`, loại `SK_ID_CURR` và toàn bộ output downstream cấm khỏi `X`, giữ 184 numeric + 17 categorical feature có role dictionary hợp lệ.
- **Kiểm tra:** key unique/non-null, target `{0: 282686, 1: 24825}`, infinity = 0, dictionary 203/203, manifest hash/schema/current provenance khớp.
- **File thay đổi:** `.gitignore`, `TV1_AGENT_RUNBOOK.local.md` (ignored), `logs/log_tv1.md`.
- **Next step:** Gate C — freeze 80/20 development/frozen-test split trước khi fit bất kỳ preprocessing hoặc model nào.

## 2026-09-23 — TV1-MASTER — Gated modeling pipeline and TV3 handoff

- **Trạng thái:** done — Gates A–Q PASS.
- **Đã làm:** khóa split 80/20 (`seed=20260922`), chọn `xgboost_depth6` bằng development-only CV, khóa threshold OOF F1 = `0.16`, đánh giá frozen test đúng một lần, sau đó refit production pipeline trên toàn bộ 307,511 dòng labeled và xuất handoff cho TV3.
- **Kết quả frozen test:** ROC-AUC `0.780060`; PR-AUC `0.270385`; Precision `0.272622`; Recall `0.426586`; F1 `0.332653`; confusion matrix `[[50887, 5651], [2847, 2118]]`.
- **Artifacts:** `models/full_inference_pipeline.joblib` và `data/processed/scored_dataset.parquet` (ignored local artifacts); `reports/model_card.md`, `reports/model_integration_profiles.csv`, `reports/figures/modeling/`.
- **Kiểm tra:** full suite `206 passed`; production verification PASS; `git diff --check` PASS.
- **Next step:** TV3 consumes `scored_dataset.parquet` and `model_integration_profiles.csv`; TV2 may consume held-out outputs only if a fairness task is explicitly authorized.

## 2026-09-23 — TV1-MASTER — Post-sync verification

- **Trạng thái:** done — verification PASS.
- **Đã làm:** đồng bộ commit modeling lên nền `origin/tv1`; xác nhận gated modeling outputs và frozen-test record vẫn khớp canonical snapshot.
- **Kiểm tra:** `pytest -q --basetemp .pytest_tmp_full` → **209 passed**, 6 cảnh báo deprecation từ thư viện seaborn/matplotlib; `pytest tests/models -q --basetemp .pytest_tmp_tv1` → **61 passed**; `python -m src.models.modeling_pipeline --verify-only` → `SUCCESS`, deterministic và unknown-category safe đều `true`, 307,511 dòng.
- **File thay đổi:** `logs/log_tv1.md`.
- **Next step:** push branch `tv1`; chờ TV3 đối soát integration profiles và TV2 thực hiện DE-08.

## 2026-09-23 — DOC-MD-VI — Hoàn tất dịch hai báo cáo TV2

- **Trạng thái:** done
- **Đã làm:** chuyển `reports/data_quality_report.md` và `reports/eda_report.md` sang tiếng Việt; giữ nguyên đường dẫn, lệnh chạy, mã cột, category raw, số liệu, checksum và artifact.
- **Kiểm tra:** 6 code fence cân bằng; `pytest tests/data/test_quality_report.py -q --basetemp .pytest_tmp_tv2` → **19 passed**; `git diff --check` đạt.
- **Next step:** tiếp tục duy trì log TV1 khi có thay đổi modeling; log cập nhật setup TV2 nằm tại `logs/log_tv2.md`.

## 2026-09-23 — FINAL-REVIEW-FIX — Cross-owner handoff and production-artifact review

- **Trạng thái:** done — TV2_FIX_GATE = PASS; TV1_GATE = PASS_WITH_WARNINGS.
- **Đã review/sửa:** xác nhận không có global numeric `-999` replacement, late-payment denominator chỉ dùng timing hợp lệ, bureau merge one-to-one, root-relative paths và manifest provenance. Bugbot phát hiện Gate Q trước đây chỉ báo cáo inference không deterministic và có thể chấp nhận score artifact stale; đã sửa để fail closed, đối chiếu full-population PD/threshold/recommendation/model version với artifact loaded, và lưu frozen-test record versioned cùng hashes artifact. Manifest hiện ghi rõ dirty worktree và hash patch thay vì gán nhầm output local vào một commit clean.
- **File thay đổi chính:** `src/data/build_pipeline.py`, `src/models/modeling_pipeline.py`, tests data/model liên quan, `.gitignore`, `reports/frozen_test_evaluation_record.json`, `docs/setup/tv1_setup.md`, `docs/setup/tv2_setup.md`, `reports/model_card.md`.
- **Kiểm tra:** `pytest -q --basetemp .pytest_tmp_final_review` → 209 passed (6 third-party deprecation warnings); `compileall -q src` → PASS; canonical rebuild và quality report được chạy lại; `--verify-only` → PASS với deterministic=true và unknown category safe=true.
- **Giới hạn:** LGD/EAD, score tiers và threshold vẫn là technical assumptions; frozen record binds local ignored artifacts by hash, nên handoff artifact phải được chuyển ngoài Git cùng record/model card.
- **Next step:** Commit các nhóm đã review lên đúng branch owner và tạo PR để cross-review trước khi bất kỳ thay đổi nào vào `main`.
