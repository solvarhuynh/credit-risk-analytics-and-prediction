# ML-LC-09 — Explainability

## 1. Mục tiêu

Giải thích hành vi của XGBoost đã khóa; không thay đổi model hoặc threshold.

## 2. Dữ liệu

Explainability dùng riêng validation: 269,070 dòng; SHAP sample 5,000 dòng, random_state=42, phân tầng theo target.
Frozen test không được dùng cho explainability.

## 3. Feature importance

Importance toàn cục cho biết model dựa vào feature nào; native XGBoost gain là đóng góp trung bình mỗi lần split, còn bảng original gộp total_gain rồi chuẩn hóa thành tỷ trọng.

## 4. SHAP

SHAP ước lượng contribution của feature cho dự đoán. Global mean(|SHAP|) mô tả mức contribution trung bình; local SHAP giải thích một loan cụ thể. SHAP mô tả model, không chứng minh quan hệ nhân quả.
SHAP đã chạy và qua kiểm tra additivity trong raw margin/log-odds.
SHAP output space là raw margin/log-odds; max additivity error=3.23e-06. Positive SHAP đẩy margin lên và thường tăng PD; không phải mức tăng phần trăm PD.

## 5. Top 10 feature gốc

| Rank | Feature | Mean absolute SHAP / gain | Diễn giải trên sample |
|---:|---|---:|---|
| 1 | term_months | 0.315463 | Không đủ biến thiên để tóm tắt chiều. |
| 2 | loan_to_income_ratio | 0.159380 | Giá trị cao hơn gắn với SHAP dương hơn (đồng biến). Spearman ρ=0.982; SHAP ở raw margin/log-odds, không phải điểm phần trăm PD. |
| 3 | fico_range_low | 0.156027 | Giá trị cao hơn gắn với SHAP âm hơn (nghịch biến). Spearman ρ=-0.973; SHAP ở raw margin/log-odds, không phải điểm phần trăm PD. |
| 4 | dti | 0.122836 | Giá trị cao hơn gắn với SHAP dương hơn (đồng biến). Spearman ρ=0.958; SHAP ở raw margin/log-odds, không phải điểm phần trăm PD. |
| 5 | issue_year | 0.110877 | Giá trị cao hơn gắn với SHAP dương hơn (đồng biến). Spearman ρ=0.782; SHAP ở raw margin/log-odds, không phải điểm phần trăm PD. |
| 6 | acc_open_past_24mths | 0.100232 | Giá trị cao hơn gắn với SHAP dương hơn (đồng biến). Spearman ρ=0.973; SHAP ở raw margin/log-odds, không phải điểm phần trăm PD. |
| 7 | home_ownership | 0.076316 | Các nhóm category có contribution khác nhau; xem local/sample, không suy ra chiều chung. |
| 8 | mths_since_recent_inq | 0.052777 | Giá trị cao hơn gắn với SHAP âm hơn (nghịch biến). Spearman ρ=-0.827; SHAP ở raw margin/log-odds, không phải điểm phần trăm PD. |
| 9 | tot_hi_cred_lim | 0.051639 | Giá trị cao hơn gắn với SHAP âm hơn (nghịch biến). Spearman ρ=-0.909; SHAP ở raw margin/log-odds, không phải điểm phần trăm PD. |
| 10 | mort_acc | 0.050942 | Giá trị cao hơn gắn với SHAP âm hơn (nghịch biến). Spearman ρ=-0.929; SHAP ở raw margin/log-odds, không phải điểm phần trăm PD. |

## 6. Ví dụ local

Đã chọn loan validation theo PD decile thấp/trung vị/cao; IDs low=94228672, medium=11885246, high=10546472. Contributor dương/âm nằm trong CSV local.

## 7. V05 dashboard

**BUSINESS QUESTION:** Model dựa vào những biến nào và chúng gắn với hướng contribution ra sao?
**WHY THIS VISUAL:** Bar xếp hạng mean(|SHAP|) giúp so sánh mức quan trọng; beeswarm bổ sung độ phân tán, giá trị feature và dấu contribution.
**INSIGHT:** Trong validation sample, các feature đứng đầu là term_months, loan_to_income_ratio, fico_range_low, dti, issue_year; hướng được mô tả là association trong không gian model, không phải nguyên nhân.
**STORY CONNECTION:** V05 nằm sau portfolio overview/segmentation/risk prediction để giải thích vì sao model đưa ra PD, trước business impact.
Global artifact: `D:\ttdltq\data\processed\modeling\ml_lc_09_global_importance.csv`. Dùng cột `feature` với tên gốc, `mean_abs_shap`, `xgboost_gain`, `direction_summary`; tránh tên one-hot nội bộ.

## 8. Giới hạn

Validation sample 5.000 dòng đại diện theo target; direction là association với contribution của model, không phải causality. Gộp one-hot về feature gốc làm mất chi tiết từng category. PD là dự đoán, không phải xác suất đã hiệu chuẩn hay nguyên nhân thực tế.

## 9. Bước tiếp theo

ML-LC-10 — PD → Credit Score / Risk Tier; chưa bắt đầu.
