# TV2 Data Handoff — Lending Club

Trạng thái: **NOT YET GENERATED**.

Sau khi TV2 chạy DE-LC-01 đến DE-LC-10, handoff cho TV1 phải có:

- `cleaned_dataset.parquet`: một dòng mỗi accepted loan có final outcome;
- `data_dictionary.csv`: dtype, policy class, model eligibility cho mọi cột;
- `cleaned_dataset_manifest.json`: dataset ID, counts và run metadata;
- `reports/data_quality_report.md`: có mục `LEAKAGE GATE` PASS;
- interim business tables và `dim_date`/`dim_state` cho audit/dashboard.

Hiện `data/interim/` và `data/processed/` đang trống ngoài `.gitkeep`. Không có row count, hash processed hoặc metric Lending Club để công bố. TV1 phải chờ đủ ba artifact canonical và gate PASS.
