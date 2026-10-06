# Kế hoạch Dashboard, Storytelling và Visual — Lending Club

**Trạng thái:** Đây là kế hoạch hiện hành; Power BI chưa được build/tích hợp/review. V01–V12 là visual đã phân công, nhưng mọi chart type dưới đây đều **PROVISIONAL**. Chưa chốt chart trước khi đọc tài liệu lý thuyết visual của giảng viên.

## Mục tiêu và ownership

Dashboard là một câu chuyện phân tích nhiều trang, không phải 12 chart rời rạc.

- **TV1:** owner V02–V06; modeling, model-risk story, storytelling/report/defense coordination. V01 đã chuyển sang TV3.
- **TV2:** owner V07–V09; PRIMARY OWNER Data Engineering, technical EDA và data semantics.
- **TV3:** owner V01, V10–V12 và MASTER POWER BI INTEGRATOR; sở hữu data model, page layout, interactions, consistency và Master PBIX.
- Review không làm thay đổi ownership; TV3 tích hợp nhưng không trở thành tác giả chính của mọi visual.

## Kiến trúc dashboard hiện tại — provisional

### Trang 1 — Portfolio & Application Overview
**Mục đích:** Danh mục và luồng application Lending Club trông như thế nào?

- V01 Geographic Risk Map — TV3.
- V07 Volume / risk over time — TV2.
- V08 Accepted vs Rejected Funnel — TV2.
- V09 Loan Purpose Analysis — TV2.

Story questions: application/loan đến từ đâu? Funnel có quy mô nào? Accepted/rejected ra sao? Volume thay đổi theo thời gian thế nào? Vay cho mục đích gì? Risk pattern xuất hiện ở đâu/theo thời điểm nào? Rejected applications không có observed default outcome; không gán/bịa rejected-loan default rate.

### Trang 2 — Borrower Risk Profile
**Mục đích:** Đặc điểm borrower/application nào đi cùng các mức risk khác nhau?

- V04 FICO vs Risk / PD — TV1.
- V10 Loan Amount vs Annual Income — TV3.
- V11 DTI / FICO Risk Matrix — TV3.
- V12 Borrower Segment Analysis — TV3.

Phân tích là association/segmentation, không chứng minh causation. Nêu population, missingness và sparse groups.

### Trang 3 — Model Risk & Explainability
**Mục đích:** Model dự đoán mức rủi ro nào và vì sao?

- V02 PD Distribution — TV1.
- V03 Risk Tier Distribution — TV1.
- V05 Feature Importance / SHAP — TV1.

Story flow: phân bố PD → nhóm PD thành tiers dễ đọc → giải thích global pattern và local borrower examples. Phân biệt predicted PD với observed default rate; SHAP là model contribution, không phải causation hoặc trực tiếp là phần trăm điểm PD.

### Trang 4 — Business Risk & Expected Loss
**Mục đích:** Risk dự đoán có ý nghĩa gì khi tính đến exposure và quy mô portfolio?

- V06 Expected Loss / Risk Contribution — TV1.
- Có thể có KPI/supporting components nếu có nguồn hợp lệ: total EAD proxy, total scenario EL, EL rate, average PD, high-risk exposure, tier contribution.

Story point: Tier D có thể có mean PD cao nhất nhưng Tier C đóng góp tổng EL lớn nhất, vì EL phụ thuộc PD × LGD × EAD và phân bố số lượng/exposure. Hiển thị LGD/EAD assumptions; scenario EL không phải realized loss/full-portfolio result nếu population chỉ là evaluated test.

### Trang 5 — Individual Prediction / Decision Support
**Trang bắt buộc trong kế hoạch, dù không thuộc V01–V12.**

**Mục đích:** Nếu đánh giá một applicant, model trả về gì và người dùng đọc kết quả thế nào?

Provisional flow: nhập/chọn borrower → validate input → predicted PD → predicted class/recommendation theo threshold → risk score → project credit score → risk tier → key explanatory factors → optional EL scenario.

Đây là model demonstration/decision support, **không phải hệ thống phê duyệt khoản vay chính thức**. UI/technical method chưa được quyết định; đánh giá khi biết môi trường cuối. ML-LC-13 xác nhận model/contract readiness, không có nghĩa UI đã tồn tại.

## Danh mục V01–V12: câu hỏi và lựa chọn chart tạm thời

Business question, grain và correctness quan trọng hơn tên chart. Mọi chart type đều provisional cho tới theory review.

| ID / Owner | Business question | Data, grain và measure cần xác nhận | Current provisional chart và lý do tạm thời | Story / caveat |
|---|---|---|---|---|
| V01 / TV3 | Bang nào có volume/risk pattern đáng xem? | Loan/application grain; state code, country, count; rate/PD chỉ ở population có nhãn/score hợp lệ | Map là option để thể hiện địa lý; phải xác minh mapping và khả năng nhận diện map | Overview; association cấp bang, không causal; rejected không có default rate |
| V02 / TV1 | Predicted PD phân bố thế nào? | Một dòng mỗi scored loan; predicted_pd, model/population | Histogram option để xem distribution/tail, ít làm mất độ phân giải hơn tier | Mở Model Risk; evaluated test, không full portfolio |
| V03 / TV1 | Quy mô và observed outcome theo tier ra sao? | Loan/summary grain; tier, count/share, mean PD, observed rate | Ordered bar/column option để so nhóm có thứ tự | Sau V02; predicted PD khác observed default rate |
| V04 / TV1 | FICO liên hệ thế nào với PD/risk? | Loan grain; fico_avg, predicted_pd, tier, target nếu hợp lệ | Scatter/density option để xem quan hệ và outlier | Borrower Risk; association không causation |
| V05 / TV1 | Những feature nào đóng góp nhiều nhất vào dự đoán của model và contribution thể hiện ra sao ở ví dụ cá nhân? | ML-LC-09 global importance; local/SHAP sources tách biệt | Global bar + local explanation là phương án tạm | SHAP raw margin/log-odds; không phải điểm phần trăm PD hay causal explanation |
| V06 / TV1 | Tier/segment nào đóng góp scenario EL lớn, đi cùng PD hay exposure? | Loan/tier grain; EL/share, exposure share, mean PD, count, LGD | Sorted horizontal bar là option để xếp hạng category song song; không phải waterfall cộng dồn | Business impact; LGD assumption, loan_amnt proxy, population evaluated |
| V07 / TV2 | Volume và observed risk accepted loans thay đổi ra sao theo thời gian? | Accepted loan grain; issue date, count/amount; target rate chỉ trên resolved eligible cohort | Line/combo và Year→Quarter→Month là option time series | Overview; xác minh coverage/date/status; không causal |
| V08 / TV2 | Accepted và rejected applications khác nhau về volume/amount ra sao? | Application grain, hai source riêng; decision, count, amount | Funnel option chỉ khi stage và grain so sánh hợp lệ | Overview; rejected không có default label |
| V09 / TV2 | Purpose nào chiếm volume/amount, có risk pattern gì? | Accepted loan grain; purpose, count/amount, eligible rate/PD | Bar/treemap là categorical options | Overview; nhóm nhỏ không ổn định, association |
| V10 / TV3 | Loan amount so với annual income phân bố thế nào? | Application grain; loan_amnt, annual_inc; missing/outlier | Scatter/bubble option cho numeric relationship, kiểm tra overplot | Borrower Risk; không kết luận affordability causality |
| V11 / TV3 | DTI và FICO kết hợp thế nào với observed/predicted risk? | Loan grain; predeclared bands, count, rate/PD | Heatmap/matrix option cho joint binned pattern | Borrower Risk; định nghĩa bins và ngưỡng sparse cell |
| V12 / TV3 | Segment borrower có composition/volume/risk khác nhau thế nào? | Loan grain; chosen segment, count/share, eligible risk metrics | Bar/100% stacked; donut chỉ khi đúng câu hỏi composition | Borrower Risk; hạn chế category và tính đại diện |

## Pending: COURSE VISUALIZATION THEORY REVIEW

Sau khi user cung cấp tài liệu giảng viên, trước khi khóa chart:

1. Đọc tài liệu theory liên quan.
2. Lập inventory chart types, visual encodings, interaction techniques, storytelling guidance được dạy.
3. Với từng V01–V12, ghi business question; data type; dimensionality; comparison/relationship/distribution cần trả lời; chart hiện tại (provisional); các chart/technique học trên lớp; strengths/weaknesses; chart cuối; lý do chọn; kỹ thuật môn học thể hiện.
4. Đối chiếu lựa chọn với actual grain, quality, sample size và rubric.
5. Giữ hoặc đổi chart có giải thích cụ thể. Không dùng chart phức tạp chỉ để trông advanced.
6. Chỉ sau review mới duyệt spec cuối và bắt đầu build/rebuild.

## Required visual record khi theory review và final build

Mỗi visual cuối phải có: Visual ID; owner/reviewer; dashboard page; business question và lý do quan trọng; source/table, population và grain; dimensions/measures/definitions/units; final chart và rationale; alternatives considered; course theory/technique; filters/slicers; tooltip; cross-filter behavior; drilldown/drillthrough nếu phù hợp; key observation; insight; business interpretation; story connection; limitation/caveat; evidence/source.

Chart type, course technique, final insight và interactions vẫn pending cho tới khi có course materials và verified evidence.

## Interaction principles

Filters/slicers, cross-filter, tooltip, drilldown, drillthrough, page navigation và guided narrative chỉ dùng khi giúp trả lời một câu hỏi phân tích. Với từng interaction, ghi rõ câu hỏi nào được giải đáp và hành vi mong đợi. Không thêm interaction để trang trí. TV3 thực hiện trong Master PBIX; visual owners cung cấp yêu cầu đã review. Không chỉnh Master PBIX đồng thời.

## Dashboard build workflow

1. **UNDERSTAND:** đọc repo, data artifacts, dictionary, contracts, tasks, ownership; hiểu grain, fields, metrics và final-vs-temporary modeling artifacts. Chưa build chart.
2. **COURSE THEORY + VISUAL REVIEW:** đọc lecturer materials, inventory techniques, review V01–V12. Chỉ khóa chart sau phase này.
3. **DATA MODEL DESIGN:** chọn file thực sự cần vào Power BI; thiết kế fact/dimensions, relationships, measures/calculated fields. Không import mọi artifact một cách máy móc.
4. **REVIEW TEAM WORK:** TV1 hoàn tất visual của mình, sau đó review work TV2/TV3 theo approved question, theory, correctness, quality, consistency và techniques. Sửa work yếu/sai; không giữ lỗi chỉ vì người khác tạo.
5. **MASTER DASHBOARD:** TV3 tích hợp pages và chuẩn hóa layout, fonts, titles, units, labels, filters, tooltips, interactions, navigation, terminology và risk definitions.
6. **STORYTELLING:** dẫn người xem qua question → evidence → insight → next question → business meaning, không kể tuần tự chart.
7. **FINAL REVIEW:** kiểm tra numbers, relationships, measures, visuals, interactions, story, limitations, ownership, report/video consistency.

## Intended storytelling flow

Credit-risk problem → dataset/application portfolio → accepted/rejected flow và portfolio activity → borrower profiles/geographic/time patterns → có dự đoán được default risk không → model generalize ra sao → PD/risk tiers được gán thế nào → vì sao model dự đoán như vậy → risk có ý nghĩa gì theo EL scenario → kết quả của một borrower → evidence-based takeaways/considerations → limitations và responsible interpretation.

## Insight standard

Mỗi insight phải tách bốn phần:

- **OBSERVATION:** dữ liệu/visual cho thấy gì (ví dụ Tier C chiếm 47.89% scenario EL, chỉ khi ghi đúng source/population).
- **INTERPRETATION:** pattern có thể quan trọng vì sao (EL phụ thuộc exposure và population size bên cạnh PD).
- **BUSINESS IMPLICATION:** điều decision-maker có thể cân nhắc; không khẳng định intervention đã được chứng minh.
- **LIMITATION:** điều không thể kết luận (ví dụ LGD minh họa, loan_amnt proxy và evaluated-test population không đại diện realized loss/full portfolio).

Không viết association thành causation; không bịa kết quả trước khi data và reviewer xác nhận.

## Report, video và defense linkage

Dùng kế hoạch này cùng canonical docs/tasks/report-writing-plan.md. Report trình bày methods/evidence/reproducibility; dashboard hỗ trợ interactive exploration; video kể một hành trình ngắn có demo; defense giải thích vì sao các lựa chọn được thực hiện. Mỗi visual record cần tái sử dụng được trong report, Power BI explanation, video và oral defense.

## Chuyển từ PLAN sang FINAL RECORD

Chỉ cập nhật khi dashboard work được hoàn tất và review thật. Giữ lại cho mỗi visual: question, final chart rationale, course technique, source/measures, interactions, observation/insight, story connection, limitation. Ghi thêm page story cuối, individual prediction flow, screenshot references trong report và video order. Không tạo thêm plan trùng lặp.
