# Báo cáo chất lượng dữ liệu Lending Club

Trạng thái tổng: **PASS**

## LEAKAGE GATE

LEAKAGE GATE = **PASS**

- Post-loan trong feature: []
- Policy-derived trong baseline: []
- Geography trong baseline: []
- Unknown cần review: []
- Identifier/target trong feature: []

## Kiểm tra chính

- Số dòng accepted source: 2,260,701
- Số dòng rejected source: 27,648,741
- Số dòng canonical labeled: 1,345,350
- Khóa null/trùng: 0 / 0
- Giá trị vô cực: 0
- Coverage state_code: 1.0
- Tỷ lệ parse issue_d: 1.0
- Target counts: {'0': 1076751, '1': 268599}
- Baseline feature count: 106
- Dictionary coverage: 1.0
- Khoản vay unresolved đã loại khỏi nhãn: 915,351
