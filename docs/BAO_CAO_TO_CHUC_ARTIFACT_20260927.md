# Báo cáo tổ chức artifact dự án NDT MOTEL

Ngày thực hiện: 27/09/2026  
Phạm vi: tổ chức file và thiết lập quy tắc sinh artifact trước Module 05. Không triển khai Module 05, không sửa business logic hoặc giao diện chức năng.

## 1. Kết quả kiểm kê

Các mục ở root được phân loại như sau:

- Source/runtime giữ nguyên: `core/`, `motel_management/`, `templates/`, `static/`, `media/`, `models/`, `tools/`, `manage.py`, `requirements.txt`.
- Tài liệu bàn giao giữ trong `docs/` để tiếp tục được review cùng source.
- Backup: 14 thư mục và 4 file, tổng cộng 18 mục có tiền tố `backup_*` hoặc là snapshot SQL lịch sử.
- Bằng chứng QA: 11 thư mục ảnh/JSON và 3 snapshot văn bản, tổng cộng 14 mục.
- Cache có thể tạo lại: 9 thư mục `__pycache__` trong source đang chạy.
- File chưa đủ căn cứ để di chuyển/xóa: `db.sqlite3`, hai model ONNX trong `models/` và `.tmp`.

`db.sqlite3` được giữ vì tài liệu lịch sử xác nhận đây là dữ liệu local/dev dù runtime hiện dùng MySQL. Hai file ONNX là tài nguyên của luồng Face ID. `.tmp` chứa hai thư mục `ndt-motel-tests-*` cũ nhưng ACL từ chối đọc sâu; do chưa xác minh được nội dung, thư mục này được giữ nguyên.

## 2. Cấu trúc sau tổ chức

```text
luu_tru/
|-- README.md
|-- ban_sao_luu/
|   `-- 18 goi/file backup giu nguyen ten goc
|-- kiem_thu/
|   |-- tai_khoan/
|   |-- kham_pha/
|   |-- foundation_v1/
|   |-- giai_doan_1/
|   |-- module_02/
|   |-- module_03/
|   `-- module_04/
`-- tam/
```

Root sau tổ chức chỉ còn source/runtime chính, `docs/`, `tools/`, `luu_tru/`, cấu hình dự án và `.tmp` được giữ có chủ đích.

## 3. Di chuyển và xóa

- Đã chuyển 18/18 mục backup vào `luu_tru/ban_sao_luu/`.
- Đã chuyển 14/14 mục QA/snapshot vào nhóm tương ứng dưới `luu_tru/kiem_thu/`.
- Tổng số mục cấp root đã chuyển: 32.
- Đã xóa 9 thư mục `__pycache__` trong source đang chạy; kiểm tra lại còn 0.
- Không xóa backup, ảnh QA, log dữ liệu, database, model hoặc tài liệu nào.
- Không xóa `.tmp` do hai thư mục con không đọc được vì ACL; đây là rủi ro còn lại cần xử lý thủ công sau khi xác minh quyền sở hữu/nội dung.

## 4. Tham chiếu đã cập nhật

Các báo cáo Module 01-04, Foundation V1, Phase 1, gallery và inventory đã được đổi sang đường dẫn `luu_tru/...`. Báo cáo Module 04 vẫn đọc được và hiện trỏ đúng tới:

- `luu_tru/ban_sao_luu/backup_before_contract_management_ui_20260927_020000/`
- `luu_tru/ban_sao_luu/backup_before_contract_management_ui_20260927_020000.sqlite3`
- `luu_tru/kiem_thu/module_04/ui_contract_management_qa/results.json`

Ba nơi sinh bằng chứng visual đã được cấu hình ghi trực tiếp vào thư mục mới:

- `tools/audit_tenant_booking_visual.py` -> `luu_tru/kiem_thu/module_02/`
- `core/tests/visual_admin_booking_audit.py` -> `luu_tru/kiem_thu/module_03/`
- `core/tests/visual_contract_management_audit.py` -> `luu_tru/kiem_thu/module_04/`

## 5. Quy tắc artifact mới

- `.gitignore`: bỏ qua backup, QA evidence, thư mục tạm và cache Python/test; source, migrations, test Python và báo cáo trong `docs/` không bị che.
- `.vscode/settings.json`: Explorer chỉ ẩn cache và `luu_tru/tam`; không ẩn backup, QA evidence hoặc source cần review.
- Terminal VS Code đặt `PYTHONDONTWRITEBYTECODE=1`, `TEMP` và `TMP` về `luu_tru/tam`.
- `tools/run_django.ps1`: wrapper Windows áp dụng cùng biến môi trường khi chạy `manage.py`.
- `tools/backup_project.ps1`: xác thực nguồn nằm trong dự án nhưng ngoài `luu_tru`, từ chối chọn toàn bộ project root hoặc ghi đè đích, rồi ghi backup trực tiếp vào `luu_tru/ban_sao_luu/<ten>_<timestamp>`; có `-WhatIf` để kiểm tra không ghi file.
- `luu_tru/README.md`: mô tả nơi đặt và nguyên tắc giữ artifact.

Không đổi tên hàng loạt source/code hiện có. Tên kỹ thuật của test, CSS, migration và API được giữ nguyên.

## 6. Kiểm tra đã chạy

### Django

Lệnh:

```powershell
.\tools\run_django.ps1 check
```

Kết quả: PASS, `System check identified no issues (0 silenced)`.

### Báo cáo và backup Module 04

- Báo cáo Module 04 đọc được, dung lượng 9.209 byte sau khi cập nhật đường dẫn.
- Source backup Module 04 còn đủ 6/6 file.
- SQLite backup Module 04 còn 131.072 byte; `PRAGMA integrity_check` trả `ok`.
- Toàn bộ 18/18 mục backup dự kiến đều tồn tại tại vị trí mới.

### Script backup mới

Lệnh:

```powershell
.\tools\backup_project.ps1 -Name kiem_tra -Source docs\UI_MODULE_04_CONTRACT_MANAGEMENT_REPORT_20260927.md -WhatIf
```

Kết quả: PASS; đích được xác định dưới `luu_tru/ban_sao_luu/`, không tạo file thử.

### QA Module 04 tại đường dẫn mới

Lệnh:

```powershell
.\tools\run_django.ps1 test core.tests.visual_contract_management_audit
```

Lần chạy trong sandbox bị chặn khi Playwright tạo subprocess (`WinError 5`). Chạy lại ngoài sandbox: PASS, 1/1 test; database `test_ndt_motel` được tạo và hủy. File `results.json` được cập nhật trực tiếp trong `luu_tru/kiem_thu/module_04/ui_contract_management_qa/` với 16 kết quả: status lỗi 0, overflow 0, ảnh hỏng 0, dòng có lỗi console/page 0.

### Dữ liệu live

Kiểm tra chỉ đọc sau cùng:

| Dữ liệu | Số lượng |
|---|---:|
| Phòng | 86 |
| Booking | 10 |
| Hợp đồng | 6 |
| Lịch sử thanh toán | 3 |
| Giao dịch cọc | 0 |
| Người thuê | 20 |

Kết quả khớp checkpoint Module 04: `86/10/6/3/0/20`. Không tạo tài khoản và không thay đổi dữ liệu live.

## 7. Kết luận và rủi ro còn lại

Task tổ chức artifact: PASS. Root đã gọn, backup và bằng chứng QA có nơi lưu rõ ràng, lệnh QA/backup mới không còn chủ động sinh output ở root.

Rủi ro còn lại duy nhất trong phạm vi kiểm kê là `.tmp/ndt-motel-tests-59npzsnv` và `.tmp/ndt-motel-tests-s95ftgam`: chưa thể đọc sâu do ACL nên được giữ nguyên. Không nên xóa cho đến khi xác minh được quyền và nội dung. Module 05 chưa được bắt đầu.
