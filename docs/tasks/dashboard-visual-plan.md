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

## Course visualization theory review — 2026-10-06

Đây là **design review trước khi build**, không phải quyết định chart cuối. Review áp dụng các nguyên tắc của môn học: message + context + audience; Less is More; chọn encoding theo data type và analytical purpose; xác định grain/LOD trước aggregation; sorting, filtering, grouping, percentage; dùng distribution chart cho spread/skew/outlier; dùng heatmap cho matrix/intensity; treemap chỉ khi hierarchy/area có ý nghĩa; map chỉ khi geographic position có ý nghĩa; reference line/drop line/tooltip chỉ khi có benchmark; trend line không hàm ý causality; calculated fields/measures phải phục vụ câu hỏi.

### 1. Tóm tắt quyết định review

| Visual | Câu hỏi chính | Ý tưởng hiện tại | Các hướng từ theory | Recommendation sau review | Lý do ngắn |
|---|---|---|---|---|---|
| V01 / TV3 | State nào có volume hoặc risk pattern đáng xem? | Map | Map; ordered bar theo state | KEEP — provisional | Có `state_code` cấp bang và `dim_state` 51 dòng; cần xác minh map recognition/measure trước build |
| V02 / TV1 | PD model phân bố, spread và tail thế nào? | Histogram | Histogram; box plot; violin; histogram + box/reference | KEEP — histogram primary, chưa lock | Câu hỏi là distribution; histogram giữ hình dạng; thêm threshold line và summary nếu hữu ích |
| V03 / TV1 | Quy mô và observed outcome theo tier ra sao? | Ordered bar/column | Bar; donut/pie; treemap | KEEP — ordered bar | Bốn tier có thứ tự; bar cho so sánh chính xác hơn part-to-whole/donut |
| V04 / TV1 | FICO liên hệ thế nào với predicted PD/risk? | Raw scatter/density | Binned scatter/heatmap; box/violin theo FICO band; sampled scatter | CHANGE — binned distribution view | 269k điểm raw sẽ overplot; box/violin theo band trả lời spread tốt hơn và giữ outlier context |
| V05 / TV1 | Feature nào đóng góp vào model prediction và ví dụ cá nhân ra sao? | Global bar + local explanation | Ranked bar; SHAP distribution; local detail/drillthrough | KEEP — mở rộng explainability | Một bar đơn lẻ không đủ; cần global ranking + SHAP distribution + local detail, giữ raw-margin semantics |
| V06 / TV1 | Tier nào đóng góp EL lớn và do PD/exposure/population nào? | Sorted horizontal bar | Ranked bar; stacked bar; treemap; KPI/scatter support | KEEP — ranked bar + support | Tier là nhóm song song, không phải bước cộng dồn; tooltip/KPI phải cho thấy PD, exposure và EL |
| V07 / TV2 | Volume và risk của accepted loans thay đổi thế nào theo thời gian? | Line/combo | Line; small multiples; separate volume/rate panels; trend/reference line | CHANGE — coordinated time views | Volume all accepted và rate resolved có coverage khác nhau; tránh dual-axis gây đọc sai |
| V08 / TV2 | Accepted và rejected applications khác nhau ra sao? | Funnel | Grouped bar; 100% stacked bar; funnel | CHANGE — bar/100% stacked | Accepted/rejected là hai outcome song song, không phải các stage tuần tự; funnel dễ hàm ý conversion path sai |
| V09 / TV2 | Purpose nào chiếm volume/amount và có risk pattern gì? | Bar/treemap | Ordered bar; stacked bar; treemap | KEEP — ordered bar primary | Purpose là categorical, không có hierarchy bắt buộc; bar dễ so sánh và không trộn measure |
| V10 / TV3 | Loan amount và annual income phân bố/liên hệ thế nào? | Scatter/bubble | Binned heatmap; sampled scatter; density/box by bands | CHANGE — binned heatmap primary | Raw accepted population lớn; binning cho thấy concentration và outlier policy rõ hơn |
| V11 / TV3 | DTI và FICO kết hợp thế nào với risk? | Heatmap/matrix | Heatmap; small multiples; grouped bars | KEEP — heatmap | Hai chiều đã được binned; color intensity phù hợp, nhưng phải hiển thị cell count và mask sparse cells |
| V12 / TV3 | Borrower segment nào có composition/volume/risk đáng chú ý? | Bar/100% stacked/donut | Ordered bar; 100% stacked; treemap; small multiples | NEEDS MORE DATA | Chưa chốt segment dimension và primary measure; không thể chọn chart có trách nhiệm trước khi định nghĩa scope |

Các recommendation trên là kết quả review, nhưng **chưa lock final chart type**. Final choice cần course-material sign-off, data-model review và kiểm tra PBIX thực tế.

### 2. Phân tích chi tiết V01–V12

#### V01 — Geographic Risk Map

- **Owner/page:** TV3; Page 1 — Portfolio & Application Overview.
- **BUSINESS QUESTION:** Portfolio/application volume và risk pattern phân bố theo state thế nào?
- **WHY THIS VISUAL:** Map dùng vị trí địa lý thật ở state-level; `state_code` được tạo từ `addr_state`, `country` là United States và `dim_state` có 51 state codes. Map có ý nghĩa nếu người xem cần đọc concentration theo không gian, không phải để trang trí.
- **Source/grain/types:** `loan_application.parquet`/accepted canonical ở loan/application grain cho count và amount; scored/canonical labeled population cho observed rate hoặc PD; `dim_state` ở state grain. `state_code` là categorical/geographic, count/amount/rate/PD là numeric.
- **Candidate approaches:** Map (geographic pattern, nhưng phụ thuộc geocoding); ordered state bar (comparison chính xác hơn, nhưng mất spatial context). Giữ map là hướng chính tạm thời và dùng bar/table làm supporting detail nếu state-level comparison cần chính xác.
- **Aggregation/LOD:** aggregate theo `state_code`; không plot từng raw row. Tách accepted volume khỏi labeled default/risk metric. Kiểm tra count trước khi diễn giải rate.
- **Interaction:** state/country, issue year/quarter/month nếu source có; tooltip state, count, amount, eligible denominator, rate/PD. Drillthrough từ state vào state detail chỉ khi có page/source.
- **Reference line:** không cần reference line trên map; nếu có portfolio mean/median rate, đặt trong tooltip/KPI chứ không tô màu tùy ý.
- **INSIGHT:** candidate — kiểm tra state nào có concentration hoặc risk pattern khác biệt; chưa tuyên bố kết quả causal. **STORY CONNECTION:** mở đầu từ portfolio overview, dẫn sang temporal/purpose và sau đó borrower/model risk.
- **Limitation:** state-level association; ZIP masked không được suy tọa độ; rejected không có default outcome; map recognition của Power BI cần verify trước build.

#### V02 — PD Distribution

- **Owner/page:** TV1; Page 3 — Model Risk & Explainability.
- **BUSINESS QUESTION:** Model tạo ra phân bố PD như thế nào, spread/tail nằm ở đâu và bao nhiêu score ở quanh operating threshold?
- **WHY THIS VISUAL:** Đây là distribution question, nên phải giữ spread/skew/tail thay vì chỉ mean PD.
- **Source/grain/types:** `ml_lc_10_scored_frozen_test.parquet`, một dòng mỗi scored loan; `predicted_pd` continuous numeric, threshold là numeric reference. Population là evaluated frozen-test sample, không phải full portfolio.
- **Candidate approaches:** Histogram cho shape/tail; box plot cho median/quartiles/outliers; violin cho density nhưng khó đọc hơn và có thể không native/dễ giải thích trong Power BI; histogram + compact summary/box-style view là phương án giàu thông tin.
- **Recommendation:** **KEEP histogram làm primary provisional chart**, cân nhắc box/summary supporting view. Đặt reference line tại `T = 0.22009515762329102` chỉ khi line giúp trả lời câu hỏi phân loại; ghi rõ đây là threshold chọn trên validation.
- **Aggregation/LOD:** bin `predicted_pd`; không hiển thị 269k điểm raw. Bin width phải nhất quán và ghi trong tooltip/metadata nếu ảnh hưởng diễn giải.
- **Interaction:** model version, population, risk tier và threshold label; tooltip bin, loan count, share. Cross-filter sang V03 risk tiers; drillthrough sang scored loan detail nếu cần.
- **INSIGHT:** candidate — PD tập trung ở vùng nào và có tail cao không. **STORY CONNECTION:** PD distribution → V03 gom PD thành tier → V05 giải thích prediction.
- **Limitation:** scores của evaluated candidate; không gọi là full portfolio; distribution không chứng minh calibration hay causal risk factor.

#### V03 — Risk Tier Distribution

- **Owner/page:** TV1; Page 3.
- **BUSINESS QUESTION:** Borrowers được phân bổ thế nào trong A/B/C/D và observed default rate/mean PD thay đổi ra sao theo tier?
- **WHY THIS VISUAL:** Tier là bốn nhóm có thứ tự; bar cho phép so sánh count/share/mean rate rõ hơn pie.
- **Source/grain/types:** ML-LC-10 scored artifact hoặc `ml_lc_10_risk_tier_summary.csv`, tier/summary grain; tier ordinal categorical, count/share/mean PD/rate numeric.
- **Candidate approaches:** Ordered bar/column (primary comparison); donut/pie (part-to-whole nhưng khó so sánh exact values); treemap (chỉ hợp nếu hierarchy/area cần, hiện không có hierarchy). **Recommendation: KEEP ordered bar.**
- **Aggregation/LOD:** một bar mỗi tier; không trộn mean PD và observed rate thành một measure. Có thể dùng small supporting markers/KPI cho mean PD và observed rate.
- **Interaction:** tier sort A→D cố định; threshold/model label; tooltip count/share/mean PD/observed rate. Cross-filter sang V04/V05 chỉ khi semantics rõ.
- **Reference line:** không cần; tier boundaries đã là policy definition. Nếu hiển thị boundary, ghi `T`, `T/2`, `2T` ở context, không tạo threshold mới.
- **INSIGHT:** observed artifact cho thấy mean PD từ 7.73% đến 51.79% và observed rate từ 6.20% đến 55.41%; hai đại lượng vẫn phải tách biệt. **STORY CONNECTION:** biến phân bố PD của V02 thành risk language trước khi đi vào borrower profile/business impact.
- **Limitation:** evaluated population; observed rate là retrospective description, không bảo đảm cho từng borrower.

#### V04 — FICO vs Risk / PD

- **Owner/page:** TV1; Page 2 — Borrower Risk Profile.
- **BUSINESS QUESTION:** FICO profile đi cùng predicted PD/risk pattern thế nào?
- **WHY THIS VISUAL:** Cần nhìn relationship và spread giữa một credit numeric variable và model risk, nhưng không được để hàng trăm nghìn điểm che mất pattern.
- **Source/grain/types:** ML-LC-10 scored artifact, một dòng mỗi evaluated loan; `fico_avg`/FICO numeric, `predicted_pd` numeric, tier ordinal, target binary descriptive.
- **Current issue:** raw scatter với 269,070 rows sẽ overplot và làm density/outlier khó đọc.
- **Candidate approaches:** sampled/transparent scatter (giữ individual relationship nhưng sampling có thể bỏ mass); heatmap theo FICO/PD bins (tốt cho density, mất individual spread); box/violin `predicted_pd` theo FICO bands (tốt cho distribution/spread, requires defensible bands); binned line/point summary (dễ đọc nhưng che variance).
- **Recommendation:** **CHANGE current raw-scatter direction** sang binned heatmap hoặc box/violin theo FICO band; sampled scatter chỉ là detail/prototype sau đó. Chưa chọn một final option trước khi TV3 xác nhận binning/data grain.
- **Aggregation/LOD:** FICO band × PD bin hoặc FICO band → distribution; report cell/row counts. Không đưa toàn bộ raw points vào visual mặc định.
- **Interaction:** FICO band, purpose, term, risk tier; tooltip count, median/mean PD, observed rate nếu target hợp lệ. Trend/reference line chỉ dùng nếu định nghĩa benchmark rõ, không viết causal.
- **INSIGHT:** candidate — các vùng FICO/PD hoặc tier có concentration/spread khác nhau. **STORY CONNECTION:** borrower profile liên kết với V02/V03 model output; sau đó V05 giải thích feature contribution.
- **Limitation:** FICO association không phải FICO gây default; missing/sparse bands và evaluated population cần hiển thị.

#### V05 — Feature Importance / SHAP

- **Owner/page:** TV1; Page 3.
- **BUSINESS QUESTION:** Feature nào đóng góp nhiều vào model predictions, và một vài borrower example được giải thích thế nào?
- **WHY THIS VISUAL:** Explainability cần global ranking và distribution/local context; một bar chart duy nhất dễ biến SHAP thành “feature causes risk”.
- **Source/grain/types:** `ml_lc_09_global_importance.csv` ở original-feature grain; `ml_lc_09_shap_sample.parquet` ở validation sample loan grain; `ml_lc_09_local_explanations.csv` cho local examples. Feature categorical/numeric, mean absolute SHAP continuous, direction/context categorical.
- **Candidate approaches:** ranked horizontal bar cho global mean absolute SHAP; SHAP-style distribution/beeswarm cho spread/direction; local explanation table/detail page/tooltip cho individual example. **Recommendation: KEEP nhưng mở rộng thành coordinated explainability view.**
- **Aggregation/LOD:** original feature đã aggregate từ transformed columns theo policy ML-LC-09; không trộn transformed names tùy ý. Local view chỉ dùng selected sample, ghi sample/provenance.
- **Interaction:** click feature để filter local examples; model/population selector; tooltip raw margin/log-odds, feature value và contribution. Drillthrough tới explanation detail nếu thật sự có consumer.
- **Reference line:** ranking baseline/zero contribution không dùng như arbitrary benchmark; SHAP zero có ý nghĩa theo output space, cần giải thích.
- **INSIGHT:** top mean absolute SHAP gồm `term_months`, `loan_to_income_ratio`, `fico_range_low`, `dti`, `issue_year`; đây là model contribution/association. **STORY CONNECTION:** sau risk tiers, trả lời “model dựa vào gì?” trước Expected Loss.
- **Limitation:** SHAP raw margin/log-odds không phải phần trăm thay đổi PD; contribution không phải causation; categorical direction không nên tóm thành một chiều.

#### V06 — Expected Loss / Risk Contribution

- **Owner/page:** TV1; Page 4 — Business Risk & Expected Loss.
- **BUSINESS QUESTION:** Tier nào đóng góp scenario EL lớn nhất, và contribution đến từ PD, exposure hay population size?
- **WHY THIS VISUAL:** Người xem cần so sánh total EL theo nhóm đồng thời nhìn context exposure/PD; bar ranking tốt hơn waterfall vì tier là nhóm song song.
- **Source/grain/types:** `ml_lc_11_risk_tier_el_summary.csv` ở tier grain và `ml_lc_11_expected_loss.parquet` nếu cần detail; total EL, EL share, exposure share, mean PD, loan count numeric; tier ordinal; LGD scenario categorical.
- **Candidate approaches:** sorted horizontal bar total EL (primary); stacked/100% bar EL share (part-to-whole); treemap nếu muốn area = EL nhưng có thể kém chính xác; KPI + tooltip/secondary table cho PD/exposure. **Recommendation: KEEP ranked bar + support.**
- **Aggregation/LOD:** aggregate theo tier và selected LGD scenario; không so sánh scenario khác nhau mà không ghi label. Tooltip phải có total EL, EL share, exposure share, mean PD, count, LGD/EAD assumptions và source units.
- **Interaction:** LGD scenario selector; tier sort; tooltip; cross-filter tới scored/risk detail nếu source hợp lệ. Drillthrough chỉ khi row-level EL consumer đã xác định.
- **Reference line:** portfolio mean/total không dùng làm reference line trên category bar nếu không giúp câu hỏi; KPI tổng EL là đủ.
- **INSIGHT:** trên evaluated population, Tier C chiếm 47.89% EL, Tier D có mean PD cao nhất 51.79% nhưng EL share 15.69%. **STORY CONNECTION:** model explanation → business impact; cho thấy PD cao nhất không mặc nhiên là total loss lớn nhất.
- **Limitation:** LGD là scenario assumption; `loan_amnt` là EAD proxy; currency không xác định; không phải realized loss/full portfolio.

#### V07 — Volume / Default or Risk over Time

- **Owner/page:** TV2; Page 1.
- **BUSINESS QUESTION:** Accepted activity và risk description thay đổi thế nào theo thời gian?
- **WHY THIS VISUAL:** Time order là cốt lõi; line chart giúp thấy volume trend và không làm mất thứ tự period.
- **Source/grain/types:** `loan_application.parquet` cho all accepted volume theo month; canonical resolved/eligible accepted rows hoặc scored source cho observed rate/PD với denominator được ghi rõ. `issue_d` temporal, count/amount/rate numeric.
- **Current issue:** volume all accepted và default rate resolved không cùng coverage/selection; dual-axis combo dễ làm người xem so sánh sai hoặc hiểu causal.
- **Candidate approaches:** line volume + separate line/small multiple for eligible risk rate; combo chỉ khi scales/axes được giải thích; bar volume + line rate có thể dùng nhưng cần cẩn thận. **Recommendation: CHANGE combo mặc định thành coordinated panels/small multiples.**
- **Aggregation/LOD:** Year→Quarter→Month; ghi rõ denominator và unresolved/maturity caveat. Do not compute default rate cho rejected hoặc unresolved statuses.
- **Interaction:** time drilldown; state, purpose, term filters; tooltip period, accepted count/amount, eligible count, rate. Trend line chỉ khi purpose là descriptive trend và ghi rõ non-causal.
- **INSIGHT:** EDA-05 chỉ xác nhận candidate insight về accepted volume 2007-06→2018-12; không bịa default-rate trend. **STORY CONNECTION:** overview từ volume/funnel dẫn vào borrower/risk pages.
- **Limitation:** vintage/maturity and resolved-only selection; trend không chứng minh nguyên nhân.

#### V08 — Accepted vs Rejected Funnel

- **Owner/page:** TV2; Page 1.
- **BUSINESS QUESTION:** Application volume/amount phân bố giữa accepted và rejected thế nào?
- **WHY THIS VISUAL:** Câu hỏi là outcome composition của hai nguồn, nhưng accepted/rejected không phải các bước tuần tự của cùng một funnel.
- **Source/grain/types:** `application_funnel.parquet` ở application decision grain; accepted/rejected counts/amounts, decision categorical, time/state/purpose nếu semantics tương đương.
- **Current issue:** funnel shape có thể hàm ý accepted là bước sau rejected hoặc một conversion pipeline có stage, trong khi đây là hai outcome/source populations.
- **Candidate approaches:** grouped bar cho count/amount; 100% stacked bar cho share; funnel chỉ giữ nếu data model sau này có các stage tuần tự thật. **Recommendation: CHANGE sang grouped bar hoặc 100% stacked bar.**
- **Aggregation/LOD:** group decision, period/state/purpose; không merge accepted loan outcome với rejected default. Tách count và amount, không dùng một encoding mơ hồ cho cả hai.
- **Interaction:** date/state/purpose; tooltip source, decision, count/amount/share. Drillthrough tới application source detail nếu được phép.
- **INSIGHT:** funnel audit khớp 2,260,701 accepted và 27,648,741 rejected; đây là volume/flow evidence. Không có rejected default rate.
- **Limitation:** accepted/rejected schema khác nhau; không diễn giải accepted rate thành causal approval quality nếu chưa có business process context.

#### V09 — Loan Purpose Analysis

- **Owner/page:** TV2; Page 1.
- **BUSINESS QUESTION:** Purpose nào chiếm volume/amount và risk description khác nhau thế nào?
- **WHY THIS VISUAL:** Purpose là categorical; ordered comparison rõ hơn khi số category vừa phải.
- **Source/grain/types:** accepted canonical/application grain; `purpose` categorical, count/amount numeric, observed rate/PD chỉ trên eligible/scored population.
- **Candidate approaches:** ordered bar cho count hoặc amount; stacked bar nếu cần composition theo selected second dimension; treemap nếu purpose có hierarchy thật và area magnitude quan trọng. **Recommendation: KEEP ordered bar primary; treemap chỉ là alternative.**
- **Aggregation/LOD:** group purpose; sort descending by selected measure; small groups cần count/uncertainty caveat. Không để amount và risk rate cùng một trục không giải thích.
- **Interaction:** state/time/term filters; tooltip count, share, amount, eligible denominator, rate/PD. Cross-filter tới borrower/risk page nếu measures cùng population.
- **INSIGHT:** candidate — purpose nào nổi bật về volume hoặc risk; chưa claim trước khi visual chạy/được review. **STORY CONNECTION:** application overview → borrower segmentation/risk.
- **Limitation:** small groups unstable; purpose association không causal; accepted-only scope.

#### V10 — Loan Amount vs Annual Income

- **Owner/page:** TV3; Page 2.
- **BUSINESS QUESTION:** Requested loan size và annual income có concentration/outlier pattern nào?
- **WHY THIS VISUAL:** Hai biến continuous phù hợp relationship analysis, nhưng raw millions of rows không phù hợp hiển thị trực tiếp.
- **Source/grain/types:** application/accepted loan grain; `loan_amnt`, `annual_inc` continuous numeric, purpose/segment categorical.
- **Candidate approaches:** sampled transparent scatter giữ relationship/outliers; 2D binned heatmap/density cho concentration; box plot by income/loan bands cho spread nhưng làm mất joint detail. **Recommendation: CHANGE raw scatter mặc định sang binned heatmap; sampled scatter là supporting/detail option.**
- **Aggregation/LOD:** define loan amount/income bins using documented, stable boundaries; show cell count and missing/outlier handling. Không dùng bin để tạo causal affordability claim.
- **Interaction:** purpose, home ownership, issue period, state if valid; tooltip bin ranges, count, median/percentile loan-to-income ratio. Drillthrough tới detail chỉ khi cần.
- **Reference/trend line:** median/income benchmark chỉ khi business question duyệt; trend line không được diễn giải causal.
- **INSIGHT:** candidate — concentration/outlier của amount-income và nhóm cần xem thêm; chưa bịa affordability finding. **STORY CONNECTION:** borrower profile trước risk matrix/segment.
- **Limitation:** income missing/outliers, sampling/binning, observational association.

#### V11 — DTI / FICO Risk Matrix

- **Owner/page:** TV3; Page 2.
- **BUSINESS QUESTION:** Joint DTI/FICO bands có vùng predicted/observed risk nào cần chú ý?
- **WHY THIS VISUAL:** Heatmap phù hợp matrix intensity; course theory trực tiếp hỗ trợ hai chiều categorical/ordinal bands.
- **Source/grain/types:** canonical labeled/scored loan grain; `dti_band`, `fico_band` ordinal/categorical; count, mean PD hoặc observed default rate numeric. EDA precedent dùng minimum cell count 100.
- **Candidate approaches:** heatmap primary; small multiples by purpose/time nếu cần context; grouped bar chỉ cho ít bands và không thay thế matrix. **Recommendation: KEEP heatmap.**
- **Aggregation/LOD:** band × band; hiển thị metric và `n`; mask/label cells dưới minimum count 100. Chọn một primary color metric (PD hoặc observed rate), không trộn chúng.
- **Interaction:** state/purpose/time slicer, metric selector nếu semantics rõ, tooltip count/mean PD/observed rate. Drilldown band → detail chỉ khi sample đủ.
- **Reference line:** matrix boundaries là predefined bands; không thêm arbitrary line.
- **INSIGHT:** candidate — ô nào có intensity/risk cao và liệu volume có đủ lớn; không causal. **STORY CONNECTION:** borrower profile kết nối FICO/DTI với risk output và chuẩn bị model explanation.
- **Limitation:** bin choice, sparse cells, observed rate retrospective; PD and observed rate are different quantities.

#### V12 — Borrower Segment Analysis

- **Owner/page:** TV3; Page 2.
- **BUSINESS QUESTION:** Segment borrower nào cần được mô tả/so sánh về composition, volume hoặc risk?
- **WHY THIS VISUAL:** Chưa thể chọn encoding khi chưa xác định segment dimension và decision question.
- **Source/grain/types:** canonical/application/scored grain cần chốt; candidate dimensions `home_ownership`, `verification_status`, `emp_length` hoặc purpose, nhưng không tự chọn chỉ vì có sẵn. Measures có thể count/share, median income, mean PD hoặc eligible observed rate.
- **Candidate approaches:** ordered bar cho comparison; 100% stacked bar cho composition; treemap cho hierarchy/area; small multiples cho nhiều segment dimensions. Donut chỉ khi ít category và câu hỏi thực sự là part-to-whole.
- **Recommendation:** **NEEDS MORE DATA / SPECIFICATION**. Cần owner/reviewer chốt một segment dimension, population, measure và intended action trước khi chọn chart.
- **Aggregation/LOD:** one row per segment/group; sort and minimum-count threshold; không gộp nhiều dimensions thành chart khó đọc.
- **Interaction:** segment filter, purpose/time/state slicer, tooltip count/share and eligible denominator. Drillthrough to borrower detail chỉ khi privacy/volume policy cho phép.
- **INSIGHT:** candidate — segment composition/risk pattern; không phát biểu trước khi segment definition và data evidence được duyệt. **STORY CONNECTION:** borrower profile → model/risk page, không lặp V03.
- **Limitation:** arbitrary segmentation, sparse groups, representativeness and association-not-causation.

### 3. Interaction review theo trang

| Trang | Interaction nên demonstrate | Câu hỏi interaction giúp trả lời |
|---|---|---|
| Page 1 Overview | Page navigation; time drilldown; state/purpose slicer; tooltip; cross-filter giữa volume/purpose/geography | Khi đổi period/state/purpose, portfolio volume và application composition thay đổi thế nào? |
| Page 2 Borrower Risk | FICO/DTI/segment filters; band grouping; cell-count tooltip; optional drillthrough | Nhóm borrower nào nằm trong vùng risk/profile cần xem thêm và sample có đủ lớn không? |
| Page 3 Model Risk | PD bin; tier filter; threshold reference; feature click → local explanation; tooltip | Từ PD liên tục sang tier và feature contribution, model output được hiểu thế nào? |
| Page 4 EL | LGD scenario selector; tier sorting; KPI tooltip; optional detail drillthrough | EL thay đổi vì scenario LGD hay vì tier/exposure/population nào? |
| Page 5 Individual Prediction | Page navigation; input validation; explanation context; no fabricated output | Một borrower cụ thể nhận PD/class/tier nào và cần caveat gì? |

Không cần dùng mọi kỹ thuật ở mọi trang. `Grouping`, `sorting`, `percentage`, `aggregation` là nền tảng cho mọi visual; reference/drop line chỉ dùng với threshold/benchmark có ý nghĩa; tooltip phải thêm context chứ không nhồi mọi field; trend line không được biến trend thành causation; calculated fields/measures chỉ tạo sau khi data model và metric contract được duyệt.

### 4. Storytelling review

Các trang hiện tại vẫn logical và giữ nguyên provisional grouping:

1. **Portfolio:** portfolio đến từ đâu, accepted/rejected flow, volume theo thời gian và purpose nào nổi bật?
2. **Borrower:** borrower/application characteristics nào đi cùng pattern risk; FICO, DTI, amount-income và segment bổ sung context gì?
3. **Model:** model tạo PD nào, chuyển thành tiers ra sao, và feature nào đóng góp vào prediction?
4. **Business impact:** khi thêm LGD/EAD/exposure, tier nào đóng góp scenario EL và vì sao không chỉ nhìn mean PD?
5. **Individual decision support:** một borrower đi qua inference contract nào; output nào được giải thích và giới hạn nào phải nói rõ?

Flow: **Portfolio → Borrower → Risk → Model/Explanation → Expected Loss → Individual applicant → decision insight → limitations.** Đây là question → evidence → insight → next question → business meaning, không phải lần lượt giới thiệu 12 chart.

### 5. Unresolved before Power BI build

- Chưa có lecturer-material package trong repository để ghi course technique cụ thể cho từng V01–V12; đây là pending input trước chart lock.
- V04 và V10 cần chốt binning/sampling/density policy trước khi plot population lớn.
- V07 cần chốt hai population/denominator cho accepted volume và resolved risk; tránh dual-axis gây hiểu nhầm.
- V08 cần xác nhận business process có stage tuần tự hay chỉ hai outcome; hiện bar/100% stacked phù hợp hơn funnel.
- V12 cần định nghĩa segment dimension, measure, minimum count và intended decision question.
- V01 cần verify Power BI map recognition của `state_code` + `country`; không suy tọa độ từ masked ZIP.
- V02 cần chốt bin width và có dùng threshold reference line hay không.
- V03/V06 cần chốt một primary measure và tooltip/supporting KPI để không trộn count, share, PD, rate, exposure, EL.
- Cần TV2/TV3 review data model, relationships, measures và actual source refresh trước build; không import mọi artifact một cách máy móc.
- Individual Prediction page mới là contract/design requirement; chưa có UI/input mechanism và không được tuyên bố là official approval system.

**Kết luận review:** giữ kiến trúc năm trang và ownership V01–V12. Giữ hướng provisional cho V01, V02, V03, V05, V06, V09, V11; đổi hướng khỏi raw scatter/combo/funnel cho V04, V07, V08, V10; V12 cần thêm specification. Không chart nào được lock cho Power BI trước theory-material review và data-model sign-off.
