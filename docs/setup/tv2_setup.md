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
- **Giới hạn:** DE-03 chỉ tạo đặc trưng row-local cho bảng application. Chưa thực hiện aggregate các bảng lịch sử (DE-04), chưa join đa bảng và chưa tạo tệp Parquet tổng hợp cuối cùng (DE-05).
- **Bước kế tiếp:** `TV2-DE-04 — Historical Table Aggregation`.
