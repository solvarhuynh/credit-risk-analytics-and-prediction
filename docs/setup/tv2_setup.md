# TV2 — Data Engineering setup & run guide

Owner: TV2 (Data Engineering & Pipeline)

## Chuẩn bị dữ liệu

Đặt 8 CSV bắt buộc vào `data/raw/`:

`application_train.csv`, `application_test.csv`, `bureau.csv`,
`bureau_balance.csv`, `previous_application.csv`, `installments_payments.csv`,
`credit_card_balance.csv`, `POS_CASH_balance.csv`.

`HomeCredit_columns_description.csv` là optional metadata.

## Chuẩn bị môi trường

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Chạy DE-01 preflight

Từ repository root:

```powershell
python -m src.data.load_data
```

Hoặc gọi API trong code:

```powershell
python -c "from src.data.load_data import run_raw_schema_preflight; import json; print(json.dumps(run_raw_schema_preflight(), ensure_ascii=False, indent=2))"
```

Preflight kiểm tra file tồn tại, schema/dtype, duplicate, key/grain,
train/test separation và foreign-key coverage. Loader không clean, aggregate,
join hoặc feature engineering.

## Validation

```powershell
python -m py_compile src\data\load_data.py
```

Nếu thiếu raw file, command phải dừng và liệt kê chính xác file cần bổ sung.

## Chạy DE-02 Data Cleaning & Sentinel Handling

Module `src/data/cleaning.py` cung cấp tầng làm sạch dữ liệu chuẩn tắc, xác định (deterministic) và chống rò rỉ (leakage-safe).

### Mục đích và chính sách làm sạch
- **Không thay đổi DataFrame đầu vào:** Các hàm trả về bản sao đã làm sạch, không sửa trực tiếp DataFrame của nơi gọi.
- **Không thực hiện suy diễn/điền khuyết thống kê (No Statistical Imputation):** DE-02 tuyệt đối KHÔNG điền giá trị thiếu (mean, median, mode hay placeholder cố định) để tránh rò rỉ dữ liệu. Các bộ imputer phục vụ mô hình bắt buộc phải do TV1 fit duy nhất trên training fold sau khi chia tập.
- **Xử lý sentinel `DAYS_EMPLOYED`:** Giá trị `365243` trên `application_train` và `application_test` được chuyển thành missing (NaN) và tạo cờ bất thường `DAYS_EMPLOYED_ANOM` (`int8`, nhận 0 hoặc 1).
- **Xử lý sentinel trên `previous_application`:** Chuyển `365243` thành missing trên đúng 5 cột ngày tài liệu: `DAYS_FIRST_DRAWING`, `DAYS_FIRST_DUE`, `DAYS_LAST_DUE_1ST_VERSION`, `DAYS_LAST_DUE`, `DAYS_TERMINATION`.
- **Chuẩn hóa chuỗi và vô cực:** Cắt bỏ khoảng trắng đầu/cuối (giữ nguyên chữ hoa/thường và khoảng trắng nội bộ); chuỗi rỗng sau khi cắt thành missing; giá trị vô cực `+inf`/`-inf` thành missing; không tự ý đổi `XNA`/`Unknown`.
- **Chính sách bản ghi trùng lặp:** Đo đạc và báo cáo bản ghi trùng lặp tuyệt đối nhưng không xóa tự động; giữ nguyên các dòng thanh toán nhiều lần hợp lệ trong `installments_payments`.
- **Xác thực khóa và Target:** Kiểm tra tính duy nhất và không null của khóa chính (`SK_ID_CURR`, `SK_ID_BUREAU`, `SK_ID_PREV`); `application_train` bắt buộc có `TARGET` nhị phân {0, 1}; `application_test` bắt buộc không có `TARGET`.

### Lệnh chạy kiểm toán dữ liệu thực tế (Real-data audit)
Từ repository root:

```powershell
python -m src.data.cleaning
```

Lệnh đọc và làm sạch tuần tự từng bảng chứa sentinel (`application_train`, `application_test`, `previous_application`), giải phóng bộ nhớ sau mỗi bảng và in báo cáo JSON tóm tắt số lượng sentinel đã xử lý cùng trạng thái xác thực.

### Lệnh kiểm thử tự động
```powershell
python -m pytest tests\data -v
```

### Input, Output và giới hạn
- **Input:** Tệp thô trong `data/raw/`.
- **Output:** Trả DataFrame đã làm sạch và từ điển báo cáo trong memory/console. Chưa lưu trữ tệp dataset cuối cùng (chưa tạo `data/processed/cleaned_dataset.parquet`).
- **Giới hạn:** Không thực hiện join, không aggregate bảng lịch sử, không tạo các đặc trưng phái sinh cấp cao (DTI, tỷ lệ khoản vay...).

## Chạy DE-03 Application-Level Feature Engineering

Module `src/features/engineering.py` cung cấp tầng tạo đặc trưng cấp hồ sơ ứng dụng (application-level), xác định (deterministic), thuần túy từng dòng (row-local) và chống rò rỉ (leakage-safe).

### Danh mục đặc trưng và nguyên tắc
Tạo đúng 6 đặc trưng trên `application_train` và `application_test`:
1. `AGE_YEARS`: `-DAYS_BIRTH / 365.25` (phạm vi hợp lệ `[18, 100]`; tuổi < 18 hoặc > 100 trở thành missing `NaN`).
2. `AGE_GROUP`: Phân nhóm độ tuổi thành categorical có thứ tự theo các bin nửa đóng nửa mở chuẩn `[18, 25, 35, 45, 55, 65, 101]` (tức `[18, 25)`, `[25, 35)`, `[35, 45)`, `[45, 55)`, `[55, 65)`, `[65, 101)`) với nhãn chính xác `['Under 25', '25-34', '35-44', '45-54', '55-64', '65+']`. Missing hoặc tuổi ngoài phạm vi hợp lệ sẽ tạo missing `AGE_GROUP`.
3. `EMPLOYED_YEARS`: `-DAYS_EMPLOYED / 365.25` (bảo toàn missing NaN từ sentinel DE-02 và cờ `DAYS_EMPLOYED_ANOM`).
4. `CREDIT_TO_INCOME_RATIO`: `AMT_CREDIT / AMT_INCOME_TOTAL`.
5. `ANNUITY_TO_INCOME_RATIO`: `AMT_ANNUITY / AMT_INCOME_TOTAL`.
6. `CREDIT_TO_ANNUITY_RATIO`: `AMT_CREDIT / AMT_ANNUITY`.

### Nguyên tắc an toàn dữ liệu và chống rò rỉ
- **Không thay đổi DataFrame đầu vào:** Trả về bản sao DataFrame mới, không thay đổi đối tượng đầu vào.
- **Phép chia an toàn (Safe ratio):** Mọi mẫu số bằng 0, missing hoặc không hợp lệ đều chuyển thành `NaN`, tuyệt đối không phát sinh giá trị vô cực `+inf`/`-inf`.
- **Row-local & Leakage-safe:** Tính toán hoàn toàn độc lập trên từng dòng; tuyệt đối không ghép train/test; không tính toán thống kê gộp (mean/median/std); không sử dụng biến mục tiêu `TARGET`; không điền khuyết thống kê.
- **Bảo toàn hạt dữ liệu và thứ tự:** Giữ nguyên 100% số dòng, danh sách khóa `SK_ID_CURR` và thứ tự ban đầu.
- **Tính tương đồng Train/Test (Parity):** Đảm bảo cả hai tập dữ liệu đều sở hữu 128 đặc trưng chung với kiểu dữ liệu đồng nhất; `TARGET` chỉ xuất hiện trên `application_train`.

### Lệnh chạy kiểm toán dữ liệu thực tế (Real-data audit)
Từ repository root:

```powershell
python -m src.features.engineering
```

Lệnh thực hiện làm sạch và tạo đặc trưng tuần tự trên `application_train` và `application_test`, xác thực tỷ lệ missing, phạm vi giá trị, kiểm tra tính tương đồng (parity) và in báo cáo JSON chi tiết.

### Lệnh kiểm thử tự động
```powershell
python -m pytest tests\features -v
```

### Giới hạn và bước kế tiếp
- **Giới hạn:** DE-03 chỉ tạo đặc trưng row-local cho bảng application.
- **Bước kế tiếp:** `TV2-DE-04 — Historical Table Aggregation`.

## Chạy DE-04 Historical Table Aggregation

Module `src/data/aggregate.py` cung cấp tầng tổng hợp các bảng lịch sử (historical tables) thành một dòng duy nhất cho mỗi khách hàng (`SK_ID_CURR`), phục vụ chuẩn bị dữ liệu trước khi kết nối (join) ở DE-05.

### Mục đích nhiệm vụ
Chuyển đổi dữ liệu giao dịch và lịch sử nhiều dòng (1:N) từ 6 bảng thô thành các chỉ số tóm tắt cấp khách hàng (`SK_ID_CURR`), loại bỏ hoàn toàn nguy cơ nhân bản dòng hồ sơ ứng dụng chính, đồng thời tuân thủ nghiêm ngặt tính xác định và nguyên tắc chống rò rỉ dữ liệu.

### Bảng đầu vào và tệp đầu ra

| Bảng nguồn thô | Hạt dữ liệu nguồn | File đầu ra Parquet (`data/interim/`) | Tiền tố đặc trưng | Số đặc trưng phái sinh |
| :--- | :--- | :--- | :--- | :--- |
| `bureau.csv` + `bureau_balance.csv` | Khoản vay (`SK_ID_BUREAU`) + Kỳ dư nợ tháng | `bureau_aggregated.parquet` | `BUREAU_` | 20 |
| `previous_application.csv` | Hồ sơ quá khứ (`SK_ID_PREV`) | `previous_application_aggregated.parquet` | `PREV_` | 15 |
| `installments_payments.csv` | Đợt thanh toán trả góp | `installments_payments_aggregated.parquet` | `INSTAL_` | 10 |
| `POS_CASH_balance.csv` | Hợp đồng - tháng (`SK_ID_PREV`, `MONTHS_BALANCE`) | `pos_cash_balance_aggregated.parquet` | `POS_` | 11 |
| `credit_card_balance.csv` | Thẻ tín dụng - tháng (`SK_ID_PREV`, `MONTHS_BALANCE`) | `credit_card_balance_aggregated.parquet` | `CC_` | 18 |

Tất cả các tệp Parquet và manifest tổng hợp `aggregation_manifest.json` được ghi nguyên tử (atomic write) vào thư mục `data/interim/` (thư mục này được gitignore).

### Danh mục đặc trưng chi tiết
- **BUREAU_ (20 đặc trưng):**
  `BUREAU_CREDIT_COUNT`, `BUREAU_ACTIVE_COUNT`, `BUREAU_ACTIVE_RATE`, `BUREAU_CLOSED_COUNT`, `BUREAU_CLOSED_RATE`, `BUREAU_DAYS_CREDIT_MEAN`, `BUREAU_DAYS_CREDIT_MAX`, `BUREAU_CREDIT_DAY_OVERDUE_MEAN`, `BUREAU_CREDIT_DAY_OVERDUE_MAX`, `BUREAU_AMT_CREDIT_SUM_SUM`, `BUREAU_AMT_CREDIT_SUM_MEAN`, `BUREAU_AMT_DEBT_SUM`, `BUREAU_AMT_DEBT_MEAN`, `BUREAU_AMT_OVERDUE_SUM`, `BUREAU_AMT_OVERDUE_MAX`, `BUREAU_BB_MONTH_COUNT`, `BUREAU_BB_DELINQUENT_MONTH_COUNT`, `BUREAU_BB_DELINQUENT_MONTH_RATE`, `BUREAU_BB_SEVERE_MONTH_COUNT`, `BUREAU_BB_SEVERE_MONTH_RATE`.
- **PREV_ (15 đặc trưng):**
  `PREV_APPLICATION_COUNT`, `PREV_APPROVED_COUNT`, `PREV_APPROVED_RATE`, `PREV_REFUSED_COUNT`, `PREV_REFUSED_RATE`, `PREV_AMT_APPLICATION_SUM`, `PREV_AMT_APPLICATION_MEAN`, `PREV_AMT_APPLICATION_MAX`, `PREV_AMT_CREDIT_SUM`, `PREV_AMT_CREDIT_MEAN`, `PREV_AMT_CREDIT_MAX`, `PREV_AMT_ANNUITY_MEAN`, `PREV_CREDIT_TO_APPLICATION_RATIO_MEAN`, `PREV_DAYS_DECISION_MEAN`, `PREV_DAYS_DECISION_MAX`.
- **INSTAL_ (10 đặc trưng):**
  `INSTAL_INSTALLMENT_COUNT`, `INSTAL_LATE_COUNT`, `INSTAL_LATE_RATE`, `INSTAL_DELAY_DAYS_MEAN`, `INSTAL_DELAY_DAYS_MAX`, `INSTAL_UNDERPAYMENT_COUNT`, `INSTAL_UNDERPAYMENT_RATE`, `INSTAL_PAYMENT_SHORTFALL_SUM`, `INSTAL_PAYMENT_SHORTFALL_MEAN`, `INSTAL_PAYMENT_RATIO_MEAN`.
- **POS_ (11 đặc trưng):**
  `POS_RECORD_COUNT`, `POS_CONTRACT_COUNT`, `POS_MONTHS_BALANCE_MIN`, `POS_MONTHS_BALANCE_MAX`, `POS_DPD_MEAN`, `POS_DPD_MAX`, `POS_DPD_DEF_MEAN`, `POS_DPD_DEF_MAX`, `POS_LATE_MONTH_COUNT`, `POS_LATE_MONTH_RATE`, `POS_INSTALMENT_FUTURE_MEAN`.
- **CC_ (18 đặc trưng):**
  `CC_RECORD_COUNT`, `CC_CONTRACT_COUNT`, `CC_MONTHS_BALANCE_MIN`, `CC_MONTHS_BALANCE_MAX`, `CC_BALANCE_MEAN`, `CC_BALANCE_MAX`, `CC_CREDIT_LIMIT_MEAN`, `CC_CREDIT_LIMIT_MAX`, `CC_UTILIZATION_MEAN`, `CC_UTILIZATION_MAX`, `CC_DPD_MEAN`, `CC_DPD_MAX`, `CC_DPD_DEF_MEAN`, `CC_DPD_DEF_MAX`, `CC_LATE_MONTH_COUNT`, `CC_LATE_MONTH_RATE`, `CC_PAYMENT_TOTAL_SUM`, `CC_PAYMENT_TOTAL_MEAN`.

### Quy tắc kiểm tra thời gian và chống rò rỉ (Temporal & Leakage Validation)
Toàn bộ các trường thời gian phải đại diện cho các sự kiện xảy ra trước hoặc đúng thời điểm nộp đơn (`<= 0`):
- `bureau.DAYS_CREDIT <= 0`
- `bureau_balance.MONTHS_BALANCE <= 0`
- `previous_application.DAYS_DECISION <= 0`
- `installments_payments.DAYS_INSTALMENT <= 0`
- `installments_payments.DAYS_ENTRY_PAYMENT <= 0`
- `POS_CASH_balance.MONTHS_BALANCE <= 0`
- `credit_card_balance.MONTHS_BALANCE <= 0`
Nếu phát hiện bất kỳ giá trị dương nào (`> 0`), quy trình sẽ chặn thực thi (`BLOCKED`) và phát sinh lỗi chi tiết.

### Xử lý thanh toán tách kỳ trong `installments_payments`
Bảng `installments_payments` có 653,483 dòng trùng lặp tổ hợp khóa kỳ `(SK_ID_PREV, SK_ID_CURR, NUM_INSTALMENT_VERSION, NUM_INSTALMENT_NUMBER)` do người vay chia nhỏ các đợt thanh toán trả góp:
- Quy trình kiểm tra tính nhất quán của ngày hẹn trả (`DAYS_INSTALMENT`) và số tiền đến hạn (`AMT_INSTALMENT`) trong từng nhóm kỳ trả góp.
- Số tiền đến hạn định kỳ được lấy đơn lẻ một lần duy nhất (không cộng dồn gây nhân bản nghĩa vụ).
- Số tiền thực trả (`AMT_PAYMENT`) được cộng dồn theo kỳ.
- Ngày thanh toán thực tế là ngày muộn nhất (`max(DAYS_ENTRY_PAYMENT)`).
- Chậm trả (`delay_days`) và thiếu nợ (`payment_shortfall`) được tính ở cấp độ kỳ hợp nhất, chặn dưới tại 0.

### Xử lý bản ghi mồ côi (Orphan) trong `bureau_balance`
Khoảng 43,041 mã `SK_ID_BUREAU` trong `bureau_balance` (tương ứng 3,120,184 dòng lịch sử) không tồn tại trong bảng `bureau`:
- Quy trình tổng hợp `bureau_balance` theo `SK_ID_BUREAU` trước, sau đó `left join` vào `bureau`.
- Các bản ghi mồ côi không có ánh xạ tới `SK_ID_CURR` nên bị loại khỏi bảng tổng hợp cấp khách hàng, đồng thời được ghi nhận vào báo cáo chẩn đoán và manifest dưới dạng cảnh báo nghiệp vụ đã ghi nhận.
- Tỷ lệ trễ hạn cấp khách hàng được tính có trọng số: `tổng tháng trễ hạn / tổng tháng có số dư quan sát được`.

### Hành vi tỷ lệ an toàn (Safe Ratios)
Mọi phép chia đều sử dụng phép chia số thực (float division). Mẫu số bằng 0 hoặc khuyết thiếu sẽ tạo giá trị `NaN`, tuyệt đối không phát sinh giá trị vô cực `+inf`/`-inf` hay gán giá trị 0 giả tạo.

### Chiến lược an toàn bộ nhớ (Memory Strategy)
1. Xử lý tuần tự từng bảng dữ liệu một, giải phóng bộ nhớ (`del` và `gc.collect()`) ngay sau khi hoàn thành mỗi bảng.
2. Sử dụng `usecols` để chỉ tải các cột cần thiết phục vụ tính toán và xác thực.
3. Ép kiểu dữ liệu tối ưu (`int32`, `int16`, `float32`, `category`) giúp giảm dung lượng RAM sử dụng xuống dưới 500 MB cho mỗi bảng lớn.
4. Ghi nguyên tử từng tệp Parquet ra đĩa và giải phóng bộ nhớ trước khi nạp bảng kế tiếp.

### Lệnh thực thi
```powershell
python -m src.data.aggregate
```

### Lệnh kiểm thử
```powershell
python -m pytest tests\data\test_aggregate.py -v
python -m pytest tests\data -v
```

### Cảnh báo dự kiến (Expected Warnings)
1. `bureau_balance`: Chứa 43,041 mã `SK_ID_BUREAU` mồ côi (3,120,184 dòng) không có cha trong `bureau`.
2. `installments_payments`: Chứa 653,483 dòng trả góp từng phần được hợp nhất bảo toàn.

### Mối liên hệ với DE-05
DE-04 chỉ tạo các tệp parquet tổng hợp trung gian tại `data/interim/`. Nhiệm vụ `TV2-DE-05 — Join and Canonical Dataset Publication` thực hiện left join các bảng tổng hợp này vào `application_train` (đã qua tiền xử lý ở DE-02 và feature engineering ở DE-03) để tạo ra tập dữ liệu chính thức `data/processed/cleaned_dataset.parquet`.

## TV2-DE-05 — Join and Canonical Dataset Publication

### Mục đích (Purpose)
Xuất bản tập dữ liệu chuẩn tắc gắn nhãn phục vụ huấn luyện mô hình (`data/processed/cleaned_dataset.parquet`) và tệp siêu dữ liệu kiểm định (`data/processed/cleaned_dataset_manifest.json`) thông qua module điều phối chuẩn hóa `src/data/build_pipeline.py`.

### Quần thể chuẩn tắc gắn nhãn (Canonical Labeled Population)
- Quần thể chuẩn tắc duy nhất được phép tham gia huấn luyện là `data/raw/application_train.csv` gồm đúng 307,511 khách hàng có nhãn `TARGET` (0 hoặc 1).
- **Loại trừ tuyệt đối `application_test.csv`:** Tập dữ liệu kiểm thử (48,744 dòng, không có `TARGET`) tuyệt đối không được đưa vào tập dữ liệu chuẩn tắc huấn luyện để ngăn chặn hoàn toàn rủi ro rò rỉ dữ liệu (data leakage) và ô nhiễm nhãn.

### Dữ liệu đầu vào & Tái sử dụng tầng tiền xử lý
1. **Dữ liệu thô:** `data/raw/application_train.csv` (307,511 dòng, 122 cột).
2. **Tái sử dụng DE-02:** Làm sạch giá trị sentinel (365,243 ngày làm việc $\rightarrow$ `NaN` và cờ `DAYS_EMPLOYED_ANOM`), chuẩn hóa chuỗi và kiểu dữ liệu qua `src/data/cleaning.py`.
3. **Tái sử dụng DE-03:** Phái sinh 6 đặc trưng tài chính và nhân khẩu học cấp hồ sơ ứng viên (`AGE_YEARS`, `AGE_GROUP`, `EMPLOYED_YEARS`, `CREDIT_TO_INCOME_RATIO`, `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_ANNUITY_RATIO`) qua `src/features/engineering.py`. Kết hợp cùng cờ `DAYS_EMPLOYED_ANOM` từ DE-02 tạo thành nhóm 7 đặc trưng phái sinh cấp hồ sơ ứng viên.
4. **Tái sử dụng DE-04:** 5 tệp Parquet tổng hợp trung gian cấp khách hàng (`SK_ID_CURR`) duy nhất từ `data/interim/`:
   - `bureau_aggregated.parquet` (20 đặc trưng `BUREAU_`)
   - `previous_application_aggregated.parquet` (15 đặc trưng `PREV_`)
   - `installments_payments_aggregated.parquet` (10 đặc trưng `INSTAL_`)
   - `pos_cash_balance_aggregated.parquet` (11 đặc trưng `POS_`)
   - `credit_card_balance_aggregated.parquet` (18 đặc trưng `CC_`)

### Thứ tự Left Join xác định (Deterministic Join Order) & Lực lượng (Cardinality)
Thực hiện phép nối trái (left join) 1-to-1 tuần tự theo đúng thứ tự:
1. `BUREAU` (độ bao phủ: 85.6851%, 263,491 khớp / 44,020 không khớp)
2. `PREV` (độ bao phủ: 94.6493%, 291,057 khớp / 16,454 không khớp)
3. `INSTAL` (độ bao phủ: 94.8399%, 291,643 khớp / 15,868 không khớp)
4. `POS` (độ bao phủ: 94.1248%, 289,444 khớp / 18,067 không khớp)
5. `CC` (độ bao phủ: 28.2608%, 86,905 khớp / 220,606 không khớp)

Khóa nối `SK_ID_CURR` trên các bảng aggregate được kiểm định nghiêm ngặt tính duy nhất (1-to-1), đảm bảo tuyệt đối không làm mất dòng hoặc nhân đôi số dòng (bảo toàn đúng 307,511 dòng).

### Chính sách xử lý khuyết thiếu lịch sử tín dụng (Missing-History Policy)
- **Cột số đếm chuẩn tắc (Count features - đúng 18 cột đã phê duyệt):** Đối với khách hàng không có lịch sử ở bảng tương ứng, điền giá trị `0` (nghiệp vụ: không có giao dịch/hồ sơ phát sinh).
  - `BUREAU`: `BUREAU_CREDIT_COUNT`, `BUREAU_ACTIVE_COUNT`, `BUREAU_CLOSED_COUNT`, `BUREAU_BB_MONTH_COUNT`, `BUREAU_BB_DELINQUENT_MONTH_COUNT`, `BUREAU_BB_SEVERE_MONTH_COUNT`.
  - `PREV`: `PREV_APPLICATION_COUNT`, `PREV_APPROVED_COUNT`, `PREV_REFUSED_COUNT`.
  - `INSTAL`: `INSTAL_INSTALLMENT_COUNT`, `INSTAL_LATE_COUNT`, `INSTAL_UNDERPAYMENT_COUNT`.
  - `POS`: `POS_RECORD_COUNT`, `POS_CONTRACT_COUNT`, `POS_LATE_MONTH_COUNT`.
  - `CC`: `CC_RECORD_COUNT`, `CC_CONTRACT_COUNT`, `CC_LATE_MONTH_COUNT`.
- **Cột tỷ lệ, số tiền và thống kê (Rates, Amounts, Statistics):** Giữ nguyên giá trị khuyết thiếu thực tế `NaN`, tuyệt đối không điền 0 giả tạo gây méo mó phân phối.

### Cổng kiểm soát chất lượng (Quality Gates - 28 quy tắc)
Bộ kiểm định chất lượng tự động thực thi 28 quy tắc kiểm tra nghiêm ngặt trước khi cho phép xuất bản:
1. Đúng 307,511 dòng.
2. Đúng 203 cột chuẩn tắc (1 `SK_ID_CURR` + 1 `TARGET` + 120 cột thô sạch + 7 cột DE-02/DE-03 + 74 cột aggregate DE-04).
3. `SK_ID_CURR` duy nhất 100%, không null, sắp xếp tăng dần.
4. `TARGET` nhị phân {0: 282,686; 1: 24,825}, không null, bất biến so với bảng thô.
5. Không có giá trị vô cực (`+inf` hoặc `-inf`).
6. Không có xung đột tên cột hoặc cột hậu tố `_x`/`_y`.
7. Đầy đủ các nhóm tiền tố `BUREAU_`, `PREV_`, `INSTAL_`, `POS_`, `CC_`.
8. Đầy đủ các cột giao ước bắt buộc (`data_contract.md`): `SK_ID_CURR`, `TARGET`, `AMT_INCOME_TOTAL`, `AMT_CREDIT`, `AMT_ANNUITY`, `AMT_GOODS_PRICE`, `CODE_GENDER`, `NAME_CONTRACT_TYPE`, `AGE_YEARS`, `AGE_GROUP`, `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_INCOME_RATIO`, `EMPLOYED_YEARS`, `DAYS_EMPLOYED_ANOM`.
9. **Kiểm định tỷ lệ chính xác:** Chỉ 10 cột tỷ lệ chuẩn tắc (`BUREAU_ACTIVE_RATE`, `BUREAU_CLOSED_RATE`, `BUREAU_BB_DELINQUENT_MONTH_RATE`, `BUREAU_BB_SEVERE_MONTH_RATE`, `PREV_APPROVED_RATE`, `PREV_REFUSED_RATE`, `INSTAL_LATE_RATE`, `INSTAL_UNDERPAYMENT_RATE`, `POS_LATE_MONTH_RATE`, `CC_LATE_MONTH_RATE`) bị chặn trong `[0, 1]`. Các tỷ lệ tài chính như `CREDIT_TO_INCOME_RATIO`, `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_ANNUITY_RATIO`, `PREV_CREDIT_TO_APPLICATION_RATIO_MEAN`, `INSTAL_PAYMENT_RATIO_MEAN`, `CC_UTILIZATION_MEAN/MAX` được phép lớn hơn 1 hợp lệ theo bản chất tài chính.

### Xuất bản nguyên tử (Atomic Publication) & Artifacts
- **Đường dẫn Parquet:** `data/processed/cleaned_dataset.parquet` (64,213,549 bytes, SHA-256: `e3cbf594a5a0a072fc1625baa11563c323b8c392afc90cb46bb17bf48c12de75`).
- **Đường dẫn Manifest:** `data/processed/cleaned_dataset_manifest.json` (17,082 bytes, SHA-256: `e633885a14ad70b7f153cc27587722c77ee6c5b73ac03495872755df7a73d3f7`).
- **Cơ chế nguyên tử:** Ghi ra tệp tạm `.tmp` tại cùng thư mục, thực hiện kiểm định đọc lại (read-back validation), sau đó thực hiện `os.replace` nguyên tử nhằm tránh tình trạng tệp hỏng khi có sự cố ngắt quãng.

### Lệnh thực thi & Tùy chọn tái tạo
- **Thực thi chuẩn tắc (sử dụng aggregate có sẵn):**
```powershell
python -m src.data.build_pipeline
```
- **Tùy chọn ép buộc tái tạo aggregate từ dữ liệu thô (`--rebuild-aggregates`):**
```powershell
python -m src.data.build_pipeline --rebuild-aggregates
```

### Lệnh kiểm thử
```powershell
python -m pytest tests\data\test_build_pipeline.py -v
python -m pytest tests\data -v
python -m pytest tests -q
```

### Cảnh báo nghiệp vụ dự kiến (Expected Warnings)
1. Tỷ lệ bao phủ lịch sử < 100% là đặc tính nghiệp vụ tự nhiên (ví dụ thẻ tín dụng chỉ có 28.26% khách hàng sử dụng).
2. Bản ghi mồ côi `bureau_balance` (43,041 mã) và các đợt thanh toán trả góp từng phần (653,483 dòng) được xử lý an toàn từ DE-04 và ghi nhận lại trong manifest.
3. Các chỉ số thống kê của khách hàng không có lịch sử được bảo toàn giá trị `NaN` thực tế.

### Xác nhận phạm vi Data Dictionary
Tệp từ điển dữ liệu `data_dictionary.csv` thuộc phạm vi công việc chuyên biệt của nhiệm vụ `TV2-DE-06 — Data Dictionary and Data Quality Report`. DE-05 không tạo tệp này.

#### Hướng dẫn cho TV1 (Modeling) và TV3 (Dashboard & Application)
- **Tệp dữ liệu sử dụng:** Đọc trực tiếp từ `data/processed/cleaned_dataset.parquet` bằng `pd.read_parquet('data/processed/cleaned_dataset.parquet')`.
- **Tính toán và huấn luyện:** Tệp đã được sắp xếp tăng dần theo `SK_ID_CURR`, bảo toàn trọn vẹn 307,511 dòng của tập huấn luyện đã được làm sạch và bổ sung đầy đủ 201 đặc trưng (bao gồm 74 đặc trưng lịch sử đa nguồn).
- **Phân tách Cross-Validation:** Luôn sử dụng Stratified K-Fold dựa trên cột `TARGET` để đảm bảo tỷ lệ mất cân bằng (imbalance) ~8.07% được phản ánh đồng đều giữa các fold.

## TV2-DE-06 — Data Dictionary and Data Quality Report

### Mục đích (Purpose)
Nhiệm vụ `TV2-DE-06` thực hiện biên dịch từ điển dữ liệu chuẩn tắc ở dạng bảng máy đọc (`data/processed/data_dictionary.csv`) và báo cáo kiểm định chất lượng dữ liệu toàn diện ở dạng văn bản người đọc (`reports/data_quality_report.md`) cho tập dữ liệu chuẩn tắc huấn luyện `data/processed/cleaned_dataset.parquet`.

**Nguyên tắc bất biến:** Nhiệm vụ này là bước kiểm toán và lập tài liệu độc lập; tuyệt đối không tái tạo, không chỉnh sửa, không ghi đè lên `data/processed/cleaned_dataset.parquet` và `data/processed/cleaned_dataset_manifest.json`.

### Dữ liệu đầu vào (Inputs)
1. **Tập dữ liệu chuẩn tắc:** `data/processed/cleaned_dataset.parquet` (307,511 dòng, 203 cột).
2. **Manifest kiểm định xuất bản:** `data/processed/cleaned_dataset_manifest.json`.
3. **Mô tả gốc của Kaggle:** `data/raw/HomeCredit_columns_description.csv` (160 dòng mô tả trường thô của cuộc thi).

### Tệp đầu ra xuất bản (Published Output Artifacts)
1. **Machine-Readable Data Dictionary:** `data/processed/data_dictionary.csv`
   - Đúng 203 dòng (1 dòng cho mỗi cột chuẩn tắc, không trùng lặp, không thiếu cột).
   - Đúng 22 cột siêu dữ liệu theo đúng thứ tự quy định của đề mục đã khóa.
   - Định dạng mã hóa: UTF-8 with BOM (`utf-8-sig`), ký tự ngắt dòng LF (`\n`).
   - Tệp này được loại trừ khỏi Git theo quy tắc `.gitignore` (`data/processed/*.csv`).
2. **Human-Readable Data Quality Report:** `reports/data_quality_report.md`
   - Gồm đúng 19 phần Markdown chuẩn tắc được đánh số rõ ràng (từ 1 đến 19).
   - Trình bày toàn diện các phát hiện kiểm toán chất lượng dữ liệu thực tế đo đạc từ 307,511 dòng.
   - Định dạng mã hóa: UTF-8, ký tự ngắt dòng LF (`\n`).
   - Trạng thái Git: Là sản phẩm bàn giao dự kiến theo dõi (intended tracked deliverable) nhưng giữ trạng thái untracked (`??`) cho đến khi hoàn thành commit đánh giá DE-06.

### Lược đồ 22 cột của Data Dictionary (Approved 22-Column Schema)
Toàn bộ 203 cột trong tập dữ liệu chuẩn tắc được mô tả tuần tự theo đúng 22 trường:
1. `position`: Vị trí chỉ mục cột từ 0 đến 202, liên tục và đơn điệu.
2. `column_name`: Tên cột chuẩn tắc (khớp 100% với tên cột trong parquet).
3. `physical_dtype`: Kiểu dữ liệu lưu trữ vật lý trong Parquet (`int64`, `int32`, `float64`, `float32`, `category`).
4. `logical_type`: Kiểu logic (`identifier`, `binary`, `categorical`, `ordinal`, `count`, `continuous`, `currency`, `duration`, `rate`, `ratio`, `flag`).
5. `role`: Vai trò nghiệp vụ chuẩn tắc (`identifier`, `target`, `feature`).
6. `feature_group`: Phân nhóm đặc trưng (`identifier`, `target`, `application_raw`, `application_cleaning`, `application_derived`, `bureau`, `previous_application`, `installments`, `pos_cash`, `credit_card`).
7. `source_table`: Tên bảng nguồn phát sinh cột (`application_train`, `bureau`, `previous_application`,...).
8. `source_columns`: Tên cột nguồn tương ứng trước khi phái sinh/làm sạch.
9. `source_grain`: Hạt dữ liệu nguồn (`application`, `credit_loan`, `cash_loan_month`,...).
10. `canonical_grain`: Hạt dữ liệu chuẩn tắc (`customer (SK_ID_CURR)`).
11. `transformation_formula`: Công thức phái sinh hoặc logic biến đổi (`cleaned identity`, `replace(...)`, công thức tài chính/tổng hợp).
12. `unit`: Đơn vị đo lường (`currency (CZK)`, `years`, `days`, `ratio`, `rate [0.0, 1.0]`, `count`, `unitless`).
13. `description`: Mô tả ngữ nghĩa nghiệp vụ bằng tiếng Anh (không được để trống).
14. `missing_value_meaning`: Ý nghĩa khi giá trị bị khuyết thiếu (ví dụ: `no_credit_history_fill_zero`, `not_applicable_complete`,...).
15. `valid_values_or_range`: Miền giá trị cho phép hoặc danh mục hợp lệ (đặc biệt phân biệt rõ rate `[0.0, 1.0]` và ratio `unbounded`).
16. `nullable`: Cờ logic cho biết cột có chứa giá trị khuyết thiếu trong tập dữ liệu hay không (`True` hoặc `False`).
17. `missing_count`: Số lượng giá trị khuyết thiếu thực tế quan sát được trong 307,511 dòng.
18. `missing_rate`: Tỷ lệ khuyết thiếu thực tế (làm tròn 6 chữ số thập phân).
19. `unique_count`: Số lượng giá trị phân biệt thực tế (không tính NaN).
20. `as_of_time_rule`: Quy tắc mốc thời gian chống rò rỉ (sự kiện lịch sử xảy ra tại thời điểm hoặc trước khi nộp đơn, `DAYS <= 0`).
21. `leakage_note`: Ghi chú an toàn chống rò rỉ dữ liệu nhãn mục tiêu.
22. `modeling_note`: Hướng dẫn kỹ thuật tiền xử lý dành cho mô hình hóa của TV1.

### Phân tầng tỷ lệ khuyết thiếu (Missingness Buckets Partition)
Quy trình áp dụng 7 nhóm phân tầng khuyết thiếu tất định, loại trừ lẫn nhau và bao phủ toàn bộ:
- `exactly 0%`: 73 cột (gồm `SK_ID_CURR`, `TARGET`, 18 cột số đếm lịch sử điền 0, và các trường hồ sơ đầy đủ).
- `greater than 0% and less than 5%`: 12 cột (`AMT_ANNUITY`, `AMT_GOODS_PRICE`, tỷ lệ tài chính DE-03).
- `greater than or equal to 5% and less than 20%`: 48 cột (`EXT_SOURCE_3` 19.83%, `DAYS_EMPLOYED` / `EMPLOYED_YEARS` 18.01%, thiếu lịch sử `BUREAU_` 14.31%).
- `greater than or equal to 20% and less than 50%`: 9 cột (`OCCUPATION_TYPE` 31.35%, đặc tính tòa nhà).
- `greater than or equal to 50% and less than 80%`: 61 cột (`EXT_SOURCE_1` 56.38%, `COMMONAREA_AVG` 69.87%, đặc trưng thẻ tín dụng `CC_*` 71.74% do độ bao phủ chỉ đạt 28.26%).
- `greater than or equal to 80% and less than 100%`: 0 cột.
- `exactly 100%`: 0 cột.
- **Tổng số cột phân tầng:** Đúng 203/203 cột.

### Phân loại đặc trưng hằng số và gần như hằng số
- **All-null (0 non-null values):** 0 cột.
- **Constant (1 unique non-null value):** 0 cột.
- **Near-constant (Tần suất giá trị áp đảo >= 99.5%):** Đúng 16 cột (gồm các cờ tài liệu `FLAG_DOCUMENT_*` và cờ điện thoại `FLAG_MOBIL`, `FLAG_CONT_MOBILE`).
- **Ghi chú về `DAYS_EMPLOYED_ANOM`:** Cờ dị biệt này có tần suất giá trị phổ biến là ~81.99% (giá trị 0 khi không phát hiện sentinel 365243, 18.01% giá trị 1 khi phát hiện sentinel), do đó không thuộc nhóm near-constant và được giữ nguyên là một cờ chất lượng dữ liệu và dị biệt quan trọng.

### Phạm vi loại trừ (Exclusions from DE-06)
Các phân tích tương quan với nhãn mục tiêu, xếp hạng dự báo đặc trưng và phân tích tương quan đa biến nâng cao được loại trừ hoàn toàn khỏi DE-06 và thuộc phạm vi chuyên biệt của `TV2-DE-07 — Exploratory Data Analysis and Data Engineering Handoff`. DE-06 chỉ kiểm toán tính toàn vẹn của nhãn mục tiêu (kiểu dữ liệu, số lượng lớp, tỷ lệ mất cân bằng).

### Lệnh thực thi & Tái tạo
```powershell
& .\.venv\Scripts\python.exe -m src.data.quality_report
```

### Lệnh kiểm thử
```powershell
& .\.venv\Scripts\python.exe -m pytest tests\data\test_quality_report.py -v
& .\.venv\Scripts\python.exe -m pytest tests\data -q
& .\.venv\Scripts\python.exe -m pytest tests -q
```

### Hướng dẫn sử dụng cho các thành viên hạ nguồn (Downstream Handoff)
- **TV1 (Modeling):**
  * Nhận các tệp: `data/processed/cleaned_dataset.parquet`, `data/processed/data_dictionary.csv`, `reports/data_quality_report.md`.
  * Bắt buộc tách `SK_ID_CURR` khỏi ma trận đặc trưng `X`.
  * Bắt buộc tách `TARGET` làm vector nhãn `y` (không đưa vào pipeline biến đổi).
  * Luôn sử dụng `StratifiedKFold` dựa trên tỷ lệ nợ xấu ~8.07%.
  * Thực hiện fit toàn bộ bộ biến đổi (imputer, scaler, encoder, selector) **duy nhất trên train fold** của mỗi fold.
  * Tự chủ ra quyết định về chiến lược lựa chọn đặc trưng và loại bỏ các cột near-constant trong quy trình mô hình hóa.
- **TV3 (Dashboard & Application):**
  * Sử dụng `cleaned_dataset.parquet` và `data_dictionary.csv` để tra cứu nhãn giao diện, phân loại và ngữ nghĩa đặc trưng.
  * Đối với các biểu đồ và giao diện liên quan đến kết quả dự báo mô hình, điểm số rủi ro và xếp hạng decile, TV3 sẽ đợi sản phẩm `data/processed/scored_dataset.parquet` từ TV1.
