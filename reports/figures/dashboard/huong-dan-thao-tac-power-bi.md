# Hướng dẫn tạo và kiểm tra V02–V06 trong Power BI Desktop

## Cách tạo một biểu đồ

1. Chọn trang cần làm ở thanh tab dưới cùng. Nhấn một vùng trống trên canvas để bỏ chọn visual cũ.
2. Trong **Visualizations**, chọn đúng loại biểu đồ ghi ở phần hướng dẫn bên dưới.
3. Trong **Data/Build visual**, kéo trường vào đúng ô **X-axis**, **Y-axis**, **Values**, **Legend**, **Tooltips** hoặc **Groups**. Nếu Power BI tự chọn phép tổng hợp khác chỉ dẫn, mở menu cạnh tên trường và chọn **Sum**, **Average** hoặc **Don’t summarize** theo hướng dẫn.
4. Đổi tiêu đề trong **Format visual → General → Title**. Đổi nhãn field chỉ trong visual bằng menu field → **Rename for this visual**; không đổi tên cột dùng chung trong model.
5. Sắp xếp bằng menu **…** ở góc biểu đồ → **Sort by** → chọn trường/measures được nêu → **Descending** hoặc **Ascending**.
6. Chọn biểu đồ rồi vào **Format visual → General → Properties → Position/Size** để đặt nó vào đúng khu vực trang. Giữ nền sáng, chữ dễ đọc và tránh để nhãn chồng lên nhau.
7. Khi xong, hover lên các cột/thanh để kiểm tra tooltip, rồi kiểm tra số liệu đối chiếu ở phần tương ứng.

## V02 — Phân bố xác suất vỡ nợ dự đoán

**Câu hỏi:** Các khoản vay được đánh giá có PD dự đoán tập trung ở khoảng nào và có đuôi rủi ro cao ra sao? **Vì sao biểu đồ này:** histogram giữ được hình dạng phân bố thay vì gộp PD thành vài nhóm rủi ro. **Insight cần đọc:** vùng có nhiều khoản vay và phần đuôi PD cao; chỉ mô tả phân bố, không diễn giải PD là default thực tế. **Mạch kể chuyện:** V02 cho thấy phân bố tổng thể, V03 nhóm kết quả thành hạng rủi ro, rồi V05 giải thích các yếu tố model dùng.

### Tạo biểu đồ

1. Chọn **Clustered column chart** (biểu đồ cột đứng nhóm).
2. Kéo `fact_evaluated_loan[pd_bin_label]` vào **X-axis**.
3. Kéo measure `[PD Bin Count]` vào **Y-axis**. Để phép tính là **Sum** nếu Power BI yêu cầu.
4. Mở menu **… → Sort by → pd_bin_sort_order → Ascending** để các khoảng PD chạy từ thấp đến cao. Nếu model đã đặt `pd_bin_label` sort theo `pd_bin_sort_order`, trục sẽ theo đúng thứ tự số.
5. Trong **Tooltips**, thêm `[PD Bin Share]`. Có thể đổi tên hiển thị thành **Tỷ trọng khoản vay**.
6. Đặt tiêu đề **V02 — Phân bố xác suất vỡ nợ**. Trên Trang 3 dùng phụ đề **Mẫu test; mỗi khoảng rộng 0,05 • chọn hạng ở V03 để lọc**. Tránh ghi một tổng số cố định vì chọn V03 sẽ lọc V02.
7. Đặt độ rộng cột/gap vừa phải; tắt data labels nếu các nhãn như `0K` làm sai cảm nhận về bin nhỏ. Không thêm đường threshold gần đúng: trục ngang là nhãn bin phân loại, threshold `0.22009515762329102` hiện chưa được thể hiện bằng đường chính xác.

### Kiểm tra

- Trục PD có 20 khoảng cố định, mỗi khoảng rộng `0,05`, từ `[0,00; 0,05)` đến `[0,95; 1,00]`; khoảng cuối bao gồm PD=1.
- Tổng count trên các bin phải bằng tổng khoản vay đang được lọc. Baseline toàn evaluated test là **269.070**; có thể thấp hơn khi V03 lọc một tier.
- Hover cột để thấy khoảng PD, số khoản vay và tỷ trọng.

## V03 — Quy mô theo hạng rủi ro

**Câu hỏi:** Có bao nhiêu khoản vay trong từng hạng A–D, và PD trung bình/default quan sát đi cùng từng hạng thế nào? **Vì sao biểu đồ này:** bar ngang giúp so sánh các hạng có thứ tự rõ ràng. **Insight cần đọc:** so sánh quy mô và tách riêng PD dự đoán khỏi tỷ lệ default quan sát. **Mạch kể chuyện:** V03 phân đoạn phân bố V02; khi đặt chung Trang 3, click tier lọc V02 và các KPI cùng nguồn, còn V05 giữ nguyên vì SHAP lấy từ validation sample riêng.

### Tạo biểu đồ

1. Chọn **Clustered bar chart** (thanh ngang nhóm).
2. Kéo `fact_evaluated_loan[risk_tier]` vào **Y-axis** (Category).
3. Kéo `[Evaluated Loan Count]` vào **X-axis** (Values).
4. Đảm bảo thứ tự tier là **A → B → C → D**. Nếu cần, chọn `risk_tier` → **Column tools → Sort by column → tier_sort_order**.
5. Trong **Tooltips**, thêm `[Risk Tier Share]`, `[Mean PD]`, `[Observed Default Rate]`. Định dạng hai tỷ lệ thành phần trăm; đặt tên tiếng Việt **Tỷ trọng**, **PD trung bình**, **Tỷ lệ default quan sát**.
6. Đặt tiêu đề **V03 — Quy mô theo hạng rủi ro**. Có thể thêm phụ đề **A–D xếp theo PD; tỷ lệ default quan sát xem ở tooltip**.
7. Giữ count là chiều dài thanh chính. Không đưa count, share, PD và observed rate chung vào một trục Values.

### Kiểm tra

- Baseline toàn test: A **66.275**, B **109.146**, C **80.423**, D **13.226**; tổng **269.070** khoản vay.
- Hover từng thanh để kiểm đủ tier, số khoản vay, tỷ trọng, PD trung bình và tỷ lệ default quan sát.
- Trên Trang 3, mở **Format → Edit interactions**: chọn V03, đặt tương tác với V02 và ba KPI thành **Filter**; đặt tương tác tới V05 thành **None**. Thử click A/B/C/D: V02/KPI đổi theo lựa chọn, V05 không đổi. Bấm lại tier đã chọn để bỏ lọc.

## V04 — Phân bố PD theo nhóm FICO

**Câu hỏi:** Phân bố PD dự đoán khác nhau thế nào giữa các nhóm FICO? **Vì sao biểu đồ này:** box plot tóm tắt trung vị, khoảng tứ phân vị và độ phân tán theo từng nhóm, thay vì vẽ hàng trăm nghìn điểm chồng lấp. **Insight cần đọc:** so sánh trung vị và độ rộng phân bố; đây là mối liên hệ trong dữ liệu, không chứng minh FICO gây ra thay đổi PD. **Mạch kể chuyện:** V04 bổ sung góc nhìn borrower profile cho risk output ở V02/V03.

### Tạo biểu đồ

1. Trong **Visualizations**, chọn custom visual **Box and Whisker** đã được nhóm duyệt/cài đặt. Nếu biểu đồ này không có trong danh sách, dừng và nhờ quản lý Power BI cài visual đã duyệt; không thay bằng bar trung bình giả dạng box plot.
2. Kéo `fact_evaluated_loan[fico_band]` vào **Groups**.
3. Kéo `fact_evaluated_loan[predicted_pd]` vào **Values**; dùng từng giá trị PD, không chọn Average.
4. Kéo `fact_evaluated_loan[loan_id]` vào **Samples** để mỗi khoản vay là một quan sát. `loan_id` là ID, không phải số khoản vay của band.
5. Đảm bảo `fico_band` được sắp theo `fico_band_sort_order`. Nhóm hiển thị theo thứ tự `<650`, `650-699`, `700-749`, `750+`; nhóm không có quan sát thì không tạo hộp giả.
6. Đặt tiêu đề **V04 — Phân bố PD theo nhóm FICO**. Tăng cỡ chữ trục/nhãn đủ đọc ở kích thước trang; với custom visual, chữ có thể render nhỏ hơn chart mặc định.
7. Nếu visual có ô **Tooltips**, chỉ kéo các measure có sẵn: `[Evaluated Loan Count]`, `[Median PD]`, `[Mean PD]`, `[PD Q1]`, `[PD Q3]`, `[Observed Default Rate]`. Đổi nhãn lần lượt thành **Số khoản vay**, **PD trung vị**, **PD trung bình**, **PD Q1**, **PD Q3**, **Tỷ lệ default quan sát**. Nếu visual không cung cấp role tooltip hoặc tiếp tục ép tooltip thống kê riêng, giữ tooltip mặc định; không gọi `# Samples` là số khoản vay.

### Kiểm tra

- Ba nhóm có dữ liệu trong evaluated test: `650-699` **164.277**, `700-749` **83.552**, `750+` **21.241**; tổng **269.070**. `<650` và `Missing` không có dòng trong population này.
- Q1 / median / Q3 để đối chiếu: `650-699` = `0,145241 / 0,208485 / 0,301042`; `700-749` = `0,086702 / 0,127668 / 0,197087`; `750+` = `0,045053 / 0,067767 / 0,115688`.
- Hover từng nhóm và xem thử tooltip. Tooltip custom visual đã có giới hạn hiển thị tiếng Anh; nếu không thể đổi an toàn qua ô Tooltips, ghi nhận giới hạn thay vì sửa semantics của model.

## V05 — 10 đặc trưng ảnh hưởng mạnh nhất

**Câu hỏi:** Những đặc trưng nào đóng góp trung bình nhiều nhất vào đầu ra của model? **Vì sao biểu đồ này:** bar ngang đã sắp hạng giúp so sánh thứ tự và độ lớn mean absolute SHAP. **Insight cần đọc:** top feature có mức đóng góp trung bình lớn; biểu đồ không cho biết chiều tăng/giảm cho từng khoản vay và không chứng minh quan hệ nhân quả. **Mạch kể chuyện:** sau phân bố và phân hạng rủi ro, V05 trả lời model dựa vào đặc trưng nào trước khi sang tác động kinh doanh ở V06.

### Tạo biểu đồ

1. Chọn **Clustered bar chart**.
2. Dùng bảng `ml_lc_09_global_importance` (SHAP validation riêng). Kéo `original_feature` vào **Y-axis**.
3. Kéo `mean_abs_shap` vào **X-axis/Values**; chọn **Sum**. Kéo `rank` vào **Filters on this visual** và giữ thứ hạng **1–10**.
4. Chọn **… → Sort by → mean_abs_shap → Descending**. Thanh đầu là đặc trưng có mean |SHAP| lớn nhất.
5. Đặt tiêu đề **V05 — 10 đặc trưng ảnh hưởng mạnh nhất**. Phụ đề nêu **validation sample**, **raw margin/log-odds**, **không phải %PD**.
6. Nếu dùng Trang 3, đặt V05 rộng ở hàng dưới V02/V03. Bên cạnh biểu đồ có thể thêm **Text box** làm chú giải tiếng Việt theo đúng thứ tự feature đang hiển thị. Giữ tên field gốc trên trục/tooltip để truy nguyên nếu model/data không được phép đổi.
7. Thêm note ngắn: **Mean |SHAP| thể hiện mức đóng góp trung bình của đặc trưng vào dự đoán model; không phải %PD và không chứng minh quan hệ nhân quả.**
8. Trên Trang 3, dùng **Format → Edit interactions** để chọn V02 rồi chọn **None** trên V05; lặp lại chọn V03 rồi chọn **None** trên V05. SHAP validation không cùng population với frozen-test fact.

### Kiểm tra

- Có đúng 10 feature; sort giảm dần theo `mean_abs_shap`; nhãn và tooltip khớp nguồn `ml_lc_09_global_importance.csv`.
- Top đầu hiện có gồm `term_months`, `loan_to_income_ratio`, `fico_range_low`, `dti`, `issue_year`; xếp hạng phải đối chiếu với nguồn nếu visual được lọc hoặc đổi dữ liệu.
- Không dùng V05 để kể chiều đóng góp cá nhân. Không nối bảng SHAP validation với fact frozen-test theo Loan ID.

## V06 — Expected Loss theo hạng rủi ro

**Câu hỏi:** Hạng rủi ro nào chiếm phần Expected Loss giả định lớn nhất? **Vì sao biểu đồ này:** thanh ngang xếp hạng phù hợp để so sánh các nhóm song song A–D; đây không phải waterfall hay các bước cộng dồn. **Insight cần đọc:** so sánh EL tổng với PD và exposure ở tooltip; EL lớn có thể đi cùng quy mô exposure lớn, không chỉ PD cao. **Mạch kể chuyện:** V06 chuyển từ giải thích model ở V05 sang kịch bản tác động tài chính ở mức danh mục.

### Tạo biểu đồ

1. Chọn **Clustered bar chart**.
2. Kéo `fact_evaluated_loan[risk_tier]` vào **Y-axis**.
3. Kéo `[Total Expected Loss]` vào **X-axis/Values**. Measure này cộng `expected_loss_lgd_45` đã lưu trong dữ liệu.
4. Chọn **… → Sort by → Total Expected Loss → Descending**.
5. Trong **Tooltips**, thêm `[EL Contribution %]`, `[Total EAD Proxy]`, `[Mean PD]`, `[Evaluated Loan Count]`. Đổi nhãn hiển thị thành **Tỷ trọng Expected Loss**, **Tổng EAD proxy**, **PD trung bình**, **Số khoản vay**.
6. Đặt tiêu đề **V06 — Expected Loss theo hạng rủi ro**; phụ đề ghi rõ **LGD giả định 45% · EAD là số tiền vay proxy · đơn vị nguồn**.
7. Trên trang V06 hiện có, giữ slicer **Nhóm FICO** riêng với mặc định **All**. Slicer này lọc population của fact; nó không đổi LGD. Không thêm LGD selector vào biểu đồ V06 hiện tại vì biểu đồ đang dùng kịch bản 45% cố định. Nếu sau này thêm lựa chọn LGD, phải dùng các cột sensitivity đã có và kiểm thử cách tổng EL/tỷ trọng đổi trước khi trình bày.

### Kiểm tra

- Thứ tự baseline dự kiến **C → B → D → A**; tổng EL ở LGD 45% là khoảng **372.579.342,19** đơn vị nguồn; tổng EAD proxy **3.878.248.925**.
- Hover mỗi tier để thấy EL, tỷ trọng EL, EAD proxy, PD trung bình và số khoản vay.
- Ghi rõ `EAD proxy = loan_amnt`, không gọi là EAD thực tế. Expected Loss là scenario `PD × LGD × EAD proxy`; không gọi là realized loss, doanh thu hay lợi nhuận. Không gắn nhãn tiền tệ như USD khi nguồn không xác nhận currency.

## Kiểm tra nhanh khi hoàn tất

1. Mở từng trang V02–V06 trong `nghia.pbip`; bảo đảm mỗi trang có đúng một biểu đồ chính và không hiện dấu lỗi.
2. V02: trục bin tăng dần và count cộng về đúng tổng population đang lọc.
3. V03: tier theo A→D, count tổng khớp 269.070 ở baseline; click tier trên Trang 3 làm V02/KPI lọc và V05 đứng yên.
4. V04: các box/median/quartile đọc được; không có hộp cho nhóm rỗng; tooltip custom chỉ được xem là hoàn tất nếu các số và nhãn đã đối chiếu.
5. V05: đúng Top-10, giảm dần, từ bảng validation riêng.
6. V06: xếp hạng C→B→D→A, tooltip nói rõ LGD 45%, EAD proxy và đơn vị nguồn.
7. Lưu bằng **File → Save** sau khi tự kiểm tra. Nếu sửa PBIR khi Desktop đóng, mở lại project để xem render trước khi lưu hoặc giao tiếp.

## Nút mở công cụ dự đoán trên Trang 3

Trang 3 có nút **MỞ CÔNG CỤ DỰ ĐOÁN** trỏ đến `http://127.0.0.1:8050`. Nút chỉ mở ứng dụng Dash đang chạy; Power BI không tự khởi động Python server.

Nếu thực hiện bằng Power BI Desktop:

1. Chạy `run_prediction_app.bat` ở thư mục gốc repository và kiểm tra `http://127.0.0.1:8050` mở được trước.
2. Mở Trang 3, chọn hoặc chèn **Button** tại vùng tiêu đề; không đặt shape trong suốt lên trên nút.
3. Mở **Format visual** → **Button** → **Action** → bật **On**.
4. Đặt **Type = Web URL** và **Web URL = `http://127.0.0.1:8050`**. Đặt text hiển thị là **MỞ CÔNG CỤ DỰ ĐOÁN**.
5. Trong chế độ chỉnh sửa, giữ **Ctrl** rồi click nút để kiểm tra URL mở bằng trình duyệt mặc định. Nếu server chưa chạy, trình duyệt sẽ báo không kết nối được; chạy launcher rồi thử lại.

Trong vòng chỉnh sửa này, agent đã cập nhật PBIR khi Desktop đóng và mở lại Desktop để kiểm tra render: nút màu xanh, chữ hiển thị đúng, tiêu đề không che nút. Việc Power BI mở Python server vẫn là giới hạn vận hành; người dùng phải chạy launcher trước.

## Sửa measure Huy trong Master PBIP

**Lưu ý lịch sử:** đoạn này ghi thao tác hợp nhất measure ở vòng trước. Các format `$`, `Top Purpose = "Debt Consolidation"`, `Peak Year = 2015`, nguồn Map và danh sách 12 trang phía dưới đã được thay đổi trong vòng sửa bốn trang ngày 2026-10-08. Muốn dựng trạng thái **hiện tại**, làm theo mục “Bản Master bốn trang” ở cuối file.

Các trang Huy đã có trong `nghia.pbip` do người dùng chuyển thủ công. Phần sửa ngày 2026-10-08 thêm 7 measure vào `cleaned_dataset`, dùng lại `Total Loans` hiện có và đổi binding của 18 visual thuộc Portfolio Overview, Portfolio Trends & Purpose, Borrower Risk Profile và TT_V11. Danh sách visual ID và validation tĩnh nằm ở [merge-huy-into-nghia-audit.md](merge-huy-into-nghia-audit.md).

**Cách làm tương đương hoàn toàn trong Power BI Desktop — tạo measure:**

1. Mở `D:/ttdltq/reports/figures/dashboard/nghia.pbip`; trong **Data/Fields pane**, chọn bảng `cleaned_dataset`.
2. Với **từng** measure dưới đây, vào **Modeling → New measure**, nhập tên và DAX tương ứng vào formula bar rồi nhấn Enter. Không tạo lại `Total Loans` vì `cleaned_dataset[Total Loans] = COUNTROWS(cleaned_dataset)` đã tồn tại.
3. Chọn từng measure trong Data/Fields pane → **Measure tools → Format** và đặt format gốc nếu có. `Observed Default Rate — Portfolio` dùng `0.0%;-0.0%;0.0%`; `Total Funded Amount` dùng `\$#,0.00;(\$#,0.00);\$#,0.00`; `Average Loan Amount` dùng `\$#,0.###############;(\$#,0.###############);\$#,0.###############`; `Average FICO Score` và `Peak Year` dùng `0`. `Top Purpose` và `Label Peak Year` không có format string riêng trong source. Ký hiệu `$` là format Huy, không xác nhận đơn vị tiền của dataset.

```DAX
Observed Default Rate — Portfolio =
VAR TotalCount = COUNTROWS(cleaned_dataset)
VAR DefaultCount = CALCULATE(COUNTROWS(cleaned_dataset), cleaned_dataset[target] = 1)
RETURN
IF(
    TotalCount >= 100,
    DIVIDE(DefaultCount, TotalCount),
    BLANK()
)

Total Funded Amount = SUM(cleaned_dataset[loan_amnt])
Average FICO Score = AVERAGE(cleaned_dataset[fico_avg])
Average Loan Amount = AVERAGE(cleaned_dataset[loan_amnt])
Top Purpose = "Debt Consolidation"
Peak Year = 2015
Label Peak Year =
IF(
    SELECTEDVALUE(dim_date[year]) = 2015,
    FORMAT([Total Loans], "0.00M") & " (Peak)",
    BLANK()
)
```

`Observed Default Rate — Portfolio` dùng `cleaned_dataset` và ẩn kết quả khi nhóm có dưới 100 khoản vay. Measure `fact_evaluated_loan[Observed Default Rate]` của TV1 tính trên tập evaluated riêng và vẫn giữ nguyên. `Top Purpose`, `Peak Year` là giá trị cố định trong DAX nguồn Huy; chúng không tự thay đổi theo filter.

**Cách làm tương đương trong GUI — đổi visual binding:**

1. Mở từng trang Huy ở trên, chọn visual có dấu lỗi field, vào **Build visual**. Tại mỗi well/field chứa measure từ `*Measure table`, bỏ field cũ và kéo measure mới từ `cleaned_dataset` vào đúng well: `Total Loans` dùng bản sẵn có; `Observed Default Rate` dùng `Observed Default Rate — Portfolio`; sáu tên còn lại giữ nguyên.
2. Với bản đồ ở **Portfolio Overview**, giữ `dim_state[state_code]` làm Location/Category và `Total Loans` làm Size. Trong **Format visual → Data colors/fx** (conditional formatting), chọn **Based on field** = `Observed Default Rate — Portfolio` để giữ ý nghĩa tô màu tỷ lệ default quan sát.
3. Kiểm tra field trong **Sort by**, filter và **Format visual → Value/Label/Callout** của các KPI/trend cards. Với visual dùng Peak Year hoặc Top Purpose, đưa đúng measure mới vào field well; nếu format tùy từng field bị mất sau thay field, áp lại theo bản gốc.
4. Ở **Borrower Risk Profile**, card “GIÁ TRỊ VAY TRUNG BÌNH” từng dùng `annual_inc` dù metadata ghi Average Loan Amount. Chọn card, trong **Build visual → Data**, gỡ `annual_inc` rồi thêm `cleaned_dataset[Average Loan Amount]`; **Sort by** cũng dùng measure này.
5. Kiểm tra trực quan các trang, đặc biệt KPI cards, time trend, purpose, map và TT_V11. Không sửa field/measure ở V02–V06 hay “4. Annalysis RISK”.

**Thao tác thực tế của agent:** sửa TMDL/PBIR khi Desktop đã đóng; sau đó mở Desktop để chạy smoke DAX cho cả 8 measure Huy và measure TV1, kết quả PASS. Agent chưa bấm các bước GUI chỉnh visual trên và chưa nghiệm thu render từng biểu đồ. Khi tự mở bằng Desktop, kiểm tra không còn dấu lỗi field, các con số phù hợp population rồi mới **File → Save**.

## Bản Master bốn trang — thao tác Desktop tương đương vòng sửa 2026-10-08

Các thay đổi dưới đây do agent chỉnh **PBIR/TMDL khi Desktop đóng**, không phải agent đã click GUI. Bản gốc và tám trang rút khỏi Master nằm trong `_merge_backup/20261008-four-page-polish/`; có thể khôi phục. Tác dụng: câu chuyện đi đúng bốn trang như `docs/tasks/dashboard-visual-plan.md`, không trộn thêm các trang thử nghiệm/tooltip.

### 1. Chỉ giữ bốn trang và đồng bộ giao diện

1. Trong Desktop, mở project `nghia.pbip`. Giữ bốn trang nội dung: **01 · Tổng quan**, **02 · Xu hướng**, **03 · Hồ sơ vay**, **04 · Rủi ro & EL**. Nhấp đúp tên tab hoặc chuột phải → **Rename page** để đặt tên ngắn như trên. Page navigator trong sidebar tự lấy tên trang, do đó không cần tạo bốn nút thủ công.
2. Với các tab thử nghiệm `p4`, `P5`, `TV1 - V02/V03/V04/V05/V06` và tooltip `TT_V11`, trước khi xóa, chuyển V04 sang trang 03 và đổi V11 sang tooltip mặc định như mục 4. Sau đó chuột phải từng tab → **Delete page**. Làm sau khi đã Save As/có backup. Không xóa biểu đồ V02–V06 đang có trên trang 04.
3. Trên ba trang đầu, click vùng canvas trống → **Format page → Canvas background** và chọn `#C5D7E9`, transparency 0% để gần với trang 04; giữ kích thước **1920 × 1080** và **Fit to page**. Nếu trang 03 trông nhỏ trong Desktop, chọn **View → Page view → Fit to page** rồi thu gọn pane Filters/Data; PBIR trước/sau đều là 1920 × 1080, không có lỗi canvas khác kích cỡ.
4. Chọn **Page navigator** trên trang 03 và 04 → **Format visual → Pages**; bỏ các cấu hình ẩn theo từng tab cũ, để navigator dùng bốn trang hiện có. Trên trang 01/02, navigator tự động chỉ còn bốn tab sau khi xóa trang thừa. Kiểm tra không còn tên bị cắt/chồng trong sidebar.

### 2. Trang 01 — Map V01 và KPI giải ngân

**Business question:** rủi ro trên các bang/khu vực Hoa Kỳ phân bố thế nào trong tập evaluated? **Vì sao Map:** `state_code` là mã địa lý thật; bản đồ cho thấy vị trí, không suy từ masked ZIP. **Insight:** chỉ đọc bang có N đủ lớn sau khi Map render, chưa kết luận vùng rủi ro cao từ tên cột. **Mạch chuyện:** quy mô/funnel → địa lý → xu hướng ở trang 02.

Audit state đầy đủ nằm ở [v01_state_audit.md](v01_state_audit.md): 51 state/state-equivalent có dữ liệu, tổng 269.070 evaluated loans, country là United States.

1. Chọn V01 → **Build visual**. Visual phải là **Map** (bubble map), không phải **Filled map/Shape map**. Trong `Location`, giữ `dim_state[state_code]` và `dim_state[country]`; `state_code` có **Data category = State or Province**, `country` có **Data category = Country/Region**. Đặt **Size** = `fact_evaluated_loan[Evaluated Loan Count]`. Nguồn là **269.070 evaluated loans**, không phải application funnel hay toàn bộ cleaned portfolio.
2. Trong **Tooltips**, kéo lần lượt: `Evaluated Loan Count`, `Observed Default Count — State Map`, `Observed Default Rate — State Map`, `Mean PD`. Đổi nhãn hiển thị thành **Số khoản vay**, **Số default**, **Tỷ lệ default quan sát**, **PD trung bình**; định dạng count là số nguyên, rate/PD là phần trăm. Measure `State Map` trả `0` cho bang có zero default, không biến thành BLANK.
3. Vào **Format visual → Data colors → fx** và chọn `Observed Default Rate — State Map`; dùng gradient tuần tự **nhạt → cam → đỏ đậm**. Không dùng palette phân loại, rainbow hoặc xanh ngẫu nhiên. Trong **Format visual → Bubbles**, giữ Size theo measure và đặt transparency vừa phải để bubble nhìn được bang nhỏ; không đặt size theo PD/default count.
4. Vào **Format visual → Map settings**: bật auto zoom, chọn nền canvas sáng, đặt culture/geocoding **English (United States)** nếu có, kiểm tra khung nhìn tập trung Hoa Kỳ và vẫn thấy Alaska/Hawaii. Không dùng `zip_code`, latitude/longitude tự tạo hoặc location bịa.
5. Đổi title thành **Rủi ro tín dụng phân bố khác nhau giữa các bang**; subtitle thành **Màu thể hiện tỷ lệ default quan sát · Kích thước thể hiện số khoản vay đánh giá**. Không thêm prefix `V01` trên dashboard.
6. Nếu Map báo *Map and filled map visuals aren't enabled for your org*: vào **File → Options and settings → Options → Global → Security → Use Map and Filled Map visuals**, bật rồi khởi động lại Desktop. Lưu ý: dấu kiểm trong mục **Current file** chỉ xác nhận cài đặt local; ảnh kiểm tra ngày 2026-10-08 cho thấy dấu kiểm đã bật nhưng canvas vẫn bị chặn ở cấp tổ chức. Khi đó tenant admin phải vào **Power BI/Fabric Admin portal → Tenant settings → Map and filled map visuals**, bật cho toàn tổ chức hoặc security group của tài khoản và bấm **Apply**; sau đó đăng nhập lại Desktop. PBIR không tự vượt quyền này; lỗi quyền là blocker vận hành, không được đổi màu để che lỗi geocoding.
7. Chọn measure `cleaned_dataset[Total Funded Amount]` và `cleaned_dataset[Average Loan Amount]` trong **Data/Model view → Measure tools → Format → Custom**, bỏ tiền tố `$`; dùng `#,0.00;(#,0.00);#,0.00` và `#,0.##;(#,0.##);#,0.##`. Lý do: data contract chưa xác nhận đơn vị tiền để in ký hiệu `$`. Thẻ giải ngân sẽ hiển thị số lớn theo display units (không có `$`); không gọi đó là USD nếu chưa xác minh.

### 3. Trang 02 — sửa xu hướng theo năm

**Business question:** số khoản vay và tỷ lệ default quan sát thay đổi theo năm phát hành ra sao? **Vì sao hai line/column views:** tách quy mô khỏi tỷ lệ, không đánh đồng mẫu số. **Insight:** dữ liệu nguồn cho năm 2007 là 251 khoản vay, 2015 là 375.546; tỷ lệ tương ứng khoảng 17,93% và 20,19%, vì vậy đường phẳng/mỗi năm cùng một count là sai. **Mạch chuyện:** địa lý trang 01 → thời gian và mục đích trang 02 → phân khúc người vay trang 03.

1. Vào **Model view → Manage relationships → New**. Nối `dim_date[date]` (**One**) tới `cleaned_dataset[issue_d]` (**Many**), active, cross-filter một chiều **dim_date → cleaned_dataset**. `dim_date.date` đã kiểm tra unique 4.238 ngày và bao phủ mọi `issue_d`. Quan hệ Auto date table trên từng cột không thay cho đường nối này.
   - Đính chính sau feedback Power BI Desktop: trong TMDL, đầu **From** của quan hệ một-nhiều phải là phía **Many**. Định nghĩa hiện tại ghi `fromColumn: cleaned_dataset.issue_d` → `toColumn: dim_date.date`; bỏ các cardinality override để Power BI dùng mặc định Many-to-One. Trong GUI, cùng quan hệ này vẫn hiển thị `dim_date (1) → cleaned_dataset (*)` và lọc một chiều từ bảng ngày sang khoản vay. Hai bản TMDL trước đã sai hướng/thiếu cardinality và gây lỗi mở; không dùng lại.
2. Chọn biểu đồ volume và default-rate: **X-axis** là `dim_date[year]` (có thể drill quarter/month), **Y-axis** lần lượt `cleaned_dataset[Total Loans]` và `cleaned_dataset[Observed Default Rate — Portfolio]`. Slicer năm cũng dùng `dim_date[year]`. Chọn 2007/2015 để thấy số thay đổi, thay vì cả hai luôn hiển thị tổng 1.345.350.
3. Trong **Modeling → New measure**, sửa `Top Purpose` thành `VAR T = ADDCOLUMNS(ALLSELECTED(cleaned_dataset[purpose]), "LoanCount", [Total Loans]) RETURN MAXX(TOPN(1, T, [LoanCount], DESC, cleaned_dataset[purpose], ASC), cleaned_dataset[purpose])`. Sửa `Peak Year` thành `VAR T = ADDCOLUMNS(ALLSELECTED(dim_date[year]), "LoanCount", [Total Loans]) RETURN MAXX(TOPN(1, T, [LoanCount], DESC, dim_date[year], ASC), dim_date[year])`. `Label Peak Year` so `SELECTEDVALUE(dim_date[year])` với `[Peak Year]`; không so với hằng 2015. Kiểm tra bằng cách đổi year slicer. Chưa xác nhận runtime DAX trong Desktop ở vòng này.

### 4. Trang 03 — điền KPI và đặt V04 vào đúng chỗ

**Business question:** đặc điểm người vay/FICO/DTI đi cùng mức rủi ro nào? **Vì sao bố cục:** KPI để đọc nhanh, V11/V12 ở giữa, V10/V04 ở dưới; box plot V04 cho thấy phân bố PD thay vì chỉ trung bình. **Insight:** FICO cao hơn đi cùng PD dự đoán thấp hơn trong tập evaluated; không nói FICO gây giảm rủi ro. **Mạch chuyện:** tổng quan khách hàng → ma trận/phân khúc → rủi ro model ở trang 04.

1. Chọn card trống ở hàng KPI → **Build visual → Data**, kéo `cleaned_dataset[Total Loans]`; trong **Format visual → Label/Category label**, đặt nhãn **KHOẢN VAY CÓ KẾT QUẢ**. Card thứ nhất giữ `Average Loan Amount` (**GIÁ TRỊ VAY TRUNG BÌNH**), card thứ ba chọn measure `Average Annual Income = AVERAGE(cleaned_dataset[annual_inc])` (**THU NHẬP NĂM TRUNG BÌNH**), card thứ tư giữ `Average FICO Score`. Khi làm bằng GUI: **Modeling → New measure** để tạo Average Annual Income trước, Format như số thường, không `$`.
2. Từ trang V04 thử nghiệm, chọn custom **Box & Whisker** → **Ctrl+C**; sang trang 03 → **Ctrl+V**; đặt ở ô dưới bên phải, khoảng `X=1106, Y=652, Width=793, Height=403`. Xóa shape/khung placeholder trắng nằm ở vị trí này. Giữ `fact_evaluated_loan[fico_band]`, `predicted_pd` và `loan_id` của visual; kiểm tra custom visual đã cài và renders. V04 dùng frozen-test evaluated population, không phải các KPI danh mục `cleaned_dataset`.
3. V11 từng dùng riêng tooltip page `TT_V11`. Chọn ma trận V11 → **Build visual → Tooltips**, thêm `cleaned_dataset[Total Loans]` để đọc N; vào **Format visual → Tooltips → Type: Default** và bỏ report-page tooltip. Trang `TT_V11` đã được cất trong backup. Nếu Desktop không hỗ trợ field well Tooltips cho matrix này hoặc không hiển thị N, khôi phục `TT_V11` từ backup (ẩn khỏi navigator) và coi yêu cầu đúng bốn trang *vật lý* là blocker — không được âm thầm mất N.
4. Đổi subtitle trang 03 sang câu phân biệt population: V04 evaluated; V10/V11/V12 và các KPI portfolio dùng `cleaned_dataset`. Trong **View → Page view**, dùng **Fit to page** để so kích cỡ với trang 04.

### 5. Nghiệm thu trước khi Save

Agent đã sửa định nghĩa PBIR/TMDL; scanner PBIR xác nhận **4 trang / 69 visual**, JSON parse và link page ID tĩnh PASS. Dữ liệu parquet xác nhận quan hệ ngày và count theo năm. Hai lượt mở của người dùng đã phát hiện lỗi định nghĩa quan hệ ngày: lần đầu One-to-One/OneDirection; lần sau From=One không hợp lệ cho One-to-Many. Agent đã đảo TMDL về **From=cleaned_dataset (Many) → To=dim_date (One)** theo quy ước các quan hệ khác trong model. Lần mở lại bằng Desktop đã nạp report `nghia` thành công: DAX theo 12 năm khác nhau (2007 = 251, 2015 = 375.546), Peak Year đổi thành 2008 khi chỉ chọn 2007–2008, tổng evaluated theo 51 mã bang = 269.070; **model/DAX runtime PASS**. **Render từng visual, V11 tooltip và quyền bật Map còn cần nghiệm thu trực quan**. Kiểm tra trên GUI: chỉ bốn tab; Map nếu đã bật quyền; biểu đồ năm không phẳng; KPI không rỗng/trùng; V04 không trống; tooltip V11 có N; trang 04 nguyên vẹn. Nếu bất kỳ mục nào lỗi, không coi dashboard hoàn toàn PASS và gửi screenshot để sửa tiếp. Không publish/commit trước nghiệm thu.
