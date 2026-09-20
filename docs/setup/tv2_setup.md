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

## Output và bước kế tiếp

DE-01 và DE-02 đã hoàn thành kiểm toán và tầng làm sạch cơ sở. Bước kế tiếp
là `TV2-DE-03 — Application-Level Feature Engineering`; sau đó tiếp tục theo
roadmap trong `logs/log_tv2.md`.
