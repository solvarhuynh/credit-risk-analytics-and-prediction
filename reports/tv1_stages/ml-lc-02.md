# ML-LC-02 — Freeze deterministic train/validation/frozen-test split

**Status: PASS**

ML-LC-02 hoàn tất; split đã được validate và persist/reuse an toàn.

```json
{
  "source_artifact": "D:\\ttdltq\\data\\processed\\cleaned_dataset.parquet",
  "source_rows": 1345350,
  "approved_feature_count_from_ml_lc_01": 106,
  "split_ratios": {
    "train": 0.6000000000000001,
    "validation": 0.2,
    "frozen_test": 0.2
  },
  "random_state": 42,
  "stratified": true,
  "train_rows": 807210,
  "validation_rows": 269070,
  "frozen_test_rows": 269070,
  "target_counts": {
    "train": {
      "0": 646051,
      "1": 161159
    },
    "validation": {
      "0": 215350,
      "1": 53720
    },
    "test": {
      "0": 215350,
      "1": 53720
    }
  },
  "full_target_counts": {
    "0": 1076751,
    "1": 268599
  },
  "default_rates": {
    "full": 0.19964990522912254,
    "train": 0.1996494096951227,
    "validation": 0.19965064853012227,
    "test": 0.19965064853012227
  },
  "overlap_checks": {
    "train_validation": 0,
    "train_test": 0,
    "validation_test": 0
  },
  "union_rows": 1345350,
  "coverage_status": "PASS",
  "stratification_rate_differences": {
    "train": 4.955339998335972e-07,
    "validation": 7.433009997226403e-07,
    "test": 7.433009997226403e-07
  },
  "deterministic": true,
  "frozen": true,
  "reused_existing_artifacts": true,
  "artifact_paths": {
    "train": "D:\\ttdltq\\data\\processed\\modeling\\train_ids.parquet",
    "validation": "D:\\ttdltq\\data\\processed\\modeling\\validation_ids.parquet",
    "test": "D:\\ttdltq\\data\\processed\\modeling\\test_ids.parquet",
    "manifest": "D:\\ttdltq\\data\\processed\\modeling\\split_manifest.json"
  },
  "preprocessing_fitted": false,
  "model_trained": false
}
```
