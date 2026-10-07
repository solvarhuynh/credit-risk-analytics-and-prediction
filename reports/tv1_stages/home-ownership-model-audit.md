# Home Ownership Audit — Dash demo 6-input

Ngày kiểm tra: 2026-10-07. Phạm vi: hai candidate demo XGBoost và Logistic Regression; **chỉ train/validation**, không đọc frozen test, không fit lại hay đổi artifact. Kết luận: **không phát hiện lỗi mapping, preprocessing, dự đoán hoặc gộp local SHAP**. Khác biệt OWN/MORTGAGE quan sát được là hành vi model đã fit. Đây không phải bằng chứng nhân quả.

## 1. Đường đi dữ liệu và UI mapping

| Nhãn form | Giá trị callback | Cột model `home_ownership` | OHE được kích hoạt |
|---|---|---|---|
| Sở hữu nhà | `OWN` | `OWN` | `categorical__home_ownership_OWN` |
| Đang trả thế chấp | `MORTGAGE` | `MORTGAGE` | `categorical__home_ownership_MORTGAGE` |
| Thuê nhà | `RENT` | `RENT` | `categorical__home_ownership_RENT` |

`app.py` tạo `dcc.Dropdown` bằng cặp nhãn/value trên; callback truyền **value** nguyên vẹn vào `run_form_prediction` → `predict_six_demo` → `validate_six_input` → `DataFrame` có đúng thứ tự `loan_amnt, annual_inc, dti, term_months, fico_avg, home_ownership`. Cả hai pipeline đã lưu đều có `sanitize` → `normalize_missing` → `preprocess` → `model`; `predict_proba(frame)[:, 1]` lấy xác suất class dương. Manifest/model hash được kiểm tra trước khi nạp. SHAP/đóng góp được tính từ **cùng dòng đã transform** và đưa về sáu input gốc; UI hiển thị dòng `Tình trạng nhà ở` của đúng kết quả đó.

Trên hai artifact thật, mỗi pipeline có **11 transformed features: 5 numeric + 6 one-hot** theo đúng thứ tự `ANY, MORTGAGE, NONE, OTHER, OWN, RENT`. Với ba category form, đúng một OHE tương ứng bằng 1, năm OHE còn lại bằng 0; các numeric transformed giữ nguyên khi chỉ đổi category. Không có integer encoding, tráo OWN/MORTGAGE, nhãn tiếng Việt truyền vào encoder, trim/case fallback hoặc cột nhà ở bị bỏ/lặp. Encoder đã fit có `handle_unknown=ignore`, nhưng lớp `validate_six_input` từ chối giá trị unknown/null/nhãn tiếng Việt trước khi encoder chạy; form mặc định `RENT`. `OTHER`, `NONE`, `ANY` tồn tại **riêng** trong train/encoder/model, không gộp vào ba category chính; chỉ bị ẩn khỏi dropdown công khai.

## 2. Phân bố TRAIN / VALIDATION

Nguồn: `data/processed/cleaned_dataset.parquet` nối 1:1 theo `loan_id` với `data/processed/modeling/train_ids.parquet` và `validation_ids.parquet`; `target` hai phía khớp. Tỷ lệ default là `default count / N` trong chính partition đó. Không dùng test.

| Category | Train N | Train default | Train rate | Validation N | Validation default | Validation rate |
|---|---:|---:|---:|---:|---:|---:|
| MORTGAGE | 399.613 | 68.712 | 17,19% | 132.805 | 22.885 | 17,23% |
| OWN | 86.453 | 17.877 | 20,68% | 29.223 | 6.026 | 20,62% |
| RENT | 320.855 | 74.524 | 23,23% | 106.949 | 24.785 | 23,17% |
| ANY | 176 | 30 | 17,05% | 51 | 13 | 25,49% |
| NONE | 28 | 3 | 10,71% | 11 | 2 | 18,18% |
| OTHER | 85 | 13 | 15,29% | 31 | 9 | 29,03% |

Tổng: train **807.210**, validation **269.070**; không có `home_ownership` thiếu trong hai partition này. Ba category hiếm có cỡ mẫu quá nhỏ để suy luận xu hướng ổn định, nên ẩn khỏi form là quyết định UX, không phải thay đổi model.

So sánh mô tả theo nhóm (median; tỷ lệ kỳ hạn 60 tháng) cho thấy các biến khác cũng khác nhau:

| Category | Train income | Train FICO | Train DTI | Train loan | Train 60 tháng | Validation income | Validation FICO | Validation DTI | Validation loan | Validation 60 tháng |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MORTGAGE | 74.628 | 692 | 17,64 | 15.000 | 28,49% | 74.200 | 692 | 17,63 | 15.000 | 28,42% |
| OWN | 60.000 | 692 | 18,19 | 12.000 | 21,64% | 59.726 | 692 | 18,30 | 12.000 | 21,87% |
| RENT | 55.000 | 687 | 17,41 | 10.450 | 19,38% | 55.000 | 687 | 17,50 | 10.500 | 19,32% |

Đây là mô tả theo nhóm, **không phải** tác động riêng của tình trạng nhà ở. Đặc biệt, MORTGAGE có income median cao hơn, nhưng cũng có tỷ lệ kỳ hạn 60 tháng cao hơn; không thể gán chênh lệch default cho một biến đơn lẻ.

## 3. PD model trên VALIDATION theo category

Nguồn: hai file `*_6input_demo_validation_predictions.parquet` đã lưu, nối 1:1 theo `loan_id` với validation; không chấm lại model, không dùng frozen test. PD là dự đoán model; observed rate lấy từ target validation và là đại lượng khác.

| Model | Category | N | Mean PD | Median PD | Observed default rate |
|---|---|---:|---:|---:|---:|
| XGBoost | MORTGAGE | 132.805 | 17,22% | 15,13% | 17,23% |
| XGBoost | OWN | 29.223 | 20,87% | 19,14% | 20,62% |
| XGBoost | RENT | 106.949 | 23,13% | 20,42% | 23,17% |
| Logistic | MORTGAGE | 132.805 | 17,18% | 14,89% | 17,23% |
| Logistic | OWN | 29.223 | 20,85% | 19,09% | 20,62% |
| Logistic | RENT | 106.949 | 23,17% | 21,24% | 23,17% |

## 4. Cùng một hồ sơ: profile B

Giữ cố định `loan_amnt=27000`, `annual_inc=65000`, `dti=25`, `term_months=36`, `fico_avg=700`; chỉ đổi `home_ownership`. Điểm cá nhân là percentile trong validation **riêng của model**, không phải PD. EL dùng LGD 45% × số tiền vay (EAD proxy). Đóng góp nhà ở ở **raw margin/log-odds**, không phải điểm phần trăm PD.

| Model | Nhà ở | PD | Điểm cá nhân | Tier/mức | Điểm an toàn | EL 45% | Đóng góp nhà ở |
|---|---|---:|---:|---|---:|---:|---:|
| XGBoost | OWN | 20,40698% | 60/100 | B / Trung bình | 796 | 2.479,45 | +0,020644 |
| XGBoost | MORTGAGE | 18,13958% | 52/100 | B / Trung bình | 819 | 2.203,96 | −0,164934 |
| XGBoost | RENT | 23,71369% | 71/100 | C / Cao | 763 | 2.881,21 | +0,185869 |
| Logistic | OWN | 21,38439% | 64/100 | B / Trung bình | 786 | 2.598,20 | −0,315151 |
| Logistic | MORTGAGE | 16,98984% | 45/100 | B / Trung bình | 830 | 2.064,27 | −0,599589 |
| Logistic | RENT | 23,58027% | 72/100 | C / Cao | 764 | 2.865,00 | −0,189072 |

MORTGAGE thấp hơn OWN trên cùng profile B: XGBoost **−2,27 điểm phần trăm PD**, Logistic **−4,39 điểm phần trăm PD**. Đó là chênh lệch *dự đoán khi thay input*, không phải tác động nhân quả của việc đổi tình trạng nhà ở.

## 5. Độ nhạy trên nhiều profile

| Profile (loan/income/DTI/term/FICO) | Model | OWN PD | MORTGAGE PD | RENT PD | MORTGAGE − OWN |
|---|---|---:|---:|---:|---:|
| A (10.000/90.000/10/36/760) | XGBoost | 5,8073% | 4,2138% | 6,1573% | −1,59 điểm % |
| A | Logistic | 6,6828% | 5,1129% | 7,5133% | −1,57 điểm % |
| B (27.000/65.000/25/36/700) | XGBoost | 20,4070% | 18,1396% | 23,7137% | −2,27 điểm % |
| B | Logistic | 21,3844% | 16,9898% | 23,5803% | −4,39 điểm % |
| C (30.000/45.000/35/60/660) | XGBoost | 57,3606% | 53,3179% | 66,2948% | −4,04 điểm % |
| C | Logistic | 58,5456% | 51,5189% | 61,5690% | −7,03 điểm % |

Thứ tự MORTGAGE < OWN < RENT lặp lại ở **ba hồ sơ này và hai model**, nhưng độ lớn thay đổi theo hồ sơ/model. Không suy rộng rằng thứ tự phải đúng cho mọi người vay hoặc nguyên nhân gây default. Với XGBoost, đóng góp SHAP nhà ở của OWN đổi dấu ở profile C, cho thấy tương tác/ngữ cảnh quan trọng; Logistic dùng hệ số tuyến tính cố định cho từng category.

## 6. SHAP / local explanation

Mỗi pipeline có 6 OHE nhà ở. `_group_transformed_features` cộng **tất cả** contribution có source `home_ownership`, không chỉ cột đang bằng 1, không cộng cột numeric và không nhân đôi. Kiểm độc lập trên **18 dự đoán** (3 profile × 3 category × 2 model): sai lệch lớn nhất giữa nhóm nhà ở hiển thị và tổng các transformed contribution nhà ở = **0,0**. Sai số lớn nhất `base + tổng sáu đóng góp gộp − raw margin` là **1,43×10⁻⁶** (XGBoost) và **2,22×10⁻¹⁶** (Logistic); sigmoid(raw margin) khớp `predict_proba[:,1]` trong **2,97×10⁻⁸** và **0**. XGBoost dùng TreeSHAP `model_output="raw"`, Logistic dùng `coefficient × transformed input` ở log-odds. Không phát hiện lỗi giải thích. Dòng headline đã đổi sang “có đóng góp tăng/giảm rủi ro lớn nhất trong dự đoán hiện tại”; không diễn giải SHAP như thay đổi PD theo % hay tác động nhân quả.

## 7. Nguyên nhân, hành động và giới hạn

**Phân loại nguyên nhân: quan hệ thống kê model đã học, không phải bug.** Validation observed default và mean/median PD đều theo thứ tự MORTGAGE < OWN < RENT. Các nhóm khác nhau về income/FICO/DTI/loan/term mix; mô hình demo chỉ có sáu input nên một feature có thể mang tín hiệu tương đối lớn. Không có bằng chứng category bị tráo, encoder fallback, feature order lệch, cache giữ lựa chọn cũ sau khi chấm, hoặc SHAP gộp sai. Kết luận này không chứng minh model đã học quy luật nhân quả hay sẽ ổn định ngoài tập dữ liệu hiện có.

Đã **chỉ sửa UI/diễn đạt/test**: ẩn `OTHER` khỏi ba lựa chọn form, giữ `OTHER`/`ANY`/`NONE` bên trong fitted artifacts; nâng stacking level của input panel khi dropdown có focus để menu nổi trước card bên dưới; đổi headline giải thích thành ngôn ngữ gắn với hồ sơ hiện tại; đổi input/model sẽ xóa kết quả cũ, inference mới vẫn chỉ khi bấm DỰ ĐOÁN. Không sửa model, PD, threshold, tier, percentile, EL hay SHAP calculation; không retrain, không dùng frozen test.

**Khuyến nghị: KEEP HOME OWNERSHIP trong demo hiện tại**, vì ba category hiển thị đều có cỡ mẫu lớn, đối chiếu pipeline/SHAP đạt và validation candidate có cải thiện so với bản 5-input đã ghi trong manifest. Nếu muốn đánh giá tính ổn định/fairness hoặc bỏ biến này, đó là **thí nghiệm model riêng trong tương lai**, cần protocol validation mới; không thực hiện trong audit này.

> Association in the Lending Club data does not mean home ownership status itself causes default risk. Chênh lệch dự đoán khi thay category không phải khuyến nghị để người vay thay tình trạng nhà ở.
