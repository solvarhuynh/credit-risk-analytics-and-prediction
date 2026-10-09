# Kế hoạch Báo cáo, Video/Thuyết trình và Storytelling — Lending Club

**Trạng thái:** Kế hoạch cho full project report và phần trình bày; chưa phải báo cáo cuối. Chỉ đưa số liệu/insight đã có source và được owner/reviewer xác nhận. TV1 điều phối mạch truyện và consistency; ownership nội dung theo bảng phân công vẫn giữ nguyên.

## Phân biệt deliverables

| Deliverable | Mục đích | Nội dung chính |
|---|---|---|
| Word report | Phương pháp, bằng chứng, diễn giải chi tiết và khả năng tái lập | Full project, nguồn, bảng/hình, assumptions, limitations, references |
| Power BI | Khám phá tương tác và truyền đạt insight | Năm trang phân tích provisional theo dashboard plan; final chart sau theory review |
| Video / main presentation | Kể hành trình quan trọng nhất và demo ngắn | Khoảng 5–8 phút; không đọc toàn report hoặc mô tả lần lượt 12 chart |
| Defense / Q&A | Chứng minh nhóm hiểu vì sao lựa chọn được thực hiện | Phần hỏi đáp để đào sâu quyết định và limitation; tổng session khoảng 15 phút |

## Ownership và review

- **TV1:** primary author modeling/prediction/evaluation/SHAP/scoring/Expected Loss; điều phối storyline và report consistency.
- **TV2:** primary author dữ liệu, nguồn, schema, cleaning, target, quality, pipeline và technical EDA; PRIMARY OWNER Data Engineering; sở hữu V07–V09.
- **TV3:** primary author dashboard architecture, Power BI data model/UI/UX/integration/user guide; sở hữu V01 và V10–V13; tích hợp Master PBIX.
- V01 thuộc TV3 (đã chuyển khỏi TV1). TV1 sở hữu V02–V06. TV3 là Master PBIX integrator, không phải sole author mọi visual.
- Abstract, Introduction, pipeline overview, integrated story, limitations, conclusion, demo script và references cần cả ba thành viên review/approve. Reviewer kiểm tra semantics/evidence, không chỉ grammar.

## Full Word report structure

Front matter gồm cover (university/course, project title, team/member roles, lecturer, date), acknowledgements nếu cần, table of contents, list of figures/tables và abbreviations/terminology khi hữu ích.

| # | Chương / nội dung | Nội dung và bằng chứng dự kiến | Primary author / reviewer |
|---|---|---|---|
| 1 | Problem / Objectives | Business context; credit-risk question; lý do dự đoán default; scope; objectives; deliverables | TV1 / TV2+TV3 |
| 2 | Understanding the Data | Lending Club 2007–2018; accepted/rejected sources; row counts; field groups; target source; data limitations; dictionary; table inventory/schema summaries | TV2 / TV1 |
| 3 | Data Engineering | Cleaning, missing values/sentinels, calculated fields, target derivation, unresolved outcomes, business-table architecture, quality gates, leakage policy, time validity; workflow diagram, target distribution, data-quality summary | TV2 / TV1 |
| 4 | EDA | Chọn static charts có mục đích; với mỗi hình: question, source, observation, insight, limitation; không paste chart không diễn giải | TV2 / TV1+TV3 |
| 5 | Modeling Methodology | Vì sao classification; Logistic baseline; preprocessing; feature policy/leakage; split; imbalance | TV1 / TV2 |
| 6 | Model Evaluation / Comparison | Logistic baseline, weighted Logistic, XGBoost; ROC-AUC, PR-AUC, precision, recall, F1, accuracy, Log Loss, Brier; vì sao không chỉ dùng accuracy | TV1 / TV2 |
| 7 | Threshold + Frozen Test | Vì sao 0.5 không mặc định đúng; threshold 0.220095... và F1 selection trên validation; trade-off; frozen-test confusion matrix; TN/FP/FN/TP; validation vs test và generalization | TV1 / TV2 |
| 8 | Explainability / SHAP | Global importance, SHAP summary, Top 10, direction patterns, local examples; raw margin/log-odds không phải PD percentage points; contribution không phải causation | TV1 / TV3 |
| 9 | Scoring / Risk Tier | PD, risk score, project credit score, risk tier; khẳng định project score ≠ FICO; tier distribution, mean PD, observed rate tách riêng | TV1 / TV3 |
| 10 | Expected Loss | EL = PD × LGD × EAD; PD model output; LGD scenario assumption; EAD loan_amnt proxy; portfolio EL, LGD sensitivity, EL by tier; Tier D highest PD nhưng Tier C largest EL contribution | TV1 / TV2+TV3 |
| 11 | Interactive Dashboard | Dashboard pages/data model; visual question/rationale/course technique/measure/interaction/insight; chỉ chọn screenshots đại diện, không chụp mọi filter state | TV3 / TV1+TV2 |
| 12 | Individual Prediction Demo | Input borrower, PD, class, risk score, project score, tier, explanation, optional EL scenario; giới hạn và không phải official approval system | TV3 / TV1 |
| 13 | Main Insights | Tổng hợp EDA, model, SHAP, risk tier, EL và dashboard; synthesis thay vì lặp chart captions | TV1 / TV2+TV3 |
| 14 | Storytelling / Recommendations | Một mạch business story; phân biệt analytical finding với recommendation; recommendations không vượt evidence | TV1 / TV2+TV3 |
| 15 | Limitations | Observational nature, no causal claims, historical data, target resolution, statistical threshold, non-FICO score, LGD assumption, EAD proxy, EL not actual loss, deployment limits | TV1 / TV2+TV3 |
| 16 | References | Dataset, libraries/frameworks, academic/technical sources, lecturer materials, visualization references, SHAP/XGBoost sources; one citation style consistently | TV1 / TV2+TV3 |

Page budget: giữ yêu cầu môn học (nếu vẫn yêu cầu ≥40 trang); chi tiết phân bổ chỉ chốt sau khi rubric/lecturer instructions được đối chiếu. Không kéo dài bằng lặp lại chart hoặc đưa phụ lục giả thành nội dung chính.

## Quy tắc bằng chứng và visual trong report

- Mọi bảng/hình phải ghi source và population/grain khi cần; metrics phải khớp artifact/report stage hiện hành.
- Với visual, nối business question → lý do chọn → observation → insight → business interpretation → limitation; xem docs/tasks/dashboard-visual-plan.md.
- Candidate insight chỉ được gọi là insight đã quan sát sau khi source chạy và reviewer xác nhận.
- Không biến correlation thành causation; không gộp predicted PD với observed default rate.
- V06/EL phải nêu LGD là assumption, EAD là loan_amnt proxy; không gọi scenario thành realized loss.
- Phân biệt evaluated candidate và full-data refit; không gắn frozen-test metrics vào refit.
- Không đưa rejected applications vào default-rate analysis như thể có outcome.
- Chỉ dùng screenshots chọn lọc của dashboard đã tích hợp/review; không trình bày ảnh giả hoặc nhiều trạng thái lọc lặp lại.

## Video / main presentation plan (5–8 phút)

Phần nói/demo chính khoảng 5–8 phút, sau đó hỏi đáp với giảng viên; tổng session dự kiến khoảng 15 phút. Phân bổ thời gian là gợi ý, có thể điều chỉnh để ưu tiên evidence/insight và không cần giải thích mọi chi tiết kỹ thuật.

| Phần | Thời lượng gợi ý | Nội dung/visual |
|---|---:|---|
| Intro / problem | 20 giây | Vấn đề credit risk và câu hỏi chính |
| Dataset | 25 giây | Lending Club 2007–2018, accepted/rejected, quy mô/giới hạn quan trọng |
| Data Engineering | 20 giây | Cleaning, target, leakage gate — chứng minh tính nghiêm túc, không sa vào code |
| EDA | 25 giây | Chỉ strongest findings từ các EDA chart đã xác nhận |
| Modeling | 30 giây | Classification, Logistic baseline và lý do so sánh model |
| Model comparison | 35 giây | Vì sao xgboost_candidate khóa theo validation; metrics cốt lõi |
| Threshold | 25 giây | Vì sao đổi từ 0.5 sang khoảng 0.2201; precision/recall/F1 trade-off |
| Frozen test | 25 giây | Validation và test gần nhau; final confusion matrix/ý nghĩa lỗi |
| Scoring / tiers | 25 giây | PD được chuyển thành tier dễ hiểu; project score không phải FICO |
| Explainability | 20 giây | Một SHAP/global explanation nếu thời gian; contribution ≠ causation |
| Expected Loss | 25 giây | PD × LGD × EAD; Tier D highest PD nhưng Tier C largest EL share |
| Dashboard guided tour | 45 giây | Dẫn qua các trang theo câu hỏi, không giới thiệu tuần tự 12 chart |
| Individual prediction demo | 45 giây | Chọn/nhập một borrower và xem PD, class, score, tier, explanation; chỉ khi demo thật sẵn sàng |
| Main insights + limitations + close | 30 giây | 3–5 takeaway mạnh nhất, ngắn gọn về assumptions/limits, kết luận |

Các mốc gợi ý cộng khoảng **6 phút 35 giây**. Dành phần còn lại trong khung 5–8 phút cho chuyển cảnh, demo loading hoặc nhấn vào finding trọng tâm; nếu UI chưa sẵn sàng, không giả lập demo tương tác.

### Narrative order

INTRO / PROBLEM → DATASET → DATA ENGINEERING (short) → EDA (highlights only) → MODELING → MODEL COMPARISON → THRESHOLD → FROZEN TEST → SCORING / RISK TIER → EXPLAINABILITY → EXPECTED LOSS → DASHBOARD journey → INDIVIDUAL PREDICTION → 3–5 MAIN INSIGHTS → LIMITATIONS → END.

Không dành thời lượng ngang nhau cho mọi stage. Full metrics, all tests, all files, code details và cả 12 visual definitions để report hoặc Q&A, không đọc trong main presentation. Không demo UI nếu chưa có UI chạy thật.

## Storytelling spine

Credit-risk problem → dữ liệu/application nào đang xét → accepted/rejected và portfolio activity → borrower profile/geographic/time patterns → có dự đoán default risk được không → model generalize thế nào → PD/tier nào được gán → vì sao model dự đoán như vậy → EL scenario có ý nghĩa gì → một borrower sẽ nhận output gì → evidence-based takeaway/consideration → limitations/responsible interpretation.

Không kể “chart 1, chart 2, chart 3”; mỗi bước nêu câu hỏi, evidence, insight và câu hỏi tiếp theo.

## Defense preparation

Mỗi thành viên phải hiểu toàn project flow; deep ownership:
- TV1: modeling/prediction/risk/story.
- TV2: Data Engineering/target/data quality/EDA semantics.
- TV3: Power BI/master dashboard/visual interaction.

Mọi thành viên cần trả lời cấp cao về problem, data, target, leakage, split, model, metrics và dashboard story. Question bank tối thiểu gồm: vì sao classification; vì sao Logistic trước; vì sao XGBoost; vì sao accuracy không đủ; class weighting đánh đổi gì; vì sao threshold khác 0.5; frozen test đảm bảo điều gì; SHAP nghĩa là gì/không có nghĩa là gì; project credit score khác FICO thế nào; vì sao Tier C có EL lớn hơn Tier D; LGD/EAD là assumption/proxy gì; rejected không có default rate vì sao; individual demo có giới hạn gì. Mỗi câu cần owner trả lời chính, cross-reviewer và evidence path trước sign-off.

## Quality gate và cập nhật cuối

Final review kiểm tra source/metrics, wording, ownership, report/dashboard/video alignment, theory techniques và limitation. Không tuyên bố dashboard/individual demo hoàn tất nếu chưa build và review thực tế.

Khi work hoàn thành, giữ report plan này làm canonical plan và cập nhật nội dung sang FINAL RECORD có evidence. Video order, final page story và selected screenshot references được ghi vào đây hoặc report cuối; không tạo plan trùng lặp.
