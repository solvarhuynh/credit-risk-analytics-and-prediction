# Báo cáo migration Lending Club

## A. Trạng thái migration

**MIGRATION: PASS** cho phạm vi dataset reset/rewrite. Raw mới đã sẵn sàng local; code và contract đã chuyển đổi; pipeline, model và dashboard **chưa chạy lại** đúng yêu cầu.

## B. Di chuyển raw data

| Nguồn ban đầu | Đích canonical | Size | SHA-256 |
|---|---|---:|---|
| `accepted_2007_to_2018q4.csv/accepted_2007_to_2018Q4.csv` | `data/raw/accepted_loans.csv` | 1,675,133,810 bytes | `3EAE03C28FD9D2E8A076EBEB73507E8D4D0F44D90500DECDB0936E0933D1F36A` |
| `rejected_2007_to_2018q4.csv/rejected_2007_to_2018Q4.csv` | `data/raw/rejected_loans.csv` | 1,782,281,620 bytes | `07EB8468D55340D8CA4145C3E3C2E2D3E25FF83C44E432A825729EE6C99C4D45` |

Hash trước/sau giống nhau. Hai wrapper folder đã được xóa sau khi xác nhận rỗng. Raw được Git ignore và vẫn untracked.

## C. Dữ liệu cũ đã loại bỏ

- Đã xóa toàn bộ raw của dataset trước reset.
- `data/interim/`, `data/processed/`, `models/` đã reset, chỉ còn `.gitkeep`.
- Đã xóa quality/EDA/model reports, scored data, model binary và toàn bộ chart cũ.
- Giữ nguyên tài liệu đề bài `Barem-TTDLTQ.docx`, `overview-du-an.pdf`.

## D. Archive log

`logs/log_tv1.md`, `log_tv2.md`, `log_tv3.md` cũ được đổi thành các file tương ứng `_old.md`. Log hiện tại chỉ ghi trạng thái Lending Club reset, không mang metric cũ. Hai local tutor/runbook cũ cũng được archive và ignore; bản mới ghi trạng thái chờ triển khai.

## E. Code đã migrate

- `src/config.py`: đường dẫn canonical, dataset ID, `loan_id`, `target`.
- `src/data/`: loader theo chunk, cleaning riêng accepted/rejected, target mapping, column policy, business tables, join 1:1, quality/leakage gate, EDA và pipeline chuẩn bị chạy.
- `src/features/engineering.py`: `fico_avg`, loan/income ratio, credit-history months, date fields và fixed bands an toàn.
- `src/models/`: split/preprocessing dùng schema mới; Logistic là baseline bắt buộc; XGBoost chỉ tùy chọn; chưa train.
- `src/dashboard/simulator_engine.py`: interface Lending Club và trạng thái chờ artifact thật.

## F. Kiến trúc dữ liệu mới

```text
accepted → application + borrower + credit + pricing + outcome
                 └── join 1:1 với target-only → canonical labeled → TV1
rejected → rejected_applications → funnel/demand analytics
accepted + rejected → dim_date + dim_state → TV3
TV1 model/scored output → TV3 prediction views
```

## G. Leakage policy

Feature được phân loại thành `APPLICATION_TIME`, `CREDIT_SNAPSHOT`, `POLICY_DERIVED`, `POST_LOAN`, `TARGET_SOURCE`, `GEOGRAPHY_ANALYTICS`, `IDENTIFIER`, `TEXT_HIGH_CARDINALITY`, `ANALYTICS_ONLY`, `UNKNOWN_REVIEW_REQUIRED`. Baseline chỉ nhận hai lớp đầu; unknown chặn handoff.

Post-loan bị cấm gồm payment/principal/interest/recovery, last-payment/last-FICO, hardship và settlement. Pricing/grade là proxy policy; state/ZIP dành cho analytics mặc định.

## H. Docs/contracts đã viết lại

Đã cập nhật README, overview, ba architecture docs, data/model contract, raw inventory, TV2 handoff, leakage policy, ba setup guides và bốn task/assignment docs. Tất cả mô tả trạng thái chưa chạy lại, không công bố metric giả.

## I. Tests và notebooks

Tám notebook đã thành skeleton sạch, không output/execution count. Các test phụ thuộc schema cũ được thay bằng fixture Lending Club nhỏ cho cleaning, target, policy, join, ratios, dimensions/EDA, split và preprocessing. Theo lệnh migration, không chạy data-dependent tests.

## J. Generated outputs

Processed/interim/model/report cũ đã xóa. Video link được reset thành `NOT YET GENERATED FOR LENDING CLUB`. Chưa tạo output Lending Club mới.

## K. Quét legacy

Không còn exact legacy dataset field/table hay metric cũ trong code/docs/tests/log hiện hành. Match lịch sử chỉ được phép trong `logs/log_tv*_old.md`, local archive và Git history. Một vài tên cột mới có thể chứa chuỗi con ngắn giống mẫu tìm kiếm; policy audit xác nhận đó là trường Lending Club hợp lệ.

## L. Static validation

- `python -m compileall -q src tests`: PASS.
- `git diff --check`: PASS (các cảnh báo LF/CRLF của Git trên Windows không phải whitespace error).
- Notebook JSON audit: PASS, 8 file không có output và mọi code cell chưa chạy.
- Policy audit header-only: 156 cột accepted sau chuẩn hóa và 10 cột rejected sau chuẩn hóa, không còn `UNKNOWN_REVIEW_REQUIRED` trong raw hiện biết.
- Không full-load raw, không chạy pipeline/EDA/train/SHAP/dashboard.

## M. Nhóm file thay đổi

- DELETE: generated reports/charts, old active image, old data/model artifacts local.
- RENAME: ba log cũ và hai local runbook/tutor cũ.
- CREATE: leakage policy, column policy, test loader, log mới, local docs mới và báo cáo này.
- REWRITE: README, active docs, source data/features/models/dashboard, tests, notebooks.
- LOCAL ONLY: hai raw CSV nhiều GB và local tutor/runbook/archive.

## N. Điều chủ repository cần hiểu

1. Accepted có outcome nên dùng được cho default modeling; rejected không có outcome nên không train default.
2. Post-loan fields biết chuyện đã xảy ra sau cấp vay, dùng chúng sẽ làm mô hình “nhìn tương lai”. Raw vẫn giữ để audit/analytics nhưng model layer loại bỏ.
3. Nhiều interim table là các nhóm nghiệp vụ cùng grain `loan_id`, giúp chứng minh Join/Merge đúng và tránh nhân dòng.
4. TV1 sau này train trên `cleaned_dataset.parquet` chỉ với final-outcome accepted loans và feature đã duyệt.
5. Map dùng bang thật từ `addr_state`; không bịa tọa độ từ ZIP masked.
6. Model/result cũ bị xóa vì thuộc dataset khác; Logistic, threshold và mọi metric phải chạy lại.
7. Người hành động tiếp theo là TV2.

## O. Bước tiếp theo chính xác

**TV2 runs DE-LC-01 — Raw Inventory & Schema Profiling.**
