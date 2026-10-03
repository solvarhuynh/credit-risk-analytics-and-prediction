# Hướng dẫn thuyết trình EDA — Lending Club

**Báo cáo EDA chi tiết:** [reports/eda_report.md](../../eda_report.md)

EDA là viết tắt của *Exploratory Data Analysis*, nghĩa là phân tích khám phá dữ liệu trước khi train model.

Năm biểu đồ này trả lời năm câu hỏi khác nhau:

- Khoản vay thường có quy mô như thế nào?
- Nhóm default và non-default khác nhau về DTI ra sao?
- FICO có liên hệ thế nào với default?
- Khi xem FICO và DTI cùng lúc thì pattern rủi ro có rõ hơn không?
- Số lượng khoản vay accepted thay đổi theo thời gian thế nào?

## Bộ năm biểu đồ cuối cùng

1. eda_01_loan_amount_distribution.png — Histogram — Loan Amount Distribution.
2. eda_02_dti_by_target.png — Boxplot — DTI Distribution by Target.
3. eda_03_default_by_fico.png — Bar chart — Observed Default Rate by FICO Band.
4. eda_04_fico_dti_heatmap.png — Heatmap — Observed Default Rate: FICO Band × DTI Band.
5. eda_05_accepted_loan_volume_over_time.png — Line chart — Accepted Loan Volume Over Time.

## EDA-01 — Loan Amount Distribution

### 1. Biểu đồ này dùng để trả lời câu hỏi gì?

Các khoản vay thường tập trung ở những khoảng số tiền nào?

### 2. Loại biểu đồ này là gì?

Đây là histogram. Biểu đồ chia loan amount thành nhiều khoảng rồi đếm số khoản vay rơi vào từng khoảng. Histogram phù hợp để xem phân bố và quy mô khoản vay, không phải để dự đoán default.

### 3. Trục X / Y / màu nghĩa là gì?

- Trục X: loan amount, tức số tiền vay.
- Trục Y: số lượng khoản vay trong mỗi khoảng.
- Màu: chỉ giúp phân biệt các cột, không phải một biến rủi ro.

### 4. Đọc biểu đồ này như thế nào?

1. Nhìn vùng có các cột cao nhất.
2. Xem dữ liệu trải rộng hay tập trung trong một vùng hẹp.
3. Chú ý các đỉnh riêng lẻ; khoản vay thường được cấp ở một số mức tiền phổ biến.

### 5. Insight chính

- Loan amount không phân bố đều giữa mọi khoảng.
- Một số mức hoặc khoảng tiền xuất hiện nhiều hơn các mức khác.
- Các đỉnh trên biểu đồ có thể xuất hiện vì khoản vay thường dùng các mức tiền phổ biến hoặc rời rạc; chưa có cơ sở để gọi đó là lỗi dữ liệu.

**Story connection:** Đây là phần mở đầu về cấu trúc danh mục, trước khi chuyển sang phân khúc người vay và rủi ro.

### 6. Tôi có thể nói gì khi thuyết trình?

“Ở biểu đồ đầu tiên, em xem quy mô các khoản vay trong dataset. Histogram cho thấy khoản vay không phân bố đều mà tập trung ở một số khoảng hoặc mức tiền phổ biến. Biểu đồ này giúp em hiểu portfolio trước khi chuyển sang các biến liên quan đến rủi ro. Em không dùng biểu đồ này để kết luận khoản vay lớn chắc chắn default.”

### 7. Điểm cần cẩn thận

- Đây là phân bố loan amount, không phải default rate.
- Không được nói các cột cao là nguyên nhân của default.
- Không gọi các đỉnh là lỗi nếu chưa có bằng chứng kiểm tra dữ liệu.

### 8. Thầy có thể hỏi gì?

- **Vì sao một số cột cao đột biến?**  
  Loan amount thường được cấp ở các mức phổ biến hoặc gần mức định sẵn, nên một số khoảng tự nhiên có nhiều khoản vay hơn.
- **Biểu đồ này có cho biết khoản vay nào rủi ro không?**  
  Chưa. Nó chỉ mô tả phân bố số tiền; cần kết hợp target hoặc model để phân tích rủi ro.

## EDA-02 — DTI Distribution by Target

### 1. Biểu đồ này dùng để trả lời câu hỏi gì?

Phân bố DTI của nhóm default và non-default khác nhau như thế nào?

### 2. Loại biểu đồ này là gì?

Đây là boxplot. Boxplot phù hợp để so sánh vị trí trung tâm, độ phân tán và các giá trị xa giữa hai nhóm.

### 3. Trục X / Y / màu nghĩa là gì?

- Trục X: hai nhóm target, gồm Non-default và Default.
- Trục Y: DTI theo đơn vị phần trăm điểm, ghi là DTI (%).
- Đường giữa hộp: median, tức giá trị ở trung tâm của nhóm.
- Phần hộp: vùng tập trung chính của dữ liệu.
- Whiskers: phạm vi chính của dữ liệu ngoài phần hộp.

### 4. Đọc biểu đồ này như thế nào?

1. So sánh vị trí đường median giữa Default và Non-default.
2. So sánh chiều cao và độ rộng của hai hộp.
3. Xem whiskers để biết độ phân tán.
4. Nhớ rằng biểu đồ chỉ hiển thị DTI hợp lệ đến P99 = 38.35 để dễ đọc.

### 5. Insight chính

- Trong dữ liệu được hiển thị, nhóm Default có phân bố DTI trung tâm cao hơn nhóm Non-default.
- Hai nhóm có thể vẫn chồng lấn; DTI không tách hai nhóm một cách tuyệt đối.
- P99 = 38.35 chỉ là giới hạn hiển thị của biểu đồ. Giá trị gốc không bị xóa hoặc thay đổi.

**Story connection:** Biểu đồ nối phần tổng quan danh mục với phân khúc credit và bước phân tích rủi ro.

### 6. Tôi có thể nói gì khi thuyết trình?

“Ở biểu đồ này, em so sánh DTI giữa hai nhóm non-default và default bằng boxplot. Đường giữa hộp là median, còn phần hộp và whiskers cho biết độ phân tán. Trong dữ liệu đang quan sát, nhóm default có DTI trung tâm cao hơn. Tuy nhiên đây chỉ là association, không chứng minh DTI cao gây ra default. P99 chỉ được dùng để biểu đồ dễ đọc, không làm thay đổi dữ liệu gốc.”

### 7. Điểm cần cẩn thận

- Không nói DTI cao gây ra default.
- P99 cap chỉ áp dụng cho việc vẽ biểu đồ; không phải xóa các dòng khỏi dataset.
- DTI được hiển thị theo percentage-point values, không nhầm với một tỷ lệ đã đổi sang thang khác.

### 8. Thầy có thể hỏi gì?

- **Vì sao loại phần trên P99 khỏi hình?**  
  Không loại khỏi dataset. Chỉ giới hạn phần hiển thị để giá trị cực đoan không làm boxplot bị nén.
- **DTI cao có gây ra default không?**  
  Không thể kết luận như vậy. EDA này chỉ cho thấy association trong dữ liệu quan sát.

## EDA-03 — Observed Default Rate by FICO Band

### 1. Biểu đồ này dùng để trả lời câu hỏi gì?

Observed default rate thay đổi như thế nào giữa các nhóm FICO?

### 2. Loại biểu đồ này là gì?

Đây là bar chart. Bar chart phù hợp để so sánh một chỉ số giữa các nhóm có thứ tự rõ ràng.

### 3. Trục X / Y / màu nghĩa là gì?

- Trục X: các FICO band theo thứ tự <650, 650-699, 700-749, 750+.
- Trục Y: observed default rate.
- Mỗi cột: trung bình của target trong một FICO band.
- Vì target = 1 là default và target = 0 là non-default, mean(target) chính là tỷ lệ default quan sát được.
- Nhãn n trên chart là số quan sát của nhóm.

### 4. Đọc biểu đồ này như thế nào?

1. Đọc FICO từ thấp lên cao.
2. Kiểm tra số quan sát của từng nhóm.
3. So sánh chiều cao các cột đủ mẫu.
4. Không diễn giải nhóm có n dưới 100 như một rate ổn định.

### 5. Insight chính

- Với các nhóm đủ mẫu, observed default rate có xu hướng giảm khi FICO band tăng.
- Nhóm <650 chỉ có n = 2 nên được xử lý là Insufficient sample và không được diễn giải về tỷ lệ.
- FICO là một tín hiệu tóm tắt creditworthiness quanh thời điểm origination, nhưng FICO một mình không quyết định default.

**Story connection:** Đây là bước chuyển từ credit segmentation sang so sánh rủi ro và bối cảnh cho model features.

### 6. Tôi có thể nói gì khi thuyết trình?

“Biểu đồ này so sánh observed default rate theo bốn nhóm FICO. Vì target bằng 1 là default và bằng 0 là non-default nên trung bình target có thể đọc như default rate. Với các nhóm đủ lớn, em quan sát thấy FICO cao hơn đi kèm default rate thấp hơn. Riêng nhóm dưới 650 chỉ có hai quan sát, nên em không diễn giải cột này vì tỷ lệ sẽ rất không ổn định.”

### 7. Điểm cần cẩn thận

- Không dùng nhóm <650 để kết luận vì chỉ có n = 2.
- Không nói FICO cao đảm bảo không default.
- Đây là observed association, không phải quan hệ nhân quả.
- Quy tắc minimum group size là 100.

### 8. Thầy có thể hỏi gì?

- **Vì sao không dùng nhóm <650?**  
  Vì nhóm này chỉ có hai quan sát, nên phần trăm tính ra không ổn định và dễ gây hiểu lầm.
- **FICO cao có nghĩa là chắc chắn không default không?**  
  Không. Nhóm FICO cao hơn chỉ có observed default rate thấp hơn; vẫn có thể có khoản default.

## EDA-04 — Observed Default Rate: FICO Band × DTI Band

### 1. Biểu đồ này dùng để trả lời câu hỏi gì?

Các tổ hợp FICO và DTI khác nhau có observed default rate như thế nào?

### 2. Loại biểu đồ này là gì?

Đây là heatmap. Mỗi ô là một nhóm kết hợp của hai biến, còn màu đậm hoặc nhạt thể hiện mức observed default rate. Heatmap giúp xem pattern hai chiều mà biểu đồ FICO đơn lẻ không thể hiện đầy đủ.

### 3. Trục X / Y / màu nghĩa là gì?

- Hàng: FICO band.
- Cột: DTI band, gồm <=10, 10-20, 20-30, >30.
- Màu trong ô: observed default rate.
- n trong ô: số quan sát của tổ hợp đó.
- Ô trống hoặc bị mask: chưa đủ 100 quan sát để diễn giải an toàn.

### 4. Đọc biểu đồ này như thế nào?

1. Đọc ngang một hàng để xem DTI thay đổi thế nào trong cùng FICO band.
2. Đọc dọc một cột để xem FICO thay đổi thế nào trong cùng DTI band.
3. So sánh màu cùng thang đo và luôn nhìn thêm n.
4. Không suy luận từ một ô rất ít dữ liệu.

### 5. Insight chính

- So với EDA-03, heatmap cho phép xem FICO và DTI cùng lúc.
- Trong các nhóm có đủ mẫu, DTI cao hơn thường đi cùng observed default rate cao hơn khi so sánh trong FICO tương đương.
- Trong các nhóm có đủ mẫu, FICO cao hơn thường đi cùng observed default rate thấp hơn khi so sánh trong DTI tương đương.
- Hàng <650 có thể trống vì không đạt minimum cell count, không phải do lỗi vẽ.

**Story connection:** Biểu đồ mở rộng segmentation một chiều thành risk matrix, tạo cầu nối tới phân tích drill-down trên dashboard.

### 6. Tôi có thể nói gì khi thuyết trình?

“EDA-03 chỉ nhìn FICO riêng lẻ, còn heatmap này xem FICO và DTI cùng lúc. Mỗi hàng là một FICO band, mỗi cột là một DTI band, màu thể hiện observed default rate và n cho biết số quan sát. Trong những ô đủ mẫu, DTI cao hơn thường đi cùng rate cao hơn, còn FICO cao hơn thường đi cùng rate thấp hơn. Các ô ít hơn 100 quan sát được để trống để tránh diễn giải quá mức.”

### 7. Điểm cần cẩn thận

- Minimum cell count là 100.
- Ô trống không có nghĩa là default rate bằng 0.
- Không nói FICO hoặc DTI gây ra default.
- Một ô riêng lẻ không nên được dùng để kết luận cho toàn bộ danh mục.

### 8. Thầy có thể hỏi gì?

- **Vì sao heatmap mạnh hơn bar chart FICO?**  
  Vì heatmap xem được hai chiều FICO và DTI cùng lúc, thay vì chỉ xem một biến.
- **Vì sao có ô trống?**  
  Vì ô đó có ít hơn 100 quan sát, nên hệ thống không hiển thị rate để tránh kết luận không ổn định.

## EDA-05 — Accepted Loan Volume Over Time

### 1. Biểu đồ này dùng để trả lời câu hỏi gì?

Số khoản vay accepted/issued thay đổi theo tháng như thế nào?

### 2. Loại biểu đồ này là gì?

Đây là line chart. Line chart phù hợp để theo dõi volume theo thứ tự thời gian và nhìn xu hướng cùng dao động giữa các tháng.

### 3. Trục X / Y / màu nghĩa là gì?

- Trục X: tháng origination.
- Trục Y: số lượng khoản vay accepted.
- Mỗi điểm hoặc đoạn nối: volume accepted trong một tháng.
- Đây là volume, không phải default rate.
- Nguồn là toàn bộ accepted loans từ data/interim/loan_application.parquet.

### 4. Đọc biểu đồ này như thế nào?

1. Đọc từ tháng đầu tiên sang tháng cuối cùng.
2. So sánh mức volume ở giai đoạn đầu, giữa và cuối.
3. Chú ý xu hướng tổng thể và các dao động theo tháng.
4. Không gán nguyên nhân kinh tế hoặc kinh doanh nếu chưa có bằng chứng riêng.

### 5. Insight chính

- Volume ở những năm đầu thấp hơn.
- Volume tăng mạnh theo thời gian.
- Các giai đoạn sau có volume cao hơn nhưng vẫn có dao động giữa các tháng.
- Biểu đồ dùng toàn bộ accepted loans, không chỉ dùng các khoản đã resolve target.

**Story connection:** Đây là bối cảnh thời gian của portfolio, giúp người xem hiểu quy mô trước khi đi vào risk analysis.

### 6. Tôi có thể nói gì khi thuyết trình?

“Biểu đồ cuối cùng theo dõi số khoản vay accepted theo tháng. Em dùng line chart vì dữ liệu có thứ tự thời gian. Nguồn là loan_application.parquet và bao gồm toàn bộ accepted loans, nên biểu đồ phản ánh volume origination chứ không phải chỉ những khoản đã có target cuối cùng. Có thể quan sát volume thấp ở giai đoạn đầu và tăng mạnh về sau, nhưng em không tự suy ra nguyên nhân của xu hướng này.”

### 7. Điểm cần cẩn thận

- Không dùng cleaned_dataset.parquet resolved-only để trả lời câu hỏi tổng volume accepted.
- Không diễn giải các tháng gần đây thấp dựa trên resolved-only data.
- Default-rate trend theo origination month đã không được dùng trong bộ static EDA này vì maturity/selection bias: khoản vay mới chưa có đủ thời gian để biết outcome cuối.

### 8. Thầy có thể hỏi gì?

- **Vì sao dùng interim thay vì cleaned_dataset?**  
  Vì câu hỏi là tổng số accepted loans. Bảng application chứa toàn bộ accepted loans, còn cleaned_dataset chỉ chứa các khoản có outcome đã resolve để modeling.
- **Vì sao bỏ default rate theo tháng?**  
  Các khoản vay mới chưa có đủ thời gian để biết outcome cuối; nếu chỉ lấy các khoản đã resolved, những tháng gần đây sẽ không đại diện đầy đủ.

# Tóm tắt 5 EDA trong 1 phút

| EDA | Tôi đang xem gì? | Điều cần nhớ |
|---|---|---|
| EDA-01 | Phân bố số tiền vay | Khoản vay tập trung ở một số mức phổ biến. |
| EDA-02 | DTI của default và non-default | Nhóm default có DTI trung tâm cao hơn trong dữ liệu hiển thị. |
| EDA-03 | FICO và observed default rate | Nhóm FICO cao hơn thường có rate thấp hơn khi đủ mẫu. |
| EDA-04 | FICO kết hợp DTI | Hai biến cùng lúc tạo ra cách nhìn phân tầng rủi ro chi tiết hơn. |
| EDA-05 | Loan volume theo thời gian | Số khoản accepted tăng mạnh qua các giai đoạn. |

# Cách nhớ nhanh khi đứng thuyết trình

- EDA-01: Tiền vay phân bố thế nào?
- EDA-02: Nhóm default khác nhóm thường ở DTI thế nào?
- EDA-03: FICO liên hệ với default thế nào?
- EDA-04: Nếu nhìn FICO và DTI cùng lúc thì sao?
- EDA-05: Quy mô cho vay thay đổi theo thời gian thế nào?

Chuỗi ghi nhớ là: **Distribution → Compare groups → One risk variable → Two risk variables → Time trend**.

Nói bằng tiếng Việt: **xem phân bố → so sánh nhóm → xem một biến rủi ro → xem hai biến rủi ro → xem xu hướng thời gian**.

# Thuật ngữ cần nhớ

- **EDA:** phân tích khám phá dữ liệu trước khi xây model.
- **Default:** khoản vay được ghi nhận là kết quả xấu; trong target, giá trị là 1.
- **Non-default:** khoản vay không default; trong target, giá trị là 0.
- **Target:** câu trả lời mà model học; ở đây là 0 hoặc 1.
- **DTI:** tỷ lệ nghĩa vụ nợ so với thu nhập; trong hình được hiển thị theo DTI (%).
- **FICO:** điểm tóm tắt mức độ tín nhiệm tín dụng.
- **Default rate:** tỷ lệ quan sát được của target = 1 trong một nhóm.
- **Distribution:** cách các giá trị trải ra và tập trung.
- **Median:** giá trị ở giữa khi sắp xếp một nhóm.
- **Percentile / P99:** ngưỡng mà 99% giá trị hợp lệ nằm tại hoặc dưới đó; P99 ở hình DTI là 38.35.
- **Heatmap:** ma trận màu, trong đó mỗi ô là một nhóm kết hợp hai biến.
- **Origination:** thời điểm khoản vay được khởi tạo hoặc phát hành.
- **Association:** hai đặc điểm xuất hiện cùng nhau trong dữ liệu.
- **Causation:** quan hệ nguyên nhân-kết quả; EDA này không chứng minh causation.
- **Maturity bias / resolved-outcome bias:** sai lệch do khoản vay mới chưa đủ thời gian để có outcome cuối, khiến nhóm resolved không đại diện đầy đủ cho các tháng gần đây.

# Những câu không nên nói khi thuyết trình

| Không nên nói | Nên nói |
|---|---|
| “DTI cao gây ra default.” | “Trong dữ liệu này, nhóm có DTI cao hơn có xu hướng ghi nhận default rate cao hơn.” |
| “FICO 750+ chắc chắn không default.” | “Nhóm FICO cao hơn có observed default rate thấp hơn, nhưng vẫn có thể có khoản default.” |
| “Nhóm <650 có default rate đáng tin cậy.” | “Nhóm <650 chỉ có n = 2 nên không đủ mẫu để diễn giải.” |
| “Loan volume giảm cuối kỳ vì Lending Club cho vay ít hơn.” | “Biểu đồ volume phải được đọc theo dữ liệu accepted; không tự suy ra nguyên nhân khi chưa có bằng chứng.” |
| “P99 đã xóa các giá trị DTI cực đoan.” | “P99 chỉ giới hạn phần hiển thị của boxplot, không thay đổi dữ liệu gốc.” |

# Cheat sheet trước khi vào thuyết trình

- Dataset: Lending Club 2007–2018.
- EDA dùng 5 loại biểu đồ bổ sung cho nhau.
- EDA là mô tả/khám phá, không phải bằng chứng nhân quả.
- Association không đồng nghĩa với causation.
- Target 0 = non-default; target 1 = default.
- P99 DTI = 38.35 chỉ áp dụng cho phần hiển thị.
- FICO <650 có n = 2, không đủ mẫu để diễn giải.
- Heatmap chỉ hiển thị cell có tối thiểu n = 100.
- Xu hướng accepted loan volume dùng toàn bộ accepted applications.
- Khoản vay mới chưa resolve bị loại khỏi dữ liệu target canonical cho modeling.
- Khi nói insight, dùng “quan sát thấy” hoặc “có liên hệ”, không dùng “chắc chắn” hay “gây ra”.
