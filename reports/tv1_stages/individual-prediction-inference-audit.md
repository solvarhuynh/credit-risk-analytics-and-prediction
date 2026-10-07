# Audit khả thi — Individual Prediction / What-if

Trạng thái hiện tại: **INDIVIDUAL_PREDICTION_PROTOTYPE_READY** cho inference cục bộ và ba CSV Power BI-ready. **Trang 6 và kết nối Power BI chưa được dựng.** Các mục 1–9 dưới đây là snapshot audit khả thi *trước* khi triển khai; đọc cập nhật triển khai ở mục 10 cho trạng thái mới, không xem các câu “chưa có wrapper/CSV” trong snapshot là trạng thái hiện hành.

## Cập nhật triển khai prototype — 2026-10-07

- Reusable wrapper/CLI: `src/models/individual_prediction.py`; tests: `tests/models/test_individual_prediction.py`. Dùng full-refit ML-LC-12 với model/canonical SHA-256 kiểm theo manifest, 103 input đúng tên/thứ tự, preprocessing có sẵn. `fetch_baseline` đọc `loan_id` từng Parquet row group để phát hiện 0 hoặc >1 ID, chỉ nạp row group của ID hợp lệ. Không dùng frozen-test output làm input.
- Chỉ bốn override `loan_amnt`, `annual_inc`, `dti`, `term_months`; validate hữu hạn và miền đúng audit. Dùng lại `engineer_lending_club_features` để cập nhật ratio/bands phụ thuộc (kể cả hai override loan/income cùng lúc). Field ngoài tập override/dependency giữ từ borrower baseline. Scoring/tier dùng hàm ML-LC-10; EL dùng `calculate_expected_loss`; local SHAP tính lại trên **đúng scenario hiện hành**, gộp one-hot với helper ML-LC-09, kiểm raw-margin additivity ≤1e-3.
- CLI đã chạy: `.venv\Scripts\python.exe -m src.models.individual_prediction --loan-id 68407277 --loan-amnt 8600`. CURRENT handoff tại `data/processed/dashboard/individual_prediction/`: `individual_prediction_result.csv` 1 row, `individual_prediction_shap.csv` 10 rows, `individual_prediction_inputs.csv` 2 rows (baseline/current), `individual_prediction_manifest.json` có schema/model hash, overrides, dependencies, policies và SHAP check. Directory nằm dưới processed data, được Git bỏ qua; manifest ghi cuối như commit marker, consumer cần đối chiếu `scenario_id` ở các bảng sau refresh. Chưa tạo history.
- Smoke baseline loan 3.600: PD `0.11998604238033295`, class 0, risk score `11.998604238033295`, project credit score 880, Tier B, EL45 `194.37738865613937`. What-if loan 8.600: ratio `0.15636363636363637`, band `5k-10k`, PD `0.14499987661838531`, class 0, risk score `14.499987661838531`, project credit score 855, Tier B, EL45 `561.1495225131512`. Đây là phản ứng model, không phải tác động nhân quả.
- Local SHAP current scenario Top 3 theo |contribution|: `term_months=-0.229906`, `dti=-0.160452`, `fico_range_low=+0.141126` trong raw margin/log-odds; không phải %PD. Additivity <1e-3. Focused `22 passed` (3 SHAP deprecation warnings); regression `tests/models tests/features` `137 passed` (cùng 3 warnings); compileall và `git diff --check` PASS. Chưa có Page 6, Power Query import hay live click-to-infer. User cần import ba CSV một lần sau prototype PASS; hướng dẫn GUI ở `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`.

## 1. Model và ranh giới đánh giá

- Inference: `data/processed/modeling/xgboost_full_refit.joblib` (SHA-256 trong `ml_lc_12_manifest.json`: `00fbab68eef6a5f5d75b1c6933d6843123c2038613eea327cc30c3851643796e`). Object thực tế là sklearn `Pipeline`: `NormalizePandasMissing` → fitted `ColumnTransformer` → `XGBClassifier`. Đầu vào **103 cột có tên và đúng thứ tự manifest**, đầu ra preprocessor **151 cột**. Có 92 numeric (median imputation) và 11 categorical (most-frequent imputation, one-hot `handle_unknown='ignore'`). Model nhận missing ở những cột đã có tên; không có nghĩa missing/unknown là giá trị nghiệp vụ an toàn để người dùng tự tạo.
- `NormalizePandasMissing`/preprocessor **không** tạo lại `term_months`, `fico_avg`, ratio, date parts hay bands. Wrapper phải làm trước khi predict; không truyền `loan_id`, `target`, outcome/post-loan hoặc field lạ vào model. Không dùng `ml_lc_10_scored_frozen_test.parquet` như engine.
- `xgboost_candidate.joblib` + frozen test ML-LC-08 chỉ là bằng chứng đánh giá. Full-refit ML-LC-12 đã fit trên toàn bộ 1.345.350 labeled rows; `ml_lc_12_full_refit_scores.parquet` là in-sample demo scores, không phải hiệu năng test không thiên lệch. Không gán metrics ML-LC-08 cho refit.

## 2. Output contract đã khóa

| Output | Công thức/chính sách | Diễn giải |
|---|---|---|
| `predicted_pd` | `pipeline.predict_proba(X)[:, 1]`, hữu hạn trong `[0,1]` | Xác suất default model dự đoán |
| `predicted_class` | `int(PD >= 0.22009515762329102)` | 1 = dự đoán default; threshold carry-forward, không retune trên refit |
| `risk_score` | `100 × PD` | 0–100, cao hơn = rủi ro dự đoán cao hơn |
| `credit_score` | `np.rint(1000 × (1 − PD))`, half-to-even | Điểm tín dụng **của mô hình**, không phải FICO |
| `risk_tier` | A: `PD < T/2`; B: `T/2 ≤ PD < T`; C: `T ≤ PD < min(2T,1)`; D: `PD ≥ min(2T,1)` | Từ `assign_pd_risk_tier`; cận trái inclusive; T = threshold trên |
| `expected_loss` (tùy chọn) | `calculate_expected_loss(PD, LGD, loan_amnt)` | LGD minh họa 0,30/0,45/0,60; baseline 0,45; `loan_amnt` chỉ là **EAD proxy**, không phải dư nợ khi default. Không gắn tiền tệ khi dictionary không xác nhận. |

Nguồn chuẩn: `src/models/scoring.py`, `src/models/cost_optimization.py`, `src/models/expected_loss.py`, `docs/contracts/model_contract.md`. Đây không phải phê duyệt tín dụng hay mô phỏng nhân quả.

## 3. Phân loại **đúng 103 input**

Danh sách có thứ tự chuẩn nằm tại `data/processed/modeling/ml_lc_12_manifest.json[actual_features]`; bảng dưới là phân loại **không chồng lấn** theo nguồn/khả năng nhập tay. `required` ở cấp API nghĩa là phải có đủ **103 tên cột**, không nghĩa cả 103 giá trị đều non-null. Pipeline có imputer cho cả numeric/categorical, nhưng **không có default nghiệp vụ được duyệt** để tạo một new-applicant giả.

| Nhóm | Số | Tất cả field | Nhập tay? |
|---|---:|---|---|
| Application/business-visible | 11 | `loan_amnt`, `purpose`, `application_type`, `emp_length`, `home_ownership`, `annual_inc`, `verification_status`, `annual_inc_joint`, `verification_status_joint`, `dti`, `dti_joint` | Một số dễ hiểu; verification/joint cần nguồn thực, không cho giá trị mặc định. |
| Derived từ nguồn application/credit/date | 12 | `term_months`, `emp_length_years`, `fico_avg`, `loan_to_income_ratio`, `credit_history_months`, `issue_year`, `issue_quarter`, `issue_month`, `loan_amount_band`, `income_band`, `fico_band`, `dti_band` | Không nên nhập độc lập; tính đồng bộ từ raw/baseline. `term_months` được parse từ raw `term` ở TV2 nhưng raw `term` không còn trong canonical. |
| Credit bureau/account snapshot | 80 | `delinq_2yrs`, `fico_range_low`, `fico_range_high`, `inq_last_6mths`, `mths_since_last_delinq`, `mths_since_last_record`, `open_acc`, `pub_rec`, `revol_bal`, `revol_util`, `total_acc`, `collections_12_mths_ex_med`, `mths_since_last_major_derog`, `acc_now_delinq`, `tot_coll_amt`, `tot_cur_bal`, `open_acc_6m`, `open_act_il`, `open_il_12m`, `open_il_24m`, `mths_since_rcnt_il`, `total_bal_il`, `il_util`, `open_rv_12m`, `open_rv_24m`, `max_bal_bc`, `all_util`, `total_rev_hi_lim`, `inq_fi`, `total_cu_tl`, `inq_last_12m`, `acc_open_past_24mths`, `avg_cur_bal`, `bc_open_to_buy`, `bc_util`, `chargeoff_within_12_mths`, `delinq_amnt`, `mo_sin_old_il_acct`, `mo_sin_old_rev_tl_op`, `mo_sin_rcnt_rev_tl_op`, `mo_sin_rcnt_tl`, `mort_acc`, `mths_since_recent_bc`, `mths_since_recent_bc_dlq`, `mths_since_recent_inq`, `mths_since_recent_revol_delinq`, `num_accts_ever_120_pd`, `num_actv_bc_tl`, `num_actv_rev_tl`, `num_bc_sats`, `num_bc_tl`, `num_il_tl`, `num_op_rev_tl`, `num_rev_accts`, `num_rev_tl_bal_gt_0`, `num_sats`, `num_tl_120dpd_2m`, `num_tl_30dpd`, `num_tl_90g_dpd_24m`, `num_tl_op_past_12m`, `pct_tl_nvr_dlq`, `percent_bc_gt_75`, `pub_rec_bankruptcies`, `tax_liens`, `tot_hi_cred_lim`, `total_bal_ex_mort`, `total_bc_limit`, `total_il_high_credit_limit`, `revol_bal_joint`, `sec_app_fico_range_low`, `sec_app_fico_range_high`, `sec_app_inq_last_6mths`, `sec_app_mort_acc`, `sec_app_open_acc`, `sec_app_revol_util`, `sec_app_open_act_il`, `sec_app_num_rev_accts`, `sec_app_chargeoff_within_12_mths`, `sec_app_collections_12_mths_ex_med`, `sec_app_mths_since_last_major_derog` | Không hợp lý để người xem tự nhập; giữ từ baseline/nguồn credit snapshot thật. FICO low/high là credit snapshot, không phải một ô FICO tự khai. |

11 categorical thực tế: `purpose`, `application_type`, `emp_length`, `home_ownership`, `verification_status`, `verification_status_joint`, `issue_quarter`, `loan_amount_band`, `income_band`, `fico_band`, `dti_band`. 92 numeric còn lại. Categorical lạ sẽ one-hot toàn 0 thay vì báo lỗi — wrapper tương lai nên kiểm vocabulary và từ chối input không hợp lệ. Numeric `NaN` được median-impute, categorical missing được most-frequent-impute; không được dùng tính năng này để làm form 5 field với 98 field bị bỏ trống. Nhóm không có safe business default: ít nhất 80 credit-snapshot fields, cùng `verification_status` và các joint fields khi không có nguồn/baseline; không tự gán 0/`None` theo tưởng tượng.

## 4. Ba cách triển khai

| Cách | Khả thi | Quyết định |
|---|---|---|
| **A — Existing borrower baseline** | Có: `cleaned_dataset.parquet` chứa 103 input + `loan_id` một dòng/khoản vay; thay ít field rồi tính lại dependencies, chạy full-refit. | **Chọn làm trải nghiệm chính**, gọi là scenario/what-if, không gọi là tác động nhân quả. Cần local wrapper cho validation và xuất kết quả. |
| B — Full new-applicant form | Về lý thuyết có thể điền 103 field + nguồn date/derived; 80 field credit snapshot, 11 categorical và domain/missing validation làm Power BI form rất kém tin cậy. | Không khuyến nghị. |
| C — External inference layer/app | Local Python companion/CLI đủ cho demo; Power Apps/API/service live cần thêm writeback, auth, refresh/integration và không hiện có trong bridge. | Dùng **C như thành phần kỹ thuật của A**, không dựng cloud/service ở giai đoạn này. |

Không có cơ chế hiện có để một slicer Power BI tự gửi baseline và tham số đến joblib, nhận response rồi cập nhật visual trong cùng tương tác. Đừng mô tả A như đã có live inference trực tiếp trong PBIP.

## 5. Field được đề xuất cho What-if và dependency

Giới hạn dưới là kiểm soát miền hợp lệ; cận trên `loan_amnt`/`annual_inc`/`dti` là khoảng **quan sát trong canonical** (Parquet statistics), không phải chính sách cấp tín dụng. Kịch bản nằm ngoài vùng quan sát cần cảnh báo hoặc từ chối ở prototype.

| Nhãn | Model field / kiểu | Khoảng và kiểm tra | Phải tính lại |
|---|---|---|---|
| Số tiền vay | `loan_amnt` / float | Hữu hạn, 500–40.000 (khoảng quan sát); >0 | `loan_to_income_ratio`; `loan_amount_band`; `ead_proxy` và EL khi hiển thị. |
| Thu nhập năm | `annual_inc` / float | Hữu hạn, >0 và ≤10.999.200 (max quan sát; 0 là raw có mặt nhưng không dùng cho editable scenario) | `loan_to_income_ratio`; `income_band`. |
| Tỷ lệ nợ/thu nhập | `dti` / float | Hữu hạn, 0–999 (max quan sát; `-1` raw không chấp nhận như entry mới) | `dti_band`. Không tự sửa `annual_inc`/`dti_joint`. |
| Kỳ hạn vay | `term_months` / int | Chỉ 36 hoặc 60 (hai giá trị observed); không nhập nhãn tùy ý | Không có derived feature khác trong 103; nguồn raw `term` không nằm trong canonical/model. |

Không đề xuất ô FICO đơn: model dùng cả `fico_range_low`, `fico_range_high`, `fico_avg`, `fico_band`; muốn thử FICO phải sửa **cặp cận thật** hợp lệ (`low ≤ high`) rồi tái tính avg/band, và ghi rõ chỉ là kịch bản trên credit snapshot, không phải điểm FICO do người dùng tạo. `emp_length` đổi → `emp_length_years`; `issue_d` đổi → `issue_year`, `issue_quarter`, `issue_month` và `credit_history_months`; `earliest_cr_line` đổi → `credit_history_months`. Các date raw không vào 103 nhưng phải có nếu wrapper tái chạy toàn bộ `engineer_lending_club_features`. `sec_app_earliest_cr_line` đã bị loại khỏi 103. Band boundaries/labels giữ nguyên từ `src/features/engineering.py`, không sửa chính sách. Baseline giữ nguyên tất cả field không được user chỉnh; không thay các credit-snapshot field khác để “phù hợp” bằng suy đoán.

## 6. Nguồn baseline và smoke test

Nguồn: `data/processed/cleaned_dataset.parquet`; key `loan_id` non-null/unique, grain một accepted loan có nhãn cuối. Đọc **chỉ** 103 input + nguồn ngày cần cho engineering và key, kiểm đúng một record ID. Không dùng file frozen-test scores hay `ml_lc_12_full_refit_scores.parquet` làm nguồn baseline: chúng là output và không chứa đủ 103 input. Sau này có thể xuất subset demo gọn, có hash/provenance và không bỏ trường; audit này **chưa tạo subset**.

Smoke test đọc một dòng đầu trong row group 0 của canonical, `loan_id=68407277` (ID mẫu, không công bố thông tin định danh cá nhân khác). Model object/feature order, 103→151, một-row predict và domain PD đều PASS. Tái tính toàn bộ engineered features trên baseline từ `issue_d`/`earliest_cr_line` cho kết quả **không khác** các feature lưu sẵn.

| Kịch bản | Input chính | PD | Class | Risk score | Credit score | Tier | EL @45% |
|---|---|---:|---:|---:|---:|---|---:|
| Baseline | `loan_amnt=3.600`, `annual_inc=55.000`, `dti=5,91`, `term_months=36`, `loan_to_income_ratio=0,0654545455`, `loan_amount_band=<=5k` | 0,1199860424 | 0 | 11,99860424 | 880 | Tier B — Moderate | 194,37738866 |
| What-if | **Chỉ đổi `loan_amnt` lên 8.600**; ratio→0,1563636364; band→`5k-10k`; 100 input còn lại giữ nguyên | 0,1449998766 | 0 | 14,49998766 | 855 | Tier B — Moderate | 561,14952251 |

What-if thay 3 **model features** (`loan_amnt`, `loan_to_income_ratio`, `loan_amount_band`) nhưng chỉ 1 input do người dùng đổi. EL thay cả PD lẫn EAD proxy. Đây là phản ứng của model với bản ghi giả định giữ các field khác cố định, **không chứng minh** tăng khoản vay gây tăng default hay tổn thất thật. Output tính từ đúng `predict_proba` của full-refit và các hàm scoring/EL chuẩn; không dùng DAX giả lập dự đoán.

## 7. Giải thích local

**SHAP engine khả thi, phần đóng gói/hiển thị `LOCAL_EXPLANATION_NEEDS_IMPLEMENTATION`.** Trên **chính** baseline và scenario ở trên, `shap.TreeExplainer(full_refit_model, model_output='raw')` sau normalize + fitted preprocess trả một vector 151 contributions; `transformed_feature_mapping` và `aggregate_shap_by_original` trong `src/models/explainability.py` gộp one-hot về 103 input gốc. Additivity error baseline `1,83e-7`, scenario `1,54e-7` (đều <1e-3) so với raw margin. Cần wrapper tính giải thích cho mỗi **record vừa dự đoán**, kiểm model hash, schema, output-space, additivity rồi lấy top dương/âm và lưu cùng scenario ID. Không tái dùng 3 validation local examples ML-LC-09; đó là model/population khác. SHAP là contribution log-odds, không phải điểm phần trăm PD hay quan hệ nhân quả. Chưa viết wrapper trong task này.

## 8. Power BI, runtime và Trang 6 tương lai

Audit dùng `pbi-analysis`/`pbi-model`/`pbi-design`: MCP `list_local_reports` trả **không có Power BI Desktop đang mở**. Bridge hiện có `list_tables`/`describe_table`/DAX truy vấn model đang mở, TOM measure/relationship, PBIR template, nhưng **không có** action gửi slicer state tới local Python/joblib hoặc gọi API inference. Không chỉnh PBIP. Power BI Desktop có slicer chọn record, numeric What-if parameter và DAX `SELECTEDVALUE` để trình bày/lọc; các thứ đó **không** chạy XGBoost. Native text-input form cho 103 field không hiện có trong luồng này. Python/Power Query thường chạy khi refresh, không theo click slicer; Power Apps visual/API có thể là tích hợp tương lai nhưng cần app, writeback/transport, security và kiểm end-to-end. Precomputed scenario table chỉ tái hiện tập kịch bản đã chạy, không phải live what-if.

Luồng prototype cục bộ đề xuất:

1. Companion CLI/app cục bộ nhận `loan_id` + tối đa bốn override trong bảng trên + LGD 0,30/0,45/0,60; chọn baseline từ canonical bằng key. **Chưa có CLI/app này.**
2. Wrapper tương lai xác nhận model/manifest hash, ID duy nhất, đủ 103 cột, dtypes, miền giá trị, category; giữ **mọi field ngoài tập override và dependencies** từ baseline; tái tính feature phụ thuộc bằng logic TV2 và kiểm chỉ những cột dự kiến đổi. Không lắp ghép loan_id/target vào model input.
3. Wrapper gọi `xgboost_full_refit.joblib` → PD; dùng `src/models/scoring.py` cho class/score/tier và `calculate_expected_loss` với EAD proxy = `loan_amnt`; chạy SHAP trên cùng scenario; xuất một kết quả có `scenario_id`, `baseline_loan_id`, `model_version/hash`, overrides, outputs, timestamp và caveat sang CSV/Parquet cục bộ. **Chưa tạo file output.**
4. Power BI `Get Data`/Power Query đọc file kết quả, user bấm **Refresh** sau khi chạy scenario; Trang 6 hiển thị bản ghi mới. Power BI không chủ động gọi wrapper trong kiến trúc tối thiểu; nếu yêu cầu live click-to-infer, cần tích hợp C riêng và phải kiểm quyền, ghi/đọc hai chiều, độ trễ và refresh trước khi hứa khả năng đó.

Trang 6 **spec only**: (A) chọn khoản vay baseline và nhãn “kịch bản trên hồ sơ có sẵn”; (B) bốn input chỉnh được + trạng thái validation/baseline; (C) năm kết quả: **Xác suất vỡ nợ dự đoán**, **Phân loại dự đoán**, **Điểm rủi ro**, **Điểm tín dụng của mô hình** (không ghi FICO), **Hạng rủi ro**; (D) top SHAP dương/âm của đúng scenario, đơn vị raw margin; (E) EAD proxy, LGD assumption và **Tổn thất kỳ vọng**. Business question: “Nếu thay giả định trên một hồ sơ nền, model phản hồi ra sao?” Bố cục từ input → output → explanation → EL giúp người xem nắm kết quả trong vài giây. Không thêm biểu đồ mô tả chỉ để đủ số lượng; nếu vẽ contribution bar sau này, cần audit câu hỏi, lý do chọn, insight có data và mối nối story.

## 9. Kết luận và giới hạn cổng

Architecture READY theo điều kiện task: artifact/schema/formulas/dependencies xác minh từ code + manifest; one-row inference và one-input scenario thực sự PASS; SHAP feasibility smoke PASS; ranh giới Power BI ↔ Python là **local run rồi manual refresh**, không phải live inference. Build prototype vẫn cần triển khai wrapper và kiểm refresh/GUI; không tự bắt đầu ở đây. Không retrain, retune, chạm frozen-test, model/data/TV2/TV3, commit/push/publish.
