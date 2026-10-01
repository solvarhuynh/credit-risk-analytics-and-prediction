# Cấu trúc và liên kết repository

```text
data/raw/accepted_loans.csv ─┐
                             ├─ TV2 cleaning + policy classification
data/raw/rejected_loans.csv ─┘
       │
       ├─ loan_application ─┐
       ├─ borrower_profile ─┼─ one-to-one join + target only
       ├─ credit_profile ───┤          ↓
       ├─ loan_pricing      │   cleaned_dataset.parquet
       └─ loan_outcome ─────┘          ↓ TV1
                                 Logistic + scoring
                                        ↓ TV3
                              Power BI risk dashboard
```

`loan_pricing` phục vụ analytics nhưng baseline loại mặc định. `loan_outcome` giữ post-loan và target source; canonical chỉ nhận `target`, không nhận payment/recovery fields. Rejected đứng riêng; chỉ concat funnel mart trên field thật sự tương đương.

`dim_date` hỗ trợ hierarchy Year → Quarter → Month. `dim_state` gồm `state_code` và `country`; Map ở cấp bang.
