# Runtime role menu audit - 2026-09-18


## Kết quả runtime mới nhất sau refactor

Mục này thay thế kết luận runtime lịch sử phía dưới. Không có screenshot/artifact mới; các đường dẫn artifact và venv cũ phía dưới chỉ là lịch sử.

### Nguyên nhân và sửa chữa

- Inbox Admin đã extends đúng `core/base.html`, không phải sai template; các class `admin-page-header/admin-list/admin-list-item` thiếu style nên nội dung mất layout. Đã thêm CSS scoped theo `notification-inbox`, empty state, phân trang, loading/error polling.
- Admin thật (id 1) có 0 thông báo, 0 chưa đọc. Badge, inbox và polling đều lọc `nguoi_nhan_user=request.user`. CSS badge `display:grid` ghi đè việc ẩn bằng thuộc tính `hidden`, tạo chấm đỏ giả. Đã thêm selector `[hidden]` ưu tiên; browser xác nhận badge không hiển thị khi count=0.
- Homepage Admin có 6 href tài khoản User; chi tiết phòng có nút ở ghép cá nhân Admin. Đã điều kiện hóa render, không dùng CSS để phân quyền.
- Flyout mobile bị rule cuối ép width 550px. Đã giới hạn width theo viewport, browser kiểm tra bounding box không vượt màn hình.
- URL polling đã được cấu hình trong `core/components/toast_container.html`, không thay đổi query hay route.

### Session và dữ liệu

Hai tài khoản có thật: Admin id 1 và User có hồ sơ người thuê đang hoạt động. Hai client/session cache và browser context riêng; không tạo database session, không login làm đổi last_login. Chỉ GET và thao tác mở/đóng menu trên production. Snapshot tất cả bảng managed trước/sau: giống nhau. Không theo link chi tiết thông báo User vì GET đó có nghiệp vụ đánh dấu đã đọc.

Cả hai tài khoản kiểm tra có 0 thông báo chưa đọc. Trường hợp có thông báo, phân biệt người nhận và POST đánh dấu tất cả đã đọc được kiểm tra trên database test, không tạo thông báo giả trên production.

### Menu/nút thực tế

Cột giao diện được kiểm tra sau khi mở sidebar/flyout trên desktop 1440x1000 và mobile 390x844. Các link chưa được điều hướng (FaceProfile, logout, đổi mật khẩu và nhóm quản trị mở rộng) chỉ xác minh hiện diện/hiển thị, không kết luận toàn bộ nghiệp vụ đã chạy. Gia hạn và thanh toán đi qua màn hình hợp đồng/hóa đơn, thao tác chi tiết tùy trạng thái dữ liệu, không phải route menu độc lập.

| Vai trò | Menu/nút | URL | Template render menu | Trong HTML | Giao diện desktop/mobile | Vai trò đúng |
|---|---|---|---|---|---|---|
| User | Đặt phòng | /dat-phong-cua-toi/ | `core/base.html` | Có | Có | Đúng |
| User | Hợp đồng/gia hạn | /hop-dong-cua-toi/ | `core/base.html` | Có | Có | Đúng |
| User | Hóa đơn/thanh toán | /hoa-don-cua-toi/ | `core/base.html` | Có | Có | Đúng |
| User | Sửa chữa | /yeu-cau-sua-chua-cua-toi/ | `core/base.html` | Có | Có | Đúng |
| User | Thông báo/chuông | /thong-bao-cua-toi/ | `core/base.html` | Có | Có | Đúng |
| User | Tài khoản | /tai-khoan/ | `core/base.html` | Có | Có | Đúng |
| User | FaceProfile | /tai-khoan/nhan-dien-su-dung-phong/ | `core/base.html` | Có | Có | Đúng |
| User | Yêu cầu ở ghép | /yeu-cau-ghep-cua-toi/ | `core/base.html` | Có | Có | Đúng |
| Admin | Dashboard | /dashboard-admin/ | `core/base.html` | Có | Có | Đúng |
| Admin | Cơ sở | /quan-ly-co-so/ | `core/base.html` | Có | Có | Đúng |
| Admin | Phòng | /quan-ly-phong/ | `core/base.html` | Có | Có | Đúng |
| Admin | Đặt phòng | /quan-ly-dat-phong/ | `core/base.html` | Có | Có | Đúng |
| Admin | Hợp đồng/gia hạn | /quan-ly-hop-dong/ | `core/base.html` | Có | Có | Đúng |
| Admin | Hóa đơn/xác nhận thanh toán | /quan-ly-hoa-don/ | `core/base.html` | Có | Có | Đúng |
| Admin | Người thuê | /quan-ly-nguoi-thue/ | `core/base.html` | Có | Có | Đúng |
| Admin | Sửa chữa | /quan-ly-sua-chua/ | `core/base.html` | Có | Có | Đúng |
| Admin | Inbox/chuông Admin | /thong-bao-admin/ | `core/base.html` | Có | Có | Đúng |
| Admin | Gửi/quản lý thông báo | /quan-ly-thong-bao/ | `core/base.html` | Có | Có | Đúng |
| Admin | Chính sách | /quan-ly-chinh-sach/ | `core/base.html` | Có | Có | Đúng |
| Admin | Quản lý ở ghép | /quan-ly-yeu-cau-ghep/ | `core/base.html` | Có | Có | Đúng |
| Admin | Smart Room | /smart-room/ | `core/base.html` | Có | Có | Đúng |
| Admin | Kiểm soát ra vào | /smart-room/access-control/ | `core/base.html` | Có | Có | Đúng |
| Admin | Người ở cùng | /smart-room/nguoi-o-cung/ | `core/base.html` | Có | Có | Đúng |
| Admin | FaceProfile quản trị | /smart-room/face-profile/ | `core/base.html` | Có | Có | Đúng |
| Admin | Quyền ra vào | /smart-room/quyen-ra-vao/ | `core/base.html` | Có | Có | Đúng |
| Admin | Lịch sử ra vào | /smart-room/lich-su-ra-vao/ | `core/base.html` | Có | Có | Đúng |
| Admin | Nhật ký | /nhat-ky-thao-tac/ | `core/base.html` | Có | Có | Đúng |
| Admin | Đổi mật khẩu | /doi-mat-khau/ | `core/base.html` | Có | Có | Đúng |
| User/Admin | Trang chủ | / | `core/base.html` | Có | Có | Đúng |
| User/Admin | Tìm phòng | /phong/ | `core/base.html` | Có | Có | Đúng |
| User/Admin | Đăng xuất | /dang-xuat/ | `core/base.html` | Có | Có | Đúng |
| Admin | Đánh dấu tất cả đã đọc | /thong-bao-admin/doc-tat-ca/ | `core/thong_bao_admin.html` | Có (POST + CSRF) | Có | Đúng; POST chỉ chạy trên DB test |

### Trang và template thực tế

| URL | Template chính khi đúng vai trò | User | Admin |
|---|---|---|---|
| / | core/home.html | 200 | 200 |
| /phong/ | core/danh_sach_phong.html | 200 | 200 |
| /phong/1/ | core/chi_tiet_phong.html | 200 | 200 |
| /dashboard-admin/ | core/dashboard_admin.html | 302 tới tài khoản | 200 |
| /thong-bao-admin/ | core/thong_bao_admin.html | 302 tới tài khoản | 200 |
| /thong-bao-cua-toi/ | core/thong_bao_cua_toi.html | 200 | 302 tới dashboard |
| /dat-phong-cua-toi/ | core/tenant/booking/list.html | 200 | 302 tới dashboard |
| /hoa-don-cua-toi/ | core/hoa_don_cua_toi.html | 200 | 302 tới dashboard |
| /tai-khoan/ | core/tai_khoan.html | 200 | 302 tới dashboard |
| /quan-ly-dat-phong/ | core/quan_ly_dat_phong.html | 302 tới tài khoản | 200 |
| /quan-ly-hoa-don/ | core/quan_ly_hoa_don.html | 302 tới tài khoản | 200 |
| /smart-room/ | core/smart_room_dashboard.html | 302 tới tài khoản | 200 |
| /hop-dong-cua-toi/ | core/hop_dong_cua_toi.html | 200 | 302 tới dashboard |
| /yeu-cau-sua-chua-cua-toi/ | core/yeu_cau_sua_chua_cua_toi.html | 200 | 302 tới quản lý sửa chữa |

Mọi trang cùng dùng base hiện tại; trang cá nhân dùng thêm tenant_base. Đã kiểm tra body role, tập href toàn HTML, mở tất cả panel sidebar, link panel hiển thị và bounding box nằm trong viewport. CSS inbox Admin: 3 stylesheet HTTP 200; User: 5 stylesheet HTTP 200. Mô phỏng lỗi polling HTTP 503 và phục hồi: PASS cho hai vai trò/hai viewport. Không dùng screenshot; bằng chứng là DOM/computed styles/bounding boxes/network responses.

### Kiểm tra cuối

Python: `D:\\NDT_MOTEL_ENV\\Scripts\\python.exe -B`.

- `manage.py check`: PASS, 0 issues.
- `manage.py makemigrations --check --dry-run`: PASS, No changes detected.
- `manage.py test core --noinput -v 2`: 260 tests, PASS, 35.701 giây. Trước: 257; thêm 3 test, không mất test.
- Ma trận render bổ sung homepage/danh sách/chi tiết phòng Admin; không chỉ kiểm tra text, parser kiểm tra href thật.
- Không chạy migrate/reset trên production; Django tự tạo/hủy database test cho full suite.
- Không đổi dữ liệu production, URL, quyền hoặc nghiệp vụ. Không dọn source hoặc tách code.

---


This matrix records server-rendered navigation after removing the legacy header from HTML.
Conditions are Django template conditions; CSS and JavaScript are not used for authorization.

## Shared/public

| Display | Template | Render condition | URL name | Allowed/observed role |
|---|---|---|---|---|
| Trang chu | `base.html` | Always | `home` | Public, User, Admin |
| Tim phong | `base.html` | Always | `danh_sach_phong` | Public, User, Admin |
| Dang nhap / Dang ky | `base.html` | Anonymous only | `dang_nhap`, `dang_ky` | Public |
| Dang xuat | `base.html` | Authenticated | `dang_xuat` | User, Admin |

## User shell

| Display | Template | Render condition | URL name | Allowed/observed role |
|---|---|---|---|---|
| Dat phong cua toi | `base.html`, `tenant_base.html` | Authenticated and not staff/superuser | `dat_phong_cua_toi` | User only |
| Hop dong cua toi | `base.html`, `tenant_base.html` | Authenticated and not staff/superuser | `hop_dong_cua_toi` | User only |
| Hoa don cua toi | `base.html`, `tenant_base.html` | Authenticated and not staff/superuser | `hoa_don_cua_toi` | User only |
| Yeu cau sua chua | `base.html`, `tenant_base.html` | Authenticated and not staff/superuser | `yeu_cau_sua_chua_cua_toi` | User only |
| Yeu cau o ghep | `base.html`, `tenant_base.html` | Authenticated and not staff/superuser | `yeu_cau_ghep_cua_toi` | User only |
| FaceProfile cua toi | `base.html`, `tenant_base.html` | Authenticated and not staff/superuser | `nhan_dien_su_dung_phong` | User only |
| Thong bao ca nhan | `base.html`, `tenant_base.html` | Authenticated and not staff/superuser | `thong_bao_cua_toi` | User only |
| Trung tam tai khoan | `base.html`, `tenant_base.html` | Authenticated and not staff/superuser | `tai_khoan` | User only |

## Admin shell

| Display group | Template | Render condition | URL names | Allowed/observed role |
|---|---|---|---|---|
| Dashboard | `base.html` | Staff or superuser | `dashboard_admin` | Admin only |
| Co so / phong | `base.html` | Staff or superuser | `quan_ly_co_so`, `quan_ly_phong` | Admin only |
| Dat phong / hop dong | `base.html` | Staff or superuser | `quan_ly_dat_phong`, `quan_ly_hop_dong` | Admin only |
| Hoa don / nguoi thue | `base.html` | Staff or superuser | `quan_ly_hoa_don`, `quan_ly_nguoi_thue` | Admin only |
| Sua chua / chinh sach / thong bao | `base.html` | Staff or superuser | `quan_ly_sua_chua`, `quan_ly_chinh_sach`, `quan_ly_thong_bao` | Admin only |
| O ghep / nguoi o cung | `base.html` | Staff or superuser | `quan_ly_yeu_cau_ghep`, `quan_ly_nguoi_o_cung` | Admin only |
| Smart Room / Face / quyen / lich su | `base.html` | Staff or superuser | `smart_room_dashboard`, `smart_access_control`, `quan_ly_face_profile`, `quan_ly_quyen_ra_vao`, `quan_ly_lich_su_ra_vao` | Admin only |
| Nhat ky thao tac | `base.html` | Staff or superuser | `nhat_ky_thao_tac` | Admin only |
| Inbox Admin | `base.html` | Staff or superuser | `thong_bao_admin` | Admin only |

## Runtime verification

- The old `.site-header` / `#adminMegaMenu` block is inside a Django `{% comment %}` and is absent from response HTML.
- Django render tests parse real anchors, panel triggers, and scoped regions on 9 User pages and 19 Admin pages.
- Render regions checked: document, topbar, sidebar, role flyouts, main content, footer, and breadcrumb-like blocks when present.
- User HTML contains no Admin route prefixes: `/quan-ly-*`, `/smart-room/`, `/nhat-ky-thao-tac/`, `/thong-bao-admin/`.
- Admin HTML contains no User-only `*-cua-toi` routes and no `/tai-khoan/` links.
- Backend access remains guarded by `la_admin()` for Admin views and ownership filters for User views.
- Playwright opens the real role flyouts and mobile sidebars for both roles and checks actual DOM link paths after opening menus.
- Admin desktop flyouts captured: operations, finance, service, smart, system, account.
- User desktop flyouts captured: stay, payment, support, account.
- Mobile captures include Admin sidebar, Admin Smart Room flyout, User sidebar, and User support flyout.

## Actual run - 2026-09-18

Commands:

```text
.\venv\Scripts\python.exe -B manage.py check
.\venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe -B manage.py test core -v 2 --keepdb
```

Results:

- `manage.py check`: PASS, 0 issues.
- `makemigrations --check --dry-run`: PASS, no changes detected.
- Full core test suite: PASS, 257 tests.
- Browser audit: PASS inside the full suite and in isolated rerun.
- Migrations generated: none.
- Test database note: the exact no-`--keepdb` test command was not used for the final run because `test_ndt_motel` already existed and the audit explicitly disallowed database reset/drop. The final full run used the existing test DB with `--keepdb`.

Artifacts:

- Browser screenshots are in `artifacts/phase6-closeout/`.
- Admin mobile menu evidence: `admin-role-menu-mobile.png` and `admin-role-menu-mobile-smart.png`.
