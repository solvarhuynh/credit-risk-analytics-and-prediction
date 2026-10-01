# Data Contract — Lending Club 2007–2018

## Grain, key và nhãn

- Raw accepted: một dòng một khoản vay đã được cấp; key chuẩn `loan_id` từ raw `id`.
- Raw rejected: một dòng một hồ sơ bị từ chối; không có default outcome và không dùng huấn luyện default.
- Canonical modeling: một dòng một accepted loan có kết quả cuối đã biết.
- `target=0`: `Fully Paid`; `target=1`: `Charged Off` hoặc `Default`.
- Các status khác, kể cả legacy variants, giữ cho analytics nhưng loại khỏi labeled modeling cho tới khi TV2 profile và policy được duyệt.

## Raw và interim

Raw local: `accepted_loans.csv`, `rejected_loans.csv`.

Interim dự kiến: `loan_application`, `borrower_profile`, `credit_profile`, `loan_pricing`, `loan_outcome`, `rejected_applications`, `dim_date`, `dim_state`. Mỗi bảng accepted có grain một dòng mỗi `loan_id` và join `one_to_one`.

Canonical được dựng bằng `loan_application LEFT JOIN borrower_profile LEFT JOIN credit_profile LEFT JOIN loan_outcome[target only]`. `loan_pricing` dùng analytics nhưng không vào baseline mặc định. Post-loan chỉ nằm trong outcome, không join vào X.

## Chính sách dữ liệu

- Missing raw được chuẩn hóa; statistical imputation thuộc preprocessing TV1.
- `issue_d` và `earliest_cr_line` parse riêng; không dùng ngày thanh toán/settlement để dự đoán.
- `state_code` từ `addr_state`, `country = United States`; ZIP giữ dạng chuỗi masked, không suy tọa độ.
- Join phải bảo toàn số dòng và uniqueness của `loan_id`.
- Rejected không merge row-to-row với accepted; chỉ có thể concat mart funnel trên trường tương đương thật.

## Output TV2 dự kiến

- `data/processed/cleaned_dataset.parquet`
- `data/processed/data_dictionary.csv`
- `data/processed/cleaned_dataset_manifest.json`
- `reports/data_quality_report.md`
- Các interim table/dimension nói trên; dashboard mart là tùy chọn có kiểm soát.

Manifest phải ghi dataset ID, row counts accepted/rejected/labeled/unresolved và trạng thái run. Dictionary phải bao phủ mọi cột, dtype, policy class và cờ model-eligible.

## Gate bắt buộc

`loan_id` non-null/unique; target nhị phân; không infinity; ratio an toàn; date/state coverage được báo cáo; dictionary bao phủ schema; join bảo toàn grain; LEAKAGE GATE không có post-loan, policy-derived, geography, identifier/target hay unknown trong baseline feature list.
