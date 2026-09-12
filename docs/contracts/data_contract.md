# Giao ước dữ liệu — TV2 → TV1 và TV3

## Tệp bàn giao

- `data/processed/cleaned_dataset.parquet`: một dòng trên một `SK_ID_CURR`.
- `data/processed/data_dictionary.csv`: cột, kiểu, nguồn, công thức, đơn vị và mô tả.
- CSV có thể xuất thêm cho dashboard; Parquet là định dạng nội bộ ưu tiên.

## Cột tối thiểu

| Nhóm | Cột |
| --- | --- |
| Khóa/nhãn | `SK_ID_CURR`, `TARGET` |
| Khoản vay | `AMT_INCOME_TOTAL`, `AMT_CREDIT`, `AMT_ANNUITY`, `AMT_GOODS_PRICE` |
| Nhân khẩu | `CODE_GENDER`, `NAME_CONTRACT_TYPE`, `AGE_YEARS`, `AGE_GROUP` |
| Derived | `ANNUITY_TO_INCOME_RATIO`, `CREDIT_TO_INCOME_RATIO`, `EMPLOYED_YEARS`, `DAYS_EMPLOYED_ANOM` |
| Aggregate | tiền tố nguồn: `BUREAU_`, `PREV_`, `INSTAL_`, `POS_`, `CC_` |

## Quality gate

1. `SK_ID_CURR` không null và duy nhất; `TARGET` chỉ 0/1.
2. Aggregate bảng 1-nhiều trước left join; báo cáo số dòng trước/sau.
3. `DAYS_EMPLOYED == 365243` thành missing và giữ anomaly flag.
4. Không có `inf`, sentinel như `NULL`/`-999`, hay cột duplicate.
5. Mẫu số bằng 0 trong feature ratio cho missing, không cho vô cực.
6. Mỗi feature có nguồn và lý do hợp lệ tại thời điểm xét duyệt.

TV1 chỉ fit imputer/encoder trên train fold.
