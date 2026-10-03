# TV2 Final Handoff Audit

Ngày audit: **2026-10-04**
Phạm vi: kiểm tra độc lập toàn bộ TV2 Data Engineering cho Lending Club trước khi mở TV1 Modeling.
Audit này thực hiện sau khi sửa đúng blocker DE-LC-09; không rebuild DE-LC-07, không sửa raw data, target policy, leakage policy, DE-LC-08 hoặc EDA.

## 1. Final gate

```text
TV2_HANDOFF_PASS
```

TV2 data handoff được phê duyệt cho TV1 Modeling.

### Repair đã xác minh

- Root cause trước đây: `_stage_09` gán `excluded_unresolved_status_rows = None`; manifest chỉ có `accepted_labeled_rows` và thiếu các row counts/provenance bắt buộc.
- DE-LC-09 hiện derive `accepted_rows` từ năm accepted business tables, `rejected_rows` từ `rejected_applications.parquet`, và `unresolved_rows = accepted_rows - labeled_rows`; không hard-code dataset-specific count.
- Validation fail-closed kiểm tra count reconciliation, target sum, canonical/dictionary coverage, leakage gate, baseline forbidden list và run/stage status trước khi ghi artifact PASS.
- [data_quality_report.md](data_quality_report.md) hiện ghi unresolved **915,351**; [cleaned_dataset_manifest.json](../data/processed/cleaned_dataset_manifest.json) có đầy đủ count, status, paths và provenance.

Canonical modeling dataset không bị rebuild hoặc thay đổi semantics trong repair.

## 2. Stage status

| Stage | Marker | Runtime evidence | Artifact evidence | Final audit status |
|---|---|---|---|---|
| DE-LC-01 | PASS | Raw inventory/profile theo chunk, sample 5 dòng, date/state/status coverage | Raw accepted/rejected tồn tại, schema 151/9 cột | PASS |
| DE-LC-02 | PASS | Cleaning evidence trên 2,260,701 accepted và 27,648,741 rejected; unresolved accepted = 915,351 | Stage report và marker tồn tại | PASS |
| DE-LC-03 | PASS | Policy classification, `unknown_columns = []`, leakage classes được kiểm tra | Stage report/marker tồn tại | PASS |
| DE-LC-04 | PASS | Sáu business tables có row count và grain được xác nhận | Năm accepted tables + một rejected table tồn tại | PASS |
| DE-LC-05 | PASS | Target audit và status mapping đã chạy trên toàn bộ accepted rows | `target_audit.csv` tồn tại; resolved target counts khớp | PASS |
| DE-LC-06 | PASS | Mười engineered features, không infinity, không POST_LOAN/TARGET_SOURCE dependency | Stage report/marker tồn tại | PASS |
| DE-LC-07 | PASS | Canonical join runtime: 1,345,350 resolved rows, leakage gate PASS | `cleaned_dataset.parquet` tồn tại và đạt key/target checks | PASS |
| DE-LC-08 | PASS | Dimension/funnel runtime và rerun-safe atomic promotion đã được kiểm tra | `dim_date`, `dim_state`, `application_funnel` tồn tại, counts chính xác | PASS |
| DE-LC-09 | PASS | Real stage rerun sau repair; count reconciliation và handoff validation PASS | Dictionary 113/113; manifest/quality report đầy đủ và nhất quán | PASS |
| DE-LC-10 | PASS | Static EDA runtime tạo đúng 5 figure canonical | Năm PNG non-empty và `eda_report.md` khớp | PASS |

Tất cả 10 marker runtime và cả 10 audit status hiện là `PASS`.

## 3. Raw data

| File | Rows đã audit | Columns | Size |
|---|---:|---:|---:|
| `data/raw/accepted_loans.csv` | 2,260,701 | 151 | 1,675,133,810 bytes |
| `data/raw/rejected_loans.csv` | 27,648,741 | 9 | 1,782,281,620 bytes |

- Accepted date range: `2007-06-01 → 2018-12-01`.
- Rejected date range: `2007-05-26 → 2018-12-31`.
- State coverage: 51 unique state codes; missing state lần lượt 33 accepted và 22 rejected ở raw profiling.
- Raw files vẫn được xử lý như immutable input; không có output pipeline ghi đè raw.
- `.gitignore` loại `data/raw/*`, nên hai CSV raw lớn không bị track vào Git.

## 4. Interim artifacts

| Artifact | Grain | Rows | Key validation / status |
|---|---|---:|---|
| `loan_application.parquet` | Một dòng / accepted `loan_id` | 2,260,701 | `loan_id` non-null, unique |
| `borrower_profile.parquet` | Một dòng / accepted `loan_id` | 2,260,701 | `loan_id` non-null, unique |
| `credit_profile.parquet` | Một dòng / accepted `loan_id` | 2,260,701 | `loan_id` non-null, unique |
| `loan_pricing.parquet` | Một dòng / accepted `loan_id` | 2,260,701 | `loan_id` non-null, unique; giữ riêng khỏi baseline join |
| `loan_outcome.parquet` | Một dòng / accepted `loan_id` | 2,260,701 | `loan_id` non-null, unique; POST_LOAN/target source tách đúng policy |
| `rejected_applications.parquet` | Một dòng / rejected application source | 27,648,741 | Giữ riêng, không merge vào accepted, không bịa rejected key |
| `dim_date.parquet` | Một dòng / ngày | 4,238 | Date key unique, có hierarchy thời gian |
| `dim_state.parquet` | Một dòng / state code | 51 | Dimension key unique |
| `application_funnel.parquet` | Một dòng / application decision | 29,909,442 | Accepted + rejected, không nhân đôi |

Không còn file `*.partial.parquet`. DE-LC-08 đã được kiểm tra với atomic promotion và rerun-safe behavior; bug pandas index alignment làm rejected funnel tăng gấp đôi không còn xuất hiện.

## 5. Canonical dataset

Artifact: `data/processed/cleaned_dataset.parquet`

| Metric | Audited value |
|---|---:|
| Rows | 1,345,350 |
| Columns | 113 |
| Unique `loan_id` | 1,345,350 |
| Null `loan_id` | 0 |
| Duplicate `loan_id` | 0 |
| Target `0` | 1,076,751 |
| Target `1` | 268,599 |
| Null target | 0 |
| Numeric infinity | 0 |
| Baseline feature count | 106 |
| Forbidden baseline features | `[]` |

Target policy đã đối chiếu:

- `Fully Paid → 0`.
- `Charged Off → 1`.
- `Default → 1`.
- `Current`, late/grace, missing status và hai legacy policy statuses không bị map mù; tổng unresolved bị loại khỏi labeled canonical là **915,351**.

Canonical là một dòng cho mỗi accepted loan có final outcome đã resolve; rejected applications không được dùng để suy ra default target.

## 6. Leakage gate

Kết quả leakage gate trên baseline `X`: **PASS**.

- Allowed baseline classes: `APPLICATION_TIME`, `CREDIT_SNAPSHOT`.
- `loan_id`: `IDENTIFIER`, không vào `X`.
- `loan_status`: `TARGET_SOURCE`, không vào `X`.
- `target`: chỉ là `y`, không vào `X`.
- `grade`, `sub_grade`, `int_rate`: `POLICY_DERIVED`, không vào baseline.
- `state_code`, `zip_code`: `GEOGRAPHY_ANALYTICS`, không vào baseline.
- `total_pymnt`, `recoveries` và last-payment/last-FICO/hardship/settlement fields: `POST_LOAN`, không vào baseline.
- Không có `UNKNOWN_REVIEW_REQUIRED` trong policy classification hoặc baseline feature list.

## 7. Funnel audit

| Decision | Expected/source rows | Actual rows | Difference |
|---|---:|---:|---:|
| accepted | 2,260,701 | 2,260,701 | 0 |
| rejected | 27,648,741 | 27,648,741 | 0 |
| total | 29,909,442 | 29,909,442 | 0 |

Funnel hiện dùng index alignment đúng, kiểm tra row preservation, ghi partial trước khi promote và không append vào canonical output cũ khi rerun. Kết quả này đã được xác nhận lại sau lỗi duplication trước đó.

## 8. EDA audit

Đúng 5 hình canonical tồn tại, non-empty và khớp [eda_report.md](eda_report.md):

1. `reports/figures/eda/eda_01_loan_amount_distribution.png` — histogram loan amount.
2. `reports/figures/eda/eda_02_dti_by_target.png` — boxplot DTI by target; P99 display cap `38.35`, chỉ ảnh hưởng hiển thị.
3. `reports/figures/eda/eda_03_default_by_fico.png` — observed default rate theo FICO band; minimum group `n = 100`, band `<650` có `n = 2` nên không diễn giải rate.
4. `reports/figures/eda/eda_04_fico_dti_heatmap.png` — FICO × DTI; cell dưới `n = 100` bị mask.
5. `reports/figures/eda/eda_05_accepted_loan_volume_over_time.png` — accepted volume theo thời gian, lấy toàn bộ `loan_application.parquet`, không dùng resolved-only canonical.

EDA chỉ mô tả association; không diễn giải association thành causation.

## 9. Tests and validation

Focused DE-LC-09 tests:

```powershell
.venv\Scripts\python.exe -m pytest tests/data/test_quality_report.py tests/data/test_tv2_runner.py tests/data/test_build_pipeline.py -q --basetemp D:\ttdltq\.pytest_tmp_de09_focused
```

Kết quả: **31 passed, 4 warnings**.

Regression suite:

```powershell
.venv\Scripts\python.exe -m pytest tests/data tests/features -q --basetemp D:\ttdltq\.pytest_tmp_de09_regression
```

Kết quả: **75 passed, 4 warnings**.

Real runtime:

```powershell
.venv\Scripts\python.exe -m src.data.tv2_runner --stage de-lc-09
```

Kết quả: **DE-LC-09 PASS**; marker và stage report cập nhật thành công.

`git diff --check` được chạy lại sau khi hoàn tất report/log này: **PASS** (exit code 0). Git chỉ phát ra cảnh báo line-ending LF/CRLF cho hai file đã có thay đổi trước đó; không có whitespace error.

## 10. Documentation consistency

**Kết quả: PASS.**

Các tài liệu kỹ thuật về target, leakage, artifact names, funnel, manifest và 5 EDA charts khớp runtime artifacts. Đã cập nhật:

- [docs/data/tv2_data_handoff.md](../docs/data/tv2_data_handoff.md) để trạng thái `GENERATED / QUALITY AND LEAKAGE GATE PASS` và ghi các count handoff hiện hành.
- [docs/tasks/thanh-vien-2-data-engineering.md](../docs/tasks/thanh-vien-2-data-engineering.md) đã thay dòng `Next step: DE-LC-01` bằng trạng thái `TV2_HANDOFF_PASS`.
- Các entry cũ trong [logs/log_tv2.md](../logs/log_tv2.md) có status `NOT RUN`/`INTERRUPTED` của những lần chạy trước. Đây là lịch sử, không dùng làm current runtime evidence; không rewrite lịch sử trong audit này.

Không còn contradiction current-status nào ảnh hưởng handoff.

## 11. Known limitations

- Target chỉ đại diện cho accepted loans có final outcome đã resolve; 915,351 accepted rows unresolved bị loại khỏi labeled modeling set.
- Rejected applications không có observed loan outcome nên không dùng để suy ra default.
- `state_code` là geographic key cấp bang; ZIP là masked. Không tạo synthetic location hoặc tọa độ giả.
- Baseline model cố ý loại policy-derived, post-loan, geography, identifier và analytics-only fields.
- EDA default-rate/target relationships là association, không phải causal effect.
- EDA-05 là accepted volume theo thời gian; không dùng resolved-only default-rate trend vì vintage gần đây có outcome resolution chưa đầy đủ.

## 12. TV1 handoff decision

**TV1 Modeling có thể bắt đầu.** Handoff đã đạt `TV2_HANDOFF_PASS`; task này không tự khởi động TV1 Modeling.

Audit artifact được tạo:

- `reports/tv2_final_handoff_audit.md`
- `reports/tv2_final_handoff_audit.json`

Không commit, không push, không chạy TV1 Modeling trong task này.
