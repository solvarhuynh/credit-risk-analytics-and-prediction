# Báo cáo chất lượng dữ liệu bộ dữ liệu chuẩn tắc

## 1. Trạng thái tổng quan
- **Kết quả cổng chất lượng:** `ĐẠT CÓ CẢNH BÁO`
- **Tổng số dòng:** 307,511
- **Tổng số cột:** 203
- **Đặc trưng dự báo:** 201
- **Tỷ lệ vỡ nợ của TARGET:** 8.07% (24,825 hồ sơ / 307,511 khách hàng)
- **Tóm tắt toàn vẹn dữ liệu:** khóa chính (`SK_ID_CURR`) duy nhất 100%, 0 khóa null, 0 sai lệch TARGET, 0 giá trị vô cực, 0 xung đột hậu tố.
- **Mức độ sẵn sàng bàn giao:** đã kiểm định đầy đủ để TV1 (tiền xử lý đặc trưng và mô hình hóa) và TV3 (dashboard tương tác) sử dụng.

## 2. Nhận dạng tạo tác và khả năng tái lập
| Hạng mục tạo tác | Giá trị |
| :--- | :--- |
| **Đường dẫn dataset** | `data/processed/cleaned_dataset.parquet` |
| **Kích thước dataset** | 64,520,535 byte (~61.53 MB) |
| **SHA-256 dataset** | `6460999371297ff2f83418a8341b0c85d4a2e4dc6c29b29e793edd2a0c755c96` |
| **Đường dẫn manifest** | `data/processed/cleaned_dataset_manifest.json` |
| **Kích thước manifest** | 17,361 byte |
| **SHA-256 manifest** | `33496d28258458501ee95b77c5f16aaede80501d6cb18d9130c802e8619a14e4` |
| **Commit Git cơ sở** | `67499751ba6f7e705a0a63ede1e5a623c75a79b5` |
| **Thời điểm tạo (UTC)** | `2026-09-22T20:38:19.875680+00:00` |
| **Phạm vi quần thể** | `application_train_only` (quần thể hồ sơ có nhãn) |
| **Loại trừ application test** | `Có (đã xác minh loại trừ hoàn toàn)` |

## 3. Kích thước và hạt dữ liệu
| Chỉ số | Giá trị đo được | Yêu cầu | Trạng thái |
| :--- | :---: | :---: | :---: |
| **Số dòng** | 307,511 | Chính xác 307,511 | ĐẠT |
| **Số cột** | 203 | Chính xác 203 | ĐẠT |
| **SK_ID_CURR duy nhất** | 307,511 | Chính xác 307,511 | ĐẠT |
| **SK_ID_CURR null** | 0 | Chính xác 0 | ĐẠT |
| **SK_ID_CURR trùng** | 0 | Chính xác 0 | ĐẠT |
| **SK_ID_CURR nhỏ nhất** | 100,002 | 100,002 | ĐẠT |
| **SK_ID_CURR lớn nhất** | 456,255 | 456,255 | ĐẠT |
| **Thứ tự dòng đơn điệu** | True | Sắp xếp tăng dần | ĐẠT |

## 4. Toàn vẹn TARGET
| Lớp | Số lượng | Tỷ lệ | Diễn giải |
| :---: | :---: | :---: | :--- |
| `0` | 282,686 | 91.9271% | Không vỡ nợ (không có khó khăn thanh toán nghiêm trọng) |
| `1` | 24,825 | 8.0729% | Vỡ nợ (khách hàng có khó khăn thanh toán >= X ngày) |

- **Kiểu dữ liệu TARGET:** `int64` (nhị phân tuyệt đối {0, 1}).
- **TARGET null:** 0 (100% có nhãn).
- **Bảo toàn TARGET theo ID:** khớp 100% với `application_train.csv` thô (0 sai lệch).
- **Tỷ lệ mất cân bằng:** khoảng 11.39 : 1 (bắt buộc dùng cross-validation phân tầng).

## 5. Thành phần schema và nhóm đặc trưng
| Nhóm đặc trưng | Số cột | Nguồn gốc / Vai trò | Mô tả |
| :--- | :---: | :--- | :--- |
| `identifier` | 1 | `SK_ID_CURR` | Khóa chính |
| `target` | 1 | `TARGET` | Nhãn thực tế cần dự đoán |
| `application_raw` | 120 | `application_train` | Thông tin nhân khẩu, tài chính và điểm ngoài đã làm sạch |
| `application_cleaning` | 1 | `DAYS_EMPLOYED_ANOM` | Cờ nhị phân cho bất thường DAYS_EMPLOYED == 365243 |
| `application_derived` | 6 | Đặc trưng DE-03 | Tỷ lệ tài chính, tuổi và thâm niên làm việc |
| `bureau` | 20 | `bureau`, `bureau_balance` | Tổng hợp lịch sử bureau và tình trạng trễ hạn |
| `previous_application` | 15 | `previous_application` | Lịch sử hồ sơ Home Credit và số quyết định trước đây |
| `installments` | 10 | `installments_payments` | Thời hạn trả, thiếu hụt và tỷ lệ thanh toán |
| `pos_cash` | 11 | `POS_CASH_balance` | Lịch sử hợp đồng POS/cash, DPD và số tháng trễ |
| `credit_card` | 18 | `credit_card_balance` | Mức sử dụng, hạn mức, dư nợ và quá hạn thẻ |
| **TỔNG** | **203** | | **201 đặc trưng dự báo + 1 ID + 1 nhãn** |

## 6. Mức bao phủ từ điển dữ liệu
- **Đường dẫn từ điển dữ liệu:** `data/processed/data_dictionary.csv`
- **Mức bao phủ:** 100.0% (203/203 cột được mô tả).
- **Độ đầy đủ metadata:** 0 ô trống hoặc NaN trong 22 cột hợp đồng.
- **Khớp thứ tự:** 100% cùng thứ tự với các cột dataset chuẩn.
- **Mã hóa và phân cách:** UTF-8 có BOM (`utf-8-sig`), phân cách bằng dấu phẩy, kết thúc dòng LF (`\n`).

## 7. Phân tích giá trị khuyết thiếu
- **Tổng số ô dữ liệu:** 62,424,733
- **Tổng số ô khuyết:** 14,515,910 (23.25%)
- **Cột có giá trị khuyết:** 130/203
- **Cột không có giá trị khuyết:** 73/203
- **Cột khuyết hoàn toàn:** 0

### Phân bố các khoảng khuyết thiếu
| Khoảng khuyết thiếu | Số cột | Tỷ lệ | Đặc điểm và ví dụ |
| :--- | :---: | :---: | :--- |
| `exactly 0%` | 73 | 35.96% | Cột đầy đủ: `SK_ID_CURR`, `TARGET`, 18 count được điền 0 và trường application sạch |
| `greater than 0% and less than 5%` | 12 | 5.91% | Khuyết thiếu nhỏ ở application (`AMT_ANNUITY`, `AMT_GOODS_PRICE`, tỷ lệ tài chính) |
| `greater than or equal to 5% and less than 20%` | 48 | 23.65% | Khuyết thiếu vừa (`EXT_SOURCE_3`, `DAYS_EMPLOYED` / `EMPLOYED_YEARS`, khoảng trống `BUREAU_`) |
| `greater than or equal to 20% and less than 50%` | 9 | 4.43% | Khuyết thiếu đáng kể (`OCCUPATION_TYPE`, đặc trưng tòa nhà) |
| `greater than or equal to 50% and less than 80%` | 61 | 30.05% | Khuyết thiếu cao (`EXT_SOURCE_1`, `COMMONAREA_AVG`, `CC_*`) |
| `greater than or equal to 80% and less than 100%` | 0 | 0.00% | Không có trong dataset chuẩn |
| `exactly 100%` | 0 | 0.00% | Không có trong dataset chuẩn |
| **TỔNG** | **203** | **100.00%** | **Các nhóm loại trừ lẫn nhau và bao phủ toàn bộ cột** |

### 15 đặc trưng có tỷ lệ khuyết cao nhất
| Tên cột | Nhóm đặc trưng | Số ô khuyết | Tỷ lệ khuyết | Bản chất khuyết thiếu |
| :--- | :--- | :---: | :---: | :--- |
| `CC_UTILIZATION_MEAN` | `credit_card` | 221,475 | 72.02% | Không có lịch sử / không sử dụng thẻ |
| `CC_UTILIZATION_MAX` | `credit_card` | 221,475 | 72.02% | Không có lịch sử / không sử dụng thẻ |
| `CC_DPD_DEF_MAX` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_BALANCE_MEAN` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_DPD_MEAN` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_MONTHS_BALANCE_MIN` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_DPD_DEF_MEAN` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_DPD_MAX` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_MONTHS_BALANCE_MAX` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_CREDIT_LIMIT_MAX` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_LATE_MONTH_RATE` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_PAYMENT_TOTAL_SUM` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_BALANCE_MAX` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_CREDIT_LIMIT_MEAN` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |
| `CC_PAYMENT_TOTAL_MEAN` | `credit_card` | 220,606 | 71.74% | Không có lịch sử / không sử dụng thẻ |

## 8. Chất lượng số
- **Giá trị vô cực:** 0 dương (`+inf`), 0 âm (`-inf`).
- **Vi phạm tỷ lệ bị chặn:** 0 (10/10 tỷ lệ nằm chặt trong `[0.0, 1.0]`).
- **Vi phạm count âm:** 0 (tất cả count đều `>= 0`).
- **Tỷ lệ không bị chặn:** Đã xác nhận các tỷ lệ như `CREDIT_TO_INCOME_RATIO`, `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_ANNUITY_RATIO`, `PREV_CREDIT_TO_APPLICATION_RATIO_MEAN`, `INSTAL_PAYMENT_RATIO_MEAN` và `CC_UTILIZATION_MEAN/MAX` có thể hợp lệ lớn hơn 1.0, không ép ngưỡng nhân tạo.

## 9. Chất lượng phân loại
- **Số cột categorical:** 17
- **Chuỗi trống bất thường:** 0 cột (tổng 0 ô).
- **Sentinel dạng chuỗi (`NULL`, `null`, `N/A`, `NA`, `-999`):** 0 cột.
- **Nhóm hiếm (< 0.1%):** xuất hiện ở 6 cột categorical; được giữ lại cho mô hình cây.

## 10. Đặc trưng hằng số và gần hằng số
- **Đặc trưng toàn null (0 giá trị khác null):** 0.
- **Đặc trưng hằng số tuyệt đối (1 giá trị duy nhất khác null):** 0.
- **Đặc trưng gần hằng số (giá trị chiếm ưu thế >= 99.5%):** 16.
- **Ghi chú DAYS_EMPLOYED_ANOM:** `DAYS_EMPLOYED_ANOM` có giá trị chiếm ưu thế khoảng 81.99% (0 khi không có sentinel, 1 khi phát hiện 365243), nên không đạt ngưỡng gần hằng số 99.5%. Cờ này được giữ như một chỉ báo dữ liệu/bất thường có ý nghĩa.

| Tên cột | Giá trị chiếm ưu thế | Tỷ lệ chiếm ưu thế | Khuyến nghị |
| :--- | :---: | :---: | :--- |
| `FLAG_MOBIL` | `1` | 99.9997% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_CONT_MOBILE` | `1` | 99.8133% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_2` | `0` | 99.9958% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_4` | `0` | 99.9919% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_7` | `0` | 99.9808% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_9` | `0` | 99.6104% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_10` | `0` | 99.9977% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_11` | `0` | 99.6088% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_12` | `0` | 99.9993% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_13` | `0` | 99.6475% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_14` | `0` | 99.7064% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_15` | `0` | 99.8790% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_17` | `0` | 99.9733% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_19` | `0` | 99.9405% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_20` | `0` | 99.9493% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |
| `FLAG_DOCUMENT_21` | `0` | 99.9665% | Giữ lại để TV1 phân tích độ biến thiên bằng mô hình cây |

## 11. Mức bao phủ theo nguồn lịch sử
| Bảng nguồn | Tiền tố | Số dòng aggregate | Khách hàng khớp | Khách hàng không khớp | Tỷ lệ bao phủ | Khách hàng chỉ có ở aggregate |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `bureau` | `BUREAU_` | 305,811 | 263,491 | 44,020 | 85.69% | 42,320 |
| `previous_application` | `PREV_` | 338,857 | 291,057 | 16,454 | 94.65% | 47,800 |
| `installments_payments` | `INSTAL_` | 339,587 | 291,643 | 15,868 | 94.84% | 47,944 |
| `pos_cash_balance` | `POS_` | 337,252 | 289,444 | 18,067 | 94.12% | 47,808 |
| `credit_card_balance` | `CC_` | 103,558 | 86,905 | 220,606 | 28.26% | 16,653 |

## 12. Toàn vẹn phép nối
- **Kiểm soát cardinality:** cả 5 phép nối đều 1-1 với `validate='one_to_one'`.
- **Bảo toàn dòng:** chính xác 307,511 dòng trước và sau mỗi phép nối (0 dòng bị mất, 0 dòng bị nhân).
- **Ngăn xung đột đặc trưng:** phát hiện 0 cột hậu tố nối (`_x`, `_y`).
- **Chính sách lịch sử thiếu:** đúng 18 feature count được phê duyệt được điền số nguyên 0 cho khách hàng không khớp; tỷ lệ, số tiền và thống kê giữ `NaN` thật.

## 13. Rà soát leakage và thời điểm dữ liệu
- **Rò rỉ từ TARGET:** `TARGET` nằm cố định ở vị trí 1 và không bao giờ là feature. 0 aggregate feature chứa thông tin target.
- **Rò rỉ từ định danh:** `SK_ID_CURR` được ghi nhận là identifier và loại khỏi toàn bộ feature model.
- **Nhiễm tập test:** 48,744 dòng `application_test.csv` bị loại hoàn toàn khỏi dataset train chuẩn.
- **Tính hợp lệ theo thời điểm:** mọi sự kiện lịch sử xảy ra trước ngày nộp đơn (`DAYS <= 0` đã kiểm tra ở DE-04).
- **Phân cấp bureau hai tầng:** `bureau_balance` được aggregate về `SK_ID_BUREAU` trước khi nối `bureau`, tránh phình dữ liệu ở cấp khách hàng.
- **Gom khoản trả góp:** 653,483 dòng trả từng phần được gom theo grain installment, bảo toàn số tiền nghĩa vụ thật.
- **Độc lập tiền xử lý:** không fit imputer, scaler, encoder hoặc resampler trên dataset chuẩn. Mọi biến đổi phải fit riêng trên fold huấn luyện của TV1.

## 14. Ma trận tuân thủ hợp đồng
| Yêu cầu hợp đồng | Đặc tả | Trạng thái đo được | Tuân thủ |
| :--- | :--- | :--- | :---: |
| **Khóa chính** | `SK_ID_CURR` không null, duy nhất | 307,511 duy nhất, 0 null | **ĐẠT** |
| **Nhãn TARGET** | Nhị phân `TARGET` trong {0, 1} | 282,686 số 0, 24,825 số 1 | **ĐẠT** |
| **Cột bắt buộc** | Có 14 cột tối thiểu | Đã xác minh đủ 14 | **ĐẠT** |
| **Đặc trưng nhân khẩu** | `AGE_YEARS`, `AGE_GROUP`, `EMPLOYED_YEARS` | Đủ cả 3 và đã xác minh | **ĐẠT** |
| **Cờ sentinel làm sạch** | `DAYS_EMPLOYED_ANOM` | Có (1 nếu 365243, ngược lại 0) | **ĐẠT** |
| **Đặc trưng aggregate** | 74 feature DE-04 từ 5 nguồn | Có chính xác 74 | **ĐẠT** |
| **Chính sách lịch sử thiếu** | 18 count được điền 0 | Đã xác minh 1,077,105 ô | **ĐẠT** |
| **Không có infinity** | 0 ô `+inf` / `-inf` | Đã xác minh 0 ô | **ĐẠT** |
| **Tỷ lệ bị chặn** | 10 tỷ lệ trong `[0.0, 1.0]` | Đã xác minh 0 vi phạm | **ĐẠT** |
| **Sắp xếp xác định** | Dòng tăng dần theo `SK_ID_CURR` | Đã xác minh đơn điệu tăng | **ĐẠT** |
| **Từ điển dữ liệu** | 203 dòng, 22 cột, metadata đầy đủ | Bao phủ 100% | **ĐẠT** |

## 15. Cảnh báo và cách xử lý ở hạ nguồn
1. **Mức bao phủ aggregate lịch sử dưới 100% ở cả 5 nguồn, phù hợp với đặc tính nghiệp vụ tín dụng.**
2. **43,041 record `SK_ID_BUREAU` orphan trong `bureau_balance` đã bị loại khỏi aggregate khách hàng ở DE-04.**
3. **653,483 record trả góp từng phần trong `installments_payments` đã được gom ở DE-04 mà không nhân bản.**
4. **Khách hàng không khớp vẫn giữ giá trị khuyết thật (`NaN`) ở tỷ lệ, số tiền và thống kê lịch sử.**
5. **16 feature gần hằng số (giá trị chiếm ưu thế >= 99.5%) vẫn được giữ trong dataset.**

## 16. Ghi chú bàn giao mô hình cho TV1
- **Tệp cần đọc:** đọc trực tiếp `data/processed/cleaned_dataset.parquet` bằng `pd.read_parquet()`.
- **Loại định danh:** phải loại `SK_ID_CURR` khỏi ma trận feature dự báo `X`.
- **Tách target:** tách `TARGET` thành vector đích `y`; không truyền `TARGET` vào pipeline biến đổi feature.
- **Cách cross-validation:** phải dùng `StratifiedKFold` (ví dụ 5 fold) theo `TARGET` để giữ tỷ lệ vỡ nợ khoảng 8.07% ở mọi fold.
- **Tiền xử lý chống rò rỉ:** fit mọi encoder, imputer và scaler **chỉ trên fold huấn luyện** của từng split, sau đó mới transform fold validation/test.
- **Xử lý feature lịch sử thiếu:** mô hình GBDT (LightGBM, XGBoost, CatBoost) có thể xử lý `NaN` tự nhiên. Không điền đồng loạt giá trị khuyết lịch sử bằng hằng số tùy ý trước khi split.

## 17. Ghi chú bàn giao dashboard cho TV3
- **Quần thể phân tích:** `cleaned_dataset.parquet` đại diện cho toàn bộ 307,511 hồ sơ lịch sử đã làm sạch.
- **Ngữ nghĩa trường:** tra cứu `data/processed/data_dictionary.csv` để lấy mô tả, đơn vị và nhóm giá trị cho nhãn giao diện và tooltip biểu đồ.
- **Các trường điểm dự báo:** với output model, điểm rủi ro và ngưỡng decile, chờ tạo tác `data/processed/scored_dataset.parquet` từ TV1.

## 18. Lệnh tái tạo
```powershell
# 1. Tái tạo và xuất bản dataset chuẩn (nếu cần):
& .\.venv\Scripts\python.exe -m src.data.build_pipeline

# 2. Chạy lại kiểm định chất lượng và tạo từ điển dữ liệu/báo cáo:
& .\.venv\Scripts\python.exe -m src.data.quality_report

# 3. Chạy bộ test quality report:
& .\.venv\Scripts\python.exe -m pytest tests\data\test_quality_report.py -v
```

## 19. Kết quả cổng chất lượng cuối cùng
```text
=================================================================
KẾT QUẢ CỔNG CHẤT LƯỢNG TV2-DE-06: ĐẠT CÓ CẢNH BÁO
-----------------------------------------------------------------
DATASET CHUẨN:     data/processed/cleaned_dataset.parquet (307,511 dòng, 203 cột)
TỪ ĐIỂN DỮ LIỆU:   data/processed/data_dictionary.csv (203 dòng, 22 cột)
BÁO CÁO CHẤT LƯỢNG: reports/data_quality_report.md (19 phần)
TRẠNG THÁI:        ĐÃ XÁC MINH VÀ SẴN SÀNG BÀN GIAO TV1 / TV3
=================================================================
```
