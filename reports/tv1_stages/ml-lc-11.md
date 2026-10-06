# ML-LC-11 — Expected Loss

## 1. Expected Loss là gì?

`EL = PD × LGD × EAD`: PD là xác suất vỡ nợ model dự đoán, LGD là tỷ lệ tổn thất giả định khi vỡ nợ, EAD là quy mô exposure đưa vào kịch bản.

## 2. Model output và scenario assumptions

- **Model output:** `predicted_pd` đã khóa từ XGBoost; không dự đoán lại.
- **EAD proxy:** `loan_amnt`, số tiền gốc tại thời điểm cấp khoản vay; không phải outstanding balance thực tế.
- **LGD:** baseline 45%, sensitivity 30% / 45% / 60%. Đây là assumption minh họa cho project, không phải estimate thực nghiệm hay quy định.
- Dictionary không xác nhận currency unit; báo cáo giữ nguyên loan_amnt source units, không tự gắn USD.

## 3. Baseline portfolio scenario

- Số khoản vay: 269,070
- Tổng EAD proxy: 3,878,248,925.00 loan_amnt source units
- Tổng Expected Loss: 372,579,342.19 loan_amnt source units
- EL trung bình/khoản: 1,384.69
- Portfolio EL rate (total EL / total EAD proxy): 9.6069%
- EAD-weighted mean PD: 21.3487%

## 4. Expected Loss theo risk tier

| Tier | Loans | Loan share | Exposure share | EL share | Mean PD | Mean EL | Observed default rate* |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tier A — Low | 66,275 | 24.63% | 22.80% | 8.21% | 7.73% | 461.55 | 6.20% |
| Tier B — Moderate | 109,146 | 40.56% | 37.33% | 28.21% | 16.03% | 962.97 | 15.78% |
| Tier C — High | 80,423 | 29.89% | 33.42% | 47.89% | 30.15% | 2,218.49 | 31.16% |
| Tier D — Very High | 13,226 | 4.92% | 6.46% | 15.69% | 51.79% | 4,420.67 | 55.41% |

*Observed default rate dùng `target` để mô tả outcome hồi cứu; target không tham gia công thức EL.*

Expected Loss cao có thể đến từ PD cao, exposure cao hoặc cả hai. Tier rủi ro cao nhất không nhất thiết đóng góp phần EL lớn nhất; so sánh cả PD, exposure share và EL share.

## 5. Sensitivity

| LGD scenario | Total Expected Loss |
|---:|---:|
| 30% | 248,386,228.13 loan_amnt source units |
| 45% | 372,579,342.19 loan_amnt source units |
| 60% | 496,772,456.26 loan_amnt source units |

PD giữ nguyên; chỉ thay LGD assumption. Đây không phải model tuning.

## 6. V06 readiness

Nguồn data-ready: `ml_lc_11_expected_loss.parquet` và `ml_lc_11_risk_tier_el_summary.csv`. Visual trả lời tier/segment nào đóng góp EL nhiều nhất và liệu tỷ trọng đó đi cùng PD cao, exposure lớn hay cả hai. Power BI chưa được dựng/tích hợp.

## 7. Giới hạn

EL là kịch bản kỳ vọng, không phải realized loss hay profit; không mang hàm ý nhân quả, không phải regulatory capital model. LGD là assumption, loan_amnt là EAD proxy, currency unit không được nêu trong data dictionary; chưa mô hình hóa recovery, thời gian hoặc outstanding balance.

## 8. Next stage

ML-LC-12 = NOT STARTED. Không thực hiện full-data refit trong stage này.
