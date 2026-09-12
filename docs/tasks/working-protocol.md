# Quy trình làm việc, log và Git

Áp dụng cho TV1, TV2, TV3 và AI hỗ trợ dự án. Mục tiêu là repository gọn, mỗi đầu ra truy được người tạo/lý do, và không có nhiều file cùng chức năng.

## 1. Một task hoàn chỉnh

Trước khi làm, xác định ngắn gọn: mục tiêu, owner, input, output canonical, kiểm tra cần chạy và điều kiện dừng. Một task nên là một kết quả kỹ thuật rõ ràng.

Khi nhờ AI, prompt cũng phải nêu file/data được đọc, việc cần làm, phạm vi cấm sửa, output/path, điều kiện PASS và STOP. Một prompt chỉ giải quyết một task kỹ thuật; không gộp audit, train, dashboard và deploy vào cùng một yêu cầu.

Sau khi xong:

1. Kiểm tra file/folder có đúng vị trí và không trùng chức năng với file cũ.
2. Nếu thay thế một file, sửa trực tiếp hoặc xóa file cũ trong cùng thay đổi.
3. Ghi một entry ngắn vào log cá nhân.
4. Commit đúng nhóm file của task.

## 2. Log cá nhân bắt buộc

Mỗi thành viên chỉ append vào log của mình:

- TV1: docs/logs/log_tv1.md
- TV2: docs/logs/log_tv2.md
- TV3: docs/logs/log_tv3.md

Mỗi entry cần: ngày, mã/tên task, trạng thái (done/blocked/in progress), việc đã làm, đường dẫn file thay đổi, kiểm tra đã chạy, và đúng một next step hoặc blocker.

Không ghi raw console log, dữ liệu nhạy cảm, token hoặc nội dung quá dài. Log là ledger đọc nhanh; chi tiết nằm trong source, notebook, contract hoặc report.

## 3. Kỷ luật file và artifact

- Trước khi tạo file, tìm file cùng vai trò. Ưu tiên update in place.
- Không dùng tên mơ hồ như final2, new, latest, copy, test_ok.
- Mọi file material mới/sửa/xóa phải được ghi đường dẫn trong log và, nếu là đầu ra dùng chung, trong tài liệu/contract liên quan.
- Chỉ tạo folder khi có file canonical cần đặt trong đó; không tạo folder trống để dành.
- Artifact lớn thuộc data/ hoặc models/ theo gitignore; repo chỉ giữ source, manifest, contract, report nhỏ và hướng dẫn tái tạo.

## 4. Git: branch → commit → push → PR

1. Làm trên branch riêng: tv1, tv2, hoặc tv3; không commit trực tiếp vào main.
2. Trước task mới, cập nhật branch từ main và xử lý conflict trên branch cá nhân.
3. Kiểm tra bằng git status; stage từng file cụ thể, không dùng git add . hoặc git add -A.
4. Chạy kiểm tra phù hợp, cập nhật log, rồi commit theo mẫu: feat(data): aggregate bureau records.
5. Chỉ khi kiểm tra pass, hoặc blocker được ghi rõ trong log/PR, mới rebase/pull branch cá nhân, push branch và tạo PR vào main.
6. Contract, schema dữ liệu/model, cấu hình dùng chung phải có review chéo trước merge.

### 4.1 giai đoạn 1

- 1. Cất code đang làm dở
```
    git stash
```
- 2. Lấy code mới nhất của dự án từ main
```
    git checkout main
    git pull origin main
```
- 3. Quay lại nhánh cá nhân và cập nhật code main vào nhánh
```
    git checkout tvX
    git merge main
```
    - Nếu có conflict: Sửa -> Commit

- 4. Lấy lại code dở ra làm tiếp
```
    git stash pop
```
### 4.2 giai đoạn 2

- Tạo các bộ git push theo từng nhóm công việc đã hoàn thành
- 1 bộ git đẩy code lên gồm:
```
    git add <tên các file đã làm việc trong nhóm đó>
    git commit -m "feat(scope): short message"
```
- Sau khi đã add + commit hết các nhóm -> đồng bộ và đẩy lên server (Chạy trước khi push để tránh bị từ chối):
```
    git pull origin tvX --rebase
    git push origin tvX
```

## 5. Review trước merge

- Scope commit khớp đúng task; không có file thừa hoặc dữ liệu/model nhị phân.
- Đường dẫn output và consumer downstream đã được cập nhật.
- Log cá nhân có entry và ghi đúng canonical paths.
- Kiểm tra liên quan pass; vấn đề còn lại ghi rõ blocker/next step.
