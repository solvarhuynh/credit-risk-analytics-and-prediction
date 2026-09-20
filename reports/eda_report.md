# Canonical Exploratory Data Analysis (EDA) Report

**Task ID:** TV2-DE-07 — Exploratory Data Analysis and Data Engineering Handoff
**Producer:** Member 2 (TV2) — Data Engineering & Data Pipeline
**Consumers:** Member 1 (TV1 — Modeling), Member 3 (TV3 — Dashboard & Application)
**Generation Timestamp (UTC):** 2026-09-20 16:25:40Z
**Execution Environment:** Python 3.13.5 (Strict Virtual Environment)

---

## 1. Scope and Data Source

This report documents the canonical Exploratory Data Analysis (EDA) conducted on the published Home Credit customer dataset. The analysis evaluates demographic profiles, financial ratios, external risk proxies, and historical bureau/transaction aggregations across the labeled population.

- **Primary Analytical Source:** `data/processed/cleaned_dataset.parquet` (Canonical labeled population derived from `application_train.csv`).
- **Baseline Raw Source for Cleaning Audit:** `data/raw/application_train.csv` (used exclusively to audit the `DAYS_EMPLOYED` anomaly sentinel transformation).
- **Strict Scope Boundary:** `application_test.csv` (48,744 rows without ground truth labels) is strictly excluded from all analytical profiling to prevent data leakage and label pollution.

---

## 2. Canonical Dataset Invariance and Shape

- **Canonical Dataset Path:** `data/processed/cleaned_dataset.parquet`
- **Shape:** 307,511 rows × 203 columns
- **Dataset SHA-256 Checksum:** `e3cbf594a5a0a072fc1625baa11563c323b8c392afc90cb46bb17bf48c12de75`
- **Manifest SHA-256 Checksum:** `e633885a14ad70b7f153cc27587722c77ee6c5b73ac03495872755df7a73d3f7`
- **Data Dictionary SHA-256 Checksum:** `efd1d1e1ad268f12ee38a901602f707a76b07a3b581ba99c25df9f6bd188ec39`
- **Integrity Status:** Byte-for-byte invariant with upstream verified baseline (DE-05 and DE-06).

---

## 3. TARGET Distribution and Class Imbalance

- **Ground Truth Label:** `TARGET` ((0, 1)), where `1` indicates client with payment difficulties (late payment > X days on at least one installment).
- **Non-Default (Target = 0):** 282,686 customers (91.9271%)
- **Default (Target = 1):** 24,825 customers (8.0729%)
- **Portfolio Observed Default Rate:** **8.0729%**
- **Imbalance Ratio:** Approximately 11.39 : 1. Stratified cross-validation is mandatory for downstream modeling.

---

## 4. Methodology and Missing-Value Handling

1. **Honest Missingness:** No global imputation is performed during EDA. Missing values are evaluated in their natural state.
2. **Approved Missing-History Policy:** Historical count features (18 columns) have unmatched customers filled with 0 per DE-05 contract. All financial ratios, rates, and amounts preserve true missingness (`NaN`).
3. **Display-Only Clipping:** When heavy right-skewness impedes visual interpretation, display-only clipping is applied strictly to plotting copies with explicit disclosure of thresholds and excluded observation counts.
4. **Non-Causality Principle:** All findings represent observed statistical associations and empirical distributions. No causal claims are asserted.

---

## 5. Detailed Visualizations and Empirical Findings

### 5.1. Figure 01: Income Distribution by Target

- **Artifact File:** `reports/figures/eda/01_income_distribution_by_target.png`
- **Objective:** Evaluate `AMT_INCOME_TOTAL` distributions between non-defaulting and defaulting applicants.
- **Empirical Evidence (Effective Sample Size: N = 307,511, Missing: 0):**
  * **Target = 0 (Non-Default, N = 282,686):**
    - Median: **148,500.0 CZK**
    - Interquartile Range (IQR): **90,000.0 CZK** (Q25: 112,500.0, Q75: 202,500.0)
  * **Target = 1 (Default, N = 24,825):**
    - Median: **135,000.0 CZK**
    - Interquartile Range (IQR): **90,000.0 CZK** (Q25: 112,500.0, Q75: 202,500.0)
- **Display-Only Clipping Disclosure:** Panel B clips income at the 99th percentile (**472,500 CZK**), excluding 3,014 observations (0.98%) from the density plot. The canonical dataset remains completely unclipped.
- **Key Observation:** Applicants who defaulted have a slightly lower median income (135,000 CZK vs 148,500 CZK, a difference of 13,500 CZK or ~9.1%), but income ranges exhibit substantial overlap. Income alone is not a deterministic predictor of credit risk.

---

### 5.2. Figure 02: Observed Default Rate by Age Group

- **Artifact File:** `reports/figures/eda/02_default_rate_by_age_group.png`
- **Objective:** Analyze default probability across customer age brackets using the canonical persisted derived feature AGE_GROUP (constructed from AGE_YEARS with authoritative boundaries [0, 25, 35, 45, 55, 65, 120], right=False).
- **Binning Specifications:** Fixed bin boundaries `[0, 25, 35, 45, 55, 65, 120]` years with `right=False`.
- **Empirical Evidence (Effective Sample Size: N = 307,511, Missing: 0, Out-of-range: 0):**

| Age Group | Total Applicants (N) | Defaults | Non-Defaults | Observed Default Rate (%) |
| :--- | :--- | :--- | :--- | :--- |
| **Under 25** | 12,233 | 1,504 | 10,729 | **12.29%** |
| **25-34** | 72,429 | 7,721 | 64,708 | **10.66%** |
| **35-44** | 84,261 | 7,085 | 77,176 | **8.41%** |
| **45-54** | 70,190 | 4,946 | 65,244 | **7.05%** |
| **55-64** | 60,522 | 3,281 | 57,241 | **5.42%** |
| **65+** | 7,876 | 288 | 7,588 | **3.66%** |

- **Reconciliation Audit:**
  * Sum of Customers: **307,511** (Matches canonical N = 307,511)
  * Sum of Defaults: **24,825** (Matches canonical TARGET=1 count = 24,825)
  * Sum of Non-Defaults: **282,686** (Matches canonical TARGET=0 count = 282,686)
  * Identity Check: 24,825 (Defaults) + 282,686 (Non-Defaults) == 307,511 (Customers).
- **Key Observation:** The reported group default rates decrease across the chosen age bins:
  * Youngest cohort (`Under 25`): **12.29%** default rate (1.52× portfolio baseline).
  * Oldest cohort (`65+`): **3.66%** default rate (0.45× portfolio baseline).
  * Older borrowers demonstrate lower observed default rates across the chosen fixed bins in this historical intake portfolio.

---

### 5.3. Figure 03: Default Rate by Occupation and Contract Type

- **Artifact File:** `reports/figures/eda/03_default_rate_by_occupation_and_contract.png`
- **Objective:** Evaluate default rate variations across 19 occupation classifications and loan contract types.
- **Empirical Evidence — Contract Types (N = 307,511):**
  * **Cash loans:** N = 278,232 | Default Rate: **8.35%**
  * **Revolving loans:** N = 29,279 | Default Rate: **5.48%**
- **Empirical Evidence — Occupation Types (N = 307,511):**
  * **Highest Risk Cohorts:**
    - `Low-skill Laborers`: N = 2,093 | Rate: **17.15%**
    - `Drivers`: N = 18,603 | Rate: **11.33%**
    - `Waiters/barmen staff`: N = 1,348 | Rate: **11.28%**
  * **Lowest Risk Cohorts:**
    - `Accountants`: N = 9,813 | Rate: **4.83%**
    - `High skill tech staff`: N = 11,380 | Rate: **6.16%**
  * **Explicit Missingness:** The `Missing/Unknown` category encompasses **96,391** customers (31.35%) with an observed default rate of **6.51%** (below portfolio average). Preserving missingness as a distinct category is critical for modeling. No demographic or employment identity may be inferred from missingness alone.

---

### 5.4. Figure 04: Spearman Rank Correlation Heatmap

- **Artifact File:** `reports/figures/eda/04_key_numeric_spearman_heatmap.png`
- **Objective:** Evaluate monotonic rank relationships among 12 key business numeric features without supervised target selection bias (`TARGET` omitted).
- **Strong Spearman Rank Associations (|ρ| >= 0.70):**
*Note: The threshold |ρ| >= 0.70 is a descriptive reporting threshold for monotonic rank association, not a formal statistical proof of multicollinearity or redundancy requiring automatic feature removal.*
- `AMT_CREDIT` <-> `AMT_ANNUITY`: Spearman ρ = 0.8302
- `AMT_CREDIT` <-> `AMT_GOODS_PRICE`: Spearman ρ = 0.9849
- `AMT_CREDIT` <-> `CREDIT_TO_INCOME_RATIO`: Spearman ρ = 0.7523
- `AMT_ANNUITY` <-> `AMT_GOODS_PRICE`: Spearman ρ = 0.8280
- `AMT_GOODS_PRICE` <-> `CREDIT_TO_INCOME_RATIO`: Spearman ρ = 0.7346
- `CREDIT_TO_INCOME_RATIO` <-> `ANNUITY_TO_INCOME_RATIO`: Spearman ρ = 0.7939
- **Modeling Implications for TV1:**
  * `AMT_CREDIT` and `AMT_GOODS_PRICE` share a very strong monotonic rank association (ρ = 0.9849), as consumer credit amounts directly track financed goods prices.
  * Pairwise Spearman correlation measures monotonic rank association; it is not proof of linear equivalence, multicollinearity, or redundancy requiring automatic feature removal.
  * TV1 should evaluate redundancy using training-only validation, coefficient stability, VIF where suitable on training folds, regularization (Ridge/L2), and out-of-sample performance.
  * Tree-based gradient boosting models (LightGBM/XGBoost) natively partition rank-associated features.

---

### 5.5. Figure 05: DAYS_EMPLOYED Sentinel Cleaning Audit

- **Artifact File:** `reports/figures/eda/05_days_employed_before_after.png`
- **Objective:** Validate the implementation of the DE-02 sentinel cleaning gate.
- **Audit Findings (N = 307,511):**
  * **Raw Sentinel Count (`DAYS_EMPLOYED == 365243`):** **55,374** observations (18.0072% of raw dataset).
  * **Cleaned Sentinel Count in Canonical Dataset:** **0** (100% purged).
  * **Cleaned Missing Count (`NaN` in `DAYS_EMPLOYED`):** **55,374** (exact 1-to-1 match with purged sentinels).
  * **Anomaly Flag (`DAYS_EMPLOYED_ANOM == 1`):** **55,374** indicator records preserved.
  * **Canonical Signed-Day Representation:** Valid non-sentinel `DAYS_EMPLOYED` values retain their canonical signed-day representation (<=0). Conversion to years is display-only for plotting.
- **Interpretability Constraint:** `DAYS_EMPLOYED_ANOM` is strictly an indicator of the anomalous 365243 sentinel in the application record; it must not be interpreted as confirmed retirement or unemployment status.

---

## 6. Initial Business & Storytelling Insights

1. **Demographic Age Pattern:** Observed loan default rates decrease across the defined age brackets in this dataset. Youngest applicants (<25) carry a 12.29% default rate compared to 3.66% for borrowers aged 65+.
2. **Employment Anomaly Significance:** Over 18.0% of the applicant population possesses the 365243 employment sentinel. Purging this extreme distortion into NaN while preserving the binary anomaly indicator ensures data quality and numerical integrity.
3. **Strong Financial Scale Rank Associations:** Loan amount, annuity, and goods price exhibit very high mutual rank correlation (>0.82), reflecting standard loan sizing policies.

---

## 7. Limitations and Non-Causality Statement

> [!IMPORTANT]
> **Non-Causality Declaration:** All findings presented in this report reflect empirical distributions and statistical correlations observed in the historical application dataset. These associations **do not imply causality**. No finding in this report supports claims such as "lower income causes default" or "younger age causes default".

---

## 8. Reproduction Command

To reproduce all five figures, recalculate metrics, and refresh this report deterministically:

```powershell
& .\.venv\Scripts\python.exe -m src.data.eda
```

---

## 9. Canonical Artifact Inventory & Invariance Status

| Artifact Path | File Size | SHA-256 Checksum | Invariance Status |
| :--- | :--- | :--- | :--- |
| `data/processed/cleaned_dataset.parquet` | 64,213,549 bytes | `e3cbf594a5a0a072fc1625baa11563c323b8c392afc90cb46bb17bf48c12de75` | **INVARIANT** |
| `data/processed/cleaned_dataset_manifest.json` | 17,082 bytes | `e633885a14ad70b7f153cc27587722c77ee6c5b73ac03495872755df7a73d3f7` | **INVARIANT** |
| `data/processed/data_dictionary.csv` | 124,732 bytes | `efd1d1e1ad268f12ee38a901602f707a76b07a3b581ba99c25df9f6bd188ec39` | **INVARIANT** |
| `reports/figures/eda/01_income_distribution_by_target.png` | 400,315 bytes | `263e84e199e9dc6cf8c2e26687c2cd636d7a9e527e439788d031f9a632b956e6` | Output deliverable |
| `reports/figures/eda/02_default_rate_by_age_group.png` | 198,222 bytes | `3d1b4352beb8862d815ebbcd2c8ff8758ff3c4872c5228dbb5478608742fc7df` | Output deliverable |
| `reports/figures/eda/03_default_rate_by_occupation_and_contract.png` | 462,301 bytes | `cb2826c968f08787e361b6cacf615552c4b6df7dca0947452fbf87e63eb88bb1` | Output deliverable |
| `reports/figures/eda/04_key_numeric_spearman_heatmap.png` | 488,137 bytes | `a7914f619916e59b445382359b14bfc429bc6de9fc559552a0c18f651ce5858b` | Output deliverable |
| `reports/figures/eda/05_days_employed_before_after.png` | 295,138 bytes | `d8a669f6094e8541002fc3babf88deae0860e0ca876c3b4a3ec2f696f4386315` | Output deliverable |

---

## 10. Handoff Readiness Status

- **TV1 Modeling Handoff:** **READY FOR HANDOFF** (Pending consumer acknowledgement)
- **TV3 Dashboard Handoff:** **READY FOR HANDOFF** (Pending consumer acknowledgement)
- **DE-08 Prerequisite Status:** **BLOCKED** until TV1 completes model training, prediction generation, and threshold analysis.
