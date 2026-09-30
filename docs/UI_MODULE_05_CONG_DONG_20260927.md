# Báo cáo Module 05 - Tenant, người cùng ở và ở ghép

Ngày thực hiện: 27/09/2026  
Phạm vi: chỉ migrate UI Module 05 sang Foundation V1. Không triển khai Module 06; không đổi business logic, trạng thái, phân quyền, endpoint, POST payload, CSRF hoặc transaction.

## 1. Nguồn đối chiếu

Checkpoint có tên chính xác `NDT MOTEL – UI/UX MIGRATION CHECKPOINT` không tồn tại trong cây dự án khi tìm bằng `rg --files` và `rg`, phù hợp ghi nhận tại báo cáo Module 04. Nguồn được dùng:

- `docs/UI_MODULE_04_CONTRACT_MANAGEMENT_REPORT_20260927.md`.
- `docs/UI_FOUNDATION_V1_REPORT_20260927.md`.
- Route, view, model, service, template và test hiện tại; implementation là chuẩn workflow.

## 2. Backup và baseline trước sửa

Backup tạo trực tiếp trong khu lưu trữ:

- `luu_tru/ban_sao_luu/before_module05_ui_20260927_123443/`.
- Nguồn đã sao lưu: `templates/core`, `static/css`, `static/js`, `core/tests`.
- Kiểm tra sau cùng: 153 file trong gói backup.

Baseline live trước sửa:

| Dữ liệu | Số lượng |
|---|---:|
| Phòng | 86 |
| Booking | 10 |
| Hợp đồng | 6 |
| Lịch sử thanh toán | 3 |
| Giao dịch cọc | 0 |
| Người thuê | 20 |
| Người cùng ở | 4 |
| Yêu cầu ở ghép | 1 |

## 3. Audit route và quyền

### Người thuê

- Admin list/detail: `motel_management/urls.py:587`, `motel_management/urls.py:593`.
- Cả hai view yêu cầu đăng nhập và `la_admin`; user thường bị chuyển về tài khoản: `core/views_nguoi_thue.py:32`, `core/views_nguoi_thue.py:35`, `core/views_nguoi_thue.py:53`, `core/views_nguoi_thue.py:56`.
- List chỉ tìm theo tên, điện thoại, CCCD hoặc email; detail chỉ đọc hồ sơ, hợp đồng và hóa đơn: `core/views_nguoi_thue.py:38`, `core/views_nguoi_thue.py:59`, `core/views_nguoi_thue.py:60`, `core/views_nguoi_thue.py:63`.
- Model `NguoiThue` bắt đầu tại `core/models.py:611`; CCCD unique tại `core/models.py:646`.

Kết luận: Module hiện có màn Admin xem/list/detail người thuê, không có route tạo/sửa/xóa người thuê trong nhánh này. UI không bổ sung action giả.

### Người cùng ở

- Admin list/create/detail/action: `motel_management/urls.py:777`, `motel_management/urls.py:783`, `motel_management/urls.py:789`, `motel_management/urls.py:795`.
- Toàn bộ bốn view chỉ cho Admin: `core/views_smart_room.py:737`, `core/views_smart_room.py:741`, `core/views_smart_room.py:868`, `core/views_smart_room.py:872`, `core/views_smart_room.py:911`, `core/views_smart_room.py:915`, `core/views_smart_room.py:1278`, `core/views_smart_room.py:1282`.
- Trạng thái model chỉ có `dang_o`, `da_roi`: `core/models.py:2109`, `core/models.py:2111`.
- List hỗ trợ `q`, `phong`, `trang_thai` và thống kê: `core/views_smart_room.py:763`, `core/views_smart_room.py:764`, `core/views_smart_room.py:765`, `core/views_smart_room.py:809`.
- Tạo thủ công chỉ chọn hợp đồng đang hiệu lực/booking đã duyệt, kiểm tra ngày, sức chứa, trùng CCCD rồi tạo `NguoiOCungPhong`: `core/views_smart_room.py:919`, `core/views_smart_room.py:927`, `core/views_smart_room.py:1018`, `core/views_smart_room.py:1120`, `core/views_smart_room.py:1151`, `core/views_smart_room.py:1223`.
- Sau tạo thủ công backend tạo/get `FaceProfile` tại `core/views_smart_room.py:1240`, nhưng không có lệnh tạo `QuyenRaVao` trong flow này.
- Action thật gồm cập nhật, `roi_phong`, `quay_lai`, `xoa`: `core/views_smart_room.py:1300`, `core/views_smart_room.py:1317`, `core/views_smart_room.py:1353`, `core/views_smart_room.py:1402`, `core/views_smart_room.py:1432`.
- Rời phòng làm hết hạn quyền ra vào; xóa bị chặn nếu có quyền legacy cần giữ lịch sử: `core/views_smart_room.py:1330`, `core/views_smart_room.py:1403`, `core/views_smart_room.py:1410`.

### Yêu cầu ở ghép

Routes thật:

- Tenant đăng ký: `motel_management/urls.py:233`.
- Chủ hợp đồng bật/tắt tiếp nhận: `motel_management/urls.py:239`.
- Tenant list và Admin list dùng chung view: `motel_management/urls.py:245`, `motel_management/urls.py:251`.
- Detail/action dùng chung: `motel_management/urls.py:257`, `motel_management/urls.py:263`.

Model `YeuCauGhepNguoi` có bốn trạng thái `cho_duyet`, `da_duyet`, `tu_choi`, `da_huy`: `core/models.py:1294`, `core/models.py:1296`. Người gửi là `NguoiThue`: `core/models.py:1315`.

Ai tạo yêu cầu:

- User đăng nhập, không phải Admin, phải có hồ sơ `NguoiThue`: `core/views_o_ghep.py:212`, `core/views_o_ghep.py:224`, `core/views_o_ghep.py:227`.
- Phòng phải có hợp đồng hiện hành, chủ thuê hoạt động, còn sức chứa và `cho_phep_ghep=True`; điều kiện dùng chung tại `core/dich_vu/dieu_kien_o_ghep.py:7` đến `core/dich_vu/dieu_kien_o_ghep.py:42`.
- Chủ hợp đồng không thể tự gửi vào phòng mình; cùng người gửi/cùng hợp đồng chỉ có một yêu cầu `cho_duyet`: `core/views_o_ghep.py:261`, `core/views_o_ghep.py:329`.
- POST giữ các field `ho_ten`, `ngay_sinh`, `gioi_tinh`, `cccd`, `so_dien_thoai`, `quan_he`, `ngay_du_kien_vao`, `ly_do`: `core/views_o_ghep.py:354` đến `core/views_o_ghep.py:396`.

Ai xem và duyệt:

- Admin list thấy mọi yêu cầu chờ; chủ hợp đồng chỉ thấy yêu cầu vào phòng mình; người gửi thấy lịch sử do mình gửi: `core/views_o_ghep.py:625`, `core/views_o_ghep.py:639`, `core/views_o_ghep.py:652`.
- Detail chỉ cho Admin, chủ hợp đồng hoặc người gửi: `core/views_o_ghep.py:730` đến `core/views_o_ghep.py:756`.
- Chỉ Admin hoặc chủ hợp đồng được duyệt/từ chối: `core/views_o_ghep.py:860` đến `core/views_o_ghep.py:879`.
- Action chỉ nhận `duyet` hoặc `tu_choi`: `core/views_o_ghep.py:881`, `core/views_o_ghep.py:886`.

Transaction duyệt:

- Transaction và lock yêu cầu/hợp đồng/phòng: `core/views_o_ghep.py:907`, `core/views_o_ghep.py:913`, `core/views_o_ghep.py:944`, `core/views_o_ghep.py:958`.
- Chặn xử lý lần hai: `core/views_o_ghep.py:929`.
- Duyệt kiểm tra lại hợp đồng, cờ tiếp nhận, sức chứa, CCCD và người đã tồn tại: `core/views_o_ghep.py:1004`, `core/views_o_ghep.py:1018`, `core/views_o_ghep.py:1056`, `core/views_o_ghep.py:1070`, `core/views_o_ghep.py:1116`.
- Khi duyệt tạo `NguoiOCungPhong`, `FaceProfile`, `QuyenRaVao` nguồn `duyet_ghep`, cập nhật yêu cầu và số người; đủ chỗ thì tự tắt nhận ghép: `core/views_o_ghep.py:1139`, `core/views_o_ghep.py:1156`, `core/views_o_ghep.py:1165`, `core/views_o_ghep.py:1180`, `core/views_o_ghep.py:1213`, `core/views_o_ghep.py:1225`.
- Chủ hợp đồng, không phải Admin, có quyền bật/tắt tiếp nhận; flow dùng transaction và lock hợp đồng/phòng: `core/views_o_ghep.py:47`, `core/views_o_ghep.py:53`, `core/views_o_ghep.py:77`, `core/views_o_ghep.py:119`.

## 4. Giới hạn backend được giữ nguyên

- Model có trạng thái `da_huy` nhưng không có action/route hủy yêu cầu trong `views_o_ghep.py`; UI không tạo nút hủy.
- `nguoi_xu_ly` và `ghi_chu_admin` có trong model nhưng flow duyệt/từ chối hiện không ghi hai field này. Detail chỉ hiển thị người xử lý nếu backend có dữ liệu cũ.
- `ThongBao` được import nhưng không được tạo trong workflow ở ghép hiện tại; UI không tuyên bố có thông báo tự động.
- Lý do từ chối không bị backend bắt buộc, nhưng form UI hiện yêu cầu để người gửi có phản hồi rõ ràng; tên payload vẫn là `ly_do_tu_choi`.
- Luồng Admin thêm người cùng ở thủ công tạo Face Profile nhưng không tự cấp quyền ra vào; đây không được thay đổi trong lượt UI.

## 5. Phạm vi UI đã migrate

Các màn route thật đã chuyển sang Foundation V1:

- Admin người thuê: list, tìm kiếm, detail, hợp đồng, hóa đơn, empty state.
- Admin người cùng ở: list/filter/stats, form tạo, detail, cập nhật, rời phòng, quay lại, xóa, empty state.
- Tenant/Admin ở ghép: form đăng ký, list theo vai trò, detail, bật/tắt tiếp nhận, duyệt/từ chối, trạng thái và empty state.

Foundation tái sử dụng: PageHeader, FilterBar, Table, Badge, Button, Form, Surface/Card, EmptyState và Dialog. Giao diện dùng teal chủ đạo, vàng cho trạng thái chờ; responsive giữ bảng trong vùng cuộn nội bộ. Không sửa `base.html`, gallery, URL, view, model, service hoặc migration.

## 6. File thay đổi

Template:

- `templates/core/quan_ly_nguoi_thue.html`
- `templates/core/chi_tiet_nguoi_thue.html`
- `templates/core/quan_ly_nguoi_o_cung.html`
- `templates/core/tao_nguoi_o_cung.html`
- `templates/core/chi_tiet_nguoi_o_cung.html`
- `templates/core/dang_ky_ghep_phong.html`
- `templates/core/yeu_cau_ghep_cua_toi.html`
- `templates/core/chi_tiet_yeu_cau_ghep.html`

File mới:

- `templates/core/partials/community_status_badge.html`
- `static/css/community.css`
- `static/js/community.js`
- `core/tests/visual_community_audit.py`
- Báo cáo này.

Đã xóa ba CSS Tenant cũ không còn reference runtime sau migration:

- `static/css/tenant/dang_ky_ghep_phong.css`
- `static/css/tenant/yeu_cau_ghep_cua_toi.css`
- `static/css/tenant/chi_tiet_yeu_cau_ghep.css`

CSS/JS Module 05 có `!important = 0`; inline `confirm()` đã thay bằng Foundation Dialog. `community.js` giữ submitter `name/value`, vì các action dùng payload `hanh_dong`.

## 7. Kiểm tra thực chạy

### Django và migration

- `.\tools\run_django.ps1 check`: PASS, `System check identified no issues (0 silenced)`.
- `.\tools\run_django.ps1 makemigrations --check --dry-run`: PASS, `No changes detected`.

### Regression

- Nhóm `test_o_ghep`, `test_giao_dien`, `test_phan_quyen`: PASS 69/69 khi chạy tuần tự.
- Một lần chạy chồng lệnh trước đó làm hai runner tranh chấp `test_ndt_motel` và bị lỗi tạo/xóa database; đây không được tính PASS. Sau khi runner cũ kết thúc, lệnh tuần tự PASS.
- Full suite cuối cùng `.\tools\run_django.ps1 test core --noinput`: PASS 308/308, 78,192 giây; database test được hủy.

### QA giao diện

Lệnh: `.\tools\run_django.ps1 test core.tests.visual_community_audit --noinput` chạy ngoài sandbox vì Playwright cần tạo Chrome subprocess.

DB: `test_ndt_motel` cô lập, được tạo và hủy. Không tạo tài khoản hoặc bản ghi live.

Màn hình đã chụp:

- Admin người thuê list/detail.
- Admin người cùng ở list/create/detail.
- Admin yêu cầu ở ghép list/detail.
- Tenant yêu cầu ở ghép list/detail/register.

Viewports: 1440×900, 1024×768, 768×900, 390×844.

Kết quả cuối: PASS 40/40 tổ hợp; HTTP lỗi 0, overflow 0, ảnh hỏng 0, dòng có lỗi console/page 0. Có 40 ảnh và `results.json` tại `luu_tru/kiem_thu/module_05/community_qa/`.

Hai lượt đầu phát hiện overflow ở detail người thuê trên 1024/768/390 và đã sửa bằng giới hạn intrinsic width của grid/surface. Một lượt PASS kỹ thuật sau đó được xem ảnh và phát hiện route form đăng ký bị redirect do fixture đã có yêu cầu chờ; fixture được tách tài khoản và lượt cuối chụp đúng form thật, PASS.

## 8. Baseline sau cùng

Baseline live sau sửa vẫn là `86/10/6/3/0/20`; người cùng ở 4, yêu cầu ở ghép 1. Không thay đổi dữ liệu live.

Gallery: 86 phòng, prepared 86, missing cover 0, mismatch 0. Không sửa gallery.

Kiểm tra cây dự án:

- Artifact ở root: 0.
- `__pycache__` trong source: 0.
- QA/log mới chỉ nằm dưới `luu_tru/kiem_thu/module_05/`.
- Backup mới chỉ nằm dưới `luu_tru/ban_sao_luu/`.

## 9. Kết luận

Module 05 PASS theo workflow backend hiện có. Giao diện Admin/Tenant trong phạm vi người thuê, người cùng ở và ở ghép đã dùng Foundation V1, giữ nguyên endpoint/payload/quyền/transaction. Các thiếu sót backend đã được ghi nhận để xử lý ở lượt riêng; Module 06 chưa được bắt đầu.
