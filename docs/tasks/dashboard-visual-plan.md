# Kế hoạch Dashboard & Storytelling — Bản gọn

## 1. Kiến trúc cuối

- **Power BI:** 4 trang.
- **External companion:** Plotly Dash — Dự đoán cá nhân.
- **TV1:** V02–V06.
- **TV2:** V07–V09, Data Engineering.
- **TV3:** V01, V10–V13, Master Power BI Integrator.
- Không thay model, target, threshold, risk-tier policy hoặc population bằng DAX.

| Page | Big Idea | Visuals | Main takeaway |
|---|---|---|---|
| **01 — Tổng quan danh mục** | Sàng lọc hồ sơ rất chặt; rủi ro evaluated loans phân bố theo địa lý. | KPI → V08 → V01 | Accepted chỉ khoảng 7.56% tổng applications; rejected không có default outcome. |
| **02 — Xu hướng & Mục đích vay** | Hoạt động danh mục thay đổi theo thời gian và tập trung vào một số nhu cầu vay chính. | V07A → V07B → V09 | Giữ riêng denominator của volume, resolved default rate và purpose. |
| **03 — Hồ sơ vay** | Phân khúc hồ sơ và các đặc điểm tài chính đi cùng rủi ro ra sao? | V11 → V12 → V04 → V13 | V13 cho thấy PD trung bình nhìn chung cao hơn ở các nhóm tỷ lệ khoản vay/thu nhập lớn; chỉ là liên hệ mô tả. |
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

## 4. Page 03 — Hồ sơ vay

**Subtitle:** Phân khúc FICO/DTI, cơ cấu nhà ở, phân bố PD và khoản vay so với thu nhập.

Trang giữ đúng **bốn visual phân tích** trong lưới 2×2; KPI đầu trang và slicer điều hướng/lọc hiện có không tính là visual phân tích:

| Ô | Visual | Loại | Population mặc định |
|---|---|---|---|
| Trên trái | V11 — FICO × DTI | Heatmap | `cleaned_dataset`, 1.345.350 khoản vay có kết quả |
| Trên phải | V12 — Cơ cấu tình trạng nhà ở | Donut | `cleaned_dataset`, 1.345.350 khoản vay có kết quả |
| Dưới trái | V04 — PD theo nhóm FICO | Box & Whisker | `fact_evaluated_loan`, 269.070 khoản vay evaluated |
| Dưới phải | V13 — Loan-to-Income Ratio × PD dự đoán | Line chart có marker theo nhóm số học | `fact_evaluated_loan`, 268.991 evaluated loans có tỷ lệ hợp lệ |

### V11 — DTI × FICO
- **Business question:** nhóm FICO/DTI nào có default quan sát và PD trung bình khác nhau?
- **Why this visual:** heatmap làm nổi cấu trúc hai chiều; `N` cần được đọc cùng mỗi ô.
- **Population:** `cleaned_dataset`, 1.345.350 resolved loans khi không lọc năm/bang.
- **Insight:** giữ insight theo dữ liệu/filters hiện tại; ô có `N < 100` phải được cảnh báo.
- **Story connection:** bắt đầu bằng phân khúc hồ sơ; V12 mô tả cơ cấu người vay kế tiếp.
- **Limit:** PD và tỷ lệ default quan sát là hai đại lượng riêng; association không chứng minh causation.

### V12 — Cơ cấu tình trạng nhà ở
- **Chart:** Donut.
- **Population:** `cleaned_dataset`, cùng resolved portfolio với V11.
- **Business question:** danh mục có cơ cấu tình trạng nhà ở thế nào?
- **Why this visual:** các lát thể hiện thành phần của một tổng; không diễn giải lát nhỏ bằng tỷ lệ rủi ro.
- **Insight:** title hiện tại cho biết trạng thái mortgage chiếm gần một nửa; vẫn phụ thuộc bộ lọc năm/bang.
- **Story connection:** thêm borrower context sau V11, trước khi chuyển sang kết quả model evaluated ở V04.
- **Limit:** mô tả thành phần, không phải quan hệ nhân quả với default.

### V04 — FICO cao hơn đi cùng phân bố PD thấp hơn
- **Chart:** giữ nguyên custom Box & Whisker.
- **Population mặc định:** 269.070 khoản vay trong `fact_evaluated_loan`; slicer năm có thể thu hẹp cohort qua quan hệ loan ID.
- **Bindings giữ nguyên:** `fico_band` làm Groups, `predicted_pd` làm Values, `loan_id` làm Samples; không thay kết quả/thuật toán quartile hoặc tooltip hiện hữu.
- **Title:** `FICO cao hơn đi cùng phân bố PD thấp hơn`.
- **Business question:** phân bố PD dự đoán thay đổi thế nào giữa các nhóm FICO?
- **Why this visual:** box plot thể hiện median, quartiles và whiskers, thay vì chỉ một trung bình.
- **Insight đã đối chiếu:** median PD ở ba nhóm có dữ liệu 650–699, 700–749, 750+ lần lượt là 0.208485, 0.127668, 0.067767.
- **Limit:** quan hệ mô tả, không causal. Nếu custom visual tự lấy mẫu nội bộ, cần kiểm tra giới hạn lấy mẫu/tooltip trong Desktop trước khi báo cáo số quartile.

### V13 — Loan-to-Income Ratio × PD dự đoán
- **Business question:** khi quy mô khoản vay so với thu nhập năm cao hơn, PD do mô hình dự đoán thay đổi thế nào?
- **Why this visual:** line chart có marker trên trục X số học giữ được khoảng cách giữa các vị trí đại diện số; nhóm theo bins giảm overplotting so với 269 nghìn điểm khoản vay.
- **Title:** `Tỷ lệ vay/thu nhập cao hơn đi cùng PD dự đoán cao hơn`.
- **Subtitle:** `PD trung bình theo nhóm ratio · tập evaluated; 79 dòng thiếu ratio không hiển thị`.
- **Population:** `fact_evaluated_loan` (269.070 evaluated rows), cùng cohort chứa `predicted_pd` và `target`; 268.991 dòng có ratio hợp lệ. 79 dòng thiếu ratio vì `annual_inc <= 0`; không loại âm thầm mà được báo rõ.
- **Bindings:** X = `Loan-to-Income Bin X`, số đại diện nhóm; Y = `[Mean PD]` duy nhất. Tooltip = `[Loan-to-Income Bin Tooltip]`, `[Evaluated Loan Count]`, `[Observed Default Rate]`, `[Grouped Observed − Predicted Difference]`, `[Loan-to-Income Sample Flag]`. Measure tooltip trả label từ cùng filter context vì native line chart giới hạn role Tooltips ở Measure; mọi giá trị vẫn lấy từ cùng evaluated cohort.
- **Bin rule:** `[0,0.1)`, `[0.1,0.2)`, `[0.2,0.3)`, `[0.3,0.4)`, `[0.4,0.5)`, `[0.5,0.6)`, `[0.6,0.8)`, `[0.8,1.0)`, `[1.0,+∞)`. Chọn bins rộng 0.1 ở vùng tập trung, mở rộng ở đuôi lệch phải; tách nhóm từ 1.0 để không gom dải rất rộng/outliers thành một điểm. 9 nhóm tie-out N=268.991, N nhỏ nhất=222 (≥100). X đặt tại trung điểm của khoảng hữu hạn, nhóm mở `[1.0,+∞)` dùng median evaluated-cohort 1.3333; sort tăng dần theo số `Loan-to-Income Bin X`, không theo nhãn.
- **Data quality / observation:** ratio có 79 missing (0,029%), không có giá trị âm hay vô hạn; median=0,20; 99th percentile=0,50; maximum=8.000 là ngoại lệ do annual income=$1. Trong bins trên, Mean PD từ 13,68% ở `[0,0.1)` lên 32,56% ở nhóm `≥1.0`; các trung bình PD tăng theo thứ tự chín nhóm, nhưng observed default rate không đơn điệu (30,50% ở `[0.4,0.5)`, 30,44% ở `[0.6,0.8)`, 31,53% ở `[0.8,1.0)`, 33,61% ở đuôi). Tiêu đề mô tả xu hướng PD nhóm, không biến observed outcomes thành quy luật.
- **Insight and limitation:** các nhóm có loan-to-income cao hơn nhìn chung cũng có Mean PD cao hơn trong evaluated cohort. Đây là association mô tả của dự đoán trên nhóm, không chứng minh tăng khoản vay hoặc giảm thu nhập gây ra rủi ro; không suy ra tác động cá nhân. Loan-to-Income không phải DTI.
- **Story connection:** V11 phân khúc FICO×DTI → V12 cơ cấu nhà ở → V04 phân bố PD theo FICO → V13 thêm góc nhìn khả năng vay so với thu nhập; cùng chuyển sang trang 04 về risk tier/SHAP/EL.

### V10 — giữ ngoài Page 03
- V10 binned heatmap Loan Amount × Annual Income được gỡ khỏi Page 03 vì trùng dạng heatmap với V11.
- Định nghĩa visual cũ được lưu trong backup `reports/figures/dashboard/_merge_backup/20261008-page03-v13/retired-page03-v10/`; mọi measure/cột semantic và source table liên quan vẫn giữ nguyên để dùng lại.

### Bộ lọc và population
- V11/V12/KPI dùng `cleaned_dataset` (1.345.350 resolved loans khi không lọc).
- V04 dùng `fact_evaluated_loan` (269.070 evaluated loans khi không lọc); V13 dùng cùng nguồn, 268.991 dòng ratio hợp lệ và tooltip báo 79 missing do mẫu số annual income không hợp lệ.
- Slicer năm dùng active `dim_date → cleaned_dataset.issue_d`; active quan hệ loan ID hai chiều nối evaluated fact với canonical context, nên slicer năm lọc đúng các evaluated loans tương ứng. Không trộn default outcomes từ full cleaned population vào V13.

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
7. **Bands / tiers:** risk tiers và feature bands model dùng policy canonical. V13 có report-only Loan-to-Income display bins để tổng hợp, không ghi vào nguồn Parquet hoặc dùng làm model feature.
8. **Measure semantics:** giữ riêng PD, observed default rate, count/share và EL.
9. **V11:** cell N < 100 cần flag/suppress.
10. **Expected Loss:** `PD × LGD × EAD proxy`; baseline LGD 45%, `loan_amnt` là EAD proxy, đơn vị nguồn.

---

## 8. Story flow cuối

**Page 1:** Quy mô → Accepted/Rejected → Geography

**Page 2:** Volume trend → Resolved risk trend → Purpose

**Page 3:** DTI/FICO segmentation → home-ownership mix → evaluated PD distribution by FICO → loan-to-income ratio and grouped predicted-risk trend

**Page 4:** PD → Risk Tier → SHAP → Expected Loss

**External Dash:** Hồ sơ cá nhân → Prediction → Explanation → EL scenario
