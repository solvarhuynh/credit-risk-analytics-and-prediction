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

## Output và bước kế tiếp

DE-01 trả report trong memory/console, chưa tạo processed dataset. Bước kế tiếp
là `DE-02 — Data Cleaning & Sentinel/Missing Handling`; sau đó tiếp tục theo
roadmap trong `logs/log_tv2.md`.
