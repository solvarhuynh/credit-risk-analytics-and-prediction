# Model Contract — Lending Club

Trạng thái: **ML-LC-01 đến ML-LC-13 PASS**. ML-LC-08 frozen-test metrics thuộc riêng `xgboost_candidate`; ML-LC-12 full-data refit là artifact khác, scores in-sample, không có unbiased test score mới. Threshold `0.22009515762329102` được carry forward không retune/revalidate. ML-LC-13 PASS là audit handoff trên artifacts hiện có; Power BI chưa được xác nhận hoàn tất.

TV1 chỉ nhận `cleaned_dataset.parquet`, dictionary và manifest khi TV2 quality/leakage gate PASS. `X` chỉ gồm cột đã duyệt thuộc `APPLICATION_TIME` hoặc `CREDIT_SNAPSHOT`; loại `loan_id`, `target`, `loan_status`, geography, policy-derived, post-loan, text cardinality cao và unknown.

Logistic Regression là baseline bắt buộc. XGBoost là so sánh tùy chọn và không thay thế yêu cầu Logistic. Split cố định, threshold chọn bằng development/validation; frozen test chỉ đánh giá cuối.

## ML-LC-06 — Quy tắc khóa candidate

Chỉ so sánh ba artifact dự đoán trên cùng validation IDs và target, sau khi đối chiếu metrics với manifest gốc. ROC-AUC là tiêu chí xếp hạng chính; nếu chênh lệch với ROC-AUC cao nhất không quá `0.002` tuyệt đối, xem như gần nhau và dùng PR-AUC để phân định. Nếu PR-AUC cũng cách nhau không quá `0.005`, ưu tiên model đơn giản, dễ giải thích hơn. Hai Logistic có cùng mức phức tạp; trong trường hợp đó, xét Log Loss rồi Brier Score thấp hơn, sau cùng dùng thứ tự tên cố định để tái lập quyết định. Các ngưỡng gần nhau là quy ước thực hành, không phải kiểm định ý nghĩa thống kê.

Log Loss và Brier Score là chẩn đoán chất lượng PD trên validation; báo cáo cả hai cho mọi candidate, không fit calibration ở stage này. Precision, recall, F1, accuracy và confusion matrix tại `0.5` chỉ là chẩn đoán vì ML-LC-07 mới chọn threshold. Khóa đúng một candidate cho ML-LC-07; không gọi đó là final model và không dùng frozen test để chọn model.

## ML-LC-07 — Quy tắc chọn operating threshold

Chỉ dùng prediction validation của candidate đã khóa. Chọn threshold tối đa F1; các F1 cách giá trị lớn nhất không quá `1e-12` được xem là hòa. Tie-break theo recall cao hơn, sau đó precision cao hơn, cuối cùng threshold cao hơn để chọn quyết định bảo thủ và tái lập. Tìm trên các prediction score phân biệt được bằng `precision_recall_curve`, không chỉ trên lưới thô.

Đây là operating threshold thống kê được chọn trên validation vì hiện chưa có ma trận chi phí kinh doanh được duyệt; không được diễn giải là ngưỡng tối ưu Expected Loss, lợi nhuận hoặc quyết định cho mọi tổ chức. Frozen test chỉ được dùng ở ML-LC-08 theo quy trình đánh giá cuối.

## ML-LC-08 — Final evaluated configuration

Frozen test được dùng đúng một lần để đo khả năng khái quát hóa của `xgboost_candidate` + threshold khóa từ ML-LC-07. Kết quả không được dùng để đổi feature, retrain, chọn model khác hay tìm ngưỡng mới. `PASS` nghĩa là quy trình final evaluation hợp lệ, không áp một ngưỡng chất lượng tự đặt. Prediction, metrics, provenance và hashes ở `data/processed/modeling/ml_lc_08_manifest.json`; báo cáo tại `reports/tv1_stages/ml-lc-08.md`. Rerun trên test thật phải fail closed nếu đã có output/one-shot lock; synthetic tests không tính là mở test thật.

## ML-LC-09 — Explainability

Giải thích cấu hình đã khóa bằng validation với mẫu SHAP phân tầng cố định; frozen test không được đọc lại. Feature gốc nhận mean absolute SHAP bằng cách cộng các transformed/one-hot contributions cùng nguồn trên từng loan rồi mới lấy trị tuyệt đối trung bình. Native gain ở mức gốc cộng total_gain của các transformed feature và chuẩn hóa thành tỷ trọng. SHAP ở raw margin/log-odds: dấu dương đẩy margin và thường PD lên; trị SHAP không phải phần trăm điểm PD. Đây là mô tả hành vi model, không phải quan hệ nhân quả. Dashboard V05 dùng tên feature gốc trong `ml_lc_09_global_importance.csv`.

## ML-LC-10 — Quy tắc PD, score và risk tier

ML-LC-10 chỉ hậu xử lý `predicted_pd` đã có; không fit, retrain, dự đoán lại, đổi candidate hoặc đổi threshold. Input là 269.070 dự đoán frozen-test ở ML-LC-08, dùng làm population đã đánh giá cho artifact/report/dashboard demo. Đây không phải full-portfolio scoring; frozen test không được dùng để điều chỉnh policy.

- `risk_score = 100 × predicted_pd`, liên tục từ 0 đến 100; số cao hơn nghĩa là model dự đoán rủi ro vỡ nợ cao hơn.
- `credit_score = round(1000 × (1 − predicted_pd))`, từ 0 đến 1000; số cao hơn nghĩa là model dự đoán rủi ro thấp hơn. Đây là project/model-derived credit score, **không phải FICO hay điểm bureau chính thức**. Công thức làm tròn là round half-to-even theo NumPy `rint`.
- Với threshold đã khóa `T = 0.22009515762329102`: Tier A — Low nếu `PD < T/2`; Tier B — Moderate nếu `T/2 ≤ PD < T`; Tier C — High nếu `T ≤ PD < min(2T, 1)`; Tier D — Very High nếu `PD ≥ min(2T, 1)`. Các cận dưới sau Tier A tính inclusive; cận trên tính exclusive, trừ miền cuối đóng tại PD=1. Quy tắc bao phủ toàn [0,1], không chồng lấn; equality thuộc tier có cận dưới bằng PD đó.

Risk tier là dải mô tả mức PD model dự đoán, không phải regulatory grade, Lending Club grade, FICO band hay lớp default frequency được bảo đảm. `target` chỉ dùng để tính observed default rate mô tả trong summary, không tham gia score/tier. Phải trình bày riêng `mean_predicted_pd` và `observed_default_rate`; không xem chúng là cùng một đại lượng. Scoring này không chọn ngưỡng mới, không dùng target để thay boundaries.

Artifact dùng cho V02–V04: `ml_lc_10_scored_frozen_test.parquet`; summary tier: `ml_lc_10_risk_tier_summary.csv`; summary phân phối: `ml_lc_10_score_summary.csv`. Các dòng giữ một hàng mỗi `loan_id` và chỉ nối context mô tả đã chọn từ canonical dataset.

Output TV3 tương lai tối thiểu: `loan_id`, `target`, `predicted_pd`, `decision_threshold`, `recommendation`, `model_version`. Có thể bổ sung `state_code`, `issue_year`, `loan_amnt`, `annual_inc`, `fico_avg`, `dti`, `purpose`, `credit_score`, `risk_tier`, `expected_loss` cho dashboard.

Khi chưa có artifact thật, simulator phải trả trạng thái `BLOCKED / WAITING FOR TV1 ARTIFACT`; không suy luận giả.

## ML-LC-11 — Expected Loss scenario policy

`Expected Loss (EL) = PD × LGD × EAD`. `PD` là xác suất vỡ nợ dự đoán đã khóa từ `xgboost_candidate`; stage này không dự đoán lại. Vì repo chưa có LGD/EAD business policy được duyệt, ML-LC-11 dùng **scenario assumption**: baseline `LGD = 0.45` và sensitivity `LGD = 0.30 / 0.45 / 0.60`. Đây là các giá trị minh họa cho project scenario analysis, không phải LGD Lending Club được ước lượng thực nghiệm, LGD regulatory hay policy của ngân hàng.

`EAD proxy = loan_amnt`, số tiền gốc lúc cấp khoản vay được giữ ở đơn vị nguồn của `loan_amnt`. Data dictionary không xác nhận đơn vị tiền tệ, vì vậy không tự gắn nhãn USD. Đây là proxy ở thời điểm application/origination, không phải outstanding exposure thực tế tại default. EL chỉ được tính bằng `predicted_pd × LGD assumption × EAD proxy`; `target` không tham gia công thức, chỉ có thể dùng để mô tả observed default rate hồi cứu theo nhóm.

Kết quả là **scenario expected loss**, không phải realized/actual loss, profit, causal effect hay regulatory capital model. Không gồm recovery, thời gian, discounting, phí, doanh thu hoặc các cấu phần vốn/quy định. Sensitivity chỉ thay đổi LGD giả định; PD, model, candidate và threshold được giữ nguyên. ML-LC-11 không tối ưu lại threshold `0.22009515762329102`.

## ML-LC-12 — Full-data refit contract

Refit dùng toàn bộ labeled canonical population với đúng cấu hình XGBoost và actual feature list của candidate đã khóa. Preprocessing fit trên `full_labeled_canonical`. Artifact `xgboost_full_refit.joblib` không ghi đè `xgboost_candidate.joblib`. Threshold ML-LC-07 là **carried-forward operating threshold**; không tìm ngưỡng mới hoặc revalidate trên in-sample refit scores. ML-LC-08 remains the only unbiased performance source, and its metrics must not be attributed to the refit. `ml_lc_12_full_refit_scores.parquet` is deployment/demo scoring output, not test predictions.

## ML-LC-13 — Handoff audit boundary

ML-LC-13 status is **PASS — satisfied by existing handoff artifacts**. V02–V04 source ML-LC-10 evaluated-population scores; V05 uses ML-LC-09 explanation-specific sources; V06 uses ML-LC-11 scenario outputs. The full-refit pipeline supports a future single-borrower inference contract with 103 named features and embedded preprocessing. Handoff/data readiness does not mean Power BI has been built, integrated, or reviewed; TV3 owns that work. See `reports/tv1_stages/ml-lc-13.md` and consolidated `reports/tv1_stages/modeling_summary.md`.
