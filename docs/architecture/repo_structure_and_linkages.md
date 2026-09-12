# Kiến trúc repository và luồng bàn giao

## Quyết định kỹ thuật

Dashboard chính là **Power BI**. Đây là lựa chọn sát với môi trường doanh nghiệp: semantic model, Power Query, DAX, role-based sharing và khả năng phân phối báo cáo. Python chịu trách nhiệm pipeline, train và xuất bảng điểm; Power BI là lớp tiêu thụ/ra quyết định.

## Cây thư mục chuẩn

```text
ttdltq/
├── data/{raw,interim,processed}    # local-only
├── dashboard/{Credit_Risk_Analytics.pbix,assets/}  # TV3
├── docs/{architecture,contracts,overview,tasks}
├── models/                         # local-only artifacts
├── notebooks/                      # minh họa, không chứa logic dùng lại
├── reports/{figures,slides,video}
└── src/{data,features,models,dashboard}
```

Logic dùng lại nằm ở `src/`; notebook gọi lại logic đó để minh họa và xuất hình.

## Luồng

```text
raw CSV → validation → clean + aggregate theo SK_ID_CURR → features
→ cleaned_dataset.parquet → train/evaluate → model + scored_dataset.parquet
→ Power BI dashboard + report
```

Mọi bảng 1-nhiều phải aggregate trước left join vào application. Sau mỗi join, kiểm tra lại số dòng và tính duy nhất của `SK_ID_CURR`.

## Bàn giao

| Thành phần | Chủ sở hữu | Đầu ra |
| --- | --- | --- |
| Data pipeline | TV2 | cleaned dataset, data dictionary, quality report |
| Modeling | TV1 | pipeline artifact, scored dataset, metrics/model card |
| Dashboard | TV3 | `.pbix`, hướng dẫn refresh, ảnh demo |
| Report/demo | cả nhóm | report, slide, video backup |

Quy định tên cột và kiểm thử nằm trong `docs/contracts/`; không tự phát schema trong notebook.
