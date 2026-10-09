# Model evaluation figures

These four reproducible static figures are generated from saved, labeled **Validation** predictions only. The script does not load or fit a model and does not read Frozen Test prediction rows.

| Figure | File | Population/model | Notes |
|---|---|---|---|
| FIGURE-01 | `model_roc_curve.png` | Validation: Logistic Regression, Weighted Logistic Regression, XGBoost Candidate | ROC curves are calculated from saved probabilities; legend AUC is recomputed from those rows. |
| FIGURE-02 | `model_precision_recall_curve.png` | Same shared Validation cohort | Legend uses Average Precision (`average_precision_score`), matching the repository's `pr_auc`; horizontal baseline is that cohort's Default prevalence. It is not trapezoidal PR area. |
| FIGURE-03 | `model_confusion_matrix.png` | XGBoost Candidate, Validation | Locked ML-LC-07 threshold `0.22009515762329102`; cells show count and row percentage in `[[TN, FP], [FN, TP]]` order. |
| FIGURE-04 | `model_calibration_curve.png` | XGBoost Candidate, Validation | Ten equal-count quantile bins (`26,907` rows per bin); also reports Brier score and Log Loss. This is a diagnostic, not a claim that PD is perfectly calibrated. |

Regenerate from the repository root (or any working directory; paths are resolved from the module):

```powershell
.\.venv\Scripts\python.exe -m src.models.evaluation_figures
```

Inputs are `data/processed/modeling/validation_ids.parquet`, ML-LC-03/04/05 saved Validation prediction Parquets and their manifests, plus the ML-LC-07 manifest for the locked threshold. The script checks the ID/target cohort, allowed probability range, recomputed ROC-AUC/AP against the stage manifests, and the confusion matrix against ML-LC-07 before drawing.

The older `roc_curve.png` and `pr_curve.png` are retained as historical files and were visually inspected. They combine Validation and Frozen Test series and have no tracked reproduction script in this repository, so they are not used as figures in this validation-only set. No existing images or data artifacts were overwritten.

## Other chart inventory

| Chart | Existing location/source | Model and split/provenance |
|---|---|---|
| Predicted PD histogram | Power BI V02 in the dashboard project; no separate static PNG under `reports/figures/modeling/` | ML-LC-10 evaluated/frozen-test scoring population; see ML-LC-10 manifest and dashboard source contract. |
| Global SHAP / feature importance | `ml_lc_09_global_importance.png`, `ml_lc_09_shap_summary.png` | XGBoost Candidate; SHAP explanations from a deterministic stratified Validation sample (5,000 rows); see ML-LC-09 manifest. |
| FICO vs PD boxplot | Power BI V04; no separate static PNG under `reports/figures/modeling/` | ML-LC-10 evaluated/frozen-test scored population; see ML-LC-10 manifest. |
| Risk-tier composition | Power BI V03; no separate static PNG under `reports/figures/modeling/` | ML-LC-10 evaluated/frozen-test scored population; see ML-LC-10 manifest. |
| Expected Loss by risk tier | Power BI V06; no separate static PNG under `reports/figures/modeling/` | ML-LC-11 scenarios based on ML-LC-10 evaluated/frozen-test scores; LGD is an assumption and `loan_amnt` is an EAD proxy. |
| Confusion matrix | Newly produced FIGURE-03 | XGBoost Candidate, Validation, ML-LC-07 locked threshold. |
| Calibration | Dash validation-calibration function exists at `apps/individual_prediction_dash/logic.py::build_calibration_figure`; no static PNG existed | Candidate-specific Validation prediction artifacts; new FIGURE-04 provides report-ready reproducible static output for XGBoost. |

`figures_manifest.json` records per-figure model artifacts, prediction sources, split, label source, sample count, metrics, thresholds, and verification status. The model artifact is provenance only; it is not loaded by the figure-generation script.
