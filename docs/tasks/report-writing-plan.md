# Report Writing Plan — Scientific Report ≥ 40 pages

Trạng thái: **PLANNED / NOT YET WRITTEN**. Không tạo prose, số liệu, bảng hay insight giả trước khi TV2/TV1/TV3 bàn giao output thật. Page budget dưới đây mục tiêu khoảng 52 trang nội dung chính, chưa tính cover/appendix nếu quy định yêu cầu.

| Section | Ước tính trang | Primary author | Cross reviewer | Dependency / figures-tables | Status |
|---|---:|---|---|---|---|
| Abstract + keywords | 2 | TV1 | TV2 + TV3 | Final results, no invented claims | WAITING |
| 1. Introduction & problem framing | 3 | TV1 | TV3 | Business question, scope | PLANNED |
| 2. Dataset and sources | 4 | TV2 | TV1 | Raw inventory, accepted/rejected table | WAITING TV2 |
| 3. System/pipeline overview | 3 | TV1 | TV2 + TV3 | Architecture diagram, handoff flow | PLANNED |
| 4. Raw schema and data contract | 3 | TV2 | TV1 | Column groups, key/target table | WAITING TV2 |
| 5. Preprocessing and cleaning | 5 | TV2 | TV1 | Missing/outlier/percent/date/ZIP tables | WAITING TV2 |
| 6. Join/Merge and business tables | 4 | TV2 | TV1 | Grain/join validation table | WAITING TV2 |
| 7. Calculated fields and leakage policy | 3 | TV2 | TV1 | Feature formulas and leakage gate | WAITING TV2 |
| 8. EDA and technical findings | 5 | TV2 | TV1 + TV3 | EDA-01…EDA-05, summary tables | WAITING DATA |
| 9. Dashboard architecture and data model | 4 | TV3 | TV1 + TV2 | Relationships, dimensions, 5-page plan | WAITING DATA |
| 10. UI/UX and interaction design | 3 | TV3 | TV1 | Filters, drill-down, tooltip, cross-filter screenshots | WAITING PBIX |
| 11. Modeling methodology | 4 | TV1 | TV2 | Split, preprocessing, Logistic, optional comparison | WAITING MODEL |
| 12. Evaluation, threshold and prediction | 3 | TV1 | TV2 | Metrics/curves/threshold table from real run | WAITING MODEL |
| 13. Explainability and Expected Loss | 3 | TV1 | TV3 | SHAP/importance/EL visual and assumptions | WAITING MODEL |
| 14. Storytelling and integrated insights | 2 | TV1 | TV2 + TV3 | Canonical flow and visual references | WAITING ALL |
| 15. Installation, demo and user guide | 1 | TV3 | TV1 + TV2 | Setup, refresh, demo script | WAITING ALL |
| 16. Limitations, ethics and risk | 1 | TV1 | TV2 + TV3 | Censoring, leakage, geography, bias | PLANNED |
| 17. Conclusion and future work | 1 | TV1 | TV2 + TV3 | Evidence-backed conclusions | WAITING ALL |
| References and checking | 1 | TV1 | TV2 + TV3 | Dataset/source/rubric references | PLANNED |

## Shared approval sections

Abstract, Introduction, System/Pipeline Overview, Storytelling summary, Limitations, Conclusion, Demo script và References cần cả ba thành viên đọc và approve. TV1 điều phối final consistency; reviewer chịu trách nhiệm bắt lỗi semantics chứ không chỉ grammar.

## Report quality gate

Không dùng correlation như causation; ghi rõ accepted-only default population; phân biệt observed data và LGD/EAD assumption; mọi chart/table trỏ về nguồn; không công bố metric trước khi pipeline/model chạy và được log.
