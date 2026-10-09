# Protocol nghiên cứu cải thiện F1 — Lending Club

Ngày: 2026-10-09  
Trạng thái: **PILOT PASS; 5-FOLD TRAIN-ONLY OOF PASS; NESTED SEARCH NOT STARTED**

## 1. Phạm vi và bảo vệ kết quả gốc

Đây là nhánh nghiên cứu độc lập cho `target=1 (Default)`. Không ghi đè hoặc đổi tên artifact/manifest ML-LC-03…13, không cập nhật Dashboard/Dash đang dùng, không đọc hoặc đánh giá lại dữ liệu frozen test. Mọi artifact thí nghiệm sẽ nằm tại `data/processed/modeling_experiments/f1_improvement/<experiment_id>/` (được `.gitignore` bỏ qua); protocol, log, summary và mã runner riêng nằm trong `reports/model_experiments/f1_improvement/` và `src/models/experiments/`.

Kết quả trên Validation vốn đã tham gia chọn candidate/ngưỡng ở ML-LC-06/07; vì vậy kết quả thí nghiệm mới trên cùng Validation chỉ là **exploratory comparison**, không phải xác nhận độc lập. Không có một independent holdout mới trong dataset hiện tại. Generalization claim mới cần dữ liệu độc lập/prospective; temporal split trên chính các IDs đã dùng cần được thiết kế riêng và không được gọi là untouched test.

## 2. Baseline đã xác minh, không fit model

Target policy: `Fully Paid → 0`; `Charged Off`/`Default → 1`. Cohort labeled canonical có 1.345.350 dòng, target 0 = 1.076.751, target 1 = 268.599 (positive prevalence ≈19,96%).

ML-LC-02 frozen random stratified split, seed 42: Train 807.210 (target 0: 646.051; target 1: 161.159), Validation 269.070 (215.350; 53.720), Frozen Test 269.070 theo manifest. Train/Validation ID overlap = 0; prediction ID và target của saved XGBoost Validation khớp chính xác `validation_ids.parquet`. Không tìm thấy OOF prediction artifacts.

`xgboost_candidate` input 103 feature, preprocessing tạo 151 transformed features; median imputation numeric, most-frequent imputation + one-hot categorical, preprocessing fit trong pipeline trên train. Fixed config: `n_estimators=200`, `max_depth=4`, `learning_rate=0.05`, `subsample=0.8`, `colsample_bytree=0.8`, `random_state=42`, `objective=binary:logistic`, `eval_metric=logloss`, `tree_method=hist`, `n_jobs=4`; không early stopping. Saved full-fit runtime 38,93 giây trên máy hiện tại.

Metric `PR-AUC` trong repo là `average_precision_score` (Average Precision). Đối chiếu lại trực tiếp từ artifact **Validation** đã lưu:

| Đánh giá XGBoost | Threshold | ROC-AUC | Average Precision | Log Loss | Brier | Precision | Recall | F1 | Accuracy | TN / FP / FN / TP |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Tham chiếu tại 0,5 | 0,5 | 0,724501 | 0,399256 | 0,447402 | 0,142595 | 0,598674 | 0,075614 | 0,134270 | 0,805326 | 212.627 / 2.723 / 49.658 / 4.062 |
| Ngưỡng ML-LC-07 đã chọn trên Validation | 0,22009515762329102 | 0,724501 | 0,399256 | 0,447402 | 0,142595 | 0,346453 | 0,602681 | 0,439981 | 0,693693 | 154.276 / 61.074 / 21.344 / 32.376 |

Frozen Test reference giữ nguyên theo ML-LC-08 manifest: ROC-AUC 0,723186; Average Precision 0,400000; F1 0,439590. Không đọc prediction/row của test cho baseline lần này. Validation positive prevalence 19,965%; baseline class imbalance không tự chứng minh nguyên nhân F1 thấp. XGBoost ranking, xác suất PD và thresholded F1 là ba thuộc tính khác nhau.

Các candidate lịch sử ở threshold chẩn đoán 0,5: Logistic baseline ROC-AUC 0,714887, AP 0,385307, F1 0,146917, Log Loss 0,451609, Brier 0,144037; weighted Logistic ROC-AUC 0,715097, AP 0,384014, F1 0,431958, Log Loss 0,619602, Brier 0,215452; XGBoost như bảng trên. Weighted Logistic cho thấy recall/F1 tại 0,5 có thể tăng cùng lúc với xác suất PD kém hơn; nó không được xem như solution tự động.

SHA-256 trước thí nghiệm: model `c1a0ddbff7d857c467553e2aa7260ffaab4a8e56fde106f4ae9b33ce52138d07`; Validation prediction `f3d22238ad755e05f734b2eb192e4844d415c4a02a82bf7d04519682678f2496`. Locked F1/ROC/PR và Frozen Test values không được ghi lại đè.

## 3. Leakage và validity gate

Feature policy loại identifiers/target/policy-derived/post-loan/unknown khỏi 103 input. Repo hiện không có source dictionary chính thức với timestamp cho từng field. `issue_d` tạo `issue_year/quarter/month`; nhiều bureau/account variables, gồm `chargeoff_within_12_mths` và `delinq_amnt`, chưa có bằng chứng ngày snapshot. Chưa có feature nào được chứng minh là post-outcome trong model input, nhưng chưa thể xác nhận toàn bộ feature có trước thời điểm quyết định.

Vì vậy, thí nghiệm được phép tiếp tục ở mức **exploratory research only** trên chính 103 approved inputs và phải giữ cảnh báo `TIME AVAILABILITY NOT FULLY VERIFIED`. Không thêm feature engineering tương tác ở lần đầu. Nếu TV1/TV2 xác nhận bất kỳ input nào post-decision, dừng tìm kiếm với feature đó và cần duyệt schema/protocol model revision trước khi fit. Kết quả không được diễn giải là model sẵn sàng chấm hồ sơ tại thời điểm cấp tín dụng.

## 4. Stage 2 proposal — train-only OOF và controlled search

### A. Threshold-only potential

Tạo 5-fold Stratified OOF predictions cho incumbent XGBoost với hyperparameters đã khóa. Mỗi fold fit imputer/encoder/model chỉ trên 4/5 train folds và dự đoán fold còn lại. Tính F1/Precision/Recall/TP/FP/TN/FN/predicted-positive rate trên pooled OOF tại ngưỡng, vẽ Precision/Recall/F1 theo threshold, và báo fold-to-fold variability. Chọn threshold thí nghiệm bằng train-only OOF với quy tắc tie-break đã ghi rõ; so với T*=0,220095 nhưng không dùng Validation để chọn.

### B. XGBoost + class-weight search

Sau pilot runtime, chạy nested, stratified CV **chỉ bên trong original Train**: 3 outer folds; mỗi outer fold dùng 3-fold inner CV để chọn hyperparameters từ tối đa 5 cấu hình randomized, cố định seed. Inner search xếp candidate theo F1 trên inner OOF với threshold được chọn từ inner OOF; outer fold đo kết quả candidate + threshold đã chọn mà không tham gia fitting/selection. Tie-break F1 → Recall → Precision → ngưỡng cao hơn. Ghi thêm ROC-AUC, Average Precision, Log Loss, Brier, precision, recall, accuracy, confusion, predicted-positive rate, fit/inference time và độ phân tán giữa các outer folds.

Search space ban đầu hẹp, giới hạn tài nguyên: `n_estimators {150,250,350}`, `max_depth {3,4,5}`, `learning_rate {0.03,0.05,0.08}`, `min_child_weight {1,5,10}`, `subsample {0.7,0.85,1}`, `colsample_bytree {0.7,0.85,1}`, `gamma {0,0.5,1}`, `reg_alpha {0,0.1,1}`, `reg_lambda {1,5,10}`, `max_delta_step {0,1,3}`, và `scale_pos_weight {1,2,3,4}`. Không thử tích Descartes đầy đủ. Dùng CPU `hist`, `n_jobs=4`; không early stop trên outer holdout hoặc Validation. Các weight value là candidates, không giả định `negative/positive` là tối ưu.

Outer OOF cung cấp ước lượng ổn định trên Train. Với final experimental candidate, threshold được mang theo là median của ba threshold do inner OOF chọn trong ba outer folds; không tính threshold từ outer held-out labels. Sau khi search/candidate protocol được khóa, fit duy nhất một experimental candidate trên toàn original Train, ghi mã run/config/feature list bất biến, và đánh giá đúng một lần trên original Validation. Do Validation đã được dùng lịch sử để chọn ML-LC-06/07, ghi rõ lần này là dữ liệu được tái sử dụng cho so sánh exploratory. Không phản hồi Validation rồi chạy vòng tuning tiếp theo. Không dự đoán/đánh giá Frozen Test.

### C. Calibration, feature engineering, error analysis

Ở lượt đầu, so sánh raw PD và train-only cross-fitted sigmoid/Platt, isotonic chỉ nếu fold sample đủ lớn. Fit calibrator chỉ từ train OOF, ghi Brier/Log Loss, reliability curve và calibration intercept/slope; không dùng Validation/Test để fit. Trước khi chạy calibration extension, thiết kế fold pairing sao cho calibration và threshold scores không được đánh giá trên chính các rows đã fit calibrator. Nếu điều đó đòi hỏi nested extra fits, báo lại compute trước.

Không thêm tương tác/feature mới cho tới khi xác nhận decision-time provenance. Error analysis dùng outer OOF predictions, nhóm FICO/DTI/LTI/term/origination year; xuất cỡ nhóm, minimum N=500, không suy luận nhân quả.

## 5. Pilot và ước lượng tài nguyên

Máy kiểm tra hiện tại: AMD Ryzen 7 7840HS, 8 core/16 logical processor; RAM 27,8 GB, lúc kiểm tra còn khả dụng khoảng 12,7 GB; ổ D còn 486,3 GB; Python packages XGBoost 3.4.1, scikit-learn 1.9.1. Không có GPU XGBoost được cấu hình. Baseline ML-LC-05 fit 807.210 dòng/103 input mất 38,93 giây với `n_jobs=4`.

| Giai đoạn | Số lần fit dự kiến | Ước lượng thời gian |
|---|---:|---:|
| Pilot 1 fit trên một train fold (khoảng 430–650 nghìn rows) | 1 | 1–3 phút gồm load/preprocess |
| A. Incumbent 5-fold OOF | 5 | 5–10 phút tổng |
| B. Nested search: 3 outer × (5 config × 3 inner + 1 outer refit + 3 OOF cho threshold) + final fit | tối đa 58 | khoảng 45–90 phút, phụ thuộc cấu hình/IO |
| Calibration extension | chưa chốt | chưa chạy cho tới khi protocol/concurrent RAM được đánh giá sau pilot |

Peak RAM rough estimate: 8–16 GB, **chưa benchmark**; có thể vượt khi DataFrame copies và preprocessing folds đồng thời còn resident. Lưu tối đa một fold/pipeline hoạt động; không parallelize CV folds/search. Pilot phải đo wall-time và process WorkingSet/PrivateMemory; dừng nếu free RAM xuống dưới 5 GB hoặc process vượt 16 GB. Sau pilot cập nhật ước lượng trước khi mở rộng. Nếu runtime pilot >3 phút hoặc peak >12 GB, thu hẹp còn 2 outer × 2 inner × 3 config và đánh dấu exploratory/low precision, hoặc dừng.

## 6. Trạng thái Stage 1 / Pilot

- Đã đối chiếu baseline/Validation predictions/target, Train–Validation disjointness, model config, feature pipeline, current artifact hashes và class distribution.
- Không có OOF artifact; threshold curves theo training OOF cần fit cross-validation.
- Feature time availability chưa được xác nhận; Stage 2 chỉ được gọi là exploratory research.
- Pilot đã được khởi chạy một lần nhưng dừng trước khi có xác nhận bắt đầu `pipeline.fit()`: system commit-memory counter đạt 98%, kích hoạt stop tại 95%. RAM khả dụng nhỏ nhất quan sát 8.663 MB; paging input lớn nhất 94 pages/sec, dưới stop threshold. Process Working Set/Private Memory không được đo đúng nên không có process peak; không có model result/artifact. Chi tiết ở `reports/model_experiments/f1_improvement/pilot-20261009.md`.
- Do pilot chưa fit, không có thời gian fit thực tế và ước lượng 5-fold OOF 5–10 phút / nested search 45–90 phút vẫn chưa được hiệu chỉnh. Monitor process-tree nay đã được sửa và kiểm thử tổng hợp; vẫn không chạy Stage B cho đến khi một lượt pilot được hoàn tất an toàn và chi phí tài nguyên được cập nhật.

### Bổ sung chẩn đoán monitor — 2026-10-09

Monitor process-tree đã được sửa và kiểm thử tổng hợp; nguyên nhân system commit 98% trong pilot cũ vẫn chưa được xác định. Snapshot preflight read-only trước đó đạt guardrails nhưng không đại diện lần chạy sau. Chi tiết lịch sử tại `reports/model_experiments/f1_improvement/monitor-diagnosis-20261009.md`. Chưa nạp Train, không fit, không đổi Stage B.

Lần thử tiếp theo theo yêu cầu người dùng trên `pilot-20261009-04` **không đạt preflight**: sample đầu đã ghi RAM khả dụng 4,38 GiB và system commit 96,92%; cực trị lần đo 3,70 GiB / 98,65%. Paging counters của phiên bản monitor lúc chạy đều thiếu; không có `CHILD_STARTED` và không đọc Train/fit. Monitor hiện đã được sửa để fail-fast, yêu cầu paging counters hợp lệ, và đo đúng 120 giây theo thời gian thực; chưa chạy lại. Pilot vẫn BLOCKED tới một preflight mới đạt.

Run `pilot-20261009-05` sau đó **đạt preflight**, load đúng 807.210 Train rows × 103 inputs rồi bị monitor dừng trong `PREPROCESSING` vì available RAM xuống 4,323 GiB. `FIT_START` không được ghi, không có bằng chứng model fit chạy và không có result/model artifact. Không tiếp tục retry sau hard stop. Xem `monitor-diagnosis-20261009.md`.

Run `pilot-20261009-06` cũng đạt preflight nhưng dừng trong `PREPROCESSING`: available RAM thấp nhất 4,585 GiB; last completed phase `DATA_LOADED`; không có `FIT_START`, fit, hay result/model artifact. Không tiếp tục retry hoặc Stage B/OOF. Preprocessing hiện tại không an toàn dưới hard-stop 5 GiB trên máy này; cần phương án giảm peak-memory được xem xét trước, không nới guardrails. Chi tiết telemetry trong `monitor-diagnosis-20261009.md`.

### Kết quả mới nhất — Pilot và Stage A OOF (2026-10-09)

Sau khi giữ nguyên toàn bộ hard stop, pilot runner được tối ưu thành preprocessing theo batch với CSR disk-backed. `pilot-20261009-11` hoàn tất một fit trên Train: 807.210 rows × 103 inputs → 151 transformed features; fit **20,18 giây**. Không scoring/đọc Validation/Frozen Test. RAM khả dụng thấp nhất 9,119 GiB; process-tree Working Set đỉnh 5,857 GiB; private commit đỉnh 8,188 GiB; system commit đỉnh 64,03%.

Theo yêu cầu tiếp tục lấy kết quả Stage 2, đã chạy đúng 5-fold stratified Train-only OOF, sequential, seed 42, incumbent parameters; thời gian toàn run 342,66 giây gồm preflight. OOF threshold tối ưu là 0,2106764764, pooled OOF F1 0,440015; áp dụng threshold ML-LC-07 0,2200951576 lên cùng OOF rows cho F1 0,439440. Chênh lệch chỉ +0,000575 và F1 tại threshold đã chọn có selection optimism; không chứng minh uplift độc lập. ROC-AUC 0,723362, AP 0,399711, Log Loss 0,447826, Brier 0,142646. OOF artifact/analysis chi tiết: `reports/model_experiments/f1_improvement/oof-20261009.md`.

Stage A OOF PASS; nested hyperparameter search **chưa chạy**. Frozen Test vẫn sealed; Validation không đọc; model/artifact chính không đổi. Cần xác nhận riêng trước nested search theo compute protocol; không được coi threshold-only OOF là F1 uplift đã xác nhận.
