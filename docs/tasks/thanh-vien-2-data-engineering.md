# TV2 — Data Engineering và Technical EDA Roadmap

TV2 vẫn là **PRIMARY OWNER** độc quyền của Data Engineering; mở rộng dashboard/report không chuyển ownership modeling sang TV2.

## PRIMARY DATA ENGINEERING

| Stage | Input | Output | Validation / Definition of Done |
|---|---|---|---|
| DE-LC-01 Raw inventory & schema profiling | Hai raw CSV | Schema/profile report | Header, sample, size, status/state/date và policy được audit; không full-load |
| DE-LC-02 Accepted/rejected cleaning | Raw chunks | Clean chunks | Percent, term, employment, date, state, ZIP, missing/outlier được chuẩn hóa |
| DE-LC-03 Leakage classification | Raw columns + semantics | Column policy | Mọi cột có lớp; unknown chặn handoff; post-loan/policy-derived được xác nhận |
| DE-LC-04 Business-table normalization | Clean inputs | Business tables | Grain một dòng mỗi `loan_id`; rejected riêng |
| DE-LC-05 Target derivation | `loan_status` | `target` + unresolved audit | Chỉ final good/bad explicit; unresolved loại khỏi labeled set |
| DE-LC-06 Application-time features | Application/credit fields | FICO, ratios, dates, bands | Deterministic, no inf, zero denominator an toàn |
| DE-LC-07 Join canonical dataset | Safe tables + target | `cleaned_dataset.parquet` | one-to-one, bảo toàn keys/rows, leakage gate PASS |
| DE-LC-08 Dimensions/marts | Accepted + rejected clean | `dim_date`, `dim_state`, funnel marts | Semantics comparable, state/date hierarchy đúng |
| DE-LC-09 Dictionary/manifest/quality | Canonical + audits | Handoff artifacts | Coverage 100%, counts, LEAKAGE GATE rõ ràng |
| DE-LC-10 Static EDA | Processed + marts | 3–5 static charts | Không metric/insight giả |

## DASHBOARD VISUALS V07–V09 — PRIMARY

TV2 chuẩn bị data source, field semantics, measures, filters và candidate insight. TV1 là cross reviewer; TV3 sẽ tích hợp vào Master PBIX.

- V07 Loan Volume & Default Rate over Time — line/combo, có Year → Quarter → Month.
- V08 Accepted vs Rejected Applications — funnel, amount/count và decision.
- V09 Loan Purpose Analysis — treemap hoặc bar tùy final layout.

TV2 không cần trực tiếp chỉnh Master PBIX. Status: `PLANNED / WAITING FOR DATA`.

## STATIC EDA SHARED RESPONSIBILITY

TV2 duy trì canonical EDA source module/notebook và trực tiếp implement/interpret:

- EDA-03 loan amount/time distribution.
- EDA-04 accepted vs rejected/data distribution.

TV1 phụ trách interpretation EDA-01 FICO vs default và EDA-02 DTI/loan-to-income vs default. TV3 phụ trách interpretation EDA-05 geography/purpose/borrower segmentation. Cả ba phải hiểu đủ cả năm biểu đồ.

## REPORT AUTHORSHIP

TV2 là primary author cho dataset, data sources, raw schema, preprocessing, cleaning, missing/outlier, Join/Merge, calculated fields, data quality và technical EDA. TV1 là cross reviewer; TV3 kiểm tra cách phần data hỗ trợ dashboard story.

## CROSS-REVIEW OBLIGATIONS

- Review feature/data inputs mà TV1 dùng trong model.
- Review các measure dashboard có liên quan semantics nguồn.
- Review data-related storytelling claims và limitation.
- Sign-off TV2 handoff trước khi TV1 mở Model Input Gate.

TV2 không train model, không tạo model binary. Next step: **DE-LC-01 — Raw Inventory & Schema Profiling**.

## Execution interface

Mỗi stage được chạy độc lập nhưng có gate tuần tự bằng:

```powershell
python -m src.data.tv2_runner --stage de-lc-01
python -m src.data.tv2_runner --stage de-lc-02
python -m src.data.tv2_runner --stage de-lc-03
python -m src.data.tv2_runner --stage de-lc-04
python -m src.data.tv2_runner --stage de-lc-05
python -m src.data.tv2_runner --stage de-lc-06
python -m src.data.tv2_runner --stage de-lc-07
python -m src.data.tv2_runner --stage de-lc-08
python -m src.data.tv2_runner --stage de-lc-09
python -m src.data.tv2_runner --stage de-lc-10
```

Runner ghi report/marker dưới `reports/tv2_stages/`; stage kế tiếp bị `BLOCKED` nếu marker trước đó không phải `PASS`. DE-LC-07 mới được tạo `data/processed/cleaned_dataset.parquet`; DE-LC-09 mới tạo dictionary/manifest/quality report; DE-LC-10 mới tạo static EDA. Chi tiết input/output/PASS/FAIL nằm trong `docs/setup/tv2_setup.md`.
