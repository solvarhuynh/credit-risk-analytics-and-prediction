# Công cụ dự đoán rủi ro khoản vay — Dash HCMUTE

Ứng dụng Dash chạy cục bộ, dùng form **6 đầu vào** cho mô hình demo phụ:

1. Số tiền vay (`loan_amnt`)
2. Thu nhập năm (`annual_inc`)
3. DTI (`dti`)
4. Kỳ hạn vay (`term_months`: 36 hoặc 60)
5. Điểm FICO (`fico_avg`, là trung bình hai đầu khoảng FICO trong dữ liệu chuẩn)
6. Tình trạng nhà ở (`home_ownership`)

## Tình trạng nhà ở

Form dùng **một dropdown** gọn với đúng ba lựa chọn: **Sở hữu nhà** → `OWN`, **Đang trả thế chấp** → `MORTGAGE`, **Thuê nhà** → `RENT` (mặc định). Khi đóng, chỉ lựa chọn đang dùng xuất hiện; menu mở nổi phía trên các card bên dưới. `OTHER`, `ANY`, `NONE` vẫn là ba category riêng trong dữ liệu/encoder/model đã fit, nhưng không hiện trong form demo và không bị gộp vào ba lựa chọn phổ biến. Giá trị ngoài schema đã train bị từ chối. Thay input hoặc model sẽ xóa kết quả cũ; bấm **DỰ ĐOÁN** để chạy inference mới.

## So sánh candidate và quy tắc chọn

Hai phiên bản 6-input được fit trên cùng train split và đánh giá trên cùng validation split 269.070 dòng, dùng threshold khóa `0.22009515762329102`. Theo lựa chọn của người dùng, việc nhận candidate chỉ dựa trên validation; **không dùng lại frozen test để chọn hay báo metrics mới**. Frozen-test metrics hiện có của hai bản 5-input là lịch sử one-shot, không được so sánh như một lượt đánh giá công bằng mới với 6-input.

| Model | Inputs | ROC-AUC | PR-AUC | F1 | Recall | Precision | Trạng thái Dash |
|---|---:|---:|---:|---:|---:|---:|---|
| XGBoost 5-input | 5 | 0,680460 | 0,341929 | 0,400753 | 0,544751 | 0,316967 | Baseline validation |
| XGBoost 6-input | 6 | 0,685266 | 0,349475 | 0,403591 | 0,546482 | 0,319936 | **ACTIVE** |
| Logistic 5-input | 5 | 0,672271 | 0,333273 | 0,391864 | 0,502103 | 0,321318 | Baseline validation |
| Logistic 6-input | 6 | 0,677361 | 0,341154 | 0,399090 | 0,535555 | 0,318048 | **ACTIVE** |

Ở validation, cả hai bản 6-input đều tăng ROC-AUC, PR-AUC và F1 so với cùng loại baseline 5-input. XGBoost precision tăng nhẹ; Logistic precision giảm nhẹ trong khi recall/F1 tăng. Vì cả hai candidate có cải thiện có thể quan sát được trên các metric chính mà không có giảm lớn ở metric hỗ trợ, Dash chuyển sang hai model 6-input để selector dùng chung một form. Đây là chọn candidate dựa validation, không phải tuyên bố mô hình tổng quát tốt hơn trên dữ liệu độc lập. Accuracy không dùng làm metric headline: default chiếm xấp xỉ 20%, nên chỉ nhìn accuracy có thể gây hiểu nhầm.

Candidate mới: `xgboost_6input_demo.joblib` và `logistic_6input_demo.joblib`; preprocessing numeric/categorical được fit trong pipeline trên train. Chúng là demo UI, **không thay thế** model chính ML-LC-12 `xgboost_full_refit.joblib` (103 input → 151 transformed) và không đại diện metrics ML-LC-08. Frozen test của hai model 6-input có trạng thái **NOT EVALUATED** theo validation-only protocol; không chạy lại test.

## Kết quả và giải thích

- Kết quả chính có đúng **bốn thẻ xếp 2×2**: hàng đầu Mức độ rủi ro tín dụng và Hạng rủi ro; hàng sau Điểm rủi ro cá nhân và Điểm an toàn mô hình. Tier ánh xạ A→THẤP, B→TRUNG BÌNH, C→CAO, D→RẤT CAO theo policy PD hiện có.
- **Điểm rủi ro cá nhân** là percentile 0–100 trong phân bố PD của đúng model đang chọn. Reference là **269.070 dự đoán validation**, riêng cho XGBoost và Logistic Regression. Công thức: `100 × số PD validation ≤ PD hồ sơ / 269.070`, sau đó làm tròn để hiển thị `xx / 100`. Ví dụ `82 / 100` nghĩa là PD hồ sơ cao hơn hoặc bằng khoảng 82% PD của reference; **không có nghĩa xác suất vỡ nợ 82%**. Các file validation đã lưu được xác thực và cache trong app; mỗi lần bấm không dự đoán lại toàn bộ dữ liệu, không dùng frozen test.
- PD là xác suất model thật từ `predict_proba`. Giao diện chính không có PD card, thước phần trăm hay cảnh báo ngưỡng. Mục thu gọn **Chi tiết mô hình** hiển thị PD, điểm rủi ro cá nhân, threshold, quyết định theo threshold và metric validation.
- Điểm an toàn là thang nội bộ của project, không phải FICO Score: điểm cao hơn thể hiện model dự đoán an toàn hơn.
- Expected Loss = `PD × LGD × số tiền vay`; `loan_amnt` chỉ là EAD proxy, không phải EAD thực tế. Phần giao diện giải thích ngắn: “Tổn thất kỳ vọng là mức tổn thất ước tính dựa trên rủi ro dự đoán, số tiền vay và LGD.” Các kịch bản LGD là 30%, 45%, 60%; đổi LGD chỉ cập nhật EL, không chạy inference lại.
- Đối chiếu train/validation và ba hồ sơ kiểm soát xác nhận mapping UI/backend đúng; chi tiết ở [báo cáo kiểm tra Home Ownership](../../reports/tv1_stages/home-ownership-model-audit.md). Mức PD khác nhau theo category là hành vi của hai model demo đã fit, không phải tác động nhân quả của tình trạng nhà ở.
- Giải thích có đủ sáu đóng góp local của **chính hồ sơ hiện tại**, không phải phát hiện chung về mọi người vay. XGBoost dùng TreeSHAP raw-margin; Logistic dùng đóng góp có dấu `coefficient × transformed input` trong log-odds. Các one-hot contribution của `home_ownership` được cộng về field gốc; không dựng SHAP giả. Dấu/độ lớn SHAP không phải mức thay đổi PD theo điểm phần trăm và không phải bằng chứng nhân quả.

## Chạy ứng dụng

Từ repo root, sau khi cài dependencies và có hai model demo 6-input, hai manifest, hai file `*_6input_demo_validation_predictions.parquet` cùng `validation_ids.parquet` trong `data/processed/modeling/`:

```powershell
.\run_prediction_app.bat
```

Hoặc chạy trực tiếp:

```powershell
.\.venv\Scripts\python.exe -m apps.individual_prediction_dash.app
```

Launcher mở `http://127.0.0.1:8050`; dừng bằng `Ctrl+C`. Nếu cổng 8050 đang phục vụ instance cũ và cần xem code mới mà không dừng instance đó, mở PowerShell tại repo root rồi chạy:

```powershell
$env:DASH_PORT = "8051"
.\run_prediction_app.bat
```

Launcher sẽ mở đúng cổng đã chọn; dùng `Ctrl+F5` nếu trình duyệt cache UI cũ. App chỉ bind loopback, chưa có authentication và không dành cho deploy công khai. Nếu artifact 6-input chưa có, inference/metrics sẽ không khả dụng; train candidate chỉ theo task được duyệt bằng `python -m src.models.demo_6input --train`. Lệnh này mở train/validation, **không đọc frozen test**, và dừng nếu output đã tồn tại để tránh ghi đè.

Giới hạn numeric input theo train và kiểm tra nghiệp vụ form: loan amount 500–40.000; annual income lớn hơn 0 đến 9.550.000; DTI `[0, 999]` (giá trị DTI âm trong nguồn được xử lý như missing khi fit, nên không cho nhập tay như một DTI hợp lệ); kỳ hạn 36/60; FICO 627–847,5. Input không hữu hạn, vượt miền hoặc home ownership không hợp lệ sẽ bị từ chối.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest tests/apps/test_individual_prediction_dash.py tests/models/test_demo_6input.py tests/models/test_risk_index.py -v
.\.venv\Scripts\python.exe -m compileall -q src apps tests
```

Power BI chỉ có nút mở ứng dụng ở working PBIP; Power BI không tự gọi model hay khởi chạy server. Các frozen-test prediction/artifact 5-input lịch sử không dùng cho inference Dash 6-input.
