# TV2 Execution Runbook — Lending Club

TV2 chạy theo đúng thứ tự **DE-LC-01 → DE-LC-10** bằng một interface duy nhất:

```powershell
python -m src.data.tv2_runner --stage de-lc-01
```

Mỗi stage tạo report tại `reports/tv2_stages/de-lc-XX.md` và marker tại `reports/tv2_stages/state/de-lc-XX.json`. Marker có một trong ba trạng thái: `PASS`, `FAIL`, `BLOCKED`.

**Do not continue to next stage unless current stage PASS.** Nếu stage FAIL/BLOCKED, sửa nguyên nhân, chạy lại đúng stage đó rồi mới tiếp tục. Không dùng `src.data.build_pipeline.run_build_pipeline()` như shortcut; stage runner mới là execution interface canonical.

## 0. Chuẩn bị chung

Raw local phải tồn tại:

- `data/raw/accepted_loans.csv`
- `data/raw/rejected_loans.csv`

Tạo environment nếu cần:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Các lệnh trên chỉ chuẩn bị dependency. Chúng không tạo processed data.

Tuỳ chọn khi test fixture nhỏ:

```powershell
python -m src.data.tv2_runner --stage de-lc-01 --raw-dir path/to/fixture/raw --reports-dir path/to/fixture/reports --interim-dir path/to/fixture/interim --processed-dir path/to/fixture/processed --chunksize 1000
```

## DE-LC-01 — Raw inventory & schema profiling

**Purpose:** Đọc header/sample, kích thước file, schema accepted/rejected, sample values, phân bố `loan_status`, semantics state/date/ZIP và policy coverage.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-01
```

**Expected inputs:** Hai raw CSV trong `data/raw/`; stage không đọc toàn bộ accepted/rejected cùng vào RAM. `loan_status` được scan theo chunk một cột để có distribution thực tế.

**Expected outputs:** `reports/tv2_stages/de-lc-01.md` và marker tương ứng.

**PASS criteria / inspect:** Có schema/sample của cả hai nguồn; size và columns hiện diện; policy accepted không có `UNKNOWN_REVIEW_REQUIRED`; report ghi rõ `addr_state`, ZIP masked và `loan_status`.

**If FAIL:** Kiểm tra tên/path raw, header, column policy và encoding; không tự thêm hoặc bịa location/status.

## DE-LC-02 — Accepted/rejected cleaning verification

**Purpose:** Xác minh percent, term, employment, dates, state, ZIP, missing representation và invalid values rõ ràng mà không statistical-impute.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-02
```

**Expected inputs:** `DE-LC-01 = PASS` và raw CSV; loader xử lý từng chunk.

**Expected outputs:** Report stage; chưa tạo canonical processed dataset.

**PASS criteria / inspect:** Accepted và rejected đều được đọc chunk-safe; không có infinity sau cleaning; số dòng, unresolved status, state/ZIP coverage được ghi; rejected giữ schema riêng; `target` chưa bị ép từ missing.

**If FAIL:** Xem exception/coverage trong report, sửa cleaning rule hoặc raw schema handling rồi chạy lại DE-LC-02. Không impute statistics ở TV2.

## DE-LC-03 — Leakage classification

**Purpose:** Phân loại mọi cột raw theo policy và chặn unknown.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-03
```

**Expected inputs:** `DE-LC-02 = PASS`, header accepted/rejected và `src/data/column_policy.py`.

**Expected outputs:** Report policy counts, model-default features, post-loan list và marker.

**PASS criteria / inspect:** Không còn `UNKNOWN_REVIEW_REQUIRED`; các lớp `APPLICATION_TIME`, `CREDIT_SNAPSHOT`, `POLICY_DERIVED`, `POST_LOAN`, `TARGET_SOURCE`, `GEOGRAPHY_ANALYTICS` xuất hiện đúng semantics; post-loan không vào model list.

**If FAIL:** Bổ sung review/classification chính thức trong `column_policy.py`, không whitelist mù; chạy lại DE-LC-03.

## DE-LC-04 — Business-table normalization

**Purpose:** Dựng và kiểm tra `loan_application`, `borrower_profile`, `credit_profile`, `loan_pricing`, `loan_outcome`, `rejected_applications`.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-04
```

**Expected inputs:** `DE-LC-03 = PASS` và raw chunks.

**Expected outputs:** Các Parquet interim trong `data/interim/` tương ứng sáu bảng.

**PASS criteria / inspect:** Mỗi accepted business table có một dòng mỗi `loan_id`; global duplicate/null key bị chặn; rejected table đứng riêng; post-loan chỉ ở `loan_outcome`; report ghi row counts.

**If FAIL:** Không bỏ qua duplicate và không nối rejected row-to-row với accepted. Xóa/đổi tên partial interim output sau khi xác định nguyên nhân, rồi chạy lại stage.

## DE-LC-05 — Target derivation

**Purpose:** Profile actual `loan_status`, map final good/bad và audit unresolved.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-05
```

**Expected inputs:** `DE-LC-04 = PASS`, accepted raw và `loan_outcome`.

**Expected outputs:** `data/interim/target_audit.csv` và stage report.

**PASS criteria / inspect:** `Fully Paid → 0`; `Charged Off/Default → 1`; `Current`, `Issued`, grace/late và status khác được thống kê unresolved, không ép thành 0; accepted `loan_id` unique.

**If FAIL:** Review status mapping explicit; không map legacy variant mù; nếu không có final status hợp lệ thì dừng và báo BLOCKED.

## DE-LC-06 — Application-time feature engineering

**Purpose:** Verify `fico_avg`, `loan_to_income_ratio`, `credit_history_months`, issue year/quarter/month và fixed bands.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-06
```

**Expected inputs:** `DE-LC-05 = PASS` và accepted raw chunks.

**Expected outputs:** Stage report; chưa tạo `cleaned_dataset.parquet`.

**PASS criteria / inspect:** Ratio denominator an toàn; không infinity; feature dependency không chứa `POST_LOAN` hoặc target; dates/bands deterministic; số dòng/labeled rows được ghi.

**If FAIL:** Kiểm tra source columns/date parsing/zero denominator; không tạo feature từ payment, recovery, settlement hoặc target.

## DE-LC-07 — Canonical modeling join

**Purpose:** Tạo canonical labeled dataset sau khi sáu stage đầu PASS.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-07
```

**Expected inputs:** Markers DE-LC-01…06 đều `PASS`; safe business tables từ DE-LC-04.

**Expected outputs:** `data/processed/cleaned_dataset.parquet` và stage report. Output chỉ được rename từ partial sau khi stage hoàn tất.

**PASS criteria / inspect:** Join dùng `loan_id`; one-to-one và row preservation; chỉ target từ `loan_outcome` đi vào canonical; `LEAKAGE GATE = PASS`; unresolved loans không nằm trong labeled dataset.

**If FAIL:** Giữ stage FAIL, không bàn giao TV1; kiểm tra marker/dependency, duplicate key và feature policy.

## DE-LC-08 — Dimensions and dashboard marts

**Purpose:** Dựng date/state dimensions và funnel accepted/rejected.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-08
```

**Expected inputs:** DE-LC-07 `PASS`, business tables và raw chunks.

**Expected outputs:** `data/interim/dim_date.parquet`, `dim_state.parquet`, `application_funnel.parquet`.

**PASS criteria / inspect:** `dim_state.state_code` unique; `dim_date.date` unique và có Year/Quarter/Month; funnel có decision accepted/rejected và chỉ dùng fields semantic tương đương; không coi state dimension là transaction table.

**If FAIL:** Kiểm tra date parsing, state normalization, dimension duplicate và schema funnel; không tạo tọa độ từ ZIP.

## DE-LC-09 — Dictionary, manifest and quality report

**Purpose:** Tạo handoff artifacts và quality gate độc lập.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-09
```

**Expected inputs:** DE-LC-08 `PASS`, canonical dataset và interim artifacts.

**Expected outputs:** `data/processed/data_dictionary.csv`, `cleaned_dataset_manifest.json`, `reports/data_quality_report.md`.

**PASS criteria / inspect:** Dictionary bao phủ 100% canonical columns; manifest có dataset ID/row counts/status; quality report ghi chính xác `LEAKAGE GATE = PASS`; key/target/infinity/coverage checks PASS.

**If FAIL:** TV1 chưa được handoff. Sửa quality/leakage/dictionary issue, chạy lại DE-LC-09 và không xóa bằng tay evidence.

## DE-LC-10 — Static EDA

**Purpose:** Sinh 3–5 static charts từ processed data/marts, không có model metrics.

**Command:**

```powershell
python -m src.data.tv2_runner --stage de-lc-10
```

**Expected inputs:** DE-LC-09 `PASS`, canonical dataset và funnel mart.

**Expected outputs:** 3–5 PNG trong `reports/figures/eda/` và `reports/eda_report.md`.

**PASS criteria / inspect:** Có loan amount, annual income và các chart default/purpose/funnel khả dụng; report ghi nguồn và sampling; không có ROC-AUC, SHAP, PD model metrics hoặc insight bịa.

**If FAIL:** Kiểm tra processed/mart schema và chart source; sửa EDA code, không chạy model để bù thiếu chart.

## Synthetic validation và giới hạn task này

Chỉ chạy fixture nhỏ:

```powershell
python -m pytest tests/data tests/features -q
```

Task này không chạy DE-LC-02…DE-LC-10 trên raw thật, không tạo processed output thật, không EDA thật, không train TV1, không mở Power BI, không commit/push. Mọi command stage ở trên là executable canonical path sau khi owner chủ động chạy.

## Trách nhiệm

TV2 vẫn là primary owner Data Engineering/technical EDA và V07–V09. TV1 review handoff và leakage/model inputs; TV3 tích hợp dimensions/marts vào Master PBIX. Chi tiết: `docs/tasks/thanh-vien-2-data-engineering.md` và `docs/tasks/dashboard-visual-plan.md`.
