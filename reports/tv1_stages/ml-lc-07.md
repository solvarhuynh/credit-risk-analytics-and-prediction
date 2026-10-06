# ML-LC-07 — Threshold Selection

## 1. Threshold là gì?

Model xuất xác suất vỡ nợ (PD). Quy tắc vận hành là `predicted_pd >= threshold` thì phân loại hồ sơ vào nhóm default-risk.

## 2. Vì sao 0.5 chưa chắc phù hợp?

Với XGBoost, tại 0.5 validation recall là 0.075614; ngưỡng đó bỏ sót nhiều khoản default. Thay threshold đổi precision/recall và số false positive/false negative, nhưng không đổi ROC-AUC/PR-AUC của cùng scores.

## 3. Dữ liệu được dùng

Chỉ dùng **269,070** validation predictions của `xgboost_candidate`; IDs và target khớp frozen validation population. Frozen test vẫn sealed; không đọc hoặc tính metric trên test.

## 4. Quy tắc chọn

Tối đa hóa F1 trên validation bằng tập ngưỡng chính xác lấy từ các prediction scores phân biệt. Nếu F1 cách mức cao nhất không quá `1e-12`, chọn recall cao hơn, sau đó precision cao hơn, cuối cùng chọn threshold cao hơn. Chưa có chi phí kinh doanh được duyệt; đây là operating threshold thống kê, không phải ngưỡng tối ưu cho Expected Loss hoặc lợi nhuận.

## 5. Bảng trade-off tham khảo

Bảng file CSV lưu tất cả score thresholds đã xét cùng các ngưỡng chẩn đoán. Bảng dưới rút gọn các mốc tham khảo và ngưỡng được chọn:

| Threshold | Precision | Recall | F1 | Accuracy | FP | FN | Predicted positive |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.1 | 0.236954 | 0.946184 | 0.378996 | 0.380934 | 163681 | 2891 | 214,510 |
| 0.2 | 0.327198 | 0.663198 | 0.438203 | 0.660494 | 73258 | 18093 | 108,885 |
| 0.220095157623 | 0.346453 | 0.602681 | 0.439981 | 0.693693 | 61074 | 21344 | 93,450 |
| 0.3 | 0.421410 | 0.385238 | 0.402513 | 0.771662 | 28414 | 33025 | 49,109 |
| 0.4 | 0.513334 | 0.189557 | 0.276874 | 0.802315 | 9654 | 43537 | 19,837 |
| 0.5 | 0.598674 | 0.075614 | 0.134270 | 0.805326 | 2723 | 49658 | 6,785 |
| 0.6 | 0.669759 | 0.020160 | 0.039142 | 0.802390 | 534 | 52637 | 1,617 |

## 6. Threshold được chọn

**0.220095157623** theo tiêu chí F1 validation.

Precision 0.346453; recall 0.602681; F1 0.439981; accuracy 0.693693.

Confusion `[ [TN, FP], [FN, TP] ]`: `[[154276, 61074], [21344, 32376]]`.

## 7. So với threshold 0.5

Precision -0.252221; recall +0.527066; F1 +0.305711; accuracy -0.111633; FP +58,351; FN -28,314.

Ngưỡng thấp hơn thường tăng recall và giảm FN, đồng thời có thể giảm precision và tăng FP. Ngưỡng được chọn thể hiện trade-off quan sát được trên validation.

## 8. Giới hạn

Threshold này được chọn trên validation; không tối ưu frozen test, Expected Loss, lợi nhuận hoặc chi phí kinh doanh. Không phải cutoff đúng cho mọi tổ chức. Model không được retrain.

## 9. Bước tiếp theo

ML-LC-08 — Frozen Test, theo đúng quy trình đánh giá một lần.
