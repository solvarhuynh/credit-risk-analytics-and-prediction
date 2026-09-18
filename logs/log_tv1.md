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
