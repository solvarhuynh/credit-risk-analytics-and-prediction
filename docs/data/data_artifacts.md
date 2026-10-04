# Data Artifacts Guide — Lending Club

Tài liệu này giải thích các file dữ liệu chính trong pipeline Lending Club theo cách dễ trình bày khi review hoặc bảo vệ đồ án.

## 1. Bức tranh lớn

### Cách hiểu đơn giản - muốn hiểu rõ hơn thì đọc các bảng sau nữa

| Tên file | Cách hiểu |
|---:|---|
|`loan_application.parquet` | thông tin chính của khoản vay như loan_id, số tiền vay, thời hạn, purpose, issue date. Đây là “bảng gốc” khi join canonical.
borrower_profile.parquet: thông tin người vay như thu nhập, employment, home ownership, verification, state/ZIP.|
|`credit_profile.parquet` |toàn bộ thông tin tín dụng/FICO/DTI/account history. Đây là nguồn chính cho nhiều feature model.|
|`loan_pricing.parquet` | các trường do Lending Club quyết định hoặc định giá như int_rate, grade, sub_grade, installment, funded amount. Dùng cho analytics, nhưng baseline model mặc định không dùng.|
|`loan_outcome.parquet` | chứa loan_status, target và các trường phát sinh sau khi khoản vay đã chạy như payment, recovery, hardship, settlement. Bảng này giữ outcome riêng để tránh leakage.|
|`rejected_applications.parquet` | toàn bộ hồ sơ bị từ chối sau cleaning. Không dùng train default model vì không có outcome, nhưng dùng cho funnel/dashboard accepted vs rejected.|  

Ba lớp có ý nghĩa khác nhau:

- `raw/`: dữ liệu nguồn, giữ gần với nguồn gốc để audit và làm input cho cleaning.
- `interim/`: lớp trung gian đã chuẩn hóa theo nghiệp vụ. Đây không phải file tạm vô nghĩa; các bảng này giúp kiểm tra grain, join và phục vụ analytics/dashboard.
- `processed/`: sản phẩm chuẩn để handoff, đặc biệt là dataset modeling canonical.

Trong báo cáo DE-LC-07 và quality report hiện có, canonical dataset ghi nhận `1,345,350` accepted loans có kết quả cuối đã resolve; null/duplicate key là `0 / 0`, infinity là `0`, và leakage gate là `PASS`. Các số liệu khác chỉ nên lấy từ manifest/quality report của run tương ứng, không suy đoán từ tên file.

## 2. Raw layer

### `data/raw/accepted_loans.csv`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng là một accepted/issued loan; khóa chuẩn sau cleaning là `loan_id` từ raw `id`. |
| Nguồn và mục đích | Nguồn chính cho modeling default và accepted-loan analytics. |
| Người dùng | TV2 cho cleaning/normalization; TV1 cho modeling sau handoff; TV3 cho dashboard qua các artifact đã chuẩn hóa. |
| Model usage | Không dùng raw trực tiếp làm `X`; chỉ dùng sau cleaning, policy classification, target derivation và leakage gate. |
| Cảnh báo | Có `loan_status` và các field post-loan. Payment, recovery, settlement, last-payment hoặc field tương tự không được đi vào model features. |

### `data/raw/rejected_loans.csv`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng là một rejected application. |
| Nguồn và mục đích | Nguồn cho funnel, demand và accepted-vs-rejected analytics. |
| Người dùng | TV2 chuẩn hóa; TV3 dùng mart funnel cho dashboard. |
| Model usage | Không dùng để train default model vì không có default outcome tương ứng. |
| Cảnh báo | Không row-to-row merge với accepted loans và không tự tạo target/default label. |

## 3. Interim layer — DE-LC-04 business tables

Năm bảng accepted có cùng grain: **một dòng cho mỗi `loan_id`**. Chúng được tách theo nhóm nghiệp vụ để join one-to-one rõ ràng và tránh nhân dòng. `loan_pricing` vẫn là bảng riêng; nó không vào baseline model join mặc định.

### `data/interim/loan_application.parquet`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi `loan_id`. |
| Main purpose | Bảng lõi mô tả khoản vay tại thời điểm application/origination. |
| Typical contents | `loan_id`, `loan_amnt`, `issue_d`, `purpose`, `term_months`, `application_type`. |
| Main consumers | Canonical join của TV2; time-based analytics và dashboard. |
| Model usage | Có thể cung cấp các field an toàn sau policy review; không tự động dùng toàn bộ cột. |
| Important caution | Đây là base table, nhưng chỉ join với các bảng đã kiểm tra uniqueness và đúng grain. |

### `data/interim/borrower_profile.parquet`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi `loan_id`. |
| Main purpose | Bối cảnh người vay và thông tin hồ sơ. |
| Typical contents | Employment, income, home ownership, verification, state/ZIP và joint-applicant fields. |
| Main consumers | TV1/TV2 cho model input review; dashboard segmentation và geography analytics. |
| Model usage | Chỉ dùng các field thuộc policy class được phép, chủ yếu application-time; geography không vào baseline `X` mặc định. |
| Important caution | Không lấy mọi cột profile làm feature chỉ vì chúng nằm trong cùng bảng. ZIP là masked string và không phải tọa độ. |

### `data/interim/credit_profile.parquet`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi `loan_id`. |
| Main purpose | Snapshot thông tin credit bureau tại hoặc gần thời điểm origination. |
| Typical contents | FICO, DTI, delinquency, account counts, utilization, balances, inquiries và credit history. |
| Main consumers | TV1 cho baseline modeling; TV2 cho quality/leakage review; analytics phù hợp. |
| Model usage | Đây là nguồn lớn của baseline features thuộc `CREDIT_SNAPSHOT`, sau khi qua policy và quality gate. |
| Important caution | Không đưa các field biết kết quả sau cấp vay vào `X`; missing vẫn phải theo policy, không tự suy diễn. |

### `data/interim/loan_pricing.parquet`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi `loan_id`. |
| Main purpose | Lưu các output về funding/pricing/decision của Lending Club. |
| Typical contents | `funded_amnt`, `funded_amnt_inv`, `int_rate`, `installment`, `grade`, `sub_grade`, `initial_list_status`. |
| Main consumers | Analytics, business interpretation và dashboard nếu cần. |
| Model usage | **Không** vào baseline model mặc định; các field này được xem là `POLICY_DERIVED`/pricing-related. |
| Important caution | Không đưa pricing hoặc grade vào `X` chỉ để tăng số lượng feature; nếu policy thay đổi phải có review riêng. |

### `data/interim/loan_outcome.parquet`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi `loan_id`. |
| Main purpose | Tách target source và các kết quả/hành vi sau khi khoản vay phát sinh. |
| Typical contents | `loan_status`, `target`, payment/recovery, hardship, settlement và last-FICO/post-loan fields nếu có trong raw. |
| Main consumers | TV2 cho target/leakage audit; TV1 nhận `target`; analytics outcome. |
| Model usage | Chỉ `target` được lấy vào canonical modeling join; `POST_LOAN` fields không được vào model `X`. |
| Important caution | Không join toàn bộ bảng outcome vào feature set. Chỉ lấy trường được contract cho phép, cụ thể là target trong baseline join. |

### `data/interim/rejected_applications.parquet`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi rejected application theo grain nguồn; hiện không có source key để kiểm chứng uniqueness ở cấp hồ sơ. |
| Main purpose | Lưu rejected data đã clean nhưng vẫn tách khỏi accepted. |
| Main consumers | TV2 audit; TV3 funnel và demand dashboard. |
| Model usage | Không dùng để train default model và không có target/default outcome. |
| Important caution | Không row-to-row merge với accepted. Contract hiện không yêu cầu `rejected_application_id`, nên không tạo synthetic key trong bảng này. |

## 4. Interim layer — DE-LC-08 dimensions và marts

### `data/interim/dim_date.parquet`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi ngày xuất hiện trong các date source hợp lệ. |
| Nội dung chính | `date`, `year`, `quarter`, `month`, `month_name`, `year_month`. |
| Nguồn | Accepted `issue_d` và rejected `application_date`. |
| Người dùng | Dashboard/analytics để lọc và drill-down `Year → Quarter → Month`. |
| Model usage | Không phải model input. |
| Cảnh báo | Đây là dimension dùng cho ngữ nghĩa thời gian, không phải bảng giao dịch loan. |

### `data/interim/dim_state.parquet`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi state code duy nhất. |
| Nội dung chính | `state_code` và `country`. |
| Nguồn | State từ accepted borrower profile và rejected applications. |
| Người dùng | Power BI Map, state filter và cross-filtering. |
| Model usage | Geography analytics-only theo baseline policy; không vào `X` mặc định. |
| Cảnh báo | Map ở cấp bang dựa trên state code thật. ZIP masked không được biến thành tọa độ giả. |

### `data/interim/application_funnel.parquet`

Đây là **dashboard mart**, không phải phép row-level join giữa accepted và rejected source tables.

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi application record trong mart; accepted dùng `loan_id`, rejected dùng một `application_id` nội bộ của mart. |
| Schema chính | `application_id`, `application_date`, `requested_amount`, `state_code`, `zip_code`, `purpose`, `decision`. |
| Decision | `accepted` hoặc `rejected`. |
| Main purpose | Funnel, demand analysis, volume/amount comparison và accepted-vs-rejected charts. |
| Main consumers | TV3/Power BI và analytics; TV2 chuẩn bị semantics. |
| Model usage | Không dùng để train default-risk model. |
| Cảnh báo | Các dòng được chuẩn hóa về schema tương đương để phân tích funnel; không được hiểu là cùng một loan hoặc là accepted-rejected pair. |

## 5. Processed layer

### `data/processed/cleaned_dataset.parquet`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng mỗi accepted loan có final outcome đã resolve. |
| Main purpose | Canonical labeled modeling handoff từ TV2 sang TV1. |
| Target | Chỉ `target=0` hoặc `target=1`; unresolved loans bị loại khỏi labeled dataset. |
| Main consumers | TV1 modeling; TV2 quality/leakage audit; downstream dashboard chỉ khi cần canonical accepted data. |
| Model usage | Có thể dùng làm nguồn `X/y`, nhưng baseline `X` chỉ gồm cột thuộc `APPLICATION_TIME` và `CREDIT_SNAPSHOT` đã được duyệt. |
| Important caution | Dataset có thể còn cột analytics. `loan_id`, `target`, geography, pricing, target-source, post-loan và forbidden/unknown classes không được đưa vào `X`. |

### `data/processed/data_dictionary.csv`

| Mục | Giải thích |
|---|---|
| Grain | Một dòng metadata cho mỗi canonical column. |
| Nội dung chính | Tên cột, `dtype`, `policy_class`, `model_eligible_default`, canonical grain. |
| Main purpose | Giải thích semantics và quyết định leakage/model eligibility. |
| Main consumers | TV1, TV2 và TV3 khi đọc handoff hoặc thiết kế dashboard. |
| Model usage | Không phải feature table; là metadata để chọn feature đúng. |
| Important caution | Không tự đổi policy class hoặc chọn feature chỉ dựa vào tên cột. Artifact này được tạo ở DE-LC-09. |

### `data/processed/cleaned_dataset_manifest.json`

| Mục | Giải thích |
|---|---|
| Grain | Một bản ghi provenance/run, không phải dữ liệu theo loan. |
| Main purpose | Tóm tắt dataset ID, row counts, trạng thái quality/leakage và đường dẫn artifact. |
| Main consumers | TV2 audit, TV1 handoff và kiểm tra reproducibility. |
| Model usage | Không dùng làm model input. |
| Important caution | Chỉ coi run là handoff hoàn tất khi manifest và quality status tương ứng với artifact hiện tại. Artifact này được tạo ở DE-LC-09. |

## 6. Reports và stage artifacts

### `reports/tv2_stages/de-lc-XX.md`

Report đọc được bằng người, ghi stage đã làm gì, output nào được tạo và payload kiểm tra. Đây là evidence cho từng stage DE-LC.

### `reports/tv2_stages/state/de-lc-XX.json`

Marker máy đọc được với trạng thái `PASS`, `FAIL` hoặc `BLOCKED`. Runner dùng marker để chặn stage sau khi dependency chưa PASS.

Hai loại file trên là **audit/gating artifacts**, không phải model features hoặc dashboard facts.

### `reports/data_quality_report.md`

Quality report của DE-LC-09 tổng hợp key/grain, target, infinity, coverage, dictionary và leakage gate cho canonical dataset. Đây là evidence kiểm định/handoff, không phải dữ liệu để train hoặc vẽ chart trực tiếp.

## 7. Quick reference

| Artifact | Layer | Grain | Main purpose | Model? | Dashboard? |
|---|---|---|---|---|---|
| `accepted_loans.csv` | Raw | Một accepted loan | Source accepted/modeling | Source only | Possible |
| `rejected_loans.csv` | Raw | Một rejected application | Source funnel/demand | No | Yes |
| `loan_application.parquet` | Interim | Một `loan_id` | Base application table | Yes, safe subset only | Possible |
| `borrower_profile.parquet` | Interim | Một `loan_id` | Borrower context | Yes, safe subset only | Yes |
| `credit_profile.parquet` | Interim | Một `loan_id` | Credit snapshot | Yes, safe subset only | Possible |
| `loan_pricing.parquet` | Interim | Một `loan_id` | Pricing/decision analytics | No | Possible |
| `loan_outcome.parquet` | Interim | Một `loan_id` | Target + outcome audit | Target only | Yes, outcome analysis |
| `rejected_applications.parquet` | Interim | Một rejected record | Rejected analytics | No | Yes |
| `dim_date.parquet` | Interim | Một ngày | Time filters/hierarchy | No | Yes |
| `dim_state.parquet` | Interim | Một state code | Geography filters/map | No | Yes |
| `application_funnel.parquet` | Interim mart | Một application record | Accepted/rejected funnel | No | Yes |
| `cleaned_dataset.parquet` | Processed | Một labeled accepted loan | Canonical modeling handoff | Yes, safe subset only | Possible |
| `data_dictionary.csv` | Processed metadata | Một canonical column | Semantics/policy metadata | No / audit only | Possible |
| `cleaned_dataset_manifest.json` | Processed metadata | Một run | Provenance/quality handoff | No / audit only | No / audit only |

## 8. Important rules

- `interim/` không phải “junk” dùng xong rồi bỏ; đây là lớp normalized có contract và grain rõ ràng.
- Không phải mọi cột trong `cleaned_dataset.parquet` đều an toàn cho `X`.
- `POST_LOAN` tuyệt đối không đi vào baseline model features.
- `POLICY_DERIVED` bị loại khỏi baseline model theo mặc định.
- Rejected data không có default outcome và không được dùng như labeled default data.
- Dimensions/marts phục vụ semantics của dashboard, filters, map và funnel; không tự biến chúng thành model input.
- `data/processed/cleaned_dataset.parquet` là canonical modeling handoff artifact.
- Correlation/association trong dashboard không được diễn giải thành causation.
- Khi một artifact chưa được stage tương ứng tạo ra, phải ghi là chưa có/PENDING; không suy đoán số liệu từ tên file.
