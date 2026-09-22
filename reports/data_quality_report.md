# Canonical Dataset Data Quality Report

## 1. Executive status
- **Quality Gate Outcome:** `PASS WITH WARNINGS`
- **Total Rows:** 307,511
- **Total Columns:** 203
- **Predictive Features:** 201
- **Target Default Rate:** 8.07% (24,825 defaults / 307,511 clients)
- **Data Integrity Summary:** 100% unique primary key (`SK_ID_CURR`), 0 null keys, 0 target mismatches, 0 infinite values, 0 suffix collisions.
- **Handoff Readiness:** Fully validated for consumption by TV1 (Feature Preprocessing & Modeling) and TV3 (Interactive Dashboard).

## 2. Artifact identity and reproducibility
| Artifact Item | Value |
| :--- | :--- |
| **Dataset Path** | `data/processed/cleaned_dataset.parquet` |
| **Dataset Size** | 64,520,535 bytes (~61.53 MB) |
| **Dataset SHA-256** | `6460999371297ff2f83418a8341b0c85d4a2e4dc6c29b29e793edd2a0c755c96` |
| **Manifest Path** | `data/processed/cleaned_dataset_manifest.json` |
| **Manifest Size** | 17,361 bytes |
| **Manifest SHA-256** | `33496d28258458501ee95b77c5f16aaede80501d6cb18d9130c802e8619a14e4` |
| **Base Git Commit** | `67499751ba6f7e705a0a63ede1e5a623c75a79b5` |
| **Generation Timestamp (UTC)** | `2026-09-22T20:38:19.875680+00:00` |
| **Population Scope** | `application_train_only` (labeled application population) |
| **Application Test Excluded** | `Yes (verified strictly excluded)` |

## 3. Dataset shape and grain
| Metric | Measured Value | Requirement | Status |
| :--- | :---: | :---: | :---: |
| **Row Count** | 307,511 | Exactly 307,511 | PASS |
| **Column Count** | 203 | Exactly 203 | PASS |
| **Unique SK_ID_CURR** | 307,511 | Exactly 307,511 | PASS |
| **Null SK_ID_CURR** | 0 | Exactly 0 | PASS |
| **Duplicate SK_ID_CURR** | 0 | Exactly 0 | PASS |
| **Min SK_ID_CURR** | 100,002 | 100,002 | PASS |
| **Max SK_ID_CURR** | 456,255 | 456,255 | PASS |
| **Row Monotonicity** | True | Sorted ascending | PASS |

## 4. Target integrity
| Class | Count | Percentage | Interpretation |
| :---: | :---: | :---: | :--- |
| `0` | 282,686 | 91.9271% | Non-default (repaid without severe payment difficulties) |
| `1` | 24,825 | 8.0729% | Default (client with payment difficulties >= X days) |

- **Target dtypes:** `int64` (strictly binary {0, 1}).
- **Target nulls:** 0 (100% labeled).
- **Target-by-ID Preservation:** 100% matched to raw `application_train.csv` (0 mismatches).
- **Imbalance Ratio:** ~11.39 : 1 (Stratified K-Fold cross-validation mandatory).

## 5. Schema and feature-group composition
| Feature Group | Column Count | Provenance / Role | Description |
| :--- | :---: | :--- | :--- |
| `identifier` | 1 | `SK_ID_CURR` | Primary key identifier |
| `target` | 1 | `TARGET` | Ground truth prediction label |
| `application_raw` | 120 | `application_train` | Cleaned applicant demographic, financial, and external scores |
| `application_cleaning` | 1 | `DAYS_EMPLOYED_ANOM` | Binary sentinel flag for DAYS_EMPLOYED == 365243 anomaly |
| `application_derived` | 6 | DE-03 Engineered | Financial ratios, applicant age, and tenure features |
| `bureau` | 20 | `bureau`, `bureau_balance` | Credit bureau history and delinquency aggregates |
| `previous_application` | 15 | `previous_application` | Past Home Credit application history and decision counts |
| `installments` | 10 | `installments_payments` | Repayment timeliness, shortfall, and payment ratio aggregates |
| `pos_cash` | 11 | `POS_CASH_balance` | POS and cash loan contract history, DPD, and late counts |
| `credit_card` | 18 | `credit_card_balance` | Credit card utilization, limit, balance, and overdue metrics |
| **TOTAL** | **203** | | **201 Predictive Features + 1 ID + 1 Label** |

## 6. Data Dictionary coverage
- **Data Dictionary Path:** `data/processed/data_dictionary.csv`
- **Coverage:** 100.0% (203 of 203 columns documented).
- **Metadata Completeness:** 0 empty or NaN metadata cells across all 22 contract columns.
- **Order Alignment:** 100% identical sequence matching canonical dataset column order.
- **Encoding & Delimiter:** UTF-8 with BOM (`utf-8-sig`), comma-separated, LF (`\n`) line endings.

## 7. Missingness analysis
- **Total Dataset Cells:** 62,424,733
- **Total Missing Cells:** 14,515,910 (23.25%)
- **Columns with Missingness:** 130 of 203
- **Columns without Missingness:** 73 of 203
- **Fully Missing Columns:** 0 (Zero fully missing columns)

### Missingness Buckets Distribution
| Missingness Bucket | Column Count | Percentage | Key Characteristics & Examples |
| :--- | :---: | :---: | :--- |
| `exactly 0%` | 73 | 35.96% | Complete columns: `SK_ID_CURR`, `TARGET`, 18 zero-filled count features, and clean application fields |
| `greater than 0% and less than 5%` | 12 | 5.91% | Minor application missingness (`AMT_ANNUITY`, `AMT_GOODS_PRICE`, engineered financial ratios) |
| `greater than or equal to 5% and less than 20%` | 48 | 23.65% | Moderate missingness (`EXT_SOURCE_3` 19.83%, `DAYS_EMPLOYED` / `EMPLOYED_YEARS` 18.01% from sentinel handling, `BUREAU_` gap 14.31%) |
| `greater than or equal to 20% and less than 50%` | 9 | 4.43% | Substantial missingness (`OCCUPATION_TYPE` 31.35%, building mode/medi features) |
| `greater than or equal to 50% and less than 80%` | 61 | 30.05% | High missingness (`EXT_SOURCE_1` 56.38%, `COMMONAREA_AVG` 69.87%, credit card balance features `CC_*` 71.74% from 28.26% coverage) |
| `greater than or equal to 80% and less than 100%` | 0 | 0.00% | Extreme missingness (None in canonical dataset) |
| `exactly 100%` | 0 | 0.00% | Fully unpopulated columns (None in canonical dataset) |
| **TOTAL** | **203** | **100.00%** | **Mutually exclusive and collectively exhaustive partition** |

### Top 15 Features by Missing Rate
| Column Name | Feature Group | Missing Count | Missing Rate | Nature of Missingness |
| :--- | :--- | :---: | :---: | :--- |
| `CC_UTILIZATION_MEAN` | `credit_card` | 221,475 | 72.02% | Historical unrecorded / non-cardholder |
| `CC_UTILIZATION_MAX` | `credit_card` | 221,475 | 72.02% | Historical unrecorded / non-cardholder |
| `CC_DPD_DEF_MAX` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_BALANCE_MEAN` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_DPD_MEAN` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_MONTHS_BALANCE_MIN` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_DPD_DEF_MEAN` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_DPD_MAX` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_MONTHS_BALANCE_MAX` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_CREDIT_LIMIT_MAX` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_LATE_MONTH_RATE` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_PAYMENT_TOTAL_SUM` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_BALANCE_MAX` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_CREDIT_LIMIT_MEAN` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |
| `CC_PAYMENT_TOTAL_MEAN` | `credit_card` | 220,606 | 71.74% | Historical unrecorded / non-cardholder |

## 8. Numeric quality
- **Infinite Values:** 0 positive infinity (`+inf`), 0 negative infinity (`-inf`).
- **Bounded-Rate Violations:** 0 (10 of 10 bounded rates strictly within `[0.0, 1.0]`).
- **Negative Count Violations:** 0 (All count features strictly `>= 0`).
- **Unbounded Ratios:** Validated that ratios such as `CREDIT_TO_INCOME_RATIO`, `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_ANNUITY_RATIO`, `PREV_CREDIT_TO_APPLICATION_RATIO_MEAN`, `INSTAL_PAYMENT_RATIO_MEAN`, and `CC_UTILIZATION_MEAN/MAX` legitimately exceed 1.0 without artificial clamping.

## 9. Categorical quality
- **Categorical Columns Count:** 17
- **Unexpected Blank Strings:** 0 columns with blanks (0 total).
- **Literal String Sentinels (`NULL`, `null`, `N/A`, `NA`, `-999`):** 0 columns with string sentinels (0 total).
- **Rare Categories (< 0.1% frequency):** Observed in 6 categorical columns (e.g. specialized occupation types or rare organization industries); retained for tree models.

## 10. Constant and near-constant features
- **All-Null Features (0 non-null values):** 0 features.
- **Strictly Constant Features (1 unique non-null value):** 0 features.
- **Near-Constant Features (Dominant value share >= 99.5%):** 16 features.
- **DAYS_EMPLOYED_ANOM Note:** `DAYS_EMPLOYED_ANOM` has a dominant value share of ~81.99% (majority 0 when sentinel not detected, minority 1 when sentinel 365243 detected) and therefore does not meet the 99.5% near-constant threshold. It is retained as a meaningful binary data-quality and anomaly indicator.

| Column Name | Dominant Value | Dominant Frequency Share | Action Recommendation |
| :--- | :---: | :---: | :--- |
| `FLAG_MOBIL` | `1` | 99.9997% | Retained for TV1 tree-based variance analysis |
| `FLAG_CONT_MOBILE` | `1` | 99.8133% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_2` | `0` | 99.9958% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_4` | `0` | 99.9919% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_7` | `0` | 99.9808% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_9` | `0` | 99.6104% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_10` | `0` | 99.9977% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_11` | `0` | 99.6088% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_12` | `0` | 99.9993% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_13` | `0` | 99.6475% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_14` | `0` | 99.7064% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_15` | `0` | 99.8790% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_17` | `0` | 99.9733% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_19` | `0` | 99.9405% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_20` | `0` | 99.9493% | Retained for TV1 tree-based variance analysis |
| `FLAG_DOCUMENT_21` | `0` | 99.9665% | Retained for TV1 tree-based variance analysis |

## 11. Historical-source coverage
| Source Table | Prefix | Agg Rows | Matched Clients | Unmatched Clients | Coverage Rate | Aggregate-Only Clients (Test) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `bureau` | `BUREAU_` | 305,811 | 263,491 | 44,020 | 85.69% | 42,320 |
| `previous_application` | `PREV_` | 338,857 | 291,057 | 16,454 | 94.65% | 47,800 |
| `installments_payments` | `INSTAL_` | 339,587 | 291,643 | 15,868 | 94.84% | 47,944 |
| `pos_cash_balance` | `POS_` | 337,252 | 289,444 | 18,067 | 94.12% | 47,808 |
| `credit_card_balance` | `CC_` | 103,558 | 86,905 | 220,606 | 28.26% | 16,653 |

## 12. Join integrity
- **Cardinality Enforcement:** All 5 joins were executed 1-to-1 with `validate='one_to_one'`.
- **Row Preservation:** Exactly 307,511 rows before and after every join (0 rows dropped, 0 rows multiplied).
- **Feature Collision Prevention:** 0 merge suffix columns (`_x`, `_y`) detected.
- **Missing-History Policy:** Exactly 18 approved count features filled with integer 0 for unmatched clients; rates, amounts, and descriptive statistics retained genuine `NaN` values.

## 13. Leakage and as-of-time review
- **Target Leakage:** `TARGET` is strictly placed at index 1 and never included as a feature. Zero aggregate features contain target information.
- **Identifier Leakage:** `SK_ID_CURR` is documented as an identifier and strictly excluded from model feature sets.
- **Test Set Contamination:** 48,744 rows of `application_test.csv` are strictly excluded from the canonical training dataset.
- **Historical As-Of Validity:** All historical events occurred strictly prior to application date (`DAYS <= 0` validated in DE-04).
- **Two-Stage Bureau Hierarchy:** `bureau_balance` aggregated to `SK_ID_BUREAU` before joining `bureau`, avoiding customer-level inflation.
- **Installment Consolidation:** 653,483 split-payment records consolidated on installment grain, preserving true obligation amounts.
- **Preprocessing Independence:** Zero imputers, scalers, encoders, or resamplers were fit on the canonical dataset. All transformations must be fit exclusively on TV1 training folds.

## 14. Contract compliance matrix
| Contract Requirement | Specification | Measured Status | Compliance |
| :--- | :--- | :--- | :---: |
| **Primary Key** | Non-null, unique `SK_ID_CURR` | 307,511 unique, 0 nulls | **COMPLIANT** |
| **Target Label** | Binary `TARGET` in {0, 1} | 282,686 zeros, 24,825 ones | **COMPLIANT** |
| **Mandatory Contract Columns** | 14 minimum columns present | All 14 verified present | **COMPLIANT** |
| **Demographic Features** | `AGE_YEARS`, `AGE_GROUP`, `EMPLOYED_YEARS` | All 3 present and verified | **COMPLIANT** |
| **Cleaning Sentinel Flag** | `DAYS_EMPLOYED_ANOM` | Present (1 if 365243, else 0) | **COMPLIANT** |
| **Aggregate Features** | 74 DE-04 features across 5 sources | Exactly 74 present | **COMPLIANT** |
| **Missing-History Policy** | 18 count features zero-filled | Verified 1,077,105 cells filled | **COMPLIANT** |
| **No Infinity** | Zero `+inf` / `-inf` cells | Verified 0 infinite cells | **COMPLIANT** |
| **Bounded Rates** | 10 bounded rates in `[0.0, 1.0]` | Verified 0 violations | **COMPLIANT** |
| **Deterministic Ordering** | Rows sorted by `SK_ID_CURR` ascending | Verified monotonic increasing | **COMPLIANT** |
| **Data Dictionary** | 203 rows, 22 columns, complete metadata | Verified 100% coverage | **COMPLIANT** |

## 15. Warnings and downstream handling
1. **Historical aggregate coverage is below 100% across all 5 historical sources (natural credit domain behavior).**
2. **43,041 orphan SK_ID_BUREAU records in bureau_balance were excluded from customer aggregates in DE-04.**
3. **653,483 installment split-payment records in installments_payments were consolidated in DE-04 without duplication.**
4. **Unmatched customers retain genuine missing values (NaN) for historical rates, amounts, and statistics.**
5. **16 near-constant features (dominant share >= 99.5%) are retained in the dataset.**

## 16. TV1 modeling handoff notes
- **File to Load:** Read directly from `data/processed/cleaned_dataset.parquet` using `pd.read_parquet()`.
- **Identifier Exclusion:** Must exclude `SK_ID_CURR` from predictor feature matrix `X`.
- **Target Separation:** Separate `TARGET` as target vector `y`; never pass `TARGET` into feature transformation pipelines.
- **Cross-Validation Scheme:** Must use `StratifiedKFold` (e.g. 5 folds) based on `TARGET` to preserve the ~8.07% default rate across all folds.
- **Leakage-Safe Preprocessing Rule:** Fit all encoders (`OneHotEncoder`, `TargetEncoder`, `OrdinalEncoder`), imputers (`SimpleImputer`, `IterativeImputer`), and scalers (`StandardScaler`, `RobustScaler`) **exclusively on the train fold** of each split, then transform validation/test folds.
- **Handling Missing Historical Features:** GBDT models (LightGBM, XGBoost, CatBoost) handle native `NaN` values naturally. Do not blanket impute missing history with arbitrary constants before splitting.

## 17. TV3 dashboard handoff notes
- **Analytical Population:** `cleaned_dataset.parquet` represents the complete, cleaned historical population of 307,511 applicants.
- **Field Semantics:** Consult `data/processed/data_dictionary.csv` for human-readable descriptions, units, and categories for all UI labels and chart tooltips.
- **Prediction Scoring Views:** For model prediction outputs, risk scores, and threshold deciles, wait for TV1's `data/processed/scored_dataset.parquet` artifact.

## 18. Reproduction commands
```powershell
# 1. Rebuild and publish canonical dataset (if needed):
& .\.venv\Scripts\python.exe -m src.data.build_pipeline

# 2. Re-run data quality audit and generate Data Dictionary & Report:
& .\.venv\Scripts\python.exe -m src.data.quality_report

# 3. Execute quality report test suite:
& .\.venv\Scripts\python.exe -m pytest tests\data\test_quality_report.py -v
```

## 19. Final quality-gate result
```text
=================================================================
TV2-DE-06 DATA QUALITY GATE RESULT: PASS WITH WARNINGS
-----------------------------------------------------------------
CANONICAL DATASET: data/processed/cleaned_dataset.parquet (307,511 rows, 203 cols)
DATA DICTIONARY:   data/processed/data_dictionary.csv (203 rows, 22 cols)
QUALITY REPORT:    reports/data_quality_report.md (19 sections)
STATUS:            VERIFIED & READY FOR TV1 / TV3 HANDOFF
=================================================================
```
