# Data Rules — Model dùng gì và không dùng gì?

## 1. Quy tắc ba nhóm

### NHÓM 1 — DÙNG ĐƯỢC CHO MODEL

Đây là thông tin có thể biết tại thời điểm xét hoặc cấp khoản vay, chẳng hạn:

- số tiền vay (`loan_amnt`);
- thu nhập năm (`annual_inc`);
- DTI (`dti`);
- FICO và lịch sử tín dụng;
- các feature an toàn được tính từ những thông tin trên, như `fico_avg` và `loan_to_income_ratio`.

Trong tên kỹ thuật, nhóm này thường thuộc `APPLICATION_TIME` hoặc `CREDIT_SNAPSHOT`. Tên kỹ thuật là cách kiểm tra chính sách; điều quan trọng trước tiên là hiểu **thông tin đó có tồn tại trước kết quả khoản vay hay không**.

### NHÓM 2 — KHÔNG DÙNG CHO MODEL

Đây là thông tin làm lộ tương lai, là kết quả khoản vay, hoặc là quyết định đã được Lending Club tạo ra. Ví dụ:

- **Sau khi cho vay:** `total_pymnt`, `recoveries`, các trường payment cuối kỳ, hardship, settlement, last FICO;
- **Nguồn tạo nhãn:** `loan_status`;
- **Thông tin do chính sách/pricing tạo ra:** `grade`, `sub_grade`, `int_rate` và các output liên quan theo policy hiện hành.

Nếu muốn dự đoán default trước khi quá trình trả nợ diễn ra mà lại đưa `recoveries` hoặc `total_pymnt` vào model, model đã được nhìn thấy thông tin sau outcome. Đó là **leakage**.

Tên kỹ thuật tương ứng là `POST_LOAN`, `TARGET_SOURCE` và `POLICY_DERIVED`. Các nhóm này không được vào baseline model `X`.

### NHÓM 3 — DÙNG CHO PHÂN TÍCH / DASHBOARD

Một số trường hữu ích để mô tả dữ liệu nhưng không thuộc baseline predictive `X`, ví dụ:

- `state_code`, `zip_code` và các trường geography;
- identifier;
- category hoặc trường dành riêng cho dashboard.

Chúng có thể hỗ trợ Map, filter, segmentation và analytics. Tên kỹ thuật thường gặp là `GEOGRAPHY_ANALYTICS`, `IDENTIFIER` và `ANALYTICS_ONLY`.

## 2. `X` và `y` là gì?

- `X` là dữ liệu model dùng để dự đoán.
- `y` là câu trả lời mà model cần học.

Trong project này, `target` là `y`, không phải một cột trong `X`:

- `target = 0`: non-default/final good, tương ứng `Fully Paid`;
- `target = 1`: default/final bad, tương ứng `Charged Off` hoặc `Default`.

`loan_status` chỉ là nguồn để derive `target`; bản thân `loan_status` không phải predictor.

## 3. Leakage là gì?

Ta muốn dự đoán khả năng default tại thời điểm xét vay. Vì vậy model chỉ được nhìn thông tin có thể biết ở thời điểm đó.

Ví dụ, `recoveries` và `total_pymnt` phản ánh những gì xảy ra trong hoặc sau quá trình trả nợ. Đưa chúng vào `X` giống như cho model xem đáp án sau khi sự việc đã xảy ra. Đó là leakage, làm kết quả đánh giá không còn công bằng cho dự đoán trước vay.

## 4. Model thực sự lấy dữ liệu như thế nào?

Model không chọn “nguyên file INTERIM” là được phép hay bị cấm. Luồng thực tế là:

```text
interim files
  ↓
cleaned_dataset.parquet
  ↓
column policy lọc từng cột
  ↓
safe X
  ↓
train
```

Ví dụ trong `cleaned_dataset.parquet`:

- `annual_inc` → có thể dùng nếu policy/quality gate xác nhận;
- `dti` → có thể dùng;
- `fico_avg` → có thể dùng;
- `target` → dùng làm `y`, không đưa vào `X`;
- `grade` → loại khỏi baseline `X`;
- `total_pymnt` → loại khỏi baseline `X`;
- `state_code` → dùng cho dashboard/analytics, mặc định loại khỏi baseline `X`.

Các cột an toàn mặc định phải thuộc `APPLICATION_TIME` hoặc `CREDIT_SNAPSHOT`. Những tên này được kiểm tra bởi `column_policy.py`; không chọn feature chỉ vì tên cột nghe có vẻ hợp lý.

## 5. Bảng nhớ nhanh

| Câu hỏi | Cách xử lý |
|---|---|
| Biết được lúc xét vay? | Có thể dùng cho model sau khi qua policy/quality gate |
| Xảy ra sau khi cho vay? | Không dùng làm `X` |
| Là kết quả hoặc status? | Không dùng làm `X` |
| Là target? | Dùng làm `y` |
| Là geography/dashboard field? | Dùng cho analytics; baseline model mặc định không dùng |

