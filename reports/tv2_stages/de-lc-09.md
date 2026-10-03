# DE-LC-09 — Dictionary, manifest and quality report

**Status: PASS**

Stage hoàn tất và có thể chuyển sang stage kế tiếp.

```json
{
  "dataset_id": "lending_club_2007_2018",
  "stage": "de-lc-09",
  "run_status": "PASS",
  "stage_status": "PASS",
  "accepted_rows": 2260701,
  "rejected_rows": 27648741,
  "labeled_rows": 1345350,
  "unresolved_rows": 915351,
  "target_counts": {
    "0": 1076751,
    "1": 268599
  },
  "target_0": 1076751,
  "target_1": 268599,
  "canonical_columns": 113,
  "dictionary_rows": 113,
  "dictionary_coverage": 1.0,
  "baseline_feature_count": 106,
  "baseline_forbidden_features": [],
  "quality_status": "PASS",
  "leakage_gate": "PASS",
  "canonical_path": "D:\\ttdltq\\data\\processed\\cleaned_dataset.parquet",
  "dictionary_path": "D:\\ttdltq\\data\\processed\\data_dictionary.csv",
  "quality_report_path": "D:\\ttdltq\\reports\\data_quality_report.md",
  "provenance": {
    "runner": "src.data.tv2_runner",
    "stage": "de-lc-09",
    "dependencies": [
      "de-lc-01",
      "de-lc-02",
      "de-lc-03",
      "de-lc-04",
      "de-lc-05",
      "de-lc-06",
      "de-lc-07",
      "de-lc-08"
    ],
    "source_artifacts": {
      "loan_application": "D:\\ttdltq\\data\\interim\\loan_application.parquet",
      "borrower_profile": "D:\\ttdltq\\data\\interim\\borrower_profile.parquet",
      "credit_profile": "D:\\ttdltq\\data\\interim\\credit_profile.parquet",
      "loan_pricing": "D:\\ttdltq\\data\\interim\\loan_pricing.parquet",
      "loan_outcome": "D:\\ttdltq\\data\\interim\\loan_outcome.parquet",
      "rejected_applications": "D:\\ttdltq\\data\\interim\\rejected_applications.parquet"
    },
    "generated_at_utc": "2026-10-03T17:24:32.633710+00:00"
  }
}
```
