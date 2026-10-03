# Phân công nhiệm vụ — Lending Club

## Nguyên tắc chung

Repository dùng mô hình **PRIMARY OWNER + SHARED RESPONSIBILITY + CROSS REVIEWER**. Phân công dưới đây phản ánh thời gian hiện tại: TV1 khoảng 45–50%, TV2 khoảng 25–30%, TV3 khoảng 25–30%. Đây là phân bổ workload, không phải điểm số.

Mọi thành viên đều phải hiểu end-to-end: dữ liệu raw/interim/processed, cleaning, Join/Merge, target, leakage, EDA, Logistic Regression, dashboard và các insight chính. Code ownership vẫn rõ ràng; kiến thức và deliverable cuối được review chéo.

## Bảng trách nhiệm tổng quát

| Thành viên | PRIMARY | SHARED | CROSS REVIEW |
|---|---|---|---|
| TV1 | Modeling; V01–V06; Storytelling Lead; Report Coordinator; Defense Coordinator | Hiểu toàn pipeline; tham gia insight, report, demo | Review handoff TV2, V07–V09, dashboard structure và consistency report |
| TV2 | Data Engineering; V07–V09; technical EDA; data report sections | Cung cấp field/measure semantics cho mọi visual; hiểu model/dashboard | Review data inputs TV1, measures liên quan source và data claims |
| TV3 | Master Power BI integration; V10–V12; dashboard report/demo | Tích hợp V01–V09; tham gia story, report và defense | Review V01–V06/model outputs và visual/layout consistency |

Không thành viên nào được tuyên bố task FINAL nếu chưa có reviewer bắt buộc sign-off.

## TV1 — Modeling, analytics và điều phối

TV1 sở hữu toàn bộ modeling roadmap: input gate, deterministic split, preprocessing, Logistic Regression bắt buộc, imbalance, XGBoost tùy chọn, evaluation, threshold, SHAP, scoring, Expected Loss, refit và TV3 handoff.

**Secondary support:** Data understanding, leakage/feature review, data-quality và TV2→TV1 handoff verification.

TV1 trực tiếp sở hữu sáu visual V01–V06, dẫn Storytelling, điều phối báo cáo và defense. TV1 không trở thành sole owner của PBIX; TV3 vẫn là integration owner.

## TV2 — Data Engineering và technical EDA

TV2 tiếp tục là **PRIMARY OWNER — Data Engineering**, chịu trách nhiệm chính và duy nhất về raw inventory, schema profiling, cleaning, missing/outlier, accepted/rejected normalization, business tables, Join/Merge, target, leakage classification, calculated fields, canonical dataset, dictionary, manifest, quality report và static EDA implementation.

TV2 trực tiếp sở hữu V07–V09 và là primary author cho dataset, preprocessing, Join/Merge, calculated fields, data quality và technical EDA. TV2 không triển khai modeling.

## TV3 — Master dashboard integration

TV3 là primary owner của Master Power BI artifact: relationships, theme, page layout, slicers, filters, drill-down, tooltips, cross-filter, navigation/bookmarks, consistency và demo readiness.

TV3 trực tiếp sở hữu V10–V12, tích hợp V01–V09 từ prototype/spec của hai thành viên còn lại, và là primary author cho dashboard architecture, UI/UX, interaction design và user guide.

## Story, report và defense

Story chung đi theo chuỗi: ai đăng ký → ai được chấp nhận/từ chối → danh mục thay đổi theo thời gian → rủi ro tập trung ở đâu → đặc trưng nào liên quan rủi ro → model ước lượng PD → yếu tố ảnh hưởng dự đoán → Expected Loss/business impact.

TV1 điều phối final consistency. Report dùng primary author + cross reviewer; các phần Abstract, Introduction, Pipeline Overview, Storytelling summary, Limitations, Conclusion, Demo script và References cần cả ba thành viên duyệt.

## Handoff

`TV2 Data → TV1 Model → Shared Analytics/Story/Report → TV3 Dashboard Integration → Shared Defense`.

Trạng thái hiện tại: **PLANNED / NOT YET IMPLEMENTED**. Chỉ được bắt đầu triển khai sau khi có dữ liệu/schema phù hợp; không tạo output giả.
