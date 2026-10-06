# TV1 Modeling Summary — Lending Club Credit Risk

> Tài liệu tổng hợp canonical cho báo cáo, thuyết trình, bảo vệ và dashboard story. Metrics frozen-test thuộc evaluated xgboost_candidate ở ML-LC-08; full-data refit là model khác và không có unbiased test score mới.

## 1. Modeling objective

Phân loại nhị phân khả năng khoản vay đi đến default: 0 = non-default / Fully Paid; 1 = default / Charged Off hoặc Default. Classification phù hợp vì cần xác suất PD trong [0,1] và lớp dự đoán. Linear Regression có thể tạo dự đoán ngoài [0,1] và không mô hình hóa trực tiếp nhãn nhị phân.

## 2. Input / leakage gate

Canonical accepted data có 1,345,350 dòng và 107 cột theo split manifest (loan_id, target và các field). Gate duyệt 106 cột model-safe theo policy; XGBoost dùng chính xác 103 actual features, sau preprocessing thành 151 transformed features. Các date field an toàn nhưng không dùng trực tiếp: issue_d, earliest_cr_line, sec_app_earliest_cr_line.

Chỉ feature APPLICATION_TIME hoặc CREDIT_SNAPSHOT được đưa vào X. Loại loan_id, target, loan_status, outcome/post-loan fields (ví dụ total_pymnt, recoveries), POLICY_DERIVED, geography và UNKNOWN_REVIEW_REQUIRED. Danh sách feature thực tế và audit nằm trong ML-LC-05/12 manifests và feature audit.

## 3. Train / Validation / Frozen Test

Split stratified, deterministic (random_state=42), không overlap; mỗi phần có default rate xấp xỉ 19.965%.

| Partition | Vai trò | Rows | Target 1 | Default rate |
|---|---|---:|---:|---:|
| Train | Học model và fit preprocessing | 807,210 | 161,159 | 19.965% |
| Validation | So sánh candidate, chọn threshold | 269,070 | 53,720 | 19.965% |
| Frozen test | Đánh giá cuối, chỉ mở một lần | 269,070 | 53,720 | 19.965% |

Train = học; Validation = lựa chọn; Frozen Test = bài thi cuối. Frozen test không tham gia training, feature/model selection hay threshold tuning.

## 4. Logistic baseline

Logistic Regression là baseline bắt buộc: solver=lbfgs, penalty=l2, max_iter=1000, class_weight=None, random_state=42; preprocessing fit trên train. Tại threshold tham chiếu 0.5 trên validation: ROC-AUC 0.714887, PR-AUC 0.385307, Log Loss 0.451609, Brier 0.144037, Precision 0.562454, Recall 0.084494, F1 0.146917, Accuracy 0.804096. Confusion matrix [[TN, FP], [FN, TP]] = [[211819, 3531], [49181, 4539]].

Accuracy tương đối cao một phần do non-default chiếm đa số; recall thấp cho thấy threshold 0.5 bỏ sót nhiều default.

## 5. Imbalance experiment

So sánh Logistic baseline và Logistic với class_weight=balanced tại threshold tham chiếu 0.5 trên cùng validation:

| Model | Precision | Recall | F1 | FP | FN |
|---|---:|---:|---:|---:|---:|
| Logistic baseline | 0.562454 | 0.084494 | 0.146917 | 3,531 | 49,181 |
| Weighted Logistic | 0.322134 | 0.655398 | 0.431958 | 74,088 | 18,512 |

Weighting giảm FN 30,669 nhưng tăng FP 70,557: bắt được nhiều default hơn nhưng tạo thêm nhiều cảnh báo nhầm. Weighted Logistic không được khóa làm candidate.

## 6. XGBoost candidate

Cấu hình: n_estimators=200, max_depth=4, learning_rate=0.05, subsample=0.8, colsample_bytree=0.8, random_state=42, objective=binary:logistic, eval_metric=logloss, tree_method=hist, n_jobs=4. Tại threshold 0.5 trên validation: ROC-AUC 0.724501, PR-AUC 0.399256, Log Loss 0.447402, Brier 0.142595, Precision 0.598674, Recall 0.075614, F1 0.134270, Accuracy 0.805326.

Được thử để xem mô hình cây có cải thiện xếp hạng và xác suất so với Logistic hay không; không thay yêu cầu baseline Logistic.

## 7. Model comparison

Metrics classification dưới đây ở threshold tham chiếu 0.5, tất cả tính trên validation.

| Model | ROC-AUC | PR-AUC | Log Loss | Brier | Precision | Recall | F1 | Accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Logistic baseline | 0.714887 | 0.385307 | 0.451609 | 0.144037 | 0.562454 | 0.084494 | 0.146917 | 0.804096 |
| Weighted Logistic | 0.715097 | 0.384014 | 0.619602 | 0.215452 | 0.322134 | 0.655398 | 0.431958 | 0.655852 |
| XGBoost | 0.724501 | 0.399256 | 0.447402 | 0.142595 | 0.598674 | 0.075614 | 0.134270 | 0.805326 |

XGBoost có ROC-AUC và PR-AUC cao nhất, cùng Log Loss/Brier thấp nhất; theo quy tắc đã ghi trước trong model contract, khóa xgboost_candidate. Đây là quyết định dựa trên validation point estimates, không phải kiểm định ý nghĩa thống kê. Weighted Logistic recall cao hơn tại 0.5 nhưng nhiều FP hơn và xác suất kém hơn theo Log Loss/Brier.

## 8. Threshold selection

Threshold tham chiếu 0.5 được thay bằng operating threshold 0.22009515762329102, chọn trên validation của candidate để tối đa F1 (quy tắc tie-break nằm trong contract). Tại threshold đã chọn: Precision 0.346453, Recall 0.602681, F1 0.439981, Accuracy 0.693693, FP 61,074, FN 21,344.

So với 0.5, Recall tăng khoảng 0.5271, FP tăng 58,351, FN giảm 28,314. Chọn F1 vì chưa có ma trận chi phí kinh doanh được duyệt; threshold không tối ưu Expected Loss/lợi nhuận và không phải cutoff phổ quát.

## 9. Frozen Test

Đánh giá một lần trên 269,070 frozen-test rows của xgboost_candidate với threshold đã khóa. ROC-AUC 0.723186, PR-AUC 0.400000, Log Loss 0.447783, Brier 0.142643, Precision 0.345877, Recall 0.602960, F1 0.439590, Accuracy 0.693065.

| | Máy dự đoán Tốt | Máy dự đoán Xấu |
|---|---:|---:|
| Thực tế Tốt | TN = 154,092 | FP = 61,258 |
| Thực tế Xấu | FN = 21,329 | TP = 32,391 |

TN: tốt → máy tốt. FP: tốt → máy xấu (cảnh báo nhầm). FN: xấu → máy tốt (bỏ sót default). TP: xấu → máy xấu.

| Metric | Validation | Frozen test | Test − validation |
|---|---:|---:|---:|
| ROC-AUC | 0.724501 | 0.723186 | -0.001315 |
| PR-AUC | 0.399256 | 0.400000 | +0.000744 |
| Precision | 0.346453 | 0.345877 | -0.000576 |
| Recall | 0.602681 | 0.602960 | +0.000279 |
| F1 | 0.439981 | 0.439590 | -0.000391 |
| Accuracy | 0.693693 | 0.693065 | -0.000628 |

These metrics belong to evaluated candidate and are the final unbiased performance evidence here. Test was not used to change the selection.

## 10. Explainability / SHAP

ML-LC-09 used a stratified sample of 5,000 validation rows (4,002 target 0; 998 target 1). SHAP output space is raw margin/log-odds; maximum absolute additivity error is 3.2284e-06. Positive SHAP increases raw margin and generally PD; negative tends to decrease it. SHAP is NOT a direct PD percentage-point change.

| Rank | Original feature | Mean absolute SHAP | Observed direction / note |
|---:|---|---:|---|
| 1 | term_months | 0.315463 | Insufficient variation for a stable direction summary. |
| 2 | loan_to_income_ratio | 0.159380 | Higher values associated with more positive SHAP (ρ=0.982). |
| 3 | fico_range_low | 0.156027 | Higher values associated with more negative SHAP (ρ=-0.973). |
| 4 | dti | 0.122836 | Higher values associated with more positive SHAP (ρ=0.958). |
| 5 | issue_year | 0.110877 | Higher values associated with more positive SHAP (ρ=0.782). |
| 6 | acc_open_past_24mths | 0.100232 | Higher values associated with more positive SHAP (ρ=0.973). |
| 7 | home_ownership | 0.076316 | Category contributions differ; no single direction. |
| 8 | mths_since_recent_inq | 0.052777 | Higher values associated with more negative SHAP (ρ=-0.827). |
| 9 | tot_hi_cred_lim | 0.051639 | Higher values associated with more negative SHAP (ρ=-0.909). |
| 10 | mort_acc | 0.050942 | Higher values associated with more negative SHAP (ρ=-0.929). |

These directions describe association with model contribution in the analyzed sample; association/model contribution ≠ causation. For categorical features, do not infer one overall direction. Canonical sources: ml_lc_09_global_importance.csv, ml_lc_09_local_explanations.csv, ml_lc_09_shap_sample.parquet; figures: reports/figures/modeling/ml_lc_09_global_importance.png and ml_lc_09_shap_summary.png.

## 11. Scoring / Risk Tier

- PD: predicted_pd, model-estimated probability of default.
- risk_score = 100 × PD; higher means higher predicted risk.
- Project credit score = round_half_to_even(1000 × (1 − PD)); higher means lower predicted risk. This project-derived score is NOT FICO.
- With T = 0.22009515762329102: A if PD < T/2; B if T/2 ≤ PD < T; C if T ≤ PD < 2T; D if PD ≥ 2T.

| Tier | Count | Share | Mean PD | Observed default rate |
|---|---:|---:|---:|---:|
| A — Low | 66,275 | 24.63% | 7.73% | 6.20% |
| B — Moderate | 109,146 | 40.56% | 16.03% | 15.78% |
| C — High | 80,423 | 29.89% | 30.15% | 31.16% |
| D — Very High | 13,226 | 4.92% | 51.79% | 55.41% |

These describe the evaluated frozen-test population. Observed default rate is retrospective outcome frequency, not predicted PD or a guarantee for an individual.

## 12. Expected Loss

EL = PD × LGD × EAD. PD is the locked model output; LGD baseline 45% with sensitivity 30/45/60% is an illustrative scenario assumption, not an empirical estimate or bank policy. EAD proxy is loan_amnt at origination, not outstanding exposure at default. Currency is unspecified by the dictionary, so retain source units.

On evaluated frozen-test population: total EAD proxy 3,878,248,925 source units; baseline EL 372,579,342.19; average EL 1,384.69; EL rate (total EL / total EAD) 9.6069%.

| LGD scenario | Total Expected Loss (source units) |
|---:|---:|
| 30% | 248,386,228.13 |
| 45% | 372,579,342.19 |
| 60% | 496,772,456.26 |

Tier C contributes the largest EL share (47.89%), while Tier D has highest mean PD (51.79%) but 15.69% of EL. EL depends on PD × exposure × group size, not PD alone.

## 13. Full-data refit

xgboost_candidate.joblib is the evaluated model whose ML-LC-08 frozen-test metrics are reported above. xgboost_full_refit.joblib is a distinct model refit using all 1,345,350 labeled rows after final evaluation, with the same locked configuration, 103 actual inputs and 151 transformed inputs. The threshold is carried forward from ML-LC-07; it was not retuned or revalidated against refit scores.

ml_lc_12_full_refit_scores.parquet contains in-sample deployment/demo scores, not unbiased test predictions. Do not attach ML-LC-08 metrics to the refit.

## 14. Dashboard-ready modeling artifacts

| Visual | Existing source | Readiness / caveat |
|---|---|---|
| V02 — PD Distribution | ml_lc_10_scored_frozen_test.parquet | Data ready; TV3 Power BI integration remains. |
| V03 — Risk Tier Distribution | ml_lc_10_scored_frozen_test.parquet, ml_lc_10_risk_tier_summary.csv | Data ready; TV3 integration remains. |
| V04 — FICO vs Risk/PD | ml_lc_10_scored_frozen_test.parquet | Data ready; TV3 integration remains. |
| V05 — Global Importance / SHAP | ml_lc_09_global_importance.csv; separate local/sample sources | Explainability artifacts remain separate. |
| V06 — Expected Loss | ml_lc_11_expected_loss.parquet, ml_lc_11_risk_tier_el_summary.csv, portfolio summary | Evaluated frozen-test scenario; not full portfolio. |

Data readiness does not mean Power BI is built, integrated, or reviewed. V01 Geographic Risk Map belongs to TV3.

## 15. Individual prediction readiness

ML-LC-13 audit confirms an inference contract for a future demo: provide exactly the 103 named features in the ML-LC-12 manifest; preprocessing is embedded in the full-refit pipeline. Do not pass loan_id, target, post-loan or unknown fields. A one-row canonical feature smoke check passed without outcome/metric evaluation.

Outputs: predicted_pd, carried-forward decision_threshold, predicted_class, risk_score, project credit_score, risk_tier. No UI or Power BI input form was built.

## 16. Limitations

- Observational dataset: association does not prove causation.
- Threshold maximizes validation F1; it is not bank-cost-optimal.
- Project credit score is not FICO or an official bureau score.
- LGD is a scenario assumption; loan_amnt is only an EAD proxy.
- Currency unit is unspecified; EL is not realized loss, profit or regulatory capital.
- EL/tier summaries describe evaluated frozen-test population, not the full portfolio.
- Full-refit scores are in-sample; the refit has no new unbiased test evaluation.
- Power BI integration/review is outside modeling completion and remains TV3's responsibility.

## 17. Tables and figures recommended for Word report

- [ ] Train/validation/frozen-test counts and target rates.
- [ ] Complete eight-metric model comparison.
- [ ] Threshold 0.5 versus selected threshold trade-off.
- [ ] Final frozen-test confusion matrix.
- [ ] Validation-versus-test table.
- [ ] SHAP Top 10 and SHAP summary figure.
- [ ] Risk tier counts, share, mean PD and observed default rate.
- [ ] Expected Loss by tier.
- [ ] Expected Loss sensitivity by LGD.

## 18. Defense quick-reference

**Why classification?** Binary outcome and required PD in [0,1]; ordinary Linear Regression does not constrain predictions to valid probabilities.

**Why Logistic first?** It is a simple, interpretable baseline.

**Why XGBoost?** To test nonlinear patterns/interactions; it led validation ranking metrics under the predeclared selection rule.

**Why not accuracy only?** Default is the minority class; accuracy can conceal missed defaults. Consider recall, PR-AUC and confusion matrix.

**What did class weighting do?** Increased default recall but generated many additional false positives.

**Why not threshold 0.5?** Validation F1 trade-off was better at the selected operating point; it is not business-cost optimization.

**Why a frozen test?** One final check on held-out data after selection, avoiding reuse for tuning.

**What is SHAP?** A model-contribution decomposition in raw margin/log-odds, not PD percentage points and not causation.

**Why is project credit score not FICO?** It is a deterministic mapping from this model's PD, not an official FICO/bureau score.

**Why can Tier C contribute more EL than Tier D?** EL also depends on exposure and number of loans, not just mean PD.

**What are LGD/EAD here?** LGD values are illustrative scenarios; loan_amnt is an origination-amount proxy, not observed outstanding exposure.

