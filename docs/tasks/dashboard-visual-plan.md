# Kế hoạch Dashboard & Storytelling — Bản gọn

## 1. Kiến trúc cuối

- **Power BI:** 4 trang.
- **External companion:** Plotly Dash — Dự đoán cá nhân.
- **TV1:** V02–V06.
- **TV2:** V07–V09, Data Engineering.
- **TV3:** V01, V10–V12, Master Power BI Integrator.
- Không thay model, target, threshold, risk-tier policy hoặc population bằng DAX.

| Page | Big Idea | Visuals | Main takeaway |
|---|---|---|---|
| **01 — Tổng quan danh mục** | Sàng lọc hồ sơ rất chặt; rủi ro evaluated loans phân bố theo địa lý. | KPI → V08 → V01 | Accepted chỉ khoảng 7.56% tổng applications; rejected không có default outcome. |
| **02 — Xu hướng & Mục đích vay** | Hoạt động danh mục thay đổi theo thời gian và tập trung vào một số nhu cầu vay chính. | V07A → V07B → V09 | Giữ riêng denominator của volume, resolved default rate và purpose. |
| **03 — Hồ sơ người vay** | Đặc điểm người vay đi cùng các mức rủi ro tín dụng khác nhau. | V04 → V11 → V10 → V12 | FICO cao hơn đi cùng PD thấp hơn; các insight khác chỉ chốt sau final review. |
| **04 — Rủi ro & Expected Loss** | **RỦI RO TẬP TRUNG Ở HẠNG B–C** | KPI → V02 → V03 → V05 → V06 | B–C >70% cohort; Tier C đóng góp EL lớn nhất tại LGD 45%. |

---

## 2. Page 01 — Tổng quan danh mục

**Subtitle:** Từ quy mô hồ sơ → accepted/rejected → rủi ro theo bang.

### V08 — Hồ sơ được chấp nhận chiếm khoảng 7.56% applications
- **Chart:** 100% stacked bar — Accepted / Rejected.
- **Population:** 29,909,442 applications.
- **Numbers:** Accepted 2,260,701 (≈7.56%); Rejected 27,648,741 (≈92.44%).
- **Tooltip:** outcome, count, share.
- **Insight:** accepted records chỉ là phần nhỏ của hai source populations đang được so sánh.
- **Limit:** rejected không có default target; không diễn giải như funnel tuần tự.

### V01 — Rủi ro tín dụng phân bố theo bang
- **Chart:** Filled map.
- **Population:** 269,070 evaluated loans có state hợp lệ.
- **Measures:** evaluated count, mean PD, observed default rate + N.
- **Insight:** **PENDING FINAL MAP REVIEW** — chỉ chốt bang nổi bật sau khi kiểm tra coverage và sample size.
- **Limit:** không geocode masked ZIP; không diễn giải nhân quả.

---

## 3. Page 02 — Xu hướng & Mục đích vay

**Subtitle:** Quy mô phát hành, rủi ro quan sát và cơ cấu mục đích vay.

### V07 — Volume và observed risk theo thời gian
- **Chart:** 2 line views phối hợp: V07A accepted volume; V07B observed default rate trên resolved accepted cohort.
- **Measures:** accepted count; target=1 / resolved N.
- **Insight:** **PENDING FINAL DATA REVIEW** — xác nhận peak period và risk trend trước khi viết headline.
- **Limit:** V07A và V07B khác denominator; origination month không phải ngày default.

### V09 — Cơ cấu mục đích vay
- **Chart:** ordered horizontal bar.
- **Population:** accepted records có canonical purpose.
- **Measures:** accepted count/share.
- **Insight:** **PENDING FINAL DATA REVIEW** — chỉ chốt dominant purpose sau khi review aggregate.
- **Limit:** accepted purpose không tương đương rejected loan_title.

---

## 4. Page 03 — Hồ sơ người vay

**Subtitle:** FICO, DTI, thu nhập, quy mô khoản vay và tình trạng nhà ở.

### V04 — FICO cao hơn đi cùng phân bố PD thấp hơn
- **Chart:** Box & Whisker.
- **Population:** 269,070 evaluated loans.
- **Bands có dữ liệu:** 650–699 = 164,277; 700–749 = 83,552; 750+ = 21,241.
- **Median PD:** 0.208485 → 0.127668 → 0.067767.
- **Insight:** FICO cao hơn đi cùng predicted PD thấp hơn.
- **Limit:** association, không phải causation; không tạo box cho nhóm không có dữ liệu.

### V11 — DTI × FICO
- **Chart:** Heatmap.
- **Measure chính:** mean PD; tooltip có cell N và observed default rate nếu đã validate.
- **Insight:** **PENDING FINAL DATA REVIEW**.
- **Rule:** cell N < 100 cần flag/suppress.
- **Limit:** PD và observed default rate là hai quantity khác nhau.

### V10 — Loan amount × income
- **Chart:** Binned heatmap.
- **Measure chính:** evaluated count/cell; tooltip mean PD + N.
- **Insight:** **PENDING FINAL DATA REVIEW**.
- **Limit:** chỉ mô tả concentration/association.

### V12 — Home ownership × Risk tier
- **Chart:** 100% stacked bar.
- **Measures:** segment N, tier count/share; mean PD nếu validate.
- **Insight:** **PENDING FINAL DATA REVIEW**.
- **Note:** ANY/OTHER/NONE rất ít; nếu giữ cần gộp có nhãn hoặc cảnh báo low-N.
- **Limit:** không causal; không gộp category nếu chưa có rule rõ.

---

## 5. Page 04 — Rủi ro & Expected Loss

### Header
**Big Idea:** **RỦI RO TẬP TRUNG Ở HẠNG B–C**

**Subtitle:** PD chủ yếu ở vùng thấp–trung bình; kỳ hạn vay là yếu tố mô hình nổi bật nhất.

### KPI
- **Khoản vay đánh giá:** 269K.
- **PD trung bình danh mục:** 19.96%.
- **Tỷ lệ default thực tế:** 19.97%.
- **Tổng tổn thất kỳ vọng:** 372.58M tại LGD 45%.

### V02 — PD đạt đỉnh ở khoảng 10–15% và giảm dần khi rủi ro tăng
- **Chart:** Histogram, bin rộng 5 điểm % PD.
- **Measures:** PD Bin Count, PD Bin Share.
- **Insight:** phần lớn evaluated loans không nằm ở extreme-high PD; vẫn có high-risk tail.
- **Limit:** PD là model prediction, không phải observed default.

### V03 — Hơn 70% danh mục nằm ở hạng B–C
- **Chart:** 1 thanh ngang 100% stacked, A → B → C → D.
- **Shares:** A 24.63%; B 40.56%; C 29.89%; D 4.92%.
- **Counts:** A 66,275; B 109,146; C 80,423; D 13,226.
- **Insight:** risk tập trung ở các tier giữa, không chủ yếu ở tier D.
- **Tooltip:** tier, count, share, mean PD, observed default rate.
- **Limit:** frozen-test cohort; không đổi tier policy.

### V05 — Kỳ hạn vay là yếu tố nổi bật nhất trong dự đoán rủi ro
- **Chart:** Lollipop Top 10 mean |SHAP|; highlight Top 3.
- **Top 3:** term_months 0.315463; loan_to_income_ratio 0.159380; fico_range_low 0.156027.
- **Insight:** kỳ hạn vay có mean |SHAP| gần gấp đôi hai feature kế tiếp.
- **Interaction:** độc lập với Risk Tier/FICO slicers.
- **Limit:** SHAP ở raw margin/log-odds; không phải %PD hay causation.

### V06 — Hạng C tạo gần 48% tổng Expected Loss
- **Chart:** **Pie chart** theo Risk Tier.
- **EL share:** A 8.21%; B 28.21%; C 47.89%; D 15.69%.
- **Total EL:** 372,579,342.19 source units tại LGD 45%; Tier C ≈178M.
- **Insight:** C tạo EL lớn nhất dù D có mean PD cao nhất, vì impact còn phụ thuộc quy mô cohort và exposure.
- **Tooltip:** tier, total EL, EL contribution %, EAD proxy, mean PD, loan count.
- **Limit:** LGD 45% là assumption; loan_amnt là EAD proxy; EL không phải realized loss.

### Interactions Page 04
- Risk Tier và FICO Band lọc KPI, V02, V03, V06.
- Chọn tier trong V03 có thể cross-filter V02/KPI/V06.
- V05 không bị page slicers tính lại.
- LGD 45% là scenario cố định, không thay PD.

---

## 6. External Companion — Dự đoán cá nhân

- **Platform:** Plotly Dash, mở ngoài Power BI.
- **Vai trò:** nhập hồ sơ demo → model prediction → local explanation → Expected Loss scenario.
- **Model:** XGBoost / Logistic Regression demo.
- **Power BI:** chỉ mở URL; không tự khởi động Dash server.
- **Limit:** kết quả demo, không phải quyết định cấp tín dụng và không chứng minh nhân quả.

---

## 7. Data & Model Guardrails

1. **Accepted vs Rejected:** khác schema/date/purpose semantics; rejected không có default rate.
2. **Observed default trend:** denominator chỉ gồm target-resolved accepted records.
3. **Evaluated risk V02–V06:** dùng 269,070 frozen-test cohort.
4. **SHAP V05:** validation sample riêng; không join/filter lại bằng frozen-test slicers.
5. **Full-refit inference:** chỉ dùng cho External Dash, không dùng báo unbiased test metrics.
6. **FactEvaluatedLoan:** 1 row / loan_id, key unique và non-null.
7. **Bands / tiers:** dùng canonical engineering/model policy; không tự re-bin trong Power BI.
8. **Measure semantics:** giữ riêng PD, observed default rate, count/share và EL.
9. **V11:** cell N < 100 cần flag/suppress.
10. **Expected Loss:** `PD × LGD × EAD proxy`; baseline LGD 45%, `loan_amnt` là EAD proxy, đơn vị nguồn.

---

## 8. Story flow cuối

**Page 1:** Quy mô → Accepted/Rejected → Geography

**Page 2:** Volume trend → Resolved risk trend → Purpose

**Page 3:** FICO → DTI/FICO → Amount/Income → Borrower segment

**Page 4:** PD → Risk Tier → SHAP → Expected Loss

**External Dash:** Hồ sơ cá nhân → Prediction → Explanation → EL scenario
