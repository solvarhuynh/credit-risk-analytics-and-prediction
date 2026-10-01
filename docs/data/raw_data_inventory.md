# Kiểm kê Raw Lending Club 2007–2018

Kiểm tra migration ngày 01/10/2026 chỉ đọc header và sample nhỏ, không nạp toàn bộ CSV.

| Local file | Original file | Size (bytes) | SHA-256 |
|---|---|---:|---|
| `data/raw/accepted_loans.csv` | `accepted_2007_to_2018Q4.csv` | 1,675,133,810 | `3EAE03C28FD9D2E8A076EBEB73507E8D4D0F44D90500DECDB0936E0933D1F36A` |
| `data/raw/rejected_loans.csv` | `rejected_2007_to_2018Q4.csv` | 1,782,281,620 | `07EB8468D55340D8CA4145C3E3C2E2D3E25FF83C44E432A825729EE6C99C4D45` |

## Accepted

- 151 cột; key raw `id`, chuẩn hóa thành `loan_id`.
- Date chính `issue_d`; geography thật ở `addr_state`, ZIP bị masked.
- `loan_status` là nguồn target; chỉ outcome cuối đã duyệt đi vào labeled model.
- Dùng cho credit risk, portfolio, temporal và geographic analysis.
- Có nhiều cột hậu kỳ thanh toán/recovery/hardship/settlement; phải tách khỏi model X.

## Rejected

- 9 cột: amount, application date, title, risk score, DTI, ZIP, state, employment length, policy code.
- Không có shared `loan_id` và không có default outcome.
- Dùng cho demand, funnel và geography; không dùng train default model.
- Risk score/policy code là policy-derived; title là text cardinality cao.

Raw là immutable, local-only và được `.gitignore` bảo vệ. Loader phải dùng `usecols`/`dtype`/`chunksize` khi chạy thật.
