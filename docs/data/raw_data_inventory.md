# Kiểm kê dữ liệu gốc (`data/raw`)

Ngày kiểm tra: 13/09/2026. Thư mục này là bộ dữ liệu **Home Credit Default Risk**.

## Cấu trúc thư mục dữ liệu

![Cấu trúc thư mục `data`, với các tệp nguồn trong `raw`](image.png)

*Hình: Các bảng CSV nguồn được lưu trong `data/raw`; dữ liệu trung gian và đã xử lý lần lượt thuộc `data/interim` và `data/processed`.*

## Danh mục từng tệp

| Tệp | Kích thước hiện tại | Khóa/liên kết | Vai trò | Quyết định |
| --- | ---: | --- | --- | --- |
| `application_train.csv` | 158.44 MB | `SK_ID_CURR` | Bảng trung tâm, một hồ sơ vay hiện tại mỗi dòng, chứa nhãn `TARGET` và các biến hồ sơ. | **Giữ bắt buộc** |
| `application_test.csv` | 25.34 MB | `SK_ID_CURR` | Cùng schema với train trừ `TARGET`; dùng tính điểm ngoài mẫu/Kaggle. | Giữ có điều kiện |
| `bureau.csv` | 162.14 MB | `SK_ID_CURR`, `SK_ID_BUREAU` | Các khoản tín dụng tại tổ chức tín dụng khác. Tạo feature dư nợ, số khoản vay, trạng thái khoản vay. | **Giữ** |
| `bureau_balance.csv` | 358.19 MB | `SK_ID_BUREAU` → `bureau` | Trạng thái tín dụng theo tháng của từng bản ghi bureau. Không join trực tiếp vào application; aggregate theo `SK_ID_BUREAU`, rồi qua `bureau` về `SK_ID_CURR`. | **Giữ** (mở rộng) |
| `previous_application.csv` | 386.21 MB | `SK_ID_CURR`, `SK_ID_PREV` | Các đơn vay trước tại Home Credit: kết quả duyệt, số tiền, sản phẩm. | **Giữ** |
| `installments_payments.csv` | 689.62 MB | `SK_ID_PREV`, `SK_ID_CURR` | Lịch sử trả góp theo kỳ; nguồn chính cho feature trả trễ/chênh lệch thanh toán. | **Giữ** |
| `POS_CASH_balance.csv` | 374.51 MB | `SK_ID_PREV`, `SK_ID_CURR` | Số dư và quá hạn hàng tháng của khoản POS/cash. | **Giữ** (mở rộng) |
| `credit_card_balance.csv` | 404.91 MB | `SK_ID_PREV`, `SK_ID_CURR` | Số dư, hạn mức, chi tiêu, thanh toán và quá hạn của thẻ tín dụng. | **Giữ** (mở rộng) |
| `HomeCredit_columns_description.csv` | 0.04 MB | Tên bảng/cột | Data dictionary từ nguồn, giải nghĩa cột và giá trị đặc biệt. | **Giữ bắt buộc** |

`data/raw/.gitkeep` là tệp kỹ thuật để Git giữ thư mục rỗng; giữ nguyên.

## Mức tối thiểu theo mục tiêu

| Mục tiêu | Tệp nên có |
| --- | --- |
| MVP đúng yêu cầu đồ án (ít nhất 3 bảng) | `application_train.csv`, `previous_application.csv`, `installments_payments.csv`, `HomeCredit_columns_description.csv` |
| Mô hình/EDA đầy đủ | Toàn bộ trừ `sample_submission.csv`; thêm `application_test.csv` nếu cần suy luận ngoài mẫu |
| Nộp Kaggle hoặc xuất điểm cho test | Mô hình/EDA đầy đủ + `application_test.csv` + `sample_submission.csv` |

Mặc dù có thể dựng MVP từ ba bảng, `bureau.csv` nên được ưu tiên thêm sớm vì nó là nguồn lịch sử tín dụng bên ngoài quan trọng. Các bảng `bureau_balance`, `POS_CASH_balance`, và `credit_card_balance` là phần mở rộng có dung lượng lớn nhưng không dư thừa: chúng bổ sung trạng thái theo thời gian mà bảng cha không có.

## Quy tắc join để không sinh dữ liệu dư/lỗi

1. Lấy `application_train` hoặc `application_test` làm bảng gốc, hạt dữ liệu là một `SK_ID_CURR`.
2. Với mọi bảng lịch sử nhiều dòng, aggregate về `SK_ID_CURR` trước khi left join vào application.
3. Riêng `bureau_balance` phải aggregate về `SK_ID_BUREAU`, join vào `bureau`, rồi mới aggregate về `SK_ID_CURR`.
4. Không nối thẳng các bảng lịch sử với nhau theo `SK_ID_CURR`; cách đó nhân bản số dòng và tạo feature sai.
5. Sau mỗi join, kiểm tra số dòng và tính duy nhất của `SK_ID_CURR`; nguyên tắc này cũng khớp với [data contract](../contracts/data_contract.md).
