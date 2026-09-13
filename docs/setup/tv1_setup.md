# TV1 — Modeling setup & run guide

Owner: TV1 (Modeling & Machine Learning)

## Trạng thái hiện tại

Các module modeling trong `src/models/` hiện là skeleton; canonical model input
(`data/processed/cleaned_dataset.parquet`) chưa được bàn giao. Vì vậy hiện chưa
có lệnh train/evaluate modeling để chạy và không được tự tạo dữ liệu thay thế.

## Chuẩn bị môi trường

Từ thư mục repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Khi có canonical handoff

TV1 chỉ bắt đầu preprocessing/split sau khi TV2 bàn giao:

- `data/processed/cleaned_dataset.parquet`
- `data/processed/data_dictionary.csv`
- quality report chứng minh `SK_ID_CURR`, `TARGET`, missing/sentinel và leakage checks.

Lệnh train chính thức: `PENDING` — sẽ cập nhật ngay khi script modeling canonical
được implement và validation được kiểm tra.

## Output dự kiến

Model artifact và `data/processed/scored_dataset.parquet` theo
`docs/contracts/model_contract.md`. Không commit model/data lớn vào Git.

## Validation bắt buộc

TV1 phải ghi lại split strategy, metric (AUC/Precision/Recall/F1), model path và
đảm bảo imputer/encoder/scaler chỉ fit trên train fold. Nếu thiếu canonical input,
trạng thái là `BLOCKED`.
