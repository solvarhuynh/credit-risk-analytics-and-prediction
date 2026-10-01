# Ghi chú dataset reset

Repository đã chuyển sang Lending Club 2007–2018. Lịch sử cũ nằm trong Git và các log `_old`; tài liệu/code đang hoạt động chỉ mô tả kiến trúc mới.

Migration chỉ chuẩn bị file, contract, code và synthetic tests. Chưa chạy pipeline, EDA, model, SHAP hay dashboard. Vì vậy không được diễn giải folder trống là lỗi: đó là trạng thái reset có chủ đích.

Thứ tự đúng: TV2 DE-LC-01 → DE-LC-10, sau đó TV1 chạy model input gate, cuối cùng TV3 tích hợp data/model thật.
