# Thiết lập TV1 — Lending Club Modeling

Trạng thái: **WAITING FOR TV2 LENDING CLUB CANONICAL HANDOFF**. Các lệnh là **EXPECTED / NOT YET VERIFIED AFTER DATASET RESET**.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Ý nghĩa: tạo môi trường Python độc lập, kích hoạt và cài dependency.

```powershell
Get-Item data/processed/cleaned_dataset.parquet,data/processed/data_dictionary.csv,data/processed/cleaned_dataset_manifest.json
```

Ý nghĩa: xác nhận đủ ba artifact TV2. Nếu thiếu thì dừng, không train.

```powershell
python -c "from src.models.modeling_pipeline import load_canonical_input,build_feature_schema; d,dd,m=load_canonical_input(); print(build_feature_schema(d,dd)); print(m)"
```

Ý nghĩa: chạy model input gate, kiểm tra dictionary coverage và chỉ chọn feature `APPLICATION_TIME`/`CREDIT_SNAPSHOT`.

```powershell
python -m pytest tests/models
```

Ý nghĩa: chạy synthetic tests cho split, preprocessing, evaluation, scoring và cost. Không thay thế kiểm tra artifact thật.

Workflow tương lai: freeze split → Logistic baseline bắt buộc → imbalance experiment → optional XGBoost → chọn model/threshold trên development → frozen test một lần → explainability/scoring/expected loss → full-data refit → TV3 handoff. Hiện chưa có lệnh train end-to-end vì artifact TV2 chưa tồn tại và không được tạo kết quả giả.

## Phạm vi trách nhiệm sau reorganize

TV1 là primary owner của modeling, V01–V06, Storytelling, report coordination và defense coordination. TV1 cross-review TV2 handoff/V07–V09 và TV3 dashboard structure. TV1 không tích hợp Master PBIX; TV3 giữ integration ownership.
