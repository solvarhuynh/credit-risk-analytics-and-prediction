# F1 pilot memory and monitor diagnosis — 2026-10-09

## Kết luận

- Lượt `pilot-20261009-02` vẫn là **ABORTED BEFORE FIT**. Không có bằng chứng model fit bắt đầu; không có thời gian fit/peak memory của model.
- Lỗi đo process đã được xác định: tiến trình từ `.venv\Scripts\python.exe` có thể được khởi tạo qua Windows venv redirector rồi chạy interpreter `Python312\python.exe` làm tiến trình con. Snapshot hiện tại chứng minh quan hệ này trên các Dash server: PID launcher venv có PrivateUsage khoảng 0,7 MB, trong khi child interpreter cùng lệnh có PrivateUsage khoảng 1,2–1,3 GB. Bộ đo cũ chỉ nhìn PID launcher nên đánh giá thấp process memory nghiêm trọng.
- Nguyên nhân làm system commit tăng 87% → 98% ở lần trước **chưa xác định**. Không có phase log hay telemetry đúng process để kết luận do nạp dataset, Arrow/Pandas, preprocessing hay ứng dụng khác.
- Monitor mới theo dõi toàn bộ process tree; các kiểm tra tổng hợp, child termination, peak sampling, checkpoint, preflight và không ghi đè đã PASS. Đây **không phải** Pilot PASS và không gọi `XGBClassifier.fit()` trong task này.

## Bằng chứng lịch sử lần Pilot

Từ `pilot-20261009.md` và log cũ: 5 samples trong 13,45 giây; available RAM thấp nhất 8.663 MB; system commit 87% → 98%, kích hoạt stop 95%; `Pages Input/sec` peak 94,1, dưới ngưỡng severe paging; stdout/stderr rỗng; không có result/model artifact. Process metric cũ báo 4 MB Working Set / 1 MB Private Memory, nhưng không đo được worker thực tế. Vì thiếu checkpoint nên phase cuối đã đạt không khôi phục được; chỉ có thể nói chưa có bằng chứng fit.

## Snapshot hệ thống và attribution

Read-only snapshot trong lượt chẩn đoán:

- Physical RAM: 29.855.539.200 bytes (27,81 GiB).
- Preflight quan sát liên tục 60 mẫu trong 120 giây: available RAM 10,69–11,62 GiB; commit utilization 80,20–82,45%; `Pages Input/sec` peak 0; ngưỡng quan sát an toàn của preflight mới đạt (commit <85%, available ≥7 GiB).
- Commit limit 45.961.666.560 bytes; pagefile `C:\pagefile.sys`, allocated 15.360 MB, current use 931 MB, historical peak 4.622 MB. `AutomaticManagedPagefile=True`; không thay đổi cài đặt pagefile.
- D: còn 525.111.934.976 bytes (489,0 GiB).
- Top observed private commit gồm Edge khoảng 1,57 GiB; ba interpreter Dash khoảng 1,18–1,28 GiB mỗi process; Power BI MCP interpreter khoảng 0,58 GiB; VS Code renderer/processes đáng kể. Các process này chỉ được quan sát, không bị dừng.
- `WorkingSetSize` và `PrivateUsage` được đọc riêng qua `GetProcessMemoryInfo`: Working Set là resident RAM; `PrivateUsage` là private commit/pagefile charge, **không phải** resident RAM. System commit/limit lấy từ `GetPerformanceInfo`; available physical lấy từ `GlobalMemoryStatusEx`. CPU dùng kernel+user time từ `GetProcessTimes`, quy về phần trăm tổng logical CPU. Paging lấy các Windows Memory performance counters.

### Confirmed vs. hypotheses

**Đã xác nhận:** monitor cũ theo PID launcher, không theo descendant interpreter; hiện có nhiều Python/Dash interpreter với private commit lớn; lần abort trước là system commit-limit pressure, không phải bằng chứng RAM vật lý xuống dưới 5 GB; pagefile là system-managed.

**Chưa xác nhận:** liệu 98% commit trước kia được gây ra chủ yếu bởi Train read, Arrow table → Pandas copy, preprocessing buffers hay các ứng dụng khác; liệu paging/commit behavior của snapshot hiện tại đại diện cho thời điểm pilot cũ.

## Monitor và runner đã sửa

- `src/models/experiments/f1_pilot_monitor.py` khởi chạy trực tiếp interpreter đã xác minh tại `.venv\Scripts\python.exe`, không dùng `py.exe`/shell wrapper, và theo dõi PID chính cùng descendants bằng Windows process snapshot.
- JSONL monitor có timestamp, PID tree và executable path (để phân biệt venv launcher với interpreter con), per-process/aggregate Working Set, private commit, peak, CPU, elapsed time, available RAM, system committed bytes/limit/utilization, paging counters, stop/failure reason và last completed pilot phase.
- Giữ nguyên hard stops: available RAM <5 GiB; system commit ≥95%; aggregate private commit của process tree >16 GiB (conservative); severe paging ≥1.000 Pages Input/sec khi available <8 GiB trong 5 mẫu liên tiếp.
- Preflight yêu cầu sustained 60 mẫu, mỗi mẫu commit <85% và available RAM ≥7 GiB; nếu không đạt, monitor thoát trước khi spawn runner/nạp dữ liệu.
- `f1_pilot.py` ghi và flush/fsync checkpoint: `START`, `LOADING_DATA`, `DATA_LOADED`, `PREPROCESSING`, `PREPROCESSING_COMPLETE`, `FIT_START`, `FIT_COMPLETE`, `ARTIFACT_SAVED`; lỗi ghi `FAILED`. Khi monitor abort, ghi `STOPPED_BY_MONITOR` kèm `last_completed_phase`.
- Monitor từ chối sử dụng lại run directory đã có để tránh ghi đè artifact. Mọi run mới nằm trong experiment-only path `data/processed/modeling_experiments/f1_improvement/<run_id>/`.

## Kiểm thử

`tests/models/test_f1_pilot_monitor.py`: **7 passed**. Đã kiểm tra hard-stop thresholds; sustained preflight; fail-closed khi paging counters thiếu; ghi/flush checkpoint; preflight hard-stop không spawn command; synthetic Python process + child được phát hiện, ghi peak metrics, terminate và không để orphan; existing run/artifact guard không ghi đè. `compileall` cho hai module monitor/runner và test: PASS.

Lần chạy pytest đầu gặp lỗi quyền trên thư mục global `C:\Users\Nghia\AppData\Local\Temp\pytest-of-Ga-eul`; chạy lại với basetemp mới trong `.pytest_cache` thì toàn bộ 6 test PASS. Không nạp dữ liệu Train, không fit, không đánh giá Validation/Frozen Test.

## Quyết định về lần Pilot mới

Trong snapshot chẩn đoán trước đó, preflight read-only 120 giây đạt guardrail kỹ thuật; tại thời điểm đó có ba Python Dash server giữ khoảng 3,6–3,9 GiB private commit cùng workload VS Code/Edge/MCP, commit nền 80,2–82,45%. Không process nào bị terminate. Đây chỉ là snapshot cũ, không phải kết quả preflight mới theo yêu cầu người dùng; lần preflight mới được ghi riêng bên dưới và đã thất bại.

## Lần thử preflight theo yêu cầu — không khởi chạy Pilot

Ngày 2026-10-09, monitor chạy với `--preflight-seconds 120` cho run ID `pilot-20261009-04`. Kết quả ghi ở thư mục Git-ignored `data/processed/modeling_experiments/f1_improvement/pilot-20261009-04/`.

- Đủ 120 sample trong 258,3 giây theo phiên bản monitor trước khi sửa fail-fast. Ngay sample đầu: available RAM **4,38 GiB** (<5 GiB hard stop và <7 GiB preflight); system commit **96,92%** (≥95% hard stop và không <85% preflight). Cực trị trong log: available RAM **3,70 GiB**, commit **98,65%**.
- Paging counters đều `null` do cách gọi PowerShell cũ không trả về dữ liệu. Vì vậy paging stop rule cũng không thể được chứng nhận ở lần đo này.
- Monitor log không có `CHILD_STARTED`; `pilot-progress.jsonl` không được tạo; **không đọc Train, không chạy preprocessing/model fit, không có artifact**. Preflight không đạt; hai system hard-stop đã cùng bị chạm. Kết luận lần chạy: **Pilot BLOCKED — RAM khả dụng <5 GiB và commit ≥95%**.
- Trong kiểm tra sửa lỗi sau lần chạy, paging query được đổi sang một PowerShell `-EncodedCommand` duy nhất; gọi trực tiếp hàm mới trả về số cho cả bốn paging counters (0 tại thời điểm kiểm tra). Preflight hiện dừng ngay ở sample đầu nếu system stop/preflight limit vi phạm hoặc paging metric thiếu; duration dựa theo đồng hồ thực, không nhân đôi thời gian lấy mẫu. Đây chỉ là sửa monitor, **không phải** preflight mới và không cấp phép chạy Pilot.
- Không thử lại preflight sau lần thất bại. Chỉ chạy lại khi người dùng chủ động yêu cầu; phải vượt đủ 120 giây an toàn mới được phép launch.

## Lần chạy lại theo yêu cầu — preflight đạt, nhưng dừng trong preprocessing

Theo yêu cầu tiếp theo của người dùng, run `pilot-20261009-05` được chạy bằng monitor đã sửa. Preflight đạt 120 giây thực tế (39 mẫu; paging counters hợp lệ); RAM khả dụng cuối preflight khoảng 11,5 GiB, system commit khoảng 47,7%. Vì preflight đạt, monitor tự khởi chạy đúng một runner.

- Runner ghi `START` → `LOADING_DATA` → `DATA_LOADED` (807.210 rows, 103 feature inputs) → `PREPROCESSING`. Last completed phase là **DATA_LOADED**; `PREPROCESSING_COMPLETE` và `FIT_START` không xuất hiện.
- Monitor dừng cây process sau khoảng 24 giây kể từ `START`, lý do `STOP_AVAILABLE_RAM_BELOW_5_GIB`. RAM khả dụng thấp nhất **4,323 GiB**; peak system commit **67,99%**; peak private commit của process tree **9,188 GiB**; peak tree Working Set **7,568 GiB**. Nguyên nhân dừng là available RAM, không phải system commit hay process-private limit.
- `Pages Input/sec` peak **5.191,1**; một mẫu đồng thời có RAM khả dụng <8 GiB, nhưng chưa đạt 5 mẫu severe paging liên tiếp. Monitor đã dừng sớm hơn theo hard stop RAM <5 GiB.
- Monitor trả exit code 124 sau khi terminate child; không còn pilot process. Run directory chỉ có `pilot-progress.jsonl` và resource JSONL; không có `pilot_result.json` hoặc `xgboost_pilot.joblib`. **Không có bằng chứng XGBoost fit bắt đầu/hoàn tất**, không đọc Validation/Frozen Test.
- Đây là một lần attempt duy nhất theo quyền đã cấp; không tiếp tục retry sau hard stop. Thời gian fit thực tế không tồn tại/không đo được; chưa thể cập nhật ước lượng OOF/tuning bằng runtime fit.

Kết luận lần chạy mới: preflight/monitor hoạt động; Pilot đã load Train nhưng bị dừng trong preprocessing trước checkpoint `FIT_START`. Không khởi chạy thêm lượt nào tới khi có yêu cầu mới.

Không chạy Stage B, không đổi model/config/primary artifact, không chỉnh pagefile, không commit/push/publish.
