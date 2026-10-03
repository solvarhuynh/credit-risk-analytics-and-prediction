# Data Workflow — Lending Club

## 1. Chỉ cần nhớ workflow này

```text
RAW
  ↓
Làm sạch
  ↓
Tách thành các bảng INTERIM
  ↓
Tạo target + feature
  ↓
Ghép thành cleaned_dataset.parquet
  ↓
Chọn các cột an toàn
  ↓
TRAIN MODEL
```

Dashboard đi theo một nhánh song song:

```text
INTERIM
  ↓
dim_date / dim_state / application_funnel
  ↓
DASHBOARD
```

- **RAW** là dữ liệu gốc từ Lending Club.
- **Làm sạch** chuẩn hóa kiểu dữ liệu, ngày tháng, số và giá trị thiếu.
- **INTERIM** chia dữ liệu đã clean thành các bảng theo mục đích nghiệp vụ.
- **Target + feature** tạo nhãn vỡ nợ và các biến có thể biết tại thời điểm xét vay.
- **`cleaned_dataset.parquet`** là dataset canonical được bàn giao cho modeling.
- **Cột an toàn** được chọn theo chính sách leakage trước khi tạo `X` và train.
- Nhánh dashboard dùng các bảng phân tích phù hợp cho bộ lọc, funnel, thời gian và bản đồ.

## 2. Ba lớp dữ liệu

### RAW

Thư mục `data/raw/` chứa dữ liệu gốc:

- `accepted_loans.csv`: các khoản vay được chấp nhận;
- `rejected_loans.csv`: các hồ sơ bị từ chối.

RAW chưa phải dữ liệu để train trực tiếp. Nó được giữ để audit và làm input cho bước cleaning.

### INTERIM

Thư mục `data/interim/` chứa dữ liệu đã clean và được chia thành các bảng theo mục đích để dễ quản lý.

Có thể nhớ ba nhóm chính:

**Nhóm A — Thông tin dùng để xây dataset cho model**

- `loan_application.parquet`
- `borrower_profile.parquet`
- `credit_profile.parquet`

Đây là các nguồn thông tin chính về khoản vay, người vay và credit snapshot để tạo dataset modeling. Tuy vậy, không phải mọi cột trong các bảng này đều tự động được phép đưa vào `X`.

**Nhóm B — Kết quả, quyết định và thông tin sau vay**

- `loan_pricing.parquet`
- `loan_outcome.parquet`

Pricing chủ yếu phục vụ analytics hoặc phản ánh quyết định/chính sách. Outcome chứa nguồn tạo target và các thông tin sau khi khoản vay phát sinh. Có thể lấy `target` từ outcome, nhưng không đưa toàn bộ cột pricing/outcome vào model features.

**Nhóm C — Hồ sơ bị từ chối**

- `rejected_applications.parquet`

Bảng này phục vụ phân tích accepted-vs-rejected và dashboard funnel. Hồ sơ rejected không có default outcome quan sát được nên không dùng làm dữ liệu labeled để train default-risk model.

Các artifact hỗ trợ dashboard:

- `dim_date.parquet` → bộ lọc và drill-down thời gian.
- `dim_state.parquet` → bộ lọc bang và Map theo `state_code`.
- `application_funnel.parquet` → so sánh accepted và rejected.

Đọc [Data Artifacts Guide](data_artifacts.md) khi cần định nghĩa chi tiết từng file, grain, consumer và giới hạn sử dụng.

### PROCESSED

Thư mục `data/processed/` chứa sản phẩm chuẩn để bàn giao. File quan trọng nhất là `cleaned_dataset.parquet`.

```text
accepted loan
  + borrower
  + credit
  + target
  + engineered features
  → cleaned_dataset.parquet
```

Điểm dễ nhầm: model **không** thường tự mở từng file INTERIM rồi tự quyết định lấy toàn bộ hay bỏ toàn bộ file đó. Pipeline sẽ:

```text
INTERIM tables
  → pipeline ghép thông tin cần thiết
  → cleaned_dataset.parquet
  → chọn các cột an toàn từ dataset này
  → X + y
  → train
```

Nói cách khác, `cleaned_dataset.parquet` là điểm giao tiếp chính giữa Data Engineering và Modeling. `data_dictionary.csv` giải thích các cột; `cleaned_dataset_manifest.json` ghi thông tin run và chất lượng bàn giao.

## 3. DE-LC-01 → DE-LC-10

| Stage | Cách nhớ ngắn |
|---|---|
| DE-LC-01 | Hiểu raw |
| DE-LC-02 | Làm sạch |
| DE-LC-03 | Phân loại cột / leakage |
| DE-LC-04 | Tách bảng interim |
| DE-LC-05 | Tạo target |
| DE-LC-06 | Tạo feature |
| DE-LC-07 | Tạo dataset model |
| DE-LC-08 | Tạo bảng dashboard |
| DE-LC-09 | Dictionary + quality + manifest |
| DE-LC-10 | EDA |

## 4. Model và dashboard khác nhau thế nào?

**MODEL**

```text
cleaned_dataset.parquet
  ↓
lọc cột an toàn
  ↓
X + target
  ↓
train
```

**DASHBOARD**

```text
cleaned_dataset / interim marts / dimensions
  ↓
analytics
  ↓
Power BI
```

Dashboard có thể dùng một số trường mà model dự báo cố ý loại bỏ, ví dụ `state_code` cho Map hoặc các trường outcome để mô tả kết quả đã quan sát. Dùng được cho dashboard không có nghĩa là dùng được cho baseline `X`.

## 5. Ghi nhớ nhanh

```text
RAW = dữ liệu gốc
INTERIM = đã clean + chia bảng
PROCESSED = output bàn giao
cleaned_dataset = dataset chính cho modeling
dimensions/marts = hỗ trợ dashboard
```

