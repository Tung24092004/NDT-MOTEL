# Báo cáo UI Module 07 - Notifications

Ngày: 2026-09-27  
Trạng thái: **PASS**. Chỉ thực hiện Module 07; chưa bắt đầu Module 08.

## Phạm vi và backup

- Checkpoint đầu vào: full suite `308/308` PASS; live `86/10/6/3/0/20`; gallery `86/86`, mismatch `0`; artifact root `0`; source `__pycache__` `0`.
- Backup trước sửa: `luu_tru/ban_sao_luu/before_module07_ui_20260927_134609` (24 file liên quan).
- Không sửa model, view, service, URL, business rule, quyền, transaction, endpoint, tên field POST hoặc CSRF.

## Audit theo code đang chạy

### Route và quyền

- Tenant: list, poll và detail tại `motel_management/urls.py:399-415`. List/detail từ chối Admin; dữ liệu được khóa theo `NguoiThue.tai_khoan=request.user` và `ThongBao.nguoi_thue` tại `core/views_thong_bao.py:208-307`.
- Admin inbox: list, poll, đọc tất cả, detail và đọc một thông báo tại `motel_management/urls.py:427-455`. Guard chỉ cho staff/superuser; mọi query inbox/detail/action đều khóa theo `nguoi_nhan_user=request.user` tại `core/views_thong_bao.py:36-85`.
- Admin quản lý/gửi: list, create, detail và xử lý tại `motel_management/urls.py:700-721`; quyền Admin tại `core/views_thong_bao.py:131-205`, `334-466`.
- Model có hai đích nhận riêng (`nguoi_thue`, `nguoi_nhan_user`), một trạng thái `da_doc/ngay_doc`, link điều hướng và mã chống trùng tại `core/models.py:1975-2044`.

### Người nhận, chuông và trạng thái đọc

- Badge Admin đếm duy nhất thông báo chưa đọc có `nguoi_nhan_user=request.user`; badge Tenant đếm duy nhất `nguoi_thue` đang hoạt động gắn với tài khoản tại `core/bo_xu_ly_bo_cuc.py:4-47`. Chuông theo vai trò ở `templates/core/base.html:631`.
- Endpoint poll giữ cùng phạm vi người nhận và trả tối đa 5 item mới tại `core/views_thong_bao.py:80-96`. URL poll theo vai trò được đặt tại `templates/core/components/toast_container.html:10`; JS cập nhật badge, toast và poll mỗi 20 giây tại `static/js/components/toast.js:50-103`.
- Admin mở detail không đổi trạng thái. Đọc một thông báo là POST, có scope người nhận, ghi `LichSuThongBao`, rồi chuyển tới `url_lien_ket` hoặc detail; đọc tất cả là POST bulk theo đúng Admin tại `core/views_thong_bao.py:45-75`.
- Tenant mở detail bằng GET sẽ tự đặt `da_doc=True/ngay_doc=now`; không có endpoint đánh dấu chưa đọc tại `core/views_thong_bao.py:285-330`.
- Màn quản lý Admin lọc toàn hệ thống theo từ khóa/loại/mức độ/trạng thái; Tenant dùng cùng bộ lọc nhưng chỉ trên thông báo của mình tại `core/views_thong_bao.py:131-183`, `208-281`.
- Điều hướng Tenant ưu tiên `url_lien_ket`, sau đó fallback theo loại; Admin inbox chỉ đi link nghiệp vụ sau POST đánh dấu đọc. Template tương ứng: `templates/core/chi_tiet_thong_bao_cua_toi.html:5-9`, `templates/core/chi_tiet_thong_bao_admin.html:5-7`.

### Nguồn tạo thông báo thực tế

- Thông báo Tenant được tạo trong các workflow đặt phòng/cọc, hợp đồng/gia hạn, hóa đơn/thanh toán và đăng ký Face ID; ví dụ: `core/views_dat_phong.py:181-186`, `core/dich_vu/hop_dong.py:162-172`, `core/views_gia_han.py:337-348`, `core/views_hoa_don.py:779-795`, `core/views_thanh_toan.py:364-382`, `core/views_smart_room.py:2570-2585`.
- Thông báo Admin được tạo cho từng tài khoản Admin đang active, chống trùng bằng reference + user id tại `core/dich_vu/thong_bao_dat_phong.py:9-14` và `core/dich_vu/thong_bao_quan_tri.py:21-38`.
- Admin có thể gửi thủ công cho một người thuê đang hoạt động; transaction và audit giữ nguyên tại `core/views_thong_bao.py:334-449`.

## UI migration và file

Migrate Foundation V1 cho 7 màn thật: Admin manage list/create/detail, Admin inbox list/detail, Tenant list/detail. Bao phủ PageHeader, stats, FilterBar, Table/list, Badge, Form, Surface, EmptyState, action và responsive.

Đã sửa:

- `templates/core/quan_ly_thong_bao.html`
- `templates/core/tao_thong_bao.html`
- `templates/core/chi_tiet_thong_bao.html`
- `templates/core/thong_bao_admin.html`
- `templates/core/chi_tiet_thong_bao_admin.html`
- `templates/core/thong_bao_cua_toi.html`
- `templates/core/chi_tiet_thong_bao_cua_toi.html`
- `static/css/ui-system.css` (gỡ lớp inbox legacy)
- `core/tests/test_thong_bao.py` (2 regression test UI contract)

Đã thêm: `static/css/notification.css`; `core/tests/visual_module07_notification_audit.py` (chỉ chạy explicit).  
Đã xóa CSS Tenant không còn dùng: `static/css/tenant/thong_bao_cua_toi.css`, `static/css/tenant/chi_tiet_thong_bao_cua_toi.css`. Kiểm tra reference: không còn tham chiếu.

Sửa lỗi UI đúng phạm vi: option filter/create/edit nay phát đúng model values `bao_tri/quan_trong/khancap`, title maxlength khớp model 200, và màn quản lý hiển thị đúng Admin recipient thay vì “Tất cả người thuê”. Endpoint và tên payload không đổi.

## Test và QA

- `manage.py check`: PASS, 0 issue.
- `makemigrations --check --dry-run`: PASS, `No changes detected`.
- Focused notification: PASS `11/11`.
- Full suite cuối: PASS `310/310`, 45.841 giây, DB `test_ndt_motel` đã hủy sau chạy.
- Visual QA: PASS `11 màn/trạng thái x 4 viewport = 44 ca`, viewport `1440x900`, `1024x768`, `768x900`, `390x844`.
- 11 ca: Admin manage mixed/empty, create, manage detail unread, inbox mixed, inbox detail unread/read, inbox empty; Tenant list mixed, detail mở từ unread và chuyển read, list empty.
- Mỗi ca xác nhận HTTP 200, overflow ngang false, broken image 0, console/page error 0. Kiểm tra ảnh trực tiếp đại diện desktop/tablet/mobile không thấy overlap hoặc clipping. Ca bị chặn cuối cùng: `0`.
- Lần đầu trong sandbox bị `WinError 5` khi Playwright tạo subprocess; rerun ngoài sandbox PASS. Một lần rerun tiếp theo lỗi fixture ORM trong event loop; đã sửa fixture và bài chạy cuối PASS.
- Bằng chứng: `luu_tru/kiem_thu/module_07/notification_qa/results.json` và 44 PNG (45 file tổng).

## Giới hạn backend còn lại

- Một số workflow legacy vẫn ghi `muc_do="canh_bao"` trong khi model choices là `binh_thuong/quan_trong/khancap`: `core/views_quan_tri.py:1191,1429`, `core/views_thanh_toan.py:856`, `core/views_hop_dong.py:1779`. Module UI không sửa các nhánh nghiệp vụ này; record đó có thể hiện raw value và toast không được tone warning như `quan_trong`.
- Tenant list dùng hồ sơ gắn tài khoản không yêu cầu `dang_hoat_dong=True`, trong khi badge/poll có yêu cầu active (`core/views_thong_bao.py:17-20,208-228`); không thay quyền hoặc rule trong lượt UI.
- Tenant detail vẫn ghi trạng thái đọc bằng GET và không tạo `LichSuThongBao`; Admin “đọc tất cả” bulk cũng không tạo lịch sử từng item. Giữ nguyên theo backend hiện tại.
- `core/views_sua_chua.py:20` import `ThongBao` nhưng không có lệnh tạo thông báo trong workflow sửa chữa. Không bổ sung thông báo mới trong Module 07.
- Admin manage list chưa phân trang; Tenant list chưa phân trang. Không thay query/business behavior.

## Xác nhận cuối

- Live data: `86/10/6/3/0/20`.
- Live notification baseline sau sửa không đổi: tổng `61`, đã đọc `16`, chưa đọc `45`, tenant-target `61`, user-target `0`.
- Gallery: `86/86`, mismatch `0`.
- Artifact root: `0`.
- Source `__pycache__`: `0`.

**Kết luận: Module 07 PASS. Dừng trước Module 08.**
