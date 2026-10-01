# Quyết định kiến trúc và rủi ro

## Quyết định

- Tách accepted thành bảng nghiệp vụ thay vì chia ngẫu nhiên để đáp ứng join rubric.
- Rejected không tham gia default modeling vì không có outcome.
- Target chỉ map ba trạng thái cuối explicit; status chưa kết thúc bị censor khỏi supervised set.
- Feature policy fail-closed; Logistic Regression là baseline bắt buộc.
- Map dùng bang thật (`state_code`), không suy latitude/longitude từ ZIP masked.
- Pipeline đọc chunk vì raw tổng cộng hơn 3 GB.

## Rủi ro cần theo dõi

- Temporal leakage từ payment, recovery, hardship, settlement và last-FICO.
- Proxy leakage từ pricing/grade do lender quyết định.
- Censoring bias khi loại trạng thái chưa kết thúc.
- Khác schema accepted/rejected và không có key chung.
- Memory pressure, dtype drift giữa các chunk và schema Parquet.
- Class imbalance.
- Geographic fairness/bias nếu dùng state/ZIP trong model.
- ZIP bị che nên chỉ Map cấp bang đáng tin cậy.
