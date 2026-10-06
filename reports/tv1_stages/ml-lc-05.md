# ML-LC-05 — Optional XGBoost candidate

## Purpose and data

Thử một mô hình cây phi tuyến để so sánh ranking trên validation; Logistic vẫn là baseline bắt buộc.
Frozen train: **807,210**; validation: **269,070**; frozen test: **269,070** (sealed).
ML-LC-01 approved: **106**; actual input: **103**; transformed: **151**.

## Feature policy and preprocessing

Dùng đúng 103 feature ML-LC-03/04 đã duyệt; không có ID, target, policy-derived, geography hoặc POST_LOAN trong X.
Ba raw date fields tiếp tục loại theo baseline audit. Numeric: median imputation; categorical: most-frequent imputation + sparse one-hot; không StandardScaler.
Imputer/encoder được fit chỉ trên train trong sklearn Pipeline. Không target encoding, không resampling và không early stopping.

## Fixed candidate configuration

`{'n_estimators': 200, 'max_depth': 4, 'learning_rate': 0.05, 'subsample': 0.8, 'colsample_bytree': 0.8, 'random_state': 42, 'objective': 'binary:logistic', 'eval_metric': 'logloss', 'tree_method': 'hist', 'n_jobs': 4}`

## Validation results

Threshold 0.5 chỉ để tham chiếu; chưa tối ưu threshold.

| Metric | Logistic baseline | Logistic weighted | XGBoost |
|---|---:|---:|---:|
| roc_auc | 0.714887 | 0.715097 | 0.724501 |
| pr_auc | 0.385307 | 0.384014 | 0.399256 |
| precision | 0.562454 | 0.322134 | 0.598674 |
| recall | 0.084494 | 0.655398 | 0.075614 |
| f1 | 0.146917 | 0.431958 | 0.134270 |
| accuracy | 0.804096 | 0.655852 | 0.805326 |

XGBoost confusion matrix `[ [TN, FP], [FN, TP] ]`: `[[212627, 2723], [49658, 4062]]`.

## Artifacts

Model with preprocessing: `D:\ttdltq\data\processed\modeling\xgboost_candidate.joblib`.
Validation predictions: `D:\ttdltq\data\processed\modeling\ml_lc_05_xgboost_validation_predictions.parquet`.

## Limitations

Đây là một candidate với cấu hình cố định. ML-LC-06 mới so sánh và khóa model; chưa chọn model cuối.
Frozen test không được dùng để train, predict, evaluate hoặc select model. Không đưa ra kết luận nhân quả từ các metric.
