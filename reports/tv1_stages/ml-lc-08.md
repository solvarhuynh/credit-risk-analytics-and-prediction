# ML-LC-08 — Frozen Test Evaluation

## 1. Mục tiêu

Frozen Test là bài thi cuối trên dữ liệu chưa dùng để huấn luyện hay chọn cấu hình.

## 2. Cấu hình khóa trước test

Model: `xgboost_candidate` (ML-LC-06 validation). Threshold: `0.22009515762329102` (ML-LC-07 validation).

## 3. Frozen test

269,070 dòng; không overlap train/validation; nhãn khớp canonical.

## 4. Kết quả cuối

ROC-AUC 0.723186; PR-AUC 0.400000; Log Loss 0.447783; Brier 0.142643.
Precision 0.345877; Recall 0.602960; F1 0.439590; Accuracy 0.693065.
Confusion [[TN, FP], [FN, TP]]: `[[154092, 61258], [21329, 32391]]`.

## 5. Validation so với test (test trừ validation)

| Metric | Validation | Test | Delta |
|---|---:|---:|---:|
| roc_auc | 0.724501 | 0.723186 | -0.001315 |
| pr_auc | 0.399256 | 0.400000 | +0.000744 |
| precision | 0.346453 | 0.345877 | -0.000576 |
| recall | 0.602681 | 0.602960 | +0.000279 |
| f1 | 0.439981 | 0.439590 | -0.000391 |
| accuracy | 0.693693 | 0.693065 | -0.000628 |

## 6. Diễn giải

Hiệu năng trên dữ liệu chưa từng dùng tương đối gần validation; không dùng test để tối ưu lại.

## 7. Tính toàn vẹn

Không retrain, đổi feature/candidate/threshold, fit preprocessing hoặc dùng test cho chọn mô hình/ngưỡng. Test thật chỉ đánh giá một lần; unit test dùng fixture synthetic không mở test thật.

## 8. Tiếp theo

ML-LC-09 Explainability; không sửa cấu hình theo kết quả test.
