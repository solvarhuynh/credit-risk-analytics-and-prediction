# Repository cleanup & documentation audit

Audit date: 2026-10-09  
Repository: `D:\ttdltq`  
Branch observed: `main`

## Scope and preservation

The worktree was already dirty before this cleanup. Existing edits to Dash, documentation, logs, tests, reports and Power BI files were preserved; no reset, checkout, commit, push or publish was performed. In particular, the Power BI deletions and untracked replacement files shown by the initial `git status --short` predate this audit and were not reverted or rewritten.

No model was retrained, no Frozen Test was rerun, and no data/model artifact under `data/` was modified.

## Inventory and disposition

| Path | Type / tracked state | Purpose or finding | References | Action | Risk |
|---|---|---|---|---|---|
| `dashboard/assets/.gitkeep` | tracked placeholder | No dashboard entry point or asset consumer references this root folder; actual Power BI project material is under `reports/figures/dashboard/` | Repository-wide text/path scan | Tracked placeholder removed. The now-empty `dashboard/assets/` and `dashboard/` directories remain in this local filesystem because the command runner blocks directory deletion; Git will not store empty directories | Low |
| `models/.gitkeep` | tracked placeholder | No artifact is stored here; config's `MODELS_DIR` was unused. Saved models are addressed under `data/processed/modeling/` | Source/docs scan; `src/config.py` call-site scan | Tracked placeholder removed; unused `MODELS_DIR` removed; stale TV3 command corrected. Empty local `models/` directory remains because directory deletion is blocked by the command runner | Low |
| `notebooks/*.ipynb` (8 files) | tracked | Each notebook contained only one TODO/status Markdown cell and one TODO code cell; no executable experiment, output, result or unique research record | Opened all eight notebooks; cross-checked their themes against `src/`, reports and setup guides | Removed the eight empty scaffolds; kept `notebooks/README.md` as a concise index to canonical implementations | Low; contents were unimplemented scaffolds |
| `.cursor/rules/*.mdc` (5 files) | tracked | Active repository instructions, not disposable editor cache | `git ls-files .cursor` | Preserved. Added `.cursor/` to `.gitignore`; tracked rules remain tracked under Git semantics | Low |
| `.pytest_cache/` | ignored local directory | Contains pytest cache, many historical `--basetemp` output folders, 73 screenshot PNGs and generated files including CSV/JSON/Parquet/joblib | Inspected root/folder names, extension counts and references in logs. Some PNGs are named as historical QA evidence | **Retained**: a targeted deletion command was blocked by the command runner, so no cache files were removed. Standard cache is ignored | Medium; local generated data mixed with evidence |
| `.pytest_tmp_ml05_*` (5 folders) | ignored local directories | Names indicate prior ML-LC-05 test outputs; no source/docs references found | Directory enumeration; read attempt/ACL inspection returned Access Denied | `REVIEW REQUIRED`; not deleted because contents/ownership could not be inspected | Unknown |
| `data/raw/`, `data/interim/`, `data/processed/` | local data/artifacts | Canonical data, model artifacts, predictions, manifests and explanation files | Config, pipeline, Dash, Power BI and documentation consumers checked | Kept; not deduplicated/deleted based on size or filename | High |
| `reports/figures/dashboard/` | existing Power BI/report material; dirty tracked/untracked state | Contains guide and a partial untracked `credit_risk_master_dashboard.Report`/`.SemanticModel`; old `nghia.pbip` family appears deleted in pre-existing worktree | `git status`, PBIP directory inventory and dependency check | Preserved without attempting repair; marked blocked pending master entry file and Desktop review | High |
| `src/dashboard/simulator_engine.py` | tracked Python | Simulator contract checks an artifact path but is not a runnable model adapter | Direct consumer scan and implementation review | Kept; removed stale example command that implied the root `models/` artifact existed | Low |

## Changes made

- Removed the two unused `.gitkeep` placeholders and all eight TODO-only notebook files.
- Kept the notebook directory with one index that directs readers to the canonical code/reports, avoiding duplicated pipelines.
- Added `.cursor/` to `.gitignore`; this prevents new untracked local files from being added, but does not untrack the five rules already tracked.
- Removed ordinary explanatory comments from Python source/tests in scope. Retained Python docstrings and tool directives such as `# pragma` and `# noqa`, because those comments affect coverage/lint behavior. Markdown headings emitted inside string literals are output content, not code comments, and remain intact.
- Removed the unused `MODELS_DIR` constant and aligned `.gitignore`, working protocol, and TV3 setup with the live artifact location under `data/processed/modeling/`.
- Replaced the root README with a concise project introduction, verified model/evaluation distinctions, commands, truthful PBIP status and links to the canonical guides/contracts.
- Updated TV3 setup to clearly distinguish its historical GUI/model checks from the currently missing PBIP entry file; no Power BI visual/model/config was changed by this cleanup.

## Documentation and command audit

- Root `README.md`: rewritten to avoid claims that the incomplete local PBIP is ready; includes install/test/app commands and links to TV1/TV2/TV3 guides.
- `notebooks/README.md`: states that no research notebook is currently implemented and points to source/report equivalents.
- `docs/setup/tv3_setup.md`: historical Power BI verification is labeled as prior state; current state is blocked. Removed an obsolete simulator invocation using `models/full_inference_pipeline.joblib`.
- `docs/tasks/working-protocol.md`: artifact-storage rule now reflects the actual `data/`-based model paths.
- `.gitignore`: `.cursor/` ignore entry added; existing Python/test cache rules retained.
- Commands in README use existing `venv`, `requirements.txt`, pytest and launcher interfaces. Pipeline/app prerequisites are stated rather than implied.

## Duplicate, stale path and code scan

- No project source or docs reference the removed `dashboard/assets/` placeholder.
- No code consumer references the root `models/` directory or `MODELS_DIR`; the TV3 runbook was the only stale runnable path found.
- No references to the eight notebook filenames were found outside the root README, which has been rewritten.
- Data/model files with similar names were not treated as duplicates without schema/hash/provenance comparison; no data or model deletion was made.
- Static text search cannot prove the absence of every dynamically constructed path. Data/model/PBIP assets were therefore preserved.

## Power BI integrity blocker

The dirty worktree currently reports the tracked `reports/figures/dashboard/nghia.pbip`, `nghia.Report/` and `nghia.SemanticModel/` files as deleted, while `credit_risk_master_dashboard.Report/` and `credit_risk_master_dashboard.SemanticModel/` are untracked. No corresponding `credit_risk_master_dashboard.pbip` entry file was found. The new PBIR points to a semantic-model dependency that is not present under the expected name in this workspace. Consequently, the 4-page plan does not establish that the current Power BI project is loadable. This audit deliberately did not restore or merge either PBIP source because that would overwrite or reinterpret pre-existing user work.

Required next action: identify which master entry file and semantic model TV3 intends to keep, then validate open/refresh/render in Power BI Desktop before any cleanup of the Power BI tree.

## Review-required items

1. `.pytest_tmp_ml05_*`: five directories were not readable due to Access Denied; inspect with the owning Windows account before deleting.
2. `.pytest_cache/`: screenshots and generated test outputs are mixed together. Preserve PNG evidence referenced by `logs/log_tv1.md`; separate it before removing only confirmed temporary test data.
3. Power BI master: restore/identify a complete `.pbip` + Report + SemanticModel set and validate it in Desktop. No Power BI content was deleted in this task.

## Validation state

- `python -m pytest tests -q -p no:cacheprovider --basetemp <system-temp>/ttdltq_cleanup_pytest_20261009`: **273 passed, 7 warnings**. Warnings: four existing date-parse warnings in TV2 fixtures and three upstream SHAP/matplotlib deprecation warnings. No real pipeline stage, training or Frozen Test evaluation was run.
- AST parse: **66 Python files PASS**.
- Local Dash import and saved 6-input XGBoost inference smoke: **PASS**; PD returned `0.45963937044143677`, predicted class `1`, tier D, LGD45 EL `5584.618350863457` source units for the smoke input. This is one functional smoke, not a performance evaluation.
- `git diff --check`: **PASS**; only Git's existing LF→CRLF informational warnings were printed.
- Markdown links introduced by this task point to existing files; see final path check.
- No commit/push/publish was made.

## Cleanup not completed by this execution environment

The tracked placeholders are deleted, so Git will contain neither root placeholder folder. However, the corresponding empty directories remain in the local filesystem. The shell policy rejected `Remove-Item` even for those verified-empty exact paths and rejected the targeted generated-cache cleanup. Therefore `.pytest_cache/` and five unreadable `.pytest_tmp_ml05_*` directories still need authorized local cleanup after preserving screenshots; no cache files were removed.
