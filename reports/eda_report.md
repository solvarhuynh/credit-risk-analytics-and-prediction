# Báo cáo phân tích khám phá dữ liệu (EDA) chuẩn tắc

**Mã nhiệm vụ:** TV2-DE-07 — Phân tích khám phá dữ liệu và bàn giao kỹ thuật dữ liệu
**Bên tạo:** Thành viên 2 (TV2) — Kỹ thuật dữ liệu và pipeline dữ liệu
**Bên sử dụng:** Thành viên 1 (TV1 — Mô hình hóa), Thành viên 3 (TV3 — Dashboard và ứng dụng)
**Thời điểm tạo (UTC):** 2026-09-20 16:25:40Z
**Môi trường thực thi:** Python 3.13.5 (virtual environment nghiêm ngặt)

---

## 1. Phạm vi và nguồn dữ liệu

Báo cáo này ghi nhận phân tích khám phá dữ liệu (EDA) chuẩn tắc trên dataset khách hàng Home Credit đã xuất bản. Phân tích đánh giá hồ sơ nhân khẩu, tỷ lệ tài chính, biến đại diện rủi ro bên ngoài và các phép tổng hợp lịch sử bureau/giao dịch trên quần thể có nhãn.

- **Nguồn phân tích chính:** `data/processed/cleaned_dataset.parquet` (quần thể có nhãn chuẩn tắc, tạo từ `application_train.csv`).
- **Nguồn dữ liệu thô đối chiếu làm sạch:** `data/raw/application_train.csv` (chỉ dùng để kiểm tra biến đổi sentinel `DAYS_EMPLOYED`).
- **Ranh giới phạm vi:** `application_test.csv` (48,744 dòng không có nhãn thực tế) bị loại hoàn toàn khỏi mọi profiling để tránh leakage và nhiễm nhãn.

---

## 2. Tính bất biến và kích thước dataset chuẩn tắc

- **Đường dẫn dataset chuẩn:** `data/processed/cleaned_dataset.parquet`
- **Kích thước:** 307,511 dòng × 203 cột
- **Checksum SHA-256 dataset:** `e3cbf594a5a0a072fc1625baa11563c323b8c392afc90cb46bb17bf48c12de75`
- **Checksum SHA-256 manifest:** `e633885a14ad70b7f153cc27587722c77ee6c5b73ac03495872755df7a73d3f7`
- **Checksum SHA-256 từ điển dữ liệu:** `efd1d1e1ad268f12ee38a901602f707a76b07a3b581ba99c25df9f6bd188ec39`
- **Trạng thái toàn vẹn:** bất biến từng byte so với đường cơ sở ban đầu đã xác minh (DE-05 và DE-06).

---

## 3. Phân phối TARGET và mất cân bằng lớp

- **Nhãn thực tế:** `TARGET` ((0, 1)), trong đó `1` là khách hàng gặp khó khăn thanh toán (trễ hơn X ngày ở ít nhất một kỳ trả góp).
- **Không vỡ nợ (TARGET = 0):** 282,686 khách hàng (91.9271%)
- **Vỡ nợ (TARGET = 1):** 24,825 khách hàng (8.0729%)
- **Tỷ lệ vỡ nợ quan sát:** **8.0729%**
- **Tỷ lệ mất cân bằng:** khoảng 11.39 : 1. Bắt buộc dùng cross-validation phân tầng cho mô hình hóa hạ nguồn.

---

## 4. Phương pháp và xử lý giá trị khuyết

1. **Khuyết thiếu trung thực:** EDA không impute toàn cục. Giá trị khuyết được đánh giá ở trạng thái tự nhiên.
2. **Chính sách lịch sử được duyệt:** 18 feature count lịch sử của khách hàng không khớp được điền 0 theo contract DE-05. Tỷ lệ và số tiền tài chính giữ khuyết thật (`NaN`).
3. **Cắt chỉ để hiển thị:** Khi phân phối lệch phải quá mạnh, chỉ bản sao dùng vẽ biểu đồ được clip và phải ghi rõ ngưỡng cùng số quan sát bị loại khỏi hình.
4. **Nguyên tắc không suy diễn nhân quả:** mọi kết quả là liên hệ thống kê và phân phối quan sát; không đưa ra kết luận nhân quả.

---

## 5. Biểu đồ chi tiết và phát hiện thực nghiệm

### 5.1. Hình 01: Phân phối thu nhập theo TARGET

- **Tệp tạo tác:** `reports/figures/eda/01_income_distribution_by_target.png`
- **Mục tiêu:** đánh giá phân phối `AMT_INCOME_TOTAL` giữa hồ sơ không vỡ nợ và vỡ nợ.
- **Bằng chứng thực nghiệm (N hiệu dụng = 307,511, khuyết: 0):**
  * **TARGET = 0 (không vỡ nợ, N = 282,686):**
    - Trung vị: **148,500.0 CZK**
    - Khoảng tứ phân vị (IQR): **90,000.0 CZK** (Q25: 112,500.0, Q75: 202,500.0)
  * **TARGET = 1 (vỡ nợ, N = 24,825):**
    - Trung vị: **135,000.0 CZK**
    - Khoảng tứ phân vị (IQR): **90,000.0 CZK** (Q25: 112,500.0, Q75: 202,500.0)
- **Ghi chú cắt chỉ để hiển thị:** Panel B cắt thu nhập tại phân vị 99 (**472,500 CZK**), loại 3,014 quan sát (0.98%) khỏi biểu đồ mật độ. Dataset chuẩn không bị cắt.
- **Quan sát chính:** nhóm vỡ nợ có thu nhập trung vị thấp hơn nhẹ (135,000 so với 148,500 CZK, chênh 13,500 CZK hay khoảng 9.1%), nhưng khoảng thu nhập chồng lấn đáng kể. Thu nhập đơn lẻ không quyết định rủi ro tín dụng.

---

### 5.2. Hình 02: Tỷ lệ vỡ nợ quan sát theo nhóm tuổi

- **Tệp tạo tác:** `reports/figures/eda/02_default_rate_by_age_group.png`
- **Mục tiêu:** phân tích xác suất vỡ nợ theo nhóm tuổi bằng feature phái sinh chuẩn `AGE_GROUP` (tạo từ `AGE_YEARS` với biên [0, 25, 35, 45, 55, 65, 120], `right=False`).
- **Quy tắc chia nhóm:** biên cố định `[0, 25, 35, 45, 55, 65, 120]` năm với `right=False`.
- **Bằng chứng thực nghiệm (N hiệu dụng = 307,511, khuyết: 0, ngoài miền: 0):**

| Nhóm tuổi | Tổng hồ sơ (N) | Vỡ nợ | Không vỡ nợ | Tỷ lệ vỡ nợ quan sát (%) |
| :--- | :--- | :--- | :--- | :--- |
| **Under 25** | 12,233 | 1,504 | 10,729 | **12.29%** |
| **25-34** | 72,429 | 7,721 | 64,708 | **10.66%** |
| **35-44** | 84,261 | 7,085 | 77,176 | **8.41%** |
| **45-54** | 70,190 | 4,946 | 65,244 | **7.05%** |
| **55-64** | 60,522 | 3,281 | 57,241 | **5.42%** |
| **65+** | 7,876 | 288 | 7,588 | **3.66%** |

- **Đối soát:**
  * Tổng khách hàng: **307,511** (khớp N chuẩn = 307,511)
  * Tổng vỡ nợ: **24,825** (khớp số TARGET=1 = 24,825)
  * Tổng không vỡ nợ: **282,686** (khớp số TARGET=0 = 282,686)
  * Kiểm tra đồng nhất: 24,825 (vỡ nợ) + 282,686 (không vỡ nợ) == 307,511 (khách hàng).
- **Quan sát chính:** tỷ lệ vỡ nợ giảm dần qua các nhóm tuổi:
  * Nhóm trẻ nhất (`Under 25`): **12.29%** (1.52 lần đường cơ sở danh mục).
  * Nhóm lớn tuổi nhất (`65+`): **3.66%** (0.45 lần đường cơ sở danh mục).
  * Trong quần thể lịch sử này, nhóm lớn tuổi có tỷ lệ vỡ nợ quan sát thấp hơn ở các nhóm cố định.

---

### 5.3. Hình 03: Tỷ lệ vỡ nợ theo nghề nghiệp và loại hợp đồng

- **Tệp tạo tác:** `reports/figures/eda/03_default_rate_by_occupation_and_contract.png`
- **Mục tiêu:** đánh giá khác biệt tỷ lệ vỡ nợ giữa 19 nhóm nghề nghiệp và các loại hợp đồng vay.
- **Bằng chứng theo loại hợp đồng (N = 307,511):**
  * **Cash loans:** N = 278,232 | Tỷ lệ vỡ nợ: **8.35%**
  * **Revolving loans:** N = 29,279 | Tỷ lệ vỡ nợ: **5.48%**
- **Bằng chứng theo nghề nghiệp (N = 307,511):**
  * **Nhóm rủi ro cao nhất:**
    - `Low-skill Laborers`: N = 2,093 | Tỷ lệ: **17.15%**
    - `Drivers`: N = 18,603 | Tỷ lệ: **11.33%**
    - `Waiters/barmen staff`: N = 1,348 | Tỷ lệ: **11.28%**
  * **Nhóm rủi ro thấp nhất:**
    - `Accountants`: N = 9,813 | Tỷ lệ: **4.83%**
    - `High skill tech staff`: N = 11,380 | Tỷ lệ: **6.16%**
  * **Khuyết thiếu tường minh:** nhóm `Missing/Unknown` gồm **96,391** khách hàng (31.35%), có tỷ lệ vỡ nợ quan sát **6.51%** (thấp hơn trung bình danh mục). Cần giữ giá trị khuyết như một nhóm riêng khi mô hình hóa; không được suy diễn nhân khẩu hay việc làm chỉ từ giá trị khuyết.

---

### 5.4. Hình 04: Heatmap tương quan hạng Spearman

- **Tệp tạo tác:** `reports/figures/eda/04_key_numeric_spearman_heatmap.png`
- **Mục tiêu:** đánh giá quan hệ đơn điệu giữa 12 feature số nghiệp vụ chính mà không chọn theo TARGET (`TARGET` được loại).
- **Liên hệ hạng Spearman mạnh (|ρ| >= 0.70):**
*Lưu ý: ngưỡng |ρ| >= 0.70 chỉ dùng để mô tả liên hệ hạng đơn điệu, không phải bằng chứng thống kê chính thức về đa cộng tuyến hay dư thừa để tự động loại feature.*
- `AMT_CREDIT` <-> `AMT_ANNUITY`: Spearman ρ = 0.8302
- `AMT_CREDIT` <-> `AMT_GOODS_PRICE`: Spearman ρ = 0.9849
- `AMT_CREDIT` <-> `CREDIT_TO_INCOME_RATIO`: Spearman ρ = 0.7523
- `AMT_ANNUITY` <-> `AMT_GOODS_PRICE`: Spearman ρ = 0.8280
- `AMT_GOODS_PRICE` <-> `CREDIT_TO_INCOME_RATIO`: Spearman ρ = 0.7346
- `CREDIT_TO_INCOME_RATIO` <-> `ANNUITY_TO_INCOME_RATIO`: Spearman ρ = 0.7939
- **Hàm ý mô hình hóa cho TV1:**
  * `AMT_CREDIT` và `AMT_GOODS_PRICE` có liên hệ hạng rất mạnh (ρ = 0.9849) vì khoản credit thường bám theo giá hàng được tài trợ.
  * Tương quan Spearman từng cặp chỉ đo liên hệ đơn điệu; không chứng minh tương đương tuyến tính, đa cộng tuyến hay dư thừa cần tự động loại.
  * TV1 nên đánh giá dư thừa bằng validation chỉ trên dữ liệu huấn luyện, độ ổn định hệ số, VIF phù hợp trên fold huấn luyện, regularization (Ridge/L2) và hiệu năng ngoài mẫu.
  * Mô hình gradient boosting dạng cây (LightGBM/XGBoost) tự phân vùng các feature có liên hệ hạng.

---

### 5.5. Hình 05: Kiểm tra làm sạch sentinel DAYS_EMPLOYED

- **Tệp tạo tác:** `reports/figures/eda/05_days_employed_before_after.png`
- **Mục tiêu:** xác thực cổng làm sạch sentinel DE-02.
- **Kết quả kiểm tra (N = 307,511):**
  * **Số sentinel thô (`DAYS_EMPLOYED == 365243`):** **55,374** quan sát (18.0072% dataset thô).
  * **Số sentinel còn lại trong dataset chuẩn:** **0** (đã loại 100%).
  * **Số khuyết sau làm sạch (`NaN` trong `DAYS_EMPLOYED`):** **55,374** (khớp 1-1 với sentinel đã loại).
  * **Số cờ bất thường (`DAYS_EMPLOYED_ANOM == 1`):** giữ lại **55,374** bản ghi chỉ báo.
  * **Biểu diễn ngày có dấu chuẩn:** giá trị `DAYS_EMPLOYED` hợp lệ không phải sentinel vẫn giữ dạng ngày có dấu (<=0). Đổi sang năm chỉ dùng để vẽ biểu đồ.
- **Giới hạn diễn giải:** `DAYS_EMPLOYED_ANOM` chỉ là cờ cho sentinel 365243 trong hồ sơ application; không được diễn giải là đã xác nhận nghỉ hưu hoặc thất nghiệp.

---

## 6. Insight nghiệp vụ và storytelling ban đầu

1. **Mẫu hình tuổi:** tỷ lệ vỡ nợ quan sát giảm theo các nhóm tuổi. Hồ sơ dưới 25 tuổi có tỷ lệ 12.29%, so với 3.66% ở nhóm 65+.
2. **Ý nghĩa bất thường việc làm:** hơn 18.0% quần thể có sentinel việc làm 365243. Đổi giá trị méo này thành NaN và giữ cờ nhị phân giúp bảo toàn chất lượng và tính số học.
3. **Liên hệ mạnh giữa quy mô tài chính:** số tiền vay, annuity và giá hàng có tương quan hạng rất cao (>0.82), phản ánh cách định cỡ khoản vay.

---

## 7. Giới hạn và tuyên bố không nhân quả

> [!IMPORTANT]
> **Tuyên bố không nhân quả:** mọi kết quả trong báo cáo phản ánh phân phối thực nghiệm và tương quan thống kê của dataset application lịch sử. Các liên hệ này **không hàm ý quan hệ nhân quả**. Không kết quả nào chứng minh “thu nhập thấp gây vỡ nợ” hoặc “tuổi trẻ gây vỡ nợ”.

---

## 8. Lệnh tái tạo

Để tái tạo cả năm hình, tính lại metric và cập nhật báo cáo một cách xác định:

```powershell
& .\.venv\Scripts\python.exe -m src.data.eda
```

---

## 9. Kiểm kê tạo tác chuẩn và trạng thái bất biến

| Đường dẫn tạo tác | Kích thước file | Checksum SHA-256 | Trạng thái bất biến |
| :--- | :--- | :--- | :--- |
| `data/processed/cleaned_dataset.parquet` | 64,213,549 byte | `e3cbf594a5a0a072fc1625baa11563c323b8c392afc90cb46bb17bf48c12de75` | **BẤT BIẾN** |
| `data/processed/cleaned_dataset_manifest.json` | 17,082 byte | `e633885a14ad70b7f153cc27587722c77ee6c5b73ac03495872755df7a73d3f7` | **BẤT BIẾN** |
| `data/processed/data_dictionary.csv` | 124,732 byte | `efd1d1e1ad268f12ee38a901602f707a76b07a3b581ba99c25df9f6bd188ec39` | **BẤT BIẾN** |
| `reports/figures/eda/01_income_distribution_by_target.png` | 400,315 byte | `263e84e199e9dc6cf8c2e26687c2cd636d7a9e527e439788d031f9a632b956e6` | Tạo tác đầu ra |
| `reports/figures/eda/02_default_rate_by_age_group.png` | 198,222 byte | `3d1b4352beb8862d815ebbcd2c8ff8758ff3c4872c5228dbb5478608742fc7df` | Tạo tác đầu ra |
| `reports/figures/eda/03_default_rate_by_occupation_and_contract.png` | 462,301 byte | `cb2826c968f08787e361b6cacf615552c4b6df7dca0947452fbf87e63eb88bb1` | Tạo tác đầu ra |
| `reports/figures/eda/04_key_numeric_spearman_heatmap.png` | 488,137 byte | `a7914f619916e59b445382359b14bfc429bc6de9fc559552a0c18f651ce5858b` | Tạo tác đầu ra |
| `reports/figures/eda/05_days_employed_before_after.png` | 295,138 byte | `d8a669f6094e8541002fc3babf88deae0860e0ca876c3b4a3ec2f696f4386315` | Tạo tác đầu ra |

---

## 10. Trạng thái sẵn sàng bàn giao

- **Bàn giao mô hình hóa cho TV1:** **SẴN SÀNG BÀN GIAO** (chờ bên sử dụng xác nhận)
- **Bàn giao dashboard cho TV3:** **SẴN SÀNG BÀN GIAO** (chờ bên sử dụng xác nhận)
- **Điều kiện DE-08:** **BỊ CHẶN** cho đến khi TV1 hoàn tất huấn luyện mô hình, tạo dự báo và phân tích ngưỡng.
