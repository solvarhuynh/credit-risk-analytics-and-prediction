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

### Sai số xác suất và độ hiệu chuẩn

Ứng dụng là bộ phân loại nhị phân tạo PD, không phải mô hình hồi quy tuyến tính. Với hồ sơ đang nhập, chưa biết kết quả trả nợ thực tế; do đó không thể tính sai số thực tế riêng cho người đó. Không hiển thị khoảng `±`, “độ chính xác của cá nhân” hoặc phần trăm chắc chắn giả định.

Các metric dưới đây là **metrics Validation của đúng candidate 6-input đang chọn**, lấy nguyên từ `validation_metrics` trong manifest; mỗi manifest xác nhận cùng 269.070 dòng validation, threshold `0.22009515762329102`, và không truy cập frozen test:

| Model 6-input | Brier Score ↓ | Log Loss ↓ | Accuracy | Precision | Recall | F1 | ROC-AUC | PR-AUC |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| XGBoost | 0,148171 | 0,464115 | 0,677537 | 0,319936 | 0,546482 | 0,403591 | 0,685266 | 0,349475 |
| Logistic Regression | 0,149154 | 0,468207 | 0,678009 | 0,318048 | 0,535555 | 0,399090 | 0,677361 | 0,341154 |

**Brier Score** = `mean((PD_dự đoán − nhãn_thực_tế)²)` trên nhãn Validation (0 = không default, 1 = default); thấp hơn tốt hơn. Đây là sai số bình phương trung bình của xác suất ở cấp tập dữ liệu, không phải biên sai số của một người.

**Log Loss** đánh giá chất lượng xác suất và phạt mạnh dự đoán quá chắc chắn nhưng sai; thấp hơn tốt hơn. Không đổi Log Loss thành “% chính xác”. Accuracy/Precision/Recall/F1 là kết quả phân loại tại threshold nêu trên; do dữ liệu mất cân bằng, không xem Accuracy hoặc `1 − Accuracy` riêng lẻ là độ tin cậy.

Biểu đồ chính là **PD và ngưỡng cảnh báo**: 120 hồ sơ lấy mẫu cố định từ prediction Validation của model đang chọn, tô màu theo ngưỡng tương tác; hình thoi biểu diễn PD hồ sơ đang nhập. Hai số ngay trên biểu đồ đếm các chấm được gắn cờ và dưới ngưỡng; tổng bằng 120 **hồ sơ tham chiếu đang hiển thị**, không phải toàn bộ 269.070 hồ sơ Validation. Trục X luôn là [0, 1]. Kéo ngưỡng chỉ chuyển đường/màu và hai số đếm, không chấm lại model hay rút mẫu mới. Đổi model thì dùng PD Validation của chính model đó. Hàm kiểm định hiệu chuẩn cũ còn trong mã phục vụ kiểm thử/chẩn đoán, không xuất hiện trong giao diện chính.

Metrics được gắn với `xgboost_6input_demo_manifest.json` hoặc `logistic_6input_demo_manifest.json`; model đang chọn và prediction artifact Validation được đối chiếu SHA-256/split trước khi hiện chart. Nếu metric thiếu trong manifest, giao diện hiện `—`, không lấy giá trị từ model 103-feature, model 5-input hay frozen test. Hai model sáu input chỉ là ứng viên demo UI, không thay model chính ML-LC-12; frozen test của chúng chưa được đánh giá theo protocol đã chọn.

## Kết quả và giải thích

- Kết quả chính có đúng **bốn thẻ xếp 2×2**: Mức độ rủi ro tín dụng, Hạng rủi ro, Xác suất vỡ nợ dự báo (PD), Điểm an toàn mô hình. Tier ánh xạ A→THẤP, B→TRUNG BÌNH, C→CAO, D→RẤT CAO theo dải PD cố định.
- PD hiển thị dạng phần trăm trực tiếp từ `predict_proba`. Điểm an toàn = `round(1000 × (1 − PD))`, điểm cao nghĩa là rủi ro dự báo thấp; đây không phải FICO. Quyết định theo ngưỡng nằm ở hàng riêng với nhãn Default/Non-default. **Chi tiết mô hình** chỉ có model, hai ngưỡng và hai kết luận, rồi Recall/Precision/Accuracy của đúng demo model trên Validation.
- **Ngưỡng phân loại tương tác** chọn trong [0, 1] (bước 0,01). Mặc định/Đặt lại dùng giá trị nội bộ chính xác `0.22009515762329102`, hiển thị `0.2201`; đây là ngưỡng tối ưu F1 trên Validation của mô hình chính, không tối ưu riêng cho hai demo 6-input. `PD >= ngưỡng` → **CẦN CẢNH BÁO (Default)**, còn lại → **CHƯA VƯỢT NGƯỠNG (Non-default)**. Đây là phân loại mô hình, không phải quyết định phê duyệt/từ chối khoản vay. Thay ngưỡng chỉ đổi phân loại, đường/màu và số đếm trên visual, cùng đối chiếu TP/TN/FP/FN; PD, tier, mức rủi ro, điểm an toàn, SHAP và EL giữ nguyên.
- **Tám hồ sơ mẫu** có loan_id và nhãn quan sát thật từ canonical/Validation. Sáu trường input được điền vào form, PD preview đọc prediction artifact Validation của model đang chọn, bấm DỰ ĐOÁN để chạy inference. Hai nhãn “Ca đối chiếu A/B” được chọn vì lần lượt là FP/FN với XGBoost tại ngưỡng tham chiếu; đó là mô tả nguồn gốc ca, không phải kết luận hiện tại. Dải đối chiếu tính động theo `actual` cố định và `PD >= ngưỡng`: TP = phát hiện đúng default, TN = phân loại đúng non-default, FP = cảnh báo nhầm non-default, FN = bỏ sót default. Chuyển model sau khi đã dự đoán sẽ suy luận lại với model mới; chỉnh bất kỳ input nào sẽ ẩn nhãn lịch sử và xóa kết quả cũ.
- Recall, Precision, F1 và Accuracy trong UI là **metrics Validation được lưu tại ngưỡng tham chiếu của artifact demo 6-input**. Chúng không tự đổi theo slider. ROC-AUC, PR-AUC, Brier Score và Log Loss cũng lấy từ manifest đúng model; thiếu metric thì hiện `—`.

Visual PD–threshold trả lời: **PD của hồ sơ đang nhập nằm phía nào của ngưỡng quyết định?** Chấm theo PD trên cùng trục 0–1 và đường dọc ngưỡng giúp thấy ngay quy tắc phân loại; màu xanh/cam biểu diễn phân loại hiện tại. Khi hạ ngưỡng, nhiều hồ sơ hơn được gắn cờ: có thể phát hiện thêm default nhưng cũng có thể tăng cảnh báo nhầm, điều này phải đối chiếu nhãn thật chứ không suy từ màu chấm. Trong câu chuyện ứng dụng, visual nối **input → PD → quyết định → đối chiếu outcome → giải thích SHAP/Expected Loss**; không suy ra nguyên nhân hay hiệu năng cá nhân từ chấm mẫu.
- Điểm an toàn là thang nội bộ của project, không phải FICO Score: điểm cao hơn thể hiện model dự đoán an toàn hơn.
- Expected Loss = `PD × LGD × số tiền vay`; `loan_amnt` chỉ là EAD proxy, không phải EAD thực tế. Công thức/giới hạn nằm trong mục **ⓘ Giải thích EL** có thể mở, không phủ lên LGD hay các KPI. Các kịch bản LGD là 30%, 45%, 60%; đổi LGD chỉ cập nhật EL, không chạy inference lại và không thay đổi PD.
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

Launcher mặc định dùng `http://127.0.0.1:8050`; dừng server bằng `Ctrl+C` trong cửa sổ app. Mỗi `DASH_PORT` là một process/địa chỉ riêng, không tự cập nhật khi code đổi. Launcher kiểm tra cổng trước khi chạy và dừng rõ ràng nếu cổng đã bị chiếm, thay vì mở nhầm server cũ. Để dùng build mới, dừng đúng app cũ rồi chạy lại. Nếu báo port bận, không đổi số cổng theo phỏng đoán: kiểm tra process bằng `Get-NetTCPConnection -State Listen -LocalPort 8050 | Select-Object LocalAddress,LocalPort,OwningProcess`, dừng phiên cũ, sau đó chạy launcher ở cổng mặc định. Chỉ chọn `DASH_PORT` khác khi đã xác minh cổng đó trống; launcher cũng sẽ kiểm tra lại.

Launcher in URL của phiên bản hiện tại trong repo ngay trước khi chạy; `Ctrl+F5` chỉ xóa cache trình duyệt, không nâng cấp code trong Python process cũ. App chỉ bind loopback, chưa có authentication và không dành cho deploy công khai. Nếu artifact 6-input chưa có, inference/metrics sẽ không khả dụng; train candidate chỉ theo task được duyệt bằng `python -m src.models.demo_6input --train`. Lệnh này mở train/validation, **không đọc frozen test**, và dừng nếu output đã tồn tại để tránh ghi đè.

Giới hạn numeric input theo train và kiểm tra nghiệp vụ form: loan amount 500–40.000; annual income lớn hơn 0 đến 9.550.000; DTI `[0, 999]` (giá trị DTI âm trong nguồn được xử lý như missing khi fit, nên không cho nhập tay như một DTI hợp lệ); kỳ hạn 36/60; FICO 627–847,5. Input không hữu hạn, vượt miền hoặc home ownership không hợp lệ sẽ bị từ chối.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest tests/apps/test_individual_prediction_dash.py tests/models/test_demo_6input.py tests/models/test_risk_index.py -v
.\.venv\Scripts\python.exe -m compileall -q src apps tests
```

Power BI chỉ có nút mở ứng dụng ở working PBIP; Power BI không tự gọi model hay khởi chạy server. Các frozen-test prediction/artifact 5-input lịch sử không dùng cho inference Dash 6-input.
