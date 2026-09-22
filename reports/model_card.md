# TV1 Model Card — TV1-MASTER-20260922-64609993

## Dataset fingerprint

- Canonical dataset: `data/processed/cleaned_dataset.parquet`
- SHA-256: `6460999371297ff2f83418a8341b0c85d4a2e4dc6c29b29e793edd2a0c755c96`
- Manifest output hash: `6460999371297ff2f83418a8341b0c85d4a2e4dc6c29b29e793edd2a0c755c96`
- Shape: 307,511 rows × 203 columns
- TARGET distribution: 0 = 282,686; 1 = 24,825
- Manifest provenance: branch `main`, commit `67499751ba6f7e705a0a63ede1e5a623c75a79b5`

## Leakage-safe feature and split policy

- `y = TARGET`; `SK_ID_CURR` and downstream scoring/output columns are excluded from X.
- Features: 184 numeric and 17 categorical (201 total).
- Review-only distribution features retained without automatic removal: CREDIT_TO_INCOME_RATIO, INSTAL_PAYMENT_RATIO_MEAN, CC_UTILIZATION_MEAN.
- Fixed seed: `20260922`; development = 246,008 rows (8.0729% default), frozen test = 61,503 rows (8.0728% default).
- Development-ID SHA-256: `560e241d20d63a91c87fb505faeecac99bb4f763e594cf69be2c0bb94548e1ba`
- Frozen-test-ID SHA-256: `dbc3ac4c03dc2557fb8232af04819ff05570c9d44185225bbe207bfdc75df2c2`
- No ID overlap: verified before any preprocessing/model fit.
- Imputation, scaling and categorical encoding are inside each CV/model pipeline. No transformer was fit on the frozen test set.

## Development-only candidate comparison

| candidate | family | mean_roc_auc | std_roc_auc | mean_pr_auc | std_pr_auc | mean_precision | mean_recall | mean_f1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| xgboost_depth6 | xgboost | 0.779133 | 0.004172 | 0.271424 | 0.002954 | 0.574472 | 0.030967 | 0.058755 |
| xgboost_depth4 | xgboost | 0.774253 | 0.003941 | 0.264598 | 0.003481 | 0.603187 | 0.018580 | 0.036045 |
| logistic_balanced | logistic | 0.767674 | 0.002990 | 0.246644 | 0.001241 | 0.171929 | 0.694612 | 0.275634 |
| logistic_baseline | logistic | 0.767136 | 0.002593 | 0.248927 | 0.000652 | 0.521331 | 0.028651 | 0.054314 |

SMOTE was intentionally not used: class-weight comparison is sufficient for this controlled run, while ordinary SMOTE over sparse one-hot categorical features is not an appropriate default. No frozen-test result was used for selection.

## Locked model configuration

- `MODEL_CONFIG_FROZEN = TRUE`
- Selected candidate: `xgboost_depth6` (xgboost)
- Parameters: `{"colsample_bytree": 0.8, "learning_rate": 0.04, "max_depth": 6, "min_child_weight": 30, "n_estimators": 240, "reg_lambda": 8.0, "subsample": 0.8}`
- Selection rule: Selected from development-only 3-fold CV by highest mean ROC-AUC, then mean PR-AUC, mean F1, and lower ROC-AUC variability.
- Threshold-selection source: development-only out-of-fold probabilities.
- Locked technical threshold: `0.16`, selected by maximum F1; this is not an approved business-cost threshold.

## Development threshold trade-off table

| threshold | precision | recall | f1 | false_positive | false_negative |
| --- | --- | --- | --- | --- | --- |
| 0.050000 | 0.135926 | 0.848640 | 0.234321 | 107140 | 3006 |
| 0.060000 | 0.150043 | 0.798590 | 0.252622 | 89843 | 4000 |
| 0.070000 | 0.163725 | 0.752417 | 0.268931 | 76326 | 4917 |
| 0.080000 | 0.177062 | 0.707150 | 0.283211 | 65273 | 5816 |
| 0.090000 | 0.190313 | 0.665358 | 0.295969 | 56219 | 6646 |
| 0.100000 | 0.202346 | 0.622810 | 0.305453 | 48759 | 7491 |
| 0.110000 | 0.214394 | 0.583787 | 0.313614 | 42484 | 8266 |
| 0.120000 | 0.226736 | 0.548036 | 0.320764 | 37119 | 8976 |
| 0.130000 | 0.237550 | 0.513293 | 0.324789 | 32719 | 9666 |
| 0.140000 | 0.248470 | 0.480312 | 0.327514 | 28852 | 10321 |
| 0.150000 | 0.259428 | 0.450655 | 0.329292 | 25549 | 10910 |
| 0.160000 | 0.269925 | 0.422910 | 0.329528 | 22717 | 11461 |
| 0.170000 | 0.280860 | 0.396173 | 0.328696 | 20146 | 11992 |
| 0.180000 | 0.290944 | 0.371400 | 0.326285 | 17976 | 12484 |
| 0.190000 | 0.299567 | 0.344713 | 0.320558 | 16007 | 13014 |
| 0.200000 | 0.308457 | 0.323212 | 0.315663 | 14391 | 13441 |
| 0.210000 | 0.318645 | 0.303676 | 0.310980 | 12896 | 13829 |
| 0.220000 | 0.329517 | 0.284038 | 0.305092 | 11478 | 14219 |
| 0.230000 | 0.340065 | 0.267069 | 0.299179 | 10293 | 14556 |
| 0.240000 | 0.351555 | 0.250957 | 0.292858 | 9193 | 14876 |
| 0.250000 | 0.362212 | 0.235146 | 0.285165 | 8223 | 15190 |
| 0.260000 | 0.370726 | 0.219486 | 0.275729 | 7399 | 15501 |
| 0.270000 | 0.381464 | 0.205791 | 0.267351 | 6627 | 15773 |
| 0.280000 | 0.390234 | 0.192346 | 0.257682 | 5969 | 16040 |
| 0.290000 | 0.400649 | 0.180211 | 0.248602 | 5354 | 16281 |
| 0.300000 | 0.411080 | 0.168882 | 0.239409 | 4805 | 16506 |
| 0.310000 | 0.418055 | 0.156697 | 0.227952 | 4332 | 16748 |
| 0.320000 | 0.426096 | 0.144864 | 0.216218 | 3875 | 16983 |
| 0.330000 | 0.434381 | 0.134995 | 0.205977 | 3491 | 17179 |
| 0.340000 | 0.444246 | 0.124975 | 0.195072 | 3105 | 17378 |
| 0.350000 | 0.451961 | 0.116062 | 0.184696 | 2795 | 17555 |
| 0.360000 | 0.460774 | 0.107351 | 0.174133 | 2495 | 17728 |
| 0.370000 | 0.470181 | 0.099245 | 0.163895 | 2221 | 17889 |
| 0.380000 | 0.479128 | 0.091893 | 0.154210 | 1984 | 18035 |
| 0.390000 | 0.488554 | 0.084894 | 0.144653 | 1765 | 18174 |
| 0.400000 | 0.501288 | 0.078399 | 0.135592 | 1549 | 18303 |
| 0.410000 | 0.507282 | 0.071903 | 0.125954 | 1387 | 18432 |
| 0.420000 | 0.512426 | 0.065408 | 0.116008 | 1236 | 18561 |
| 0.430000 | 0.519356 | 0.060121 | 0.107767 | 1105 | 18666 |
| 0.440000 | 0.525233 | 0.053978 | 0.097895 | 969 | 18788 |
| 0.450000 | 0.533405 | 0.049849 | 0.091177 | 866 | 18870 |
| 0.460000 | 0.546866 | 0.046123 | 0.085071 | 759 | 18944 |
| 0.470000 | 0.550201 | 0.041390 | 0.076988 | 672 | 19038 |
| 0.480000 | 0.555718 | 0.038167 | 0.071429 | 606 | 19102 |
| 0.490000 | 0.565362 | 0.034189 | 0.064479 | 522 | 19181 |
| 0.500000 | 0.575843 | 0.030967 | 0.058773 | 453 | 19245 |

## One-time frozen-test evaluation

- ROC-AUC: `0.780060`
- PR-AUC: `0.270385`
- Precision: `0.272622`
- Recall: `0.426586`
- F1: `0.332653`
- Accuracy (supplementary only): `0.861828`
- Confusion matrix at locked threshold `0.16`: TN=50,887, FP=5,651, FN=2,847, TP=2,118.

This is the single unbiased frozen-test evaluation. The configuration must not be retuned from this result.
The versioned control record `reports/frozen_test_evaluation_record.json` prevents an accidental rerun against the same frozen IDs and binds this evaluation to the exported model and scored-data hashes.

## Explainability

Artifacts: `D:\ttdltq\reports\figures\modeling\frozen_test_roc_curve.png`, `D:\ttdltq\reports\figures\modeling\frozen_test_precision_recall_curve.png`, `D:\ttdltq\reports\figures\modeling\xgboost_shap_global_importance.png`, `D:\ttdltq\reports\figures\modeling\xgboost_shap_local_1.png`, `D:\ttdltq\reports\figures\modeling\xgboost_shap_local_2.png`, `D:\ttdltq\reports\figures\modeling\xgboost_shap_local_3.png`.

These explanations describe how features contribute to model predictions; they do not establish that any feature causes default.

## Scoring and Expected-Loss assumptions

- PD-to-score uses bad-to-good odds with base score 600, base odds 0.05, PDO 20, clipped to [300, 850]. Higher PD produces lower score.
- Risk tiers by score: `HIGH_RISK` ≤ 550, `MEDIUM_RISK` ≤ 650, `LOW_RISK` > 650. This is a technical presentation policy, not an approved lending policy.
- Recommendation is technical only: `APPROVE` when PD < locked threshold; otherwise `REJECT`.
- Expected Loss is the scenario `PD × LGD × EAD`, with LGD assumed at 0.45 and `AMT_CREDIT` used only as an EAD proxy, not claimed to be true EAD.
- Frozen-test scenario: approved=53,734, rejected=7,769, observed defaults among approved=2,847, expected loss of approved portfolio=773,709,964.44.
- Full scored portfolio scenario expected loss=6,191,419,576.33; this is not profit, realised loss, or a causal business-benefit claim.

## Production refit and handoff

- `FINAL_CONFIGURATION_FROZEN = TRUE`
- The locked pipeline was refit once on all 307,511 labeled canonical rows only after frozen-test evaluation. No full-training metric is presented as generalization evidence.
- Artifact: `models/full_inference_pipeline.joblib`
- Scored dataset: `data/processed/scored_dataset.parquet`
- TV3 integration reference cases: `reports/model_integration_profiles.csv` (two anonymized `SK_ID_CURR` cases with expected scored output).
- Reproducibility verification: deterministic=True, unknown-category-safe=True, PD range on fresh load=[0.010056, 0.493950].
- Re-run command: `& .\.venv\Scripts\python.exe -m src.models.modeling_pipeline`
