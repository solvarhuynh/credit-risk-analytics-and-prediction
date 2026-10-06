# ML-LC-13 — Dashboard / Inference Handoff Audit

**Status: PASS — satisfied by existing handoff artifacts**

## 1. Kết luận audit

ML-LC-12 scores, ML-LC-10 scoring contract, ML-LC-09 explainability outputs và ML-LC-11 Expected Loss artifacts đã cung cấp các đầu ra modeling cần thiết. Không tạo parquet handoff mới để tránh bản sao không cần thiết.
Dashboard data readiness không đồng nghĩa Power BI đã được xây dựng hoặc TV3 đã tích hợp/duyệt Master PBIX.

## 2. Artifact mapping

| Consumer | Existing source | Audit result |
|---|---|---|
| V02 | `D:\ttdltq\data\processed\modeling\ml_lc_10_scored_frozen_test.parquet` | READY; Power BI integration remains TV3 responsibility |
| V03 | `D:\ttdltq\data\processed\modeling\ml_lc_10_scored_frozen_test.parquet` | READY; Power BI integration remains TV3 responsibility |
| V04 | `D:\ttdltq\data\processed\modeling\ml_lc_10_scored_frozen_test.parquet` | READY; Power BI integration remains TV3 responsibility |
| V05 | `D:\ttdltq\data\processed\modeling\ml_lc_09_global_importance.csv` | READY; Power BI integration remains TV3 responsibility |
| V06 | `D:\ttdltq\data\processed\modeling\ml_lc_11_risk_tier_el_summary.csv` | READY; Power BI integration remains TV3 responsibility |

`V05` tiếp tục đọc các file explainability riêng ML-LC-09; SHAP không bị flatten vào score dataset. `V06` tiếp tục dùng ML-LC-11 scenario source; nó vẫn mô tả evaluated frozen-test population, không phải full portfolio.

## 3. Scoring contract

Full-refit model: `D:\ttdltq\data\processed\modeling\xgboost_full_refit.joblib`; input schema gồm 103 actual features (trong 106 policy-approved features). Preprocessing nằm trong pipeline của model. Inference helper/UI không được tạo trong task này.
Input một borrower phải có đúng named fields của `actual_features` trong ML-LC-12 manifest, theo schema/dtypes canonical; không truyền `loan_id`, `target`, post-loan hay unknown fields vào model. Pipeline đã gồm missing-value normalization, imputation và one-hot encoding.
Output contract: `predicted_pd`; `predicted_class = (PD >= carried_forward_threshold)`; `risk_score = 100 × PD`; `credit_score = round_half_to_even(1000 × (1 − PD))`; risk tier theo ML-LC-10 boundaries. Project credit score không phải FICO. Threshold được carry từ ML-LC-07, chưa revalidated trên refit.

## 4. Provenance / limitations

Frozen-test metrics vẫn thuộc `xgboost_candidate` ở ML-LC-08; không gắn các metrics này vào full-data refit. Full-refit scores là in-sample. LGD/EAD scenario không được tự ghép vào score output; V06 dùng policy/artifacts ML-LC-11.
