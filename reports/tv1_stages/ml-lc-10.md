# ML-LC-10 — PD → Score / Risk Tier

## 1. Mục tiêu

PD là xác suất vỡ nợ do model ước lượng. Stage này đổi PD thành hai thang điểm dễ đọc và một nhóm rủi ro, không huấn luyện lại model.

## 2. PD là gì?

Ví dụ PD = 0.25 nghĩa là model ước lượng xác suất vỡ nợ là 25%; đây không phải lời khẳng định chắc chắn về kết quả của một khoản vay.

## 3. Risk Score

`risk_score = 100 × predicted_pd`. Điểm cao hơn tương ứng PD model dự đoán cao hơn.

## 4. Project Credit Score

`credit_score = round(1000 × (1 − predicted_pd))` (làm tròn half-to-even). Điểm cao hơn tương ứng PD model dự đoán thấp hơn. Đây là điểm do project/model tạo ra, **không phải FICO và không phải điểm bureau chính thức**.

## 5. Risk Tier

Với threshold khóa T = `0.22009515762329102`: Tier A: PD < 0.110047578812; Tier B: 0.110047578812 ≤ PD < 0.220095157623; Tier C: 0.220095157623 ≤ PD < 0.440190315247; Tier D: PD ≥ 0.440190315247.
Các tier mô tả mức PD do model dự đoán; chúng không phải grade pháp quy, Lending Club grade, FICO band hoặc bảo đảm tần suất vỡ nợ.

## 6. Phân bố theo tier

`Mean PD` là trung bình xác suất model dự đoán. `Observed default rate` là tỷ lệ target=1 quan sát trong population đánh giá; hai số đo này khác nhau.

| Tier | Loans | Share | Mean PD | Observed default rate |
|---|---:|---:|---:|---:|
| Tier A — Low | 66,275 | 24.63% | 0.0773 | 0.0620 |
| Tier B — Moderate | 109,146 | 40.56% | 0.1603 | 0.1578 |
| Tier C — High | 80,423 | 29.89% | 0.3015 | 0.3116 |
| Tier D — Very High | 13,226 | 4.92% | 0.5179 | 0.5541 |

## 7. Dashboard outputs

- **V02 — PD Distribution: READY**, dùng `predicted_pd`.
- **V03 — Risk Tier Distribution: READY**, dùng `risk_tier` hoặc file summary.
- **V04 — FICO vs Risk / PD: READY**, dùng `fico_avg`, `predicted_pd` và `risk_tier`.

Population là 269.070 frozen-test predictions đã được ML-LC-08 đánh giá; đây là artifact cho reporting/demo, chưa phải scoring toàn bộ portfolio. Không có visual Power BI nào được dựng ở stage này.

## 8. Giới hạn

Score và tier chỉ mô tả output của model; không chứng minh quan hệ nhân quả, không phải score pháp quy và không đảm bảo outcome cá nhân. Observed default rate chỉ dùng để mô tả population, không tham gia tạo score/tier.

## 9. Bước tiếp theo

ML-LC-11 — Expected Loss; cần LGD/EAD assumption được duyệt trước khi tính.
