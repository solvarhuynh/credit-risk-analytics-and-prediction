# Kiểm toán toàn bộ mô hình theo Chương 9 — HCMUTE

Ngày kiểm toán: 09/10/2026. Phạm vi: trạng thái **worktree hiện tại**, không phải một bản phát hành đã khóa. Đây là kiểm toán đọc dữ liệu/artifact và kiểm tra tĩnh; không huấn luyện lại, không chọn lại ngưỡng và **không chạy lại đánh giá frozen test**. `PASS` dưới đây chỉ áp dụng cho điều đã đối chiếu trực tiếp; kiểm tra giao diện Power BI bằng Desktop được đánh dấu riêng.

Tài liệu học thuật đã đọc: `C:\Users\Nghia\Downloads\GSV_Chuong09_mohinhdubao.pdf` (53 trang). Text của tất cả trang đã được trích xuất; các trang nhiều hình/ít text (14–15, 32–35) không được diễn giải quá nội dung trích xuất. Số trang dưới đây là số trang **PDF**, không phải số slide in trên trang.

## A. Kết luận điều hành

**Mô hình chính có chuỗi bằng chứng hợp lý**: nhãn default đúng chiều, split rời nhau, preprocessing nằm trong pipeline fit trên train, ba candidate so sánh cùng validation, ngưỡng 0,220095 chọn trên validation, frozen test có kết quả one-shot được lưu, SHAP và EL dùng công thức/đơn vị đã mô tả. Chưa thấy bằng chứng đảo nhãn, lấy nhầm `predict_proba[:, 0]`, hay dùng rejected làm non-default.

**Không đồng nghĩa sẵn sàng triển khai tín dụng thật.** Ba rủi ro cần xử lý: (1) bằng chứng nghiệp vụ về *thời điểm khả dụng* của 103 feature chưa đủ để xác nhận không leakage tuyệt đối, nhất là các cột credit-snapshot và `issue_year`; (2) Dash demo có nhãn “Threshold tham chiếu tối ưu” dù 0,220095 được tối ưu cho mô hình **103-input**, không tối ưu riêng cho hai mô hình 6-input; (3) bản PBIR master hiện có đường dẫn nguồn tuyệt đối sang máy `D:\Huy\...`, không có tệp `.pbip` trong thư mục và `pages.json` liệt kê 10 trang, nên không thể xác nhận bản Power BI mở/refresh đúng tại `D:\ttdltq` hay phù hợp kế hoạch 4 trang. Đây là rủi ro tích hợp, **không phải bằng chứng model tính sai**.

Không phát hiện P0 đã được chứng minh. Có P1 về diễn đạt ngưỡng và tính khả dụng/đồng bộ Power BI; có P2 về thiếu diagnostic tương tác và mâu thuẫn tài liệu. Phần chỉ được xác nhận bằng manifest/code được ghi rõ, không nâng thành xác nhận vận hành GUI.

## B. Inventory: không gộp ba vai trò model

| Vai trò / artifact | Input → transformed | Fit / nguồn metric | Mục đích và giới hạn |
|---|---:|---|---|
| `logistic_baseline.joblib` | 103 → 151 | Train 807.210; validation 269.070, ngưỡng tham chiếu 0,5 | Baseline, `class_weight=None`, L2/lbfgs/max_iter=1000. |
| `logistic_weighted.joblib` | 103 → 151 | Cùng train/validation; tham chiếu 0,5 | `class_weight='balanced'`; không SMOTE, không tăng số dòng dữ liệu. |
| `xgboost_candidate.joblib` | 103 → 151 | Cùng train/validation; được chọn ML-LC-06; frozen test một lần ML-LC-08 | Mô hình **được đánh giá**; source V02–V06. SHA-256 `c1a0ddbff7d857c467553e2aa7260ffaab4a8e56fde106f4ae9b33ce52138d07`. |
| `xgboost_full_refit.joblib` | 103 → 151 | Fit sau đánh giá trên toàn bộ 1.345.350 labeled rows; **không có unbiased test metric riêng** | Inference/demo; SHA-256 `00fbab68eef6a5f5d75b1c6933d6843123c2038613eea327cc30c3851643796e`. Điểm trên full-refit là in-sample. |
| `xgboost_6input_demo.joblib` | 6 → 11 | Train 807.210; **validation** 269.070; không mở frozen test | Demo cá nhân; SHA khớp manifest `d17953f7...a51bae8d7ea`. |
| `logistic_6input_demo.joblib` | 6 → 11 | Cùng train/validation; không mở frozen test | Demo đối chiếu; SHA khớp manifest `f08a475a...e161dbc2b1`. |

Tất cả sáu artifact trên được nạp **read-only** bằng `joblib.load`: đều là `sklearn.pipeline.Pipeline`, đều có `classes_=[0,1]`; Logistic/XGBoost chính gồm `normalize_missing → preprocess → model`; demo 6-input còn có `sanitize` trước đó. Code inference lấy `predict_proba(...)[:, 1]`, không áp sigmoid lần thứ hai. Demo 5-input vẫn tồn tại trong kho nhưng là lịch sử riêng, **không** trộn metric frozen-test cũ của nó vào bản demo 6-input.

## C. Truy vết pipeline và population

| Chặng | Code/entry point | Input → output / grain | Kết quả xác minh / khả năng tái lập |
|---|---|---|---|
| Raw/clean/label | `src/data/build_pipeline.py::run_build_pipeline`, `prepare_accepted_batch`; `src/data/cleaning.py::derive_target` | Accepted/rejected CSV tách riêng → business tables + canonical labeled theo `loan_id` | Raw files tồn tại; manifest ghi accepted 2.260.701, rejected 27.648.741 (**không đếm lại toàn bộ CSV**). `Fully Paid=0`, `Charged Off`/`Default=1`; Current/Late/Grace/missing/legacy unresolved bị loại khỏi labeled cohort. |
| Feature/policy | `src/features/engineering.py::engineer_lending_club_features`; `src/data/column_policy.py` | 106 policy-approved → 103 actual inputs; 151 sau one-hot | 17 `APPLICATION_TIME`, 86 `CREDIT_SNAPSHOT` trong artifact; không có `TARGET_SOURCE`/`POST_LOAN` trong 103. Không chứng minh thời điểm nghiệp vụ chỉ bằng tên class. |
| Split | `src/models/data_split.py`, `src/models/tv1_runner.py::run_ml_lc_02` | Canonical 1.345.350 → train 807.210, validation 269.070, test 269.070 | Đọc trực tiếp Parquet: ID trong từng split duy nhất; giao từng cặp rỗng; hợp đúng canonical; target từng ID khớp. Stratified random seed 42; **không** phải out-of-time. |
| Candidate/train | `src/models/tv1_runner.py::run_ml_lc_03/04/05/06` | Train fit preprocessing/model; validation dùng so sánh | Logistic thường, weighted, XGBoost cùng cohort và target. XGBoost 200 trees, depth 4, eta 0,05, subsample/colsample 0,8, `binary:logistic`, `hist`, seed 42; **không** early stopping, scale_pos_weight, SMOTE hoặc calibration fit. |
| Ngưỡng | `src/models/evaluation.py::select_validation_threshold`, `tv1_runner.py::run_ml_lc_07` | Validation XGBoost candidate → `T*=0.22009515762329102` | Max F1, tie-break recall → precision → threshold; chỉ ML-LC-07 chọn. `y_hat = 1` khi `PD >= T`, kể cả bằng ngưỡng. |
| Test/score | `src/models/frozen_test.py::run_ml_lc_08`; `src/models/scoring.py`; `src/models/expected_loss.py` | 269.070 test rows → prediction/score/tier/EL | Lock và manifest xác nhận một đợt final evaluation; lần audit này **chỉ đọc manifest**, không tính metric lại từ test. V02–V06 dùng evaluated cohort, không phải toàn bộ portfolio. |
| Giải thích | `src/models/explainability.py::run_ml_lc_09` | 5.000 mẫu stratified **validation** → global/local SHAP | Raw margin/log-odds, additivity error trong manifest `3,23e-6`; không phải %PD. V05 không nên chịu slicer của frozen-test. |
| Inference | `src/models/final_model.py::run_ml_lc_12` và `src/models/demo_6input.py::predict_six_demo` | Full-refit 103-input cho inference chính; hai demo 6-input riêng cho form | Cùng công thức score/tier/EL nhưng **khác model và training scope**. Demo 6-input không đại diện hiệu năng 103-input. |
| Hiển thị | `src/models/tv1_dashboard_data.py`, PBIR trong `reports/figures/dashboard/`, Dash `apps/individual_prediction_dash/` | Fact evaluated 269.070; SHAP validation; Dash demo validation | Data artifacts truy được; PBIR chỉ kiểm tĩnh do entry `.pbip`/đường dẫn nguồn đang có vấn đề. |

Canonical Parquet có **1.345.350 dòng, 113 cột**, `loan_id` không null/trùng, `target` không null: 0 = 1.076.751; 1 = 268.599. `data_dictionary.csv` có 113 dòng. Mỗi split cũng có tỉ lệ positive gần 19,965%. `modeling_summary.md:11` viết **107 cột** là sai so với Parquet và split manifest **113**; 106 ở cùng đoạn là số *feature được policy duyệt*, không phải tổng cột canonical.

### Feature provenance và leakage gate

| Feature/nhóm | Nguồn và thời điểm cần xác minh | Risk | Bằng chứng hiện có | Hành động |
|---|---|---|---|---|
| `loan_status`, payment/recoveries/last payment | Kết quả sau khoản vay | Cấm dùng | `cleaning.py`, `column_policy.py` gắn target/post-loan; vắng khỏi `feature_names_in_` | Giữ gate hiện có. |
| `loan_amnt`, `annual_inc`, `purpose`, `term_months`, `home_ownership` | Hồ sơ/application | Thấp nếu snapshot tại quyết định | Trong nhóm 17 application-time; xuất hiện trong model và demo | Ghi thời điểm và phiên bản dữ liệu nguồn. |
| `fico_range_low/high`, `fico_avg`, `dti` và 86 credit-snapshot fields | Bureau/credit snapshot tại quyết định **chưa có timestamp per-field** | Trung bình | Policy xếp `CREDIT_SNAPSHOT`; dictionary chỉ có dtype/class/grain, **không có source timestamp** | Xin định nghĩa gốc/snapshot; review từng field theo thời điểm quyết định. |
| `chargeoff_within_12_mths`, `delinq_amnt`, `sec_app_chargeoff_within_12_mths` | Lịch sử tín dụng hay sự kiện của chính khoản vay? Cần xác nhận bằng nguồn Lending Club | Cao nếu sau quyết định | Được xếp `CREDIT_SNAPSHOT`, không có mô tả nguồn trong dictionary; chưa có bằng chứng chúng là leakage, cũng chưa đủ bằng chứng phủ định | P1: lưu source semantics và kiểm snapshot-date trước khi tuyên bố leak-free. |
| `issue_year/quarter/month` từ `issue_d` | Ngày phát hành; có thể biết sau quyết định cấp tín dụng | Cao cho use case *pre-origination* | `engineering.py` tạo từ `issue_d`; hiện class `APPLICATION_TIME`; SHAP `issue_year` đứng thứ 5 | Định nghĩa prediction time: nếu trước phát hành, dùng application timestamp hợp lệ hoặc đánh giá lại chính sách feature (task sau, không sửa ở audit). |
| `loan_to_income_ratio`, `fico_band`, `dti_band`, `credit_history_months` | Derived từ input/snapshot | Phụ thuộc nguồn | Code kiểm denominator >0, missing FICO, lịch sử âm; `right=False` cho band FICO | Bảo đảm inference dùng cùng công thức và version; audit source fields. |

Train-only median imputation/scaling và most-frequent/one-hot `handle_unknown='ignore'` nằm trong pipeline; model fit trên train. Feature **policy selection** dựa trên quy tắc/tên cột trước split, không thấy statistical selection fit toàn dữ liệu. Tuy nhiên raw schema/data dictionary cũng không thay thế hồ sơ feature-availability. Không suy ra “không leakage tuyệt đối” chỉ từ unit test.

## D. So sánh Logistic, weighted Logistic, XGBoost

Các số này là **Validation 269.070** trong `ml_lc_06_manifest.json`; mọi confusion có dạng `[[TN,FP],[FN,TP]]` và ngưỡng **0,5**. Đã đối chiếu số hàng và các tỉ số trong manifest; không chạy model lại.

| Model | ROC-AUC | PR-AUC | Log Loss | Brier | Precision | Recall | F1 | Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Logistic | 0,714887 | 0,385307 | 0,451609 | 0,144037 | 0,562454 | 0,084494 | 0,146917 | 0,804096 |
| Weighted Logistic | 0,715097 | 0,384014 | 0,619602 | 0,215452 | 0,322134 | 0,655398 | 0,431958 | 0,655852 |
| XGBoost | 0,724501 | 0,399256 | 0,447402 | 0,142595 | 0,598674 | 0,075614 | 0,134270 | 0,805326 |

Weighting làm tăng recall ở **cùng ngưỡng 0,5**, nhưng làm giảm precision và làm Log Loss/Brier xấu hơn; nó thay đổi loss, **không cân bằng số dòng**. XGBoost hơn Logistic baseline **0,009614 ROC-AUC** và **0,013949 PR-AUC**, cải thiện nhỏ, không “áp đảo”. F1 XGBoost thấp ở 0,5 không tự chứng minh ranking kém. Candidate được chọn bằng quy tắc validation trong ML-LC-06, sau đó ML-LC-07 mới chọn ngưỡng cho **candidate đó**. Không so F1 weighted tại 0,5 với F1 XGBoost tại 0,2201 như phép so sánh model công bằng.

ML-LC-07 validation ở T*: precision 0,346453; recall 0,602681; F1 0,439981; confusion `[[154276,61074],[21344,32376]]`. ML-LC-08 **frozen test** ở T*: ROC-AUC 0,723186; PR-AUC 0,400000; Log Loss 0,447783; Brier 0,142643; precision 0,345877; recall 0,602960; F1 0,439590; confusion `[[154092,61258],[21329,32391]]`. Test là một lần final evaluation theo lock/manifest; audit này không chứng minh bằng log hệ thống độc lập rằng từ trước đến nay chưa từng có lần test khác.

ROC-AUC đo khả năng xếp hạng; PR-AUC hữu ích khi default là lớp thiểu số; F1/confusion là hiệu năng tại **ngưỡng**; Log Loss/Brier là sai số xác suất trên population. Không chỉ số nào là “sai số ±% của một người”. Random holdout không chứng minh generalization theo thời gian. Calibration chưa được fit, do đó PD phải gọi là *xác suất mô hình ước tính*, không tự nhận đã được hiệu chuẩn hoàn hảo.

## E. Model evaluation khác model analysis

| Mục tiêu / biểu đồ | Hiện có và tính hợp lệ | Nơi trình bày hợp lý / bổ sung không trùng lặp |
|---|---|---|
| **Evaluation:** ROC/PR | `reports/figures/modeling/roc_curve.png`, `pr_curve.png`; ML-LC-06/08 metrics lưu theo split; chưa render kiểm nội dung hai PNG ở audit này | Báo cáo Ch.4 + một slide so sánh cùng validation; ghi rõ test riêng. |
| **Evaluation:** confusion/FP/FN | Manifest lưu TN/FP/FN/TP; Dash chỉ so actual cho **preset nguyên bản**, chưa có confusion matrix toàn validation động | Báo cáo/slide dùng frozen-test matrix đã khóa; Dash Details có thể dùng **validation** predictions đúng model để làm ma trận theo slider. |
| **Evaluation:** metric theo threshold | ML-LC-07 có `ml_lc_07_threshold_table.csv` cho candidate; Dash slider đổi class và màu, nhưng F1/Precision/Recall vẫn tĩnh (được ghi nhãn đúng) | Dash Details: nếu thêm thì tính từ toàn bộ labeled validation predictions theo model đang chọn, không từ 120 điểm trang trí; không tối ưu lại threshold. |
| **Evaluation:** calibration | Hàm `logic.py::build_calibration_figure` có bin 10%, x=mean PD, y=observed rate, y=x, fixed axes [0,1], gắn cờ bin <500; **UI chính hiện không gọi biểu đồ này** | Ch.4 hoặc Dash Details (mở rộng), ghi bin count/cohort; render browser cần xác minh sau. Trục âm/ >100% của phiên cũ không xuất hiện trong cấu hình code hiện tại. |
| **Evaluation:** subgroup reliability | Chưa thấy artifact chuẩn hóa theo FICO/DTI/term/home/year với cỡ nhóm và uncertainty | Ch.4 nếu có đủ cỡ mẫu; không tuyên bố fairness hay causal effect. |
| **Analysis:** V02 PD distribution, V03 tier | PBIR có fact evaluated và measures; không đo model tốt hay sai | Trang risk của Power BI; kể câu chuyện phân phối → phân khúc. |
| **Analysis:** V04 FICO–PD, V13 loan/income–PD | PBIR có table/measure/visual; diễn giải association trên cohort, không chứng minh model/biến gây ra default | Trang borrower risk, tránh lặp plot với cùng câu hỏi. |
| **Analysis:** V05 global SHAP | 5.000 mẫu validation, mean absolute SHAP raw margin; Top 3: `term_months` 0,315463, `loan_to_income_ratio` 0,159380, `fico_range_low` 0,156027 | Trang model explanation; tách khỏi slicer evaluated cohort. |
| **Analysis:** local contribution + EL sensitivity | Dash dùng đúng model 6-input đang chọn; XGB TreeSHAP raw margin, Logistic `coef × transformed input` log-odds **không phải SHAP**; EL ở LGD 30/45/60% | Dash cá nhân; đổi tên trục/chú thích để rõ log-odds và phân biệt Logistic coefficient contribution. |

## F. Ma trận tuân thủ Chương 9

`PASS` = đối chiếu được code/artifact; `PARTIAL` = có nhưng thiếu hiển thị/giới hạn; `BLOCKED` = chưa kiểm Desktop/nguồn; `N/A` = không bắt buộc cho binary classification.

| Trang PDF | Nguyên lý | Repo / bằng chứng | Status | Vấn đề → hành động | Ưu tiên |
|---|---|---|---|---|---|
| 5–10 | Data → model → dự báo → trực quan → quyết định | `build_pipeline.py`, `tv1_runner.py`, Dash, PBIR | PARTIAL | Chuỗi code đầy đủ; Power BI runtime chưa xác minh → kiểm PBIP/refresh. | P1 |
| 11–27 | Linear residual/MSE | Bài toán default nhị phân | N/A | Không ép residual plot hồi quy tuyến tính thành tiêu chí logistic. | — |
| 28–30 | Nhãn và xác suất lớp 1 | `cleaning.py:63`, `predict_proba[:,1]`, artifact `classes_=[0,1]` | PASS | Ghi rõ `1=Default`; không nhầm logit/SHAP với PD. | — |
| 28–30 | Logistic sigmoid | `modeling_pipeline.py`, Logistic artifact | PASS | Hệ số/odds ratio nếu trình bày phải xét scaling/one-hot. | — |
| 36–38 | PD và threshold là hai đại lượng | `evaluation.py:100`, `logic.py:51`, Dash slider | PASS | Slider chỉ đổi nhãn/visual; giữ PD/score/tier/EL cố định. | — |
| 37–43 | Confusion TN/FP/FN/TP | ML-LC-07/08 manifest, `logic.py:62` | PARTIAL | Matrix có trong artifact nhưng chưa có visual toàn validation động. | P2 |
| 41–43 | Precision/Recall/F1 trade-off | `ml_lc_07_threshold_table.csv`; Dash static metric có ghi ngưỡng | PARTIAL | Có table, chưa có biểu đồ metric theo slider trong app. | P2 |
| 46 | Split → fit → predict proba → evaluate | split IDs, `preprocess_pipeline.py`, `tv1_runner.py` | PASS | Random holdout, không out-of-time; giữ giới hạn này khi thuyết trình. | P2 |
| 47 | Probability/class distribution | V02/V03 PBIR; Dash probability plot | PARTIAL | Dữ liệu có; Desktop render/refresh chưa xác minh. | P1 |
| 47 | Calibration/sai số xác suất | ML-LC-06/08 Brier/Log Loss, `logic.py:178` | PARTIAL | Hàm plot đúng trục nhưng chưa hiện trên UI chính; chưa chứng minh calibration thật. | P2 |
| 48–49 | Chọn hồ sơ → PD → threshold → lỗi → hành động | `app.py` callbacks, 8 preset đúng validation | PARTIAL | Dynamic class/preset error có; dynamic *population* confusion chưa có; ngưỡng demo bị gọi “tối ưu”. | P1 |
| 50 | Giới hạn/uncertainty | Docs, UI tooltips, EL caveat | PARTIAL | Bổ sung cohort/time drift, không coi score demo là quyết định tín dụng thực. | P2 |
| 5–10, 50 | Model–dashboard consistency | PBIR TMDL + `ml_lc_10/11` manifests | BLOCKED | Nguồn tuyệt đối máy khác, thiếu PBIP entry, 10 pages; cần mở Desktop/refresh thật. | P1 |

## G. Dash demo 6-input: nguồn, tương tác, lỗi tiềm ẩn

Hai model 6-input dùng **cùng** train/validation, cùng `target`; features theo thứ tự `loan_amnt`, `annual_inc`, `dti`, `term_months`, `fico_avg`, `home_ownership`, thành 11 cột sau preprocessing. `fico_score` form đi vào `fico_avg`, **không tính lại từ FICO low/high** vì đây là một model demo độc lập; không được trình bày là chạy model 103-input từ sáu ô. DTI sử dụng thang `24` cho 24%, **không** `0,24`; code validate dti ≥0, thu nhập >0, kỳ hạn 36/60 và bounds từ train; category form chỉ OWN/MORTGAGE/RENT dù model đã thấy cả các category rất hiếm.

Validation prediction files của hai demo đều có **269.070** ID, cùng bộ `validation_ids`, không giao với `test_ids`; SHA-256 model/prediction/validation IDs khớp manifest. Vì vậy việc validation và test cùng số dòng **không phải** dấu hiệu đổi nhãn test. XGBoost 6-input: ROC-AUC 0,685266; PR-AUC 0,349475; F1 0,403591, Brier 0,148171. Logistic 6-input: ROC-AUC 0,677361; PR-AUC 0,341154; F1 0,399090, Brier 0,149154. F1 của hai demo được tính tại **ngưỡng mượn** 0,220095 từ ML-LC-07; không phải tối ưu riêng trên validation demo.

Tám preset tại `logic.py:39–48` đều có ID trong validation, target và **cả sáu giá trị** khớp canonical. PD theo thứ tự preset (XGB / Logistic): `6925546` 0,024990/0,037165 (TN/TN); `77570711` 0,080000/0,096874 (TN/TN); `126453130` 0,160002/0,132676 (TN/TN); `34954120` 0,220100/0,213388 (FP/TN); `67266660` 0,449971/0,401599 (TP/TP); `94290852` 0,650346/0,582469 (TP/TP); `92214524` 0,350001/0,372360 (FP/FP); `96513927` 0,100000/0,105213 (FN/FN). Đây là mô tả **ở ngưỡng tham chiếu**; khi người dùng kéo ngưỡng, FP/TN/TP/FN có thể đổi. `app.py::_form_matches_preset` không hiện nhãn thật nếu sửa một trong sáu giá trị; chọn model khác cập nhật prediction/metric. Không dùng tám preset suy ra accuracy tổng thể.

Slider [0,1] với `>=`: ở 0, mọi PD hợp lệ bị cảnh báo; ở 1 chỉ PD đúng 1 bị cảnh báo; `PD=T` thuộc cảnh báo. `app.py:291–350` tách classification/visual ngưỡng khỏi `result-store`; `render_outputs` đọc payload và LGD, không đọc slider, nên PD/score/tier/SHAP/EL không đổi khi chỉ kéo ngưỡng. Risk tier cố định theo policy T*: A `<0,1100475788`, B `[0,1100475788;0,2200951576)`, C `[0,2200951576;0,4401903152)`, D `>=0,4401903152`; **risk tier không phải decision class slider**. `risk_score=100×PD`; `project_credit_score=round(1000×(1−PD))`, khác FICO.

Visual threshold hiện dùng **120 PD validation lấy mẫu cố định** (code `logic.py:291`), không chứa nhãn thật trong plot; số “cần cảnh báo” trong plot là của 120 điểm, **không phải** confusion/flagged count của toàn 269.070. Static ROC/PR/F1/Brier/Log Loss đọc manifest đúng model và có ghi là Validation/không đổi theo slider. Calibration code thiết lập trục x/y `[0,1]`, đường y=x, bin theo PD, cảnh báo bin <500; plot hiện không xuất hiện trong app layout/callback chính. Không thể kết luận browser render tuyệt đối đúng nếu chưa mở UI.

SHAP XGB dùng `TreeExplainer(model_output='raw')`, additive margin; Logistic dùng `coef × transformed input` cộng vào intercept, là **linear contribution**, không phải TreeSHAP. Cả hai được gộp từ 11 cột về sáu input, kiểm additivity `≤1e-3`; UI gọi chung “đóng góp”, nhưng trục `Đóng góp vào dự đoán` chưa nêu đơn vị log-odds. EL demo = PD đúng model × LGD (0,30/0,45/0,60) × `loan_amnt` EAD proxy, không phải realized loss; đổi threshold không đổi EL, đổi LGD không đổi PD. `amount_unit` trong ML-LC-11 chỉ xác nhận *đơn vị gốc của loan_amnt*, chưa xác nhận currency trong dictionary.

## H. Power BI: kiểm tĩnh, chưa chứng nhận Desktop

Trong `reports/figures/dashboard/credit_risk_master_dashboard.SemanticModel/definition/tables/`, `fact_evaluated_loan.tmdl` có measures `Evaluated Loan Count`, `Mean PD`, `Observed Default Rate Test`, `Risk Tier Share`, `Total Expected Loss`, `EL Contribution %`. Fact lấy `ml_lc_11_expected_loss.parquet` của frozen-test evaluated cohort; SHAP lấy artifact validation riêng. V02 phân phối PD, V03 tier, V04 FICO–PD, V05 global SHAP, V06 EL và V13 ratio–PD có PBIR definitions; **đây là xác nhận file tĩnh**, không phải xác nhận render đúng hay interaction trong Desktop. `relationships.tmdl` không join SHAP sample với fact evaluated; lại có auto relationships SHAP sample↔global feature và local rank↔global rank, cần review filter direction/grain trước khi tuyên bố không ảnh hưởng chéo.

Rủi ro tích hợp cụ thể: `pages/pages.json` liệt kê **10** page IDs, trong khi `docs/tasks/dashboard-visual-plan.md` mô tả **4 trang**; các page TV1 riêng có thể là trang staging nhưng chưa được ẩn/loại khỏi pageOrder. Thư mục hiện tại **không có `.pbip` entry file**; `nghia.pbip` cũ đang ở trạng thái deleted trong git. M-query của `fact_evaluated_loan.tmdl:320` và các table khác trỏ về `D:\Huy\HCMUTE\...`, không phải `D:\ttdltq`; trên máy hiện tại khả năng refresh lỗi. `*Measure table.tmdl:36,39` còn hard-code `Top Purpose="Debt Consolidation"`, `Peak Year=2015`; visual tại page `420b.../visuals/9c147.../visual.json` tham chiếu `Peak Year`, nên đây không phải metric động dưới filter. Chưa kiểm Desktop runtime, interaction và screenshot; status **BLOCKED** cho các câu hỏi đó.

Giữ story 4 trang theo plan; ROC/PR/confusion/calibration có thể ở Ch.4, slide hoặc Dash Details, không ép thêm vào Power BI business pages. Không diễn giải observed default rate như PD; không dùng SHAP validation như thể cùng population với V02–V06.

## I. Vấn đề và mức ưu tiên

| ID | Mức | Phát hiện có chứng cứ | Hệ quả / giới hạn kết luận |
|---|---|---|---|
| F01 | **P1** | `app.py:603` ghi “Threshold tham chiếu tối ưu” cho demo 6-input; ngưỡng đến từ validation model chính (`ml_lc_07_manifest.json`), demo manifests ghi carried-forward | Giảng viên dễ hiểu lầm đây là optimum cho cả XGB/Logistic 6-input. Đây là **lỗi ngữ nghĩa UI**, không làm PD sai. |
| F02 | **P1** | PBIR master thiếu `.pbip`, M-query `D:\Huy\...`, `pages.json` 10 IDs vs kế hoạch 4 | Không thể xác nhận mở/refresh/dashboard nhất quán; phải kiểm và sửa trong task Power BI riêng. |
| F03 | **P1, chưa chứng minh leakage** | `issue_year` từ `issue_d`, 86 `CREDIT_SNAPSHOT` chỉ được policy gắn nhãn, dictionary không có snapshot timestamp | Chưa đủ bằng chứng phục vụ chấm điểm **trước phát hành**; review availability trước claim deploy. Không tự loại feature/retrain trong audit. |
| F04 | **P2** | Dash dùng 120 điểm không nhãn cho threshold plot; ML-LC-07 table có threshold diagnostics; validation predictions đầy đủ cho demo | Chưa thấy population-level dynamic confusion/Precision/Recall/F1 theo slider, nhưng static metrics có nhãn đúng. |
| F05 | **P2** | `modeling_summary.md:11` 107 cột; canonical và split manifest 113 | Tài liệu sai số cột, dễ lẫn 106 approved với 103 actual. |
| F06 | **P2** | `logic.py:336–369` trục local contributions không ghi log-odds; `demo_6input.py:425–438` Logistic là coefficient contribution, không phải SHAP | Dễ bị đọc như %PD hoặc cùng thuật toán giải thích. |
| F07 | **P2** | `*Measure table.tmdl:36,39` hard-code Top Purpose/Peak Year; `Peak Year` được visual dùng | Dễ sai dưới filter/refresh; cần measure động hoặc ghi là annotation cố định. |
| F08 | **P3** | Model validation là random holdout và dữ liệu 2007–2018 | Cần ghi giới hạn temporal drift; không gọi kết quả này out-of-time. |

## J. Kế hoạch xử lý có điều kiện nghiệm thu

| Thứ tự | Lý do / file sẽ tác động trong task sau | Retrain? / evaluation mới? / frozen test? | Độ khó / acceptance test |
|---|---|---|---|
| 1. Correctness ngữ nghĩa | Sửa `apps/individual_prediction_dash/app.py` nhãn thành “Ngưỡng tham chiếu từ model chính” ở chi tiết demo; phân biệt ngưỡng kéo và metric validation cố định | Không / không / không | Thấp; UI và test kiểm cả XGB/Logistic không còn chữ “tối ưu” gắn với demo. |
| 2. Feature availability gate | Bổ sung source/time provenance vào data/model contract và feature audit cho `issue_d`, `chargeoff_within_12_mths`, `delinq_amnt`, các bureau fields | Có thể **có**, nếu phát hiện post-decision feature; khi ấy phải thiết kế đánh giá mới, không tái sử dụng frozen test cũ như chưa từng xem | Trung bình–cao; mỗi feature có source timestamp và decision-time verdict đã được TV1/TV2 duyệt. |
| 3. Power BI viability | Khôi phục/tạo PBIP entry đúng, sửa M source path, reconcile 10 page entries với 4-page plan; kiểm `relationships.tmdl` và hard-code measure | Không / không / không | Trung bình; mở trong Desktop, refresh 4 trang, screenshot + kiểm V02–V06/V13, không trộn SHAP cohort. |
| 4. Model evaluation completeness | Dùng **labeled validation predictions** đúng model để thêm confusion/Precision/Recall/F1 theo slider trong Dash Details; thêm bin counts cho calibration nếu đưa vào UI | Không / chỉ diagnostic validation, **không chọn lại ngưỡng** / không | Trung bình; so counts trên toàn 269.070, boundary 0/1/PD=T, không gọi 120 điểm là tổng population. |
| 5. Model analysis clarity | Sửa nhãn/chú giải local explanation trong Dash; Logistic gọi coefficient contribution, XGB gọi SHAP raw margin; hai bên đều log-odds | Không / không / không | Thấp; đối chiếu additivity và text không dùng “%PD contribution” hoặc causal. |
| 6. Báo cáo học thuật | Sửa `modeling_summary.md:11`, bổ sung Ch.4/slide so sánh 3 model cùng validation, frozen-test matrix riêng, calibration/limitations và source PDF trang 28–50 | Không / không / không | Thấp–trung bình; mọi chart ghi cohort/model/threshold, metrics khớp manifest, không đổi kết quả cũ. |

**Không có hành động nào ở bảng này đã được triển khai trong audit.** Nếu feature availability gate buộc thay input/model, đó là dự án model revision mới cần protocol test mới; không ghi đè artifacts và one-shot evidence cũ.

## K. Kiểm tra đã thực hiện, chưa thực hiện và bằng chứng

- Đã đọc các rule `.cursor/rules/`, model/data contracts, README, dashboard plan, setup/task/log, reports ML-LC-02…13, PDF 53 trang, source code và manifests. Đã kiểm tĩnh các TMDL/PBIR hiện diện.
- Đã đọc trực tiếp `cleaned_dataset.parquet` (ID/target và sáu cột preset), ba split IDs và hai validation prediction Parquet; đối chiếu membership, nhãn và các preset. Không đọc lại raw CSV 3,45 GB toàn bộ; accepted/rejected counts chỉ được xác nhận qua manifest.
- Đã nạp read-only sáu joblib để kiểm pipeline, số feature và `classes_`; SHA-256 của candidate/full-refit/demo/predictions khớp các manifest liên quan. **Không** gọi `fit`/`predict_proba` trên frozen test trong audit này.
- Đã chạy `pytest tests/apps/test_individual_prediction_dash.py tests/models/test_demo_6input.py tests/models/test_evaluation.py tests/models/test_scoring.py -q`. Lần đầu: 93 passed, 4 setup errors do **PermissionError** ở thư mục temp hệ thống `C:\Users\Nghia\AppData\Local\Temp\pytest-of-Ga-eul` (không phải assertion fail). Chạy lại cùng bốn file với `--basetemp D:\ttdltq\.audit_pytest_tmp`: **97 passed, 3 warning** của SHAP/matplotlib PendingDeprecation. Các test khác/chạy full pipeline: **không chạy**.
- Thư mục tạm `.audit_pytest_tmp/` (42 mục do pytest tạo) còn lại: lệnh dọn đúng đường dẫn đã được kiểm tra nhưng môi trường từ chối thao tác xóa. Không coi đây là artifact dự án; cần dọn thủ công khi được phép. `git diff --check` trả mã 0 (chỉ có cảnh báo line-ending ở các file đã dirty); file báo cáo mới không có trailing whitespace.
- Chưa thực hiện Power BI Desktop render/refresh, chưa đọc trực quan nội dung hai PNG ROC/PR, chưa xác nhận thuật ngữ nguồn gốc/timestamp của mọi cột credit snapshot. Các mục đó là `BLOCKED` hoặc `PARTIAL`, không được tính PASS.

Nguồn kiểm tra chính: `src/data/cleaning.py:63`; `src/data/column_policy.py:26–98`; `src/features/engineering.py:26`; `src/models/modeling_pipeline.py:175–263`; `src/models/evaluation.py:82–120,262–373`; `src/models/tv1_runner.py:614,805,1213,1425,1656`; `src/models/frozen_test.py:156`; `src/models/explainability.py:192`; `src/models/scoring.py:255–305`; `src/models/expected_loss.py:251`; `src/models/final_model.py:183`; `src/models/demo_6input.py:39–101,350–476`; `apps/individual_prediction_dash/logic.py:39–48,178–334`; `apps/individual_prediction_dash/app.py:279–350,379–497,509–630`; `data/processed/modeling/*_manifest.json`; `data/processed/modeling/{train,validation,test}_ids.parquet`; `docs/tasks/dashboard-visual-plan.md`; `reports/tv1_stages/modeling_summary.md:11`; PBIR master `pages/pages.json`, `relationships.tmdl`, `tables/*.tmdl`.

## L. Câu hỏi bảo vệ — trả lời ngắn

1. **Vì sao Logistic trước?** Đây là baseline tuyến tính dễ giải thích và kiểm tra dấu xác suất, rồi so model phức tạp trên cùng validation.
2. **Mất cân bằng xử lý thế nào?** Khoảng 20% default; thử `class_weight='balanced'` cho Logistic, không resampling/SMOTE. Weighting tăng recall ở 0,5 nhưng làm Brier/Log Loss xấu hơn.
3. **Vì sao XGBoost?** Trên cùng validation, ROC-AUC/PR-AUC nhỉnh hơn Logistic baseline (0,7245/0,3993 so 0,7149/0,3853), nên được chọn theo rule ML-LC-06; cải thiện nhỏ, không khẳng định vượt trội mọi chiều.
4. **XGBoost thay Logistic không?** Nó là candidate chính cho đánh giá và phân tích; Logistic vẫn là baseline và bản demo đối chiếu, không phải một sigmoid với một vector β duy nhất.
5. **PD là gì?** `predict_proba[:,1]` ước lượng xác suất lớp default của model, không phải kết quả thực tế hay đảm bảo rủi ro sẽ xảy ra.
6. **T*=0,2201 từ đâu?** Max F1 trên validation của XGBoost 103-input ở ML-LC-07; được mượn làm ngưỡng tham chiếu 6-input, không phải optimum riêng cho chúng và không phải tối ưu chi phí ngân hàng.
7. **Vì sao kéo ngưỡng không đổi PD?** Ngưỡng chỉ đổi rule `PD>=T`; model, input, PD, SHAP, tier cố định và EL theo PD không đổi.
8. **FP/FN là gì?** FP: cảnh báo default nhưng thực tế không default; FN: không cảnh báo nhưng thực tế default. Xác định theo đúng model, cohort và ngưỡng.
9. **Vì sao Precision/Recall/F1?** Chúng thể hiện trade-off cảnh báo nhầm/bỏ sót khi lớp default ít hơn; accuracy đơn độc dễ che FN.
10. **Chứng minh model tốt bằng gì?** ROC/PR cho ranking, confusion/Precision/Recall/F1 tại threshold, Brier/Log Loss/calibration cho xác suất, test holdout cho ước lượng cuối; nói rõ giới hạn random holdout.
11. **Evaluation khác analysis?** Evaluation hỏi “dự báo đúng đến đâu/sai ở đâu”; analysis hỏi “model phản ứng/giải thích ra sao”, ví dụ FICO–PD hay SHAP.
12. **SHAP nói gì?** Đóng góp feature vào raw margin/log-odds của XGBoost so baseline, không phải %PD hoặc bằng chứng nhân quả. Logistic demo dùng coefficient contribution, không gọi là SHAP.
13. **Calibration nói gì?** So PD trung bình với tỉ lệ default thực quan sát theo bin; plot/Log Loss/Brier hỗ trợ kiểm chất lượng xác suất, không đưa khoảng tin cậy cá nhân.
14. **EL là gì?** `PD × LGD × loan_amnt` (loan amount chỉ là EAD proxy), LGD 45% baseline; là tổn thất *kỳ vọng theo giả định*, không phải loss đã xảy ra.
15. **Áp dụng thực tế ngay?** Chưa. Cần chứng minh feature availability, kiểm temporal drift/out-of-time và calibration, duyệt policy/chi phí, kiểm Power BI/UX và governance; demo chỉ phục vụ học tập.

**Chuỗi chứng cứ học thuật:** dữ liệu/nhãn → split/train-only preprocessing → ba candidate → PD lớp 1 → ngưỡng validation → frozen-test error → SHAP/score/EL → Power BI/Dash. Các chặng tính toán đã truy được từ repo; chặng PBIR runtime và quyết định tín dụng thực vẫn **BLOCKED** cho đến khi có chứng cứ bổ sung.

## L. Phụ lục khắc phục 09/10/2026 — không viết lại kết luận audit gốc

Đây là trạng thái **sau** audit ở các mục A–K. Không retrain/refit/retune, không tính lại frozen-test metrics hoặc ghi đè model/artifact. `F01` **FIXED**: UI gọi 0,2201 là ngưỡng tham chiếu từ mô hình chính 103-input, không là optimum của hai demo. `F04` **FIXED bằng Validation diagnostics**: Dash có TN/FP/FN/TP và Precision/Recall/F1/Accuracy động theo model/ngưỡng trên đúng 269.070 prediction có nhãn; 120 chấm chỉ để minh họa. Nhãn TP/TN/FP/FN cho preset nguyên bản vẫn tính lại theo ngưỡng/model, sửa input thì không gán outcome lịch sử. `F05` **FIXED**: `modeling_summary.md` phân biệt 113 cột canonical, 106 policy-approved, 103 actual model inputs và 151 transformed. `F06` **FIXED**: trục/tooltip local contribution nói rõ log-odds; XGBoost là TreeSHAP raw margin, Logistic là coefficient × transformed input, không phải %PD hay nhân quả. `F08` **LIMITATION DOCUMENTED**: random holdout không xác nhận temporal generalization.

`F02` **PARTIAL / Desktop BLOCKED**: master trước sửa thực sự không có `.pbip` entry, không phải audit false positive. `nghia.pbip` mới chỉ làm entry tới Report/SemanticModel đã tồn tại; `definition.pbir` nối đúng model và tám M path `D:\Huy\...` đã đổi sang file thực tại `D:\ttdltq\data\...`. PBIR hiện có 10 page IDs, trong đó một tooltip page, không tự xóa/ẩn vì plan bốn trang chưa chỉ định staging ownership. Chưa mở/Refresh/kiểm render bằng Desktop sau sửa. `F07` **SOURCE FIXED / DAX RUNTIME BLOCKED**: `Top Purpose`, `Peak Year`, `Label Peak Year` đã thay hằng số bằng DAX dựa filter; chưa chứng nhận kết quả khi mở Desktop. `F03` **OPEN — TIME AVAILABILITY NOT FULLY VERIFIED**: phân loại kỹ thuật của feature không thay thế timestamp nghiệp vụ.

### Bảng truy xuất thời điểm feature (decision-time = trước quyết định cấp khoản vay)

`Source` ở đây là file/cột đã kiểm trong repo, **không phải** tài liệu gốc Lending Club có timestamp. Repo chưa có source dictionary chính thức theo từng cột hoặc timestamp snapshot per-field. Vì thế “reasonably assumed” không được gọi “verified available”. Không có feature nào trong bảng được chứng minh hậu quyết định ở chính record model; cũng không có bằng chứng đủ để tuyên bố toàn bộ 103 input leak-free cho pre-origination.

| Feature / nhóm | Source | Meaning được hỗ trợ | Known at decision time? | Evidence | Status |
|---|---|---|---|---|---|
| `loan_amnt`, `annual_inc`, `purpose`, `term_months`, `home_ownership` | accepted loan → `loan_application`/`borrower_profile` | Thông tin khoản vay/người vay trong hồ sơ | Có thể có, chưa có snapshot timestamp | `aggregate.py`, `column_policy.py`, `data_dictionary.csv` | Reasonably assumed, not proven |
| `issue_d` → `issue_year`, `issue_quarter`, `issue_month` | accepted `issue_d` → `engineering.py` | Thời điểm phát hành và thành phần lịch | **Không xác nhận trước khi phát hành**; `issue_year` là actual input | `engineering.py`, `modeling_pipeline.py`, SHAP rank trong mục E | Unknown / high-priority temporal review |
| `earliest_cr_line` → `credit_history_months` | accepted credit line + `issue_d` → `engineering.py` | Tuổi lịch sử tín dụng tính tới issue month | Phụ thuộc ngày snapshot và `issue_d` | `engineering.py`, dictionary | Unknown |
| `fico_range_low`, `fico_range_high` → `fico_avg`, `fico_band` | accepted credit snapshot → `engineering.py` | Khoảng FICO nguồn và trung bình/nhóm dẫn xuất | Chưa có bureau pull timestamp | `aggregate.py`, `engineering.py`, dictionary | Reasonably assumed, not proven |
| `dti`, `dti_joint` → `dti_band` | accepted credit snapshot → `engineering.py` | Debt-to-income và nhóm DTI | Chưa có snapshot timestamp | `aggregate.py`, `engineering.py`, dictionary | Reasonably assumed, not proven |
| `chargeoff_within_12_mths`, `sec_app_chargeoff_within_12_mths` | accepted credit snapshot | Tên cột gợi ý lịch sử charge-off, nhưng source semantics chưa được xác nhận | Không biết đó là lịch sử trước quyết định hay event hậu kỳ | `column_policy.py`, dictionary chỉ ghi class/dtype/grain | Unknown / high-priority review |
| `delinq_amnt`, `acc_now_delinq`, `num_tl_120dpd_2m` | accepted credit snapshot | Trường nợ quá hạn/tài khoản theo tên; chưa có định nghĩa gốc | Không xác nhận ngày đo | `aggregate.py`, `column_policy.py`, dictionary | Unknown / high-priority review |
| `inq_last_6mths`, `mths_since_recent_inq`, `acc_open_past_24mths`, `tot_hi_cred_lim` và các bureau-like fields còn lại | accepted credit snapshot | Inquiry, tuổi/giới hạn tài khoản theo schema; không suy luận thời điểm từ tên | Không có timestamp per-field | `aggregate.py`, dictionary, `column_policy.py` | Reasonably assumed, not proven |
| `loan_to_income_ratio`, `loan_amount_band`, `income_band` | dẫn xuất từ `loan_amnt`/`annual_inc` | Ratio/nhóm của application fields | Phụ thuộc source inputs | `engineering.py` | Reasonably assumed, not proven |
| `loan_status` và payment/recoveries/settlement | accepted outcome → target/post-loan policy | Kết quả/sự kiện sau khoản vay | Không dùng cho inference tại quyết định | `cleaning.py`, `column_policy.py`; vắng trong 103 model inputs | Proven post-outcome; excluded |

Để đóng `F03`, TV1/TV2 cần định nghĩa thời điểm prediction (trước phát hành hay tại origination), lấy mô tả gốc và snapshot-date cho từng credit field, đối chiếu tất cả 103 input với thời điểm đó, duyệt lại policy. Nếu chứng minh được field hậu quyết định đã vào model, đó là **P0 / model revision riêng**: dừng claim deploy-ready, không lặng lẽ loại feature hoặc tái dùng frozen-test one-shot để chọn lại model.

Kiểm tra mã đã chạy: `tests/apps` cùng `test_demo_6input.py`, `test_evaluation.py`, `test_scoring.py` **105 passed, 3 SHAP/matplotlib deprecation warnings**; không gọi training hay model inference trên frozen test. PBIR JSON/đường dẫn kiểm tĩnh riêng, **không tương đương Desktop PASS**. Hướng dẫn GUI tương đương cho mọi sửa Power BI ở `reports/figures/dashboard/huong-dan-thao-tac-power-bi.md`.
