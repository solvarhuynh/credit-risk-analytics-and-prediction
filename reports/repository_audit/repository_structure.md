# Repository structure

This is the repository layout observed after the safe structural cleanup. Local-only data directories are shown even though their large contents are ignored by Git. The Power BI files are in a pre-existing incomplete/dirty state; they are shown as present workspace material, not as a validated project.

```text
ttdltq/
├── .cursor/rules/                 Project workflow and coding rules (tracked)
├── apps/
│   └── individual_prediction_dash/ Dash app, UI logic, assets and user guide
├── data/
│   ├── raw/                       Local Lending Club accepted/rejected CSVs
│   ├── interim/                   Intermediate business tables and dimensions
│   └── processed/
│       └── modeling/              Canonical dataset and local model/evaluation artifacts
├── docs/
│   ├── architecture/              Architecture and decision records
│   ├── contracts/                 Data and model contracts
│   ├── data/                      Data workflow, policies and handoff guides
│   ├── setup/                     Canonical TV1/TV2/TV3 runbooks
│   └── tasks/                     Team responsibilities and dashboard plans
├── logs/                          Append-only TV1/TV2/TV3 work histories
├── notebooks/
│   └── README.md                  Index; no implemented research notebook currently
├── reports/
│   ├── figures/
│   │   ├── dashboard/             Power BI guides and incomplete local PBIP material
│   │   ├── eda/                   Static EDA figures and presentation guide
│   │   └── modeling/              Modeling figures
│   ├── repository_audit/          This cleanup audit and structure map
│   ├── tv1_stages/                Modeling stage reports/manifests documentation
│   └── tv2_stages/                Data Engineering stage reports
├── src/
│   ├── data/                      Loading, cleaning, aggregation and stage runner
│   ├── dashboard/                 TV3 simulator contract (not a deployed app)
│   ├── features/                  Application-time feature engineering
│   └── models/                    Split, modeling, explainability, scoring and EL
├── tests/                         Data, feature, model and app tests
├── .gitignore
├── README.md                      Project entry point
├── requirements.txt
└── run_prediction_app.bat         Local Dash launcher
```

## Main entry points

- **Project overview:** `README.md`
- **TV2 pipeline:** `docs/setup/tv2_setup.md`; runner `python -m src.data.tv2_runner --stage de-lc-01`
- **TV1 modeling:** `docs/setup/tv1_setup.md`; stage runner `python -m src.models.tv1_runner --stage <stage>`
- **TV3 dashboard:** `docs/setup/tv3_setup.md`; currently blocked pending complete PBIP entry/dependencies and Desktop validation
- **Dash demo:** `apps/individual_prediction_dash/README.md`; launcher `run_prediction_app.bat`
- **Shared policy:** `docs/contracts/data_contract.md` and `docs/contracts/model_contract.md`
- **Repository audit:** `reports/repository_audit/repo_cleanup_audit.md`

`models/` and `dashboard/` are intentionally absent: neither root directory had a live artifact/consumer. Model files that the app and pipeline use remain under `data/processed/modeling/` locally.
