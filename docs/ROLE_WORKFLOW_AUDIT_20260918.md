# NDT_MOTEL: phân vai và luồng nghiệp vụ, Bước 2

## Final pre-demo payment hardening

Verified on 2026-09-18:

- A tenant payment report changes an invoice only to `cho_xac_nhan`; it does not set payment time, confirmer, transaction code or payment history.
- The Admin settlement action accepts only an invoice locked in `cho_xac_nhan`. Direct settlement from `chua_thanh_toan`, `qua_han`, `huy` or `da_thanh_toan` is rejected without payment side effects.
- The Admin invoice detail renders the settlement control only for `cho_xac_nhan`.
- Repeated tenant reports and repeated Admin confirmations remain idempotent under the existing transaction guards.

Ngày: 18/09/2026. Source: D:\NDT_MOTEL. Đối chiếu INVENTORY_AUDIT_20260918.md và đọc trực tiếp URL, view, model, template, context processor, Django admin, quy_tac_nghiep_vu và command hiện tại. Đây là thiết kế để triển khai sau; mọi URL/view/template ghi "dự kiến" chưa tồn tại nếu không trùng bộ ba hiện tại.

Phạm vi thay đổi bước này: chỉ tài liệu. Không tách views.py, sửa model/database, xóa file hoặc triển khai luồng. Backup source Bước 1: backup_inventory_audit_20260918_163543. Kiểm tra AST hiện tại không có tên hàm cấp module trùng trong core/views.py, bao gồm các hàm thông báo, chi tiết ghép và Smart Room.

## 1. Quy ước và bảng phân quyền toàn bộ route

A: phía User (bao gồm public phục vụ tìm phòng/đăng ký). B: phía Admin. C: cả hai nhưng phân màn hình/hành động theo vai trò. D: System, bảng riêng phía dưới. Đăng nhập/đổi mật khẩu/đăng xuất là tiện ích tài khoản chung, có thể dùng chung logic; không cần tạo hai cơ chế xác thực. PDF có thể dùng chung bộ sinh với kiểm tra sở hữu và điểm gọi riêng.

Admin của ứng dụng = request.user.is_authenticated và (is_staff hoặc is_superuser), qua la_admin tại core/views.py:150; chưa có phân vai Admin nghiệp vụ chi tiết theo nhóm/permission ở các view này. Django admin dùng staff active và permission model, khác guard của ứng dụng. "Chủ phòng" dưới đây là chủ hợp đồng/người thuê chính, không phải chủ sở hữu bất động sản.

Mỗi dòng tương ứng một path khai báo trong motel_management/urls.py: 89 route (88 ứng dụng, 1 resolver /admin/). Không coi /admin/ là một view ứng dụng đơn lẻ: các URL con được Django sinh theo model đã register. Media DEBUG là URL hạ tầng có điều kiện, không phải nghiệp vụ User/Admin. Template ghi tên trong templates/core; endpoint xử lý có thể redirect về trang nhưng không render template riêng. Bảng phân loại: A=24, B=56, C=9; các tác vụ D không có route độc lập.

| Nghiệp vụ | Nhóm | URL hiện tại | View (dòng source) | Template hiện tại | Quyền trong source | Vai trò mục tiêu | Vấn đề | Quyết định | URL/view/template dự kiến |
|---|---|---|---|---|---|---|---|---|---|
| chinh sach ho tro | A | `/chinh-sach-ho-tro/` | `chinh_sach_ho_tro` (9) | `chinh_sach_ho_tro.html` | Public, không cần login | Public/User; Admin được xem | Không phát hiện đặt sai phía; public là tiện ích hỗ trợ User | Giữ | Giữ bộ ba hiện tại |
| admin.site.urls | B | `/admin/` | `admin.site.urls` (Django) | Không render trực tiếp (redirect/JSON/PDF/Django) | Django staff active + quyền model/superuser | Admin hỗ trợ kỹ thuật | LichSuRaVaoAdmin mặc định cho thêm/sửa/xóa theo permission; khác chính sách web app cấm xóa audit | Giữ + giới hạn quyền audit | Giữ /admin/; Django admin templates |
| Trang chủ | A | `/` | `home` (433) | `home.html` | Public, không cần login | Public/User; Admin được xem | Không phát hiện đặt sai phía; public là tiện ích hỗ trợ User | Giữ | Giữ bộ ba hiện tại |
| Tìm phòng | A | `/phong/` | `danh_sach_phong` (601) | `danh_sach_phong.html` | Public, không cần login | Public/User; Admin được xem | Không phát hiện đặt sai phía; public là tiện ích hỗ trợ User | Giữ | Giữ bộ ba hiện tại |
| Xem phòng | A | `/phong/<int:id>/` | `chi_tiet_phong` (838) | `chi_tiet_phong.html` | Public, không cần login | Public/User; Admin được xem | Không phát hiện đặt sai phía; public là tiện ích hỗ trợ User | Giữ | Giữ bộ ba hiện tại |
| Gửi đặt phòng | A | `/phong/<int:id>/dat/` | `dat_phong` (1054) | `dat_phong.html`, `dat_phong_thanh_cong.html` | User có hồ sơ đang hoạt động; chặn staff/superuser | User | Thiếu số người, khai báo người cùng, nhu cầu ghép, đồng ý điều khoản và thanh toán cọc | Bổ sung dữ liệu User; System tính toán | Giữ URL/view/template; thêm luồng cọc ở mục 7 |
| dang ky ghep phong | A | `/phong/<int:id>/dang-ky-ghep/` | `dang_ky_ghep_phong` (13967) | `dang_ky_ghep_phong.html` | Login + hồ sơ người thuê; không phải chủ hợp đồng | User gửi | Chỉ tạo cho_duyet; chưa có hai bước đồng ý/xác minh | Giữ phía User | Giữ bộ ba hiện tại |
| bat tat cho phep ghep | A | `/hop-dong/<int:id>/bat-tat-ghep/` | `bat_tat_cho_phep_ghep` (13804) | Không render trực tiếp (redirect/JSON/PDF/Django) | Login + đúng chủ hợp đồng đang hiệu lực; POST | User chủ hợp đồng | Đã đúng người thao tác; cần giữ kiểm tra ngày/sức chứa tại thời điểm ghi | Giữ | Giữ URL/view; không có template riêng |
| yeu cau ghep cua toi | C | `/yeu-cau-ghep-cua-toi/` | `yeu_cau_ghep_cua_toi` (14342) | `yeu_cau_ghep_cua_toi.html` | Login; User xem gửi/cần duyệt; Admin xem mọi yêu cầu chờ | User gửi/chủ hợp đồng; Admin trang riêng | Một trang tenant dùng cho cả Admin; context yeu_cau chứa queryset toàn hệ thống nhưng template hiện chỉ lặp hai danh sách đã phân phạm vi | Tách danh sách | User giữ hiện tại; Admin /quan-ly-yeu-cau-ghep/ -> quan_ly_yeu_cau_ghep -> quan_ly_yeu_cau_ghep.html |
| chi tiet yeu cau ghep | C | `/yeu-cau-ghep/<int:id>/` | `chi_tiet_yeu_cau_ghep` (14454) | `chi_tiet_yeu_cau_ghep.html` | Người gửi hoặc chủ hợp đồng hoặc Admin | User xem; Admin xem/xác minh riêng | Cùng template tenant; chủ và Admin cùng quyền duyệt cuối | Tách màn hình/hành động | User giữ; Admin /quan-ly-yeu-cau-ghep/<int:id>/ -> chi_tiet_yeu_cau_ghep_admin -> chi_tiet_yeu_cau_ghep_admin.html |
| xu ly yeu cau ghep | C | `/yeu-cau-ghep/<int:id>/xu-ly/` | `xu_ly_yeu_cau_ghep` (14589) | Không render trực tiếp (redirect/JSON/PDF/Django) | Chủ hợp đồng hoặc Admin; POST duyet/tu_choi | Chủ đồng ý; Admin xác minh; System tạo người ở | Ai trong hai cũng duyệt cuối; tạo quyền hoat_dong trước đăng ký Face ID; không gán nguoi_xu_ly trong nhánh duyệt/từ chối | Tách đôi + tự động hóa hậu xử lý | Thay bằng chu_phong_phan_hoi_ghep và xu_ly_yeu_cau_ghep_admin; mục 7 |
| dang ky | A | `/dang-ky/` | `dang_ky` (1905) | `dang_ky.html` | Public; người đăng nhập redirect theo vai trò | User/Public | Đăng ký khách thuê; không phải tạo Admin | Giữ | Giữ bộ ba |
| dang nhap | C | `/dang-nhap/` | `dang_nhap` (2168) | `dang_nhap.html` | Public; điều hướng theo staff/superuser | Public/User/Admin | Điểm xác thực chung hợp lệ | Giữ | Giữ bộ ba |
| dang xuat | C | `/dang-xuat/` | `dang_xuat` (2324) | Không render trực tiếp (redirect/JSON/PDF/Django) | Gọi logout, không kiểm tra vai trò riêng | User/Admin | Nên quy định POST cho thay đổi phiên ở giai đoạn triển khai | Giữ chức năng chung | Giữ URL/view, không template |
| tai khoan | A | `/tai-khoan/` | `tai_khoan` (2525) | `tai_khoan.html` | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| Bắt đầu đăng ký nhận diện | A | `/tai-khoan/nhan-dien-su-dung-phong/` | `nhan_dien_su_dung_phong` (16919) | Không render trực tiếp (redirect/JSON/PDF/Django) | Login; chặn Admin; hồ sơ đang hoạt động + hợp đồng duy nhất hợp lệ | User; System tạo hồ sơ | Chỉ người thuê chính; tạo hồ sơ qua GET; chuyển sang chi tiết dùng chung | Giữ ý nghĩa, tách màn hình User | Giữ điểm vào; /face-id-cua-toi/ -> face_profile_cua_toi -> face_profile_cua_toi.html |
| huy dat phong cua toi | A | `/tai-khoan/dat-phong/<int:id>/huy/` | `huy_dat_phong_cua_toi` (2780) | Không render trực tiếp (redirect/JSON/PDF/Django) | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| doi mat khau | C | `/doi-mat-khau/` | `doi_mat_khau` (2331) | `doi_mat_khau.html` | Đã đăng nhập + kiểm tra mật khẩu hiện tại | User/Admin cho chính tài khoản | Đúng chức năng tài khoản chung; UI cần điểm vào Admin rõ ràng | Giữ | Giữ bộ ba, điểm vào riêng theo vai trò |
| cap nhat thong tin | A | `/cap-nhat-thong-tin/` | `cap_nhat_thong_tin` (2419) | `cap_nhat_thong_tin.html` | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| hop dong cua toi | A | `/hop-dong-cua-toi/` | `hop_dong_cua_toi` (8721) | `hop_dong_cua_toi.html` | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| chi tiet hop dong cua toi | A | `/hop-dong-cua-toi/<int:id>/` | `chi_tiet_hop_dong_cua_toi` (8834) | `chi_tiet_hop_dong_cua_toi.html` | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| gui yeu cau gia han | A | `/hop-dong-cua-toi/<int:id>/gia-han/` | `gui_yeu_cau_gia_han` (8925) | Không render trực tiếp (redirect/JSON/PDF/Django) | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| huy yeu cau gia han | A | `/yeu-cau-gia-han/<int:id>/huy/` | `huy_yeu_cau_gia_han` (9288) | Không render trực tiếp (redirect/JSON/PDF/Django) | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| xuat hop dong pdf | C | `/hop-dong/<int:id>/xuat-pdf/` | `xuat_hop_dong_pdf` (9416) | Không render trực tiếp (redirect/JSON/PDF/Django) | Login; Admin mọi hợp đồng hoặc đúng tài khoản người thuê | User tải của mình; Admin xuất quản trị | Đã kiểm tra sở hữu; PDF ReportLab, không dùng hop_dong_pdf.html | Giữ bộ sinh PDF dùng chung; điểm gọi theo vai trò | Giữ URL/view; không template |
| hoa don cua toi | A | `/hoa-don-cua-toi/` | `hoa_don_cua_toi` (8082) | `hoa_don_cua_toi.html` | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| chi tiet hoa don cua toi | A | `/hoa-don-cua-toi/<int:id>/` | `chi_tiet_hoa_don_cua_toi` (8188) | `chi_tiet_hoa_don_cua_toi.html` | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| thanh toan hoa don cua toi | A | `/hoa-don-cua-toi/<int:id>/thanh-toan/` | `thanh_toan_hoa_don_cua_toi` (8314) | `thanh_toan_hoa_don_cua_toi.html` | User; truy vấn hóa đơn theo người thuê đang hoạt động; POST | User báo thanh toán; Admin đối soát riêng | Đã đúng phân vai; chỉ chuyển cho_xac_nhan, không xác nhận tiền về | Giữ | Giữ bộ ba |
| thong bao cua toi | A | `/thong-bao-cua-toi/` | `thong_bao_cua_toi` (11941) | `thong_bao_cua_toi.html` | Login + NguoiThue của request.user; không chặn Admin có hồ sơ thuê | User | Không truy vấn nguoi_nhan_user; không phải inbox Admin | Giữ phạm vi User | Giữ bộ ba; thêm thong_bao_admin |
| chi tiet thong bao cua toi | A | `/thong-bao-cua-toi/<int:id>/` | `chi_tiet_thong_bao_cua_toi` (12015) | `chi_tiet_thong_bao_cua_toi.html` | Login + đúng người thuê nhận thông báo | User | Xem GET tự đánh dấu đã đọc; không phục vụ người nhận Admin | Giữ; thiết kế POST đánh dấu đọc | Giữ bộ ba; endpoint POST đọc riêng |
| dashboard admin | B | `/dashboard-admin/` | `dashboard_admin` (3052) | `dashboard_admin.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| nhat ky thao tac | B | `/nhat-ky-thao-tac/` | `nhat_ky_thao_tac` (19852) | `nhat_ky_thao_tac.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| chi tiet nhat ky thao tac | B | `/nhat-ky-thao-tac/<int:id>/` | `chi_tiet_nhat_ky_thao_tac` (20019) | `chi_tiet_nhat_ky_thao_tac.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| quan ly phong | B | `/quan-ly-phong/` | `quan_ly_phong` (4393) | `quan_ly_phong.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| tao phong | B | `/quan-ly-phong/tao/` | `tao_phong` (4671) | `tao_phong.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| sua phong | B | `/quan-ly-phong/<int:id>/sua/` | `sua_phong` (5161) | `sua_phong.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xoa phong | B | `/quan-ly-phong/<int:id>/xoa/` | `xoa_phong` (4501) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| quan ly dat phong | B | `/quan-ly-dat-phong/` | `quan_ly_dat_phong` (3219) | `quan_ly_dat_phong.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| chi tiet dat phong | B | `/quan-ly-dat-phong/<int:id>/` | `chi_tiet_dat_phong` (3440) | `chi_tiet_dat_phong.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly dat phong | B | `/quan-ly-dat-phong/<int:id>/xu-ly/` | `xu_ly_dat_phong` (3543) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin; POST duyet/tu_choi/huy | Admin | Duyệt chỉ đổi đơn, không sinh hợp đồng; chưa có bước kiểm tra cọc | Tách xác nhận có hợp đồng thành một transaction | Giữ từ chối/hủy; duyệt chuyển sang xac_nhan_dat_phong_va_tao_hop_dong |
| Lập hợp đồng từ đặt phòng | B | `/quan-ly-dat-phong/<int:dat_phong_id>/tao-hop-dong/` | `tao_hop_dong` (6757) | `tao_hop_dong.html` | Admin; đơn da_duyet chưa có hợp đồng, có thời hạn | Admin xác nhận; System sinh hợp đồng | Bước riêng sau duyệt; Admin nhập số người/cho phép ghép/điều khoản; GET có thể sửa ngay_tra_du_kien; chưa đối soát cọc | Gộp xác nhận và sinh hợp đồng; giữ hỗ trợ đơn cũ | /quan-ly-dat-phong/<int:id>/xac-nhan/ -> xac_nhan_dat_phong_va_tao_hop_dong; trang chi_tiet_dat_phong.html |
| quan ly hop dong | B | `/quan-ly-hop-dong/` | `quan_ly_hop_dong` (6018) | `quan_ly_hop_dong.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| chi tiet hop dong | B | `/quan-ly-hop-dong/<int:id>/` | `chi_tiet_hop_dong` (6228) | `chi_tiet_hop_dong.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| sua hop dong | B | `/quan-ly-hop-dong/<int:id>/sua/` | `sua_hop_dong` (7173) | `sua_hop_dong.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly hop dong | B | `/quan-ly-hop-dong/<int:id>/xu-ly/` | `xu_ly_hop_dong` (7618) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly yeu cau gia han | B | `/quan-ly-hop-dong/yeu-cau-gia-han/<int:id>/xu-ly/` | `xu_ly_yeu_cau_gia_han` (6300) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| quan ly hoa don | B | `/quan-ly-hoa-don/` | `quan_ly_hoa_don` (10352) | `quan_ly_hoa_don.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| tao hoa don | B | `/quan-ly-hoa-don/tao/` | `tao_hoa_don` (12768) | `tao_hoa_don.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| chi tiet hoa don | B | `/quan-ly-hoa-don/<int:id>/` | `chi_tiet_hoa_don` (10494) | `chi_tiet_hoa_don.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| Ghi nhận/hoàn trạng thái thanh toán | B | `/quan-ly-hoa-don/<int:id>/xu-ly/` | `xu_ly_hoa_don` (10561) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin; POST xac_nhan_thanh_toan/huy_thanh_toan | Admin ghi nhận tiền mặt/đối soát; System ghi lịch sử | Không phải User thanh toán; thiếu nhánh từ chối báo thanh toán đang cho_xac_nhan; hủy chỉ áp dụng da_thanh_toan | Giữ + tách rõ ghi nhận/đối soát/từ chối | Giữ URL/view; bổ sung hành động dự kiến trong chi_tiet_hoa_don.html |
| quan ly sua chua | B | `/quan-ly-sua-chua/` | `quan_ly_sua_chua` (11107) | `quan_ly_sua_chua.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| chi tiet sua chua | B | `/quan-ly-sua-chua/<int:id>/` | `chi_tiet_sua_chua` (11174) | `chi_tiet_sua_chua.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly sua chua | B | `/quan-ly-sua-chua/<int:id>/xu-ly/` | `xu_ly_sua_chua` (11199) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| Tạo sửa chữa phía Admin | B | `/tao-sua-chua/` | `tao_sua_chua` (11396) | `tao_sua_chua.html` | Admin; phòng phải thuộc hợp đồng hiệu lực của người thuê | Admin ghi phiếu nội bộ/hỗ trợ | Hiện bắt buộc người thuê và phòng đang thuê; chưa thể ghi sự cố phòng trống/khu chung | Đổi nghĩa thành phiếu nội bộ có nguồn | /quan-ly-sua-chua/tao-noi-bo/ -> tao_phieu_su_co_noi_bo -> tao_phieu_su_co_noi_bo.html |
| yeu cau sua chua cua toi | A | `/yeu-cau-sua-chua-cua-toi/` | `yeu_cau_sua_chua_cua_toi` (11600) | `yeu_cau_sua_chua_cua_toi.html` | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| tao yeu cau sua chua | A | `/yeu-cau-sua-chua-cua-toi/tao/` | `tao_yeu_cau_sua_chua` (11648) | `tao_yeu_cau_sua_chua.html` | Login; hồ sơ người thuê và dữ liệu của chính tài khoản | User | Không phát hiện đặt sai phía; các thiếu sót toàn luồng ở mục 4 | Giữ | Giữ bộ ba hiện tại |
| chi tiet yeu cau sua chua cua toi | A | `/yeu-cau-sua-chua-cua-toi/<int:id>/` | `chi_tiet_yeu_cau_sua_chua_cua_toi` (11760) | `chi_tiet_yeu_cau_sua_chua_cua_toi.html` | Login; đúng nguoi_thue; Admin redirect sang quản trị | User | Chỉ xem, chưa có thao tác hủy | Giữ + thêm endpoint hủy riêng | Giữ bộ ba; thêm huy_yeu_cau_sua_chua_cua_toi |
| quan ly chinh sach | B | `/quan-ly-chinh-sach/` | `quan_ly_chinh_sach` (11800) | `quan_ly_chinh_sach.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| tao chinh sach | B | `/quan-ly-chinh-sach/tao/` | `tao_chinh_sach` (12572) | `tao_chinh_sach.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| chi tiet chinh sach | B | `/quan-ly-chinh-sach/<int:id>/` | `chi_tiet_chinh_sach` (11835) | `chi_tiet_chinh_sach.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly chinh sach | B | `/quan-ly-chinh-sach/<int:id>/xu-ly/` | `xu_ly_chinh_sach` (13211) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| quan ly thong bao | B | `/quan-ly-thong-bao/` | `quan_ly_thong_bao` (11860) | `quan_ly_thong_bao.html` | Admin; queryset tất cả ThongBao | Admin quản lý gửi; inbox nhận riêng | Trang quản lý tất cả, không lọc nguoi_nhan_user=request.user; badge đã đọc là người nhận | Tách gửi/nhận | Giữ bộ ba quản lý; thêm /thong-bao-admin/ |
| tao thong bao | B | `/quan-ly-thong-bao/tao/` | `tao_thong_bao` (12065) | `tao_thong_bao.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| chi tiet thong bao | B | `/quan-ly-thong-bao/<int:id>/` | `chi_tiet_thong_bao` (11916) | `chi_tiet_thong_bao.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly thong bao | B | `/quan-ly-thong-bao/<int:id>/xu-ly/` | `xu_ly_thong_bao` (12201) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| quan ly co so | B | `/quan-ly-co-so/` | `quan_ly_co_so` (12433) | `quan_ly_co_so.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| tao co so | B | `/quan-ly-co-so/tao/` | `tao_co_so` (12670) | `tao_co_so.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| chi tiet co so | B | `/quan-ly-co-so/<int:id>/` | `chi_tiet_co_so` (12511) | `chi_tiet_co_so.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly co so | B | `/quan-ly-co-so/<int:id>/xu-ly/` | `xu_ly_co_so` (13610) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| smart room dashboard | B | `/smart-room/` | `smart_room_dashboard` (15017) | `smart_room_dashboard.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| smart access control | B | `/smart-room/access-control/` | `smart_access_control` (15313) | `smart_access_control.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| quan ly nguoi o cung | B | `/smart-room/nguoi-o-cung/` | `quan_ly_nguoi_o_cung` (15699) | `quan_ly_nguoi_o_cung.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| Thêm người ở cùng | B | `/smart-room/nguoi-o-cung/tao/` | `tao_nguoi_o_cung` (15879) | `tao_nguoi_o_cung.html` | Admin | User khai báo thường; Admin hỗ trợ/xác minh | Tạo dang_o ngay, tự tạo FaceProfile; không có yêu cầu chờ xác minh; chưa có tài khoản người cùng | Chuyển khởi tạo thường sang User; giữ hỗ trợ | User khai_bao_nguoi_o_cung; Admin giữ bộ ba với lý do/audit |
| chi tiet nguoi o cung | B | `/smart-room/nguoi-o-cung/<int:id>/` | `chi_tiet_nguoi_o_cung` (15832) | `chi_tiet_nguoi_o_cung.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly nguoi o cung | B | `/smart-room/nguoi-o-cung/<int:id>/xu-ly/` | `xu_ly_nguoi_o_cung` (16249) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin; POST | Admin xác minh/rời phòng/điều chỉnh | Có nhánh xoa hard-delete người và quyền không legacy, kéo theo FaceProfile; rời phòng chỉ update quyền hoat_dong | Giữ quản trị; thiết kế giữ lịch sử/thu hồi mọi quyền liên quan | Giữ endpoint; giới hạn hành động, thêm duyệt khai báo riêng |
| quan ly face profile | B | `/smart-room/face-profile/` | `quan_ly_face_profile` (16972) | `quan_ly_face_profile.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| tao face profile | B | `/smart-room/face-profile/tao/` | `tao_face_profile` (17069) | `tao_face_profile.html` | Admin | Admin hỗ trợ đặc biệt; System khởi tạo thông thường | Admin tạo hồ sơ trống, không phải tự chụp trong view; lời nhắc dẫn sang camera | Giữ với nghĩa hỗ trợ | Giữ bộ ba; ẩn khỏi luồng đăng ký thông thường |
| chi tiet face profile | C | `/smart-room/face-profile/<int:id>/` | `chi_tiet_face_profile` (16993) | `chi_tiet_face_profile.html` | Admin hoặc tài khoản của fp.nguoi_thue | User xem/chụp của mình; Admin xác minh | Dùng tenant_base cho cả hai; người ở cùng không có quyền tự truy cập | Tách đôi | Admin giữ URL/view, đổi template chi_tiet_face_profile_admin.html; User face_profile_cua_toi |
| xu ly face profile | B | `/smart-room/face-profile/<int:id>/xu-ly/` | `xu_ly_face_profile` (18242) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin; POST | Admin xác minh/từ chối/vô hiệu; System đồng bộ | Cập nhật trạng thái tổng quát; chưa có cho_xac_minh/tu_choi; xác thực thủ công không gọi helper cấp quyền; vô hiệu có thu hồi quyền | Tách hành động xác minh rõ ràng | Giữ endpoint, thiết kế xac_minh/tu_choi/vo_hieu + dịch vụ đồng bộ; mục 8 |
| Chụp đăng ký Face ID | C | `/smart-room/face-profile/<int:id>/dang-ky/` | `face_id_dang_ky` (17238) | Không render trực tiếp (redirect/JSON/PDF/Django) | Login; Admin hoặc đúng tài khoản người thuê chính; POST | User chụp; System lưu chờ xác minh | Gán da_xac_thuc và cấp quyền ngay; Admin có thể chụp thay; người cùng chưa tự chụp | Chuyển luồng bình thường sang User; tách xác minh | /face-id-cua-toi/dang-ky/ -> dang_ky_face_id_cua_toi (JSON); endpoint cũ chỉ hỗ trợ đặc biệt có audit |
| trang xac thuc face id | B | `/smart-room/face-id/` | `trang_xac_thuc_face_id` (17696) | `xac_thuc_face_id.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| face id xac thuc | B | `/smart-room/face-id/xac-thuc/` | `face_id_xac_thuc` (17732) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| quan ly quyen ra vao | B | `/smart-room/quyen-ra-vao/` | `quan_ly_quyen_ra_vao` (18508) | `quan_ly_quyen_ra_vao.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| tao quyen ra vao | B | `/smart-room/quyen-ra-vao/tao/` | `tao_quyen_ra_vao` (18556) | `tao_quyen_ra_vao.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| chi tiet quyen ra vao | B | `/smart-room/quyen-ra-vao/<int:id>/` | `chi_tiet_quyen_ra_vao` (18530) | `chi_tiet_quyen_ra_vao.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly quyen ra vao | B | `/smart-room/quyen-ra-vao/<int:id>/xu-ly/` | `xu_ly_quyen_ra_vao` (19063) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| quan ly lich su ra vao | B | `/smart-room/lich-su-ra-vao/` | `quan_ly_lich_su_ra_vao` (19384) | `quan_ly_lich_su_ra_vao.html` | Admin | Admin | Chỉ lọc phòng/loại sự kiện; chưa có lọc người/khoảng thời gian trong view | Giữ; bổ sung lọc sau | Giữ bộ ba; User lich_su_ra_vao_cua_toi |
| tao lich su ra vao | B | `/smart-room/lich-su-ra-vao/tao/` | `tao_lich_su_ra_vao` (19431) | `tao_lich_su_ra_vao.html` | Admin; nguồn cố định thu_cong; chủ thể đúng phòng/thời điểm | Admin hỗ trợ đặc biệt; terminal/System ghi tự động | Luồng thủ công đã phân nguồn; không dùng làm camera giả | Giữ hỗ trợ; tự động ghi sự kiện thật | Giữ bộ ba |
| chi tiet lich su ra vao | B | `/smart-room/lich-su-ra-vao/<int:id>/` | `chi_tiet_lich_su_ra_vao` (19413) | `chi_tiet_lich_su_ra_vao.html` | Admin: login + la_admin (staff hoặc superuser) | Admin | Không phát hiện đặt sai phía; phụ thuộc luồng liên quan ở mục 3 | Giữ | Giữ bộ ba hiện tại |
| xu ly lich su ra vao | B | `/smart-room/lich-su-ra-vao/<int:id>/xu-ly/` | `xu_ly_lich_su_ra_vao` (19791) | Không render trực tiếp (redirect/JSON/PDF/Django) | Admin; yêu cầu xóa bị từ chối | Admin chỉ xem audit | Web app đã chặn xóa; Django admin chưa chặn tương đương | Giữ kiểm soát; kiểm tra mọi đường ghi/xóa | Giữ endpoint tương thích; không tạo nút xóa audit |

### Tác vụ System (D)

| Nghiệp vụ | URL/view/template hiện tại | Quyền hiện tại | Vai trò đúng | Vấn đề | Quyết định và đích dự kiến |
|---|---|---|---|---|---|
| Tính ngày trả/tiền cọc | dat_phong; tinh_ngay_ket_thuc_theo_thang:78; dat_phong.html | User khởi tạo, server tính | System | Cọc dự kiến không chứng minh đã nhận tiền | Giữ tính server; thiết kế chụp giá/điều khoản tại thời điểm gửi |
| Kiểm tra sức chứa/khả dụng | Phong.so_nguoi_dang_o/so_cho_con_lai; view đặt/ghép/thêm người | Được gọi trong thao tác User/Admin | System | Tổng thực tế = 1 + người cùng dang_o; khác số người Admin nhập trong hợp đồng | Chuẩn hóa nguồn số người; kiểm tra lại trong transaction cuối |
| Giữ phòng | dat_phong kiểm tra đơn chờ; DatPhong.save -> Phong.dong_bo_trang_thai | Nội bộ | System | Chờ duyệt chặn đặt mới qua truy vấn đơn, không được mô tả nhầm thành trạng thái da_dat; chưa có hạn giữ | Thiết kế hạn giữ và giải phóng; không chạy command ghi DB ở bước audit |
| Sinh hợp đồng/số hợp đồng | tao_hop_dong:6757, HopDong.objects.create | Admin kích hoạt | System | Hai bước rời; số thứ tự theo chuỗi lớn nhất có rủi ro cạnh tranh | Dịch vụ xác nhận + tạo hợp đồng atomic/idempotent; có unique/retry hoặc bộ đếm khi triển khai |
| Đồng bộ vòng đời phòng/hợp đồng | cap_nhat_trang_thai_hop_dong:164; helper phòng:418; dong_bo_hop_dong command | Nội bộ/command; hiện còn gọi ở GET quản trị | System | Không nên phụ thuộc người mở dashboard để cập nhật | Command/job định kỳ; chưa xác minh lịch chạy ngoài source |
| QR và ghi thanh toán | thanh_toan_hoa_don_cua_toi, xu_ly_hoa_don; Report/JSON không riêng | User báo, Admin xác nhận | System hậu xử lý | QR chỉ tạo nội dung chuyển khoản, không phải chứng từ ngân hàng | Giữ QR; log sau xác nhận, chống xác nhận trùng; config ngân hàng sau |
| Hóa đơn quá hạn | quy_tac_nghiep_vu.dong_bo_hoa_don_qua_han + command cùng tên | Command explicit | System | Có command, chưa chứng minh scheduler hoạt động | Lập lịch; giữ nguyên trạng thái cho_xac_nhan để đối soát, quy định cách hiển thị quá hạn |
| Khởi tạo FaceProfile | nhan_dien_su_dung_phong; tao_nguoi_o_cung; xu_ly_yeu_cau_ghep | Nội bộ | System | Ba điểm tạo; người cùng chưa liên kết account | Một quy tắc tạo khi User bắt đầu; không tạo trùng |
| Cấp/cập nhật quyền | _smart_room_dong_bo_quyen_sau_dang_ky:16892; xu_ly_yeu_cau_ghep; gia hạn/hủy | Nội bộ | System sau xác minh Admin | Hiện đăng ký camera tự xác thực; ghép tạo quyền hoạt động trước xác minh | Chỉ cấp sau danh tính + hợp đồng + xác minh; không mở lại quyền tam_khoa/bi_thu_hoi khi chụp lại |
| Ghi lượt ra/vào | face_id_xac_thuc:17732, smart_access_control:15313 | Hiện Admin vận hành endpoint | System/terminal được xác thực | Chưa có tài khoản/credential terminal riêng; simulation không phải sự kiện phần cứng thật | Giữ Admin vận hành hiện tại; thiết kế terminal riêng, phân nguồn; không mở API public |
| Thông báo sự kiện/nhắc hạn | ThongBao.objects.create trong view; dong_bo_hop_dong command | Nội bộ | System | Người nhận chủ yếu nguoi_thue; nguoi_nhan_user chưa được view/command dùng | Gửi đến đúng User/Admin sau commit; mã sự kiện chống trùng, trạng thái đọc riêng |
| Nhật ký và lịch sử | ghi_nhat_ky; LichSuHopDong/ThanhToan/SuaChua/RaVao | Nội bộ | System | Đường Django admin còn cho sửa/xóa audit theo permission | Audit giữ lịch sử, không sửa/xóa; chỉnh sai bằng bản ghi bổ sung |

Template không render hiện tại: hop_dong_pdf.html, lich_su_ra_vao.html. Giữ lại để đánh giá sau, không tự tái sử dụng làm trang User vì chưa kiểm tra context/mức lộ dữ liệu. base.html và tenant_base.html là layout đang dùng.

## 2. Chức năng đang sai phía hoặc trộn trách nhiệm

| Ưu tiên | Bằng chứng source | Kết luận nghiệp vụ |
|---|---|---|
| Cao | face_id_dang_ky:17554 và helper:16892 | Camera tạo encoding rồi gán da_xac_thuc/cấp quyền; bỏ qua bước Admin xác minh danh tính mục tiêu. Kiểm tra ảnh sáng/kích thước/trùng vector không thay thế đối chiếu người thật với hồ sơ |
| Cao | xu_ly_yeu_cau_ghep:14589 (tạo người/FaceProfile/QuyenRaVao trong nhánh duyet) | Chủ hợp đồng hoặc Admin đều duyệt cuối độc lập. Thiếu trình tự chủ đồng ý rồi Admin xác minh; quyền hoat_dong sinh trước Face ID. Endpoint camera vẫn lọc FaceProfile đã xác thực nên không kết luận quyền này tự nó mở cửa qua camera |
| Cao | helper _smart_room_user_co_quyen_voi_face_profile:16877; NguoiOCungPhong:1959 | Người ở cùng không liên kết account và không tự đăng ký/xem Face ID; Admin là người đang thao tác thay. Không được suy ra quyền sở hữu bằng tên/CCCD hoặc cho chủ hợp đồng chụp thay người cùng |
| Cao | core/admin.py: LichSuRaVaoAdmin kế thừa ModelAdmin mặc định | App chặn xóa tại xu_ly_lich_su_ra_vao:19791 nhưng Django admin còn có quyền sửa/xóa theo permission. Chính sách audit chưa đồng nhất; kiểm tra cả cascade Phong.on_delete=CASCADE |
| Trung bình | tao_hop_dong:6876-6882; dat_phong:1054 | Số người/cho phép ghép đang nhập phía Admin vì User chưa cung cấp trong đặt phòng. Không phải dữ liệu User đã gửi mà Admin đang nhập lại: source hiện chưa có các trường này trong DatPhong |
| Trung bình | tao_nguoi_o_cung:15879 | Khai báo thường đặt ở Admin; tạo dang_o trực tiếp. Giữ Admin nhập hỗ trợ đặc biệt với lý do/người nhập, chuyển khai báo thường sang User và có bước xác minh |
| Trung bình | chi_tiet_face_profile:16993, template tenant_base | Trang chi tiết/chụp chung cho hai vai trò; tách trang User đăng ký với trang Admin duyệt |
| Trung bình | tao_sua_chua:11396 | Admin tạo thay người thuê. Có thể giữ hỗ trợ và đổi nghĩa phiếu sự cố nội bộ; hiện bắt buộc phòng thuộc hợp đồng hiệu lực nên chưa dùng được cho khu chung/phòng trống |

yeu_cau_ghep_cua_toi không nên là trang Admin: tên/URL thể hiện sở hữu cá nhân, template là tenant, hai danh sách "cần duyệt/đã gửi" khác với quản trị toàn hệ thống có lịch sử/lọc/audit. Hiện source cố ý cho Admin vào, nên đây là vấn đề phân vai thiết kế, không phải endpoint bị truy cập trái guard hiện có.

Queryset tat_ca_yeu_cau được đưa vào context dưới key yeu_cau cho cả User. Template hiện không lặp key này; chưa có bằng chứng lộ danh sách toàn hệ thống ra HTML. Khi tách cần loại context rộng để tránh phát sinh lộ dữ liệu về sau.

## 3. Đánh giá kỹ 10 nhóm nghiệp vụ

| Nhóm | Hiện tại có gì | Vai trò và quyết định mục tiêu |
|---|---|---|
| Đặt phòng | User gửi họ tên/SDT/email/CCCD/ngày nhận/tháng/ghi chú; server tính ngày trả và cọc; xem trong tai_khoan, hủy cho_duyet có lý do. Admin xem/duyệt/từ chối/hủy trước hợp đồng | User thêm số người, người cùng, nhu cầu ghép, chấp thuận điều khoản, báo chuyển cọc. Admin đối soát/kiểm tra dữ liệu rồi xác nhận một lần; không nhập lại thông tin User. System giữ phòng theo hạn, kiểm tra sức chứa và sinh hợp đồng |
| Hợp đồng | Admin duyệt đơn rồi mở tao_hop_dong nhập thông số; ngày/thời hạn được lấy từ đơn. User xem/PDF/gửi-hủy gia hạn; Admin sửa/hủy/gia hạn | Gộp thao tác thường thành "Xác nhận đặt phòng & tạo hợp đồng". Giữ tao_hop_dong.html làm trang hỗ trợ xử lý đơn cũ thiếu dữ liệu/ngoại lệ, có lý do và audit. Không xóa route cũ trước chuyển link/test. Điều khoản và giá cần snapshot; ngoại lệ phải được User biết/chấp thuận |
| Người cùng | Admin quản trị/thêm/sửa/rời/quay lại/xóa có điều kiện; tạo FaceProfile trống. NguoiOCungPhong chỉ có dang_o/da_roi | User khai báo và xem người phòng mình; chỉnh/hủy yêu cầu chưa xử lý. Admin xác minh/rời phòng. Cần thiết kế đối tượng yêu cầu chờ và liên kết account/mời người cùng, không dùng dang_o làm "chờ xác minh". Admin tạo thủ công chỉ hỗ trợ đặc biệt |
| Ở ghép | Người khác gửi; chủ bật/tắt; chủ hoặc Admin duyệt một bước, tạo người cùng/hồ sơ/quyền và cập nhật số người | Người gửi xem/hủy trước xử lý; chủ đồng ý/từ chối; Admin chỉ xác minh sau chủ đồng ý, không tự bỏ qua chủ. System kiểm tra cuối/tạo người cùng idempotent; đăng ký Face ID sau đó. Cần trạng thái tách cho_chu_phong/cho_admin (tên dự kiến), chủ phản hồi và Admin xử lý lưu người/thời điểm riêng |
| Face ID | User chính bắt đầu tạo hồ sơ và chụp; Admin list/tạo/chi tiết/cập nhật trạng thái/ảnh/vô hiệu. Chụp tự gán đã xác thực | User tự chụp/xem trạng thái/chụp lại sau từ chối. Admin xác minh/từ chối/vô hiệu, không chụp thay trong luồng thường. Cần tách "có encoding" với "đã xác minh danh tính", lưu người xác minh/thời gian/lý do. Tạo profile thủ công giữ ở hỗ trợ |
| Quyền ra vào | Toàn bộ route list/tạo/chi tiết/xử lý thuộc Admin; chi tiết FaceProfile có hiển thị một quyền gắn hợp đồng hiện tại | User chỉ đọc quyền chính mình. Admin khóa/mở/thu hồi, cấp thủ công có lý do. System cấp sau Face xác minh và hợp đồng hợp lệ, hết hạn không vượt hợp đồng; giữ khóa/thu hồi khi chụp lại/gia hạn |
| Lịch sử ra vào | Admin list lọc phòng/loại, chi tiết, thêm thủ công; endpoint xóa từ chối; camera ghi tự động | User chỉ lịch sử định danh mình, không toàn bộ người cùng/phòng. Admin lọc người/phòng/khoảng thời gian, không xóa. Terminal ghi sự kiện tự động có credential; nhập thủ công là ngoại lệ phân nguồn |
| Hóa đơn/thanh toán | User chọn tiền mặt/chuyển khoản, QR, xác nhận gửi -> cho_xac_nhan. Admin xu_ly_hoa_don xác nhận -> da_thanh_toan, tạo lịch sử; hoàn xác nhận -> trạng thái theo hạn | Phân vai hiện cơ bản đúng. Không có hàm/URL thanh_toan_hoa_don phía Admin trong source hiện tại; chỉ xu_ly_hoa_don. Admin ghi nhận tiền mặt/đối soát khác User báo trả tiền. Cần nhánh từ chối báo thanh toán có lý do, không dùng huy_thanh_toan vì nhánh đó chỉ cho da_thanh_toan |
| Sửa chữa | User tạo/xem; chi tiết chỉ render, không có route/nhánh hủy User. Admin tiếp nhận/cập nhật trạng thái/chi phí/người xử lý và tạo thay | Giữ User gửi/xem, bổ sung hủy khi chưa xử lý. Admin phiếu nội bộ phải phân nguồn và xử lý khu chung/phòng trống nếu yêu cầu; cần schema đề xuất sau, không chỉ đổi nhãn form hiện tại |
| Thông báo | User list/chi tiết theo nguoi_thue; mở chi tiết tự đọc. Admin list tất cả/tạo/xử lý. ThongBao có nguoi_nhan_user nhưng chưa được source view/command dùng | Chưa có inbox nhận nghiệp vụ riêng cho Admin. Chuông Admin đang vào quản lý. Giữ quản lý gửi; thêm inbox cá nhân Admin/read action. System gửi đúng recipient khi đặt/cọc/hóa đơn/sửa chữa/Face/ghép/gia hạn; không dùng da_doc người thuê làm badge Admin |

## 4. Chức năng User còn thiếu

| Chức năng thiếu | Phạm vi/chốt quyền | Phụ thuộc |
|---|---|---|
| Đặt phòng đầy đủ | Số người, danh sách người cùng, nhu cầu ghép, chấp thuận điều khoản | Snapshot dữ liệu trong yêu cầu, chính sách sức chứa/đồng ý |
| Thanh toán cọc | QR/báo chuyển/xem trạng thái, chỉ đơn của mình; QR không tự xác nhận | Cơ chế chứng từ/cọc, đối soát Admin, hạn giữ/hoàn cọc |
| Khai báo/quản lý yêu cầu người cùng | Chủ hợp đồng tạo/chỉnh/hủy trước xử lý; chỉ phòng của mình | Yêu cầu chờ, Admin xác minh |
| Tài khoản người cùng + Face tự đăng ký | Người cùng tự đăng nhập/chụp hồ sơ của chính mình | Account binding xác minh, lời mời/nhận lời, tránh ghép theo tên/CCCD |
| FaceProfile riêng và trạng thái xét duyệt | User xem/chụp lại hồ sơ mình, không sửa trạng thái xét duyệt | cho_xac_minh/tu_choi hoặc trạng thái kiểm duyệt riêng |
| Quyền ra vào của tôi | Chỉ đọc quyền gắn chính chủ thể tài khoản, gồm trạng thái/hạn/lý do | Account mapping và nguồn/hợp đồng quyền |
| Lịch sử ra vào của tôi | Chỉ sự kiện định danh mình; sự kiện không nhận diện không được gán theo phòng | Account mapping; chính sách thời hạn lưu dữ liệu |
| Hủy yêu cầu ghép của tôi | Người gửi, chưa có quyết định cuối; quy định rõ sau chủ đồng ý | Trạng thái hai bước/kiểm tra atomic |
| Hủy sửa chữa của tôi | Người gửi khi còn mới, chưa tiếp nhận | Trạng thái hủy hoặc thiết kế sự kiện hủy, lịch sử |
| Lịch sử thanh toán riêng | Có lịch sử tại chi tiết hóa đơn, thiếu trang tổng hợp cá nhân | Truy vấn qua hợp đồng của mình; không đọc audit toàn hệ thống |

Đã có gửi/hủy gia hạn, hủy đặt phòng chờ, PDF, thông báo cá nhân và đăng ký Face ID người thuê chính: không liệt kê sai là chức năng chưa có.

## 5. Chức năng Admin cần giữ và việc tự động hóa

Giữ dashboard; quản lý cơ sở/phòng/giá/sức chứa; quản lý đặt phòng và kiểm tra cọc; quản lý hợp đồng/sửa/hủy/gia hạn; tạo hóa đơn/đối soát/ghi tiền mặt/điều chỉnh có audit; tiếp nhận sửa chữa/phiếu nội bộ; quản lý chính sách; soạn/gửi/quản lý thông báo; quản lý người cùng/xác minh/rời phòng; list FaceProfile/xác minh/từ chối/vô hiệu; quản lý quyền/khóa/mở/thu hồi/cấp ngoại lệ; lịch sử ra vào và nhật ký; vận hành camera/Smart Room. Các chức năng tạo người cùng/tạo FaceProfile/cấp quyền/thêm lịch sử thủ công giữ trong nhóm hỗ trợ đặc biệt, có lý do và audit, không là bước User thường phải nhờ Admin nhập.

System cần xử lý: tính ngày/giá cọc; giữ/giải phóng phòng theo hạn; kiểm tra sức chứa; sinh số/hợp đồng sau xác nhận; cập nhật phòng; khởi tạo FaceProfile; cấp quyền sau xác minh; cập nhật hạn theo gia hạn; thu hồi khi hủy/rời/vô hiệu/hết hạn; ghi sự kiện/nhật ký/lịch sử; thông báo sự kiện/nhắc hạn; hóa đơn quá hạn. "Tự động" không đồng nghĩa bỏ quyết định Admin: Admin xác minh tiền/danh tính, System chỉ ghi hậu quả đã được phép.

## 6. Menu và điều hướng

| Nơi | Bằng chứng | Vấn đề/đích cần sửa sau |
|---|---|---|
| base.html menu Admin vận hành | dòng 643 và 993: url yeu_cau_ghep_cua_toi | Trỏ trang tenant. Chuyển quan_ly_yeu_cau_ghep sau khi route mới tồn tại |
| base.html chuông Admin | dòng 613 và 1499: quan_ly_thong_bao | Quản lý toàn bộ thông báo, không inbox nhận. Trỏ thong_bao_admin; giữ quản lý gửi ở menu dịch vụ |
| base.html tài khoản Admin | dòng 595/630/1574: tai_khoan | View tai_khoan:2525 redirect Admin về dashboard; không phải hồ sơ Admin thực sự. Thiết kế tai_khoan_admin hoặc đổi điểm vào phù hợp |
| tenant_base.html | dòng 14 chỉ kiểm tra not is_staff, bỏ is_superuser | Superuser không staff có thể thấy thanh điều hướng tenant dù nhiều view chặn. Đồng nhất guard menu theo la_admin; không kết luận User thường được quyền Admin |
| tenant_base.html | dòng 16-23 có tài khoản/hợp đồng/hóa đơn/sửa chữa/ghép/thông báo/chính sách/Face | Đã có Face ID; thiếu người cùng/quyền của tôi/lịch sử của tôi/tổng hợp thanh toán (route chưa có) |
| Dashboard Admin | dashboard_admin.html:1289-1443 | Link quản trị hiện đúng; chưa có link quản lý ghép/inbox nhận riêng. Không có bằng chứng dashboard này trỏ trực tiếp yeu_cau_ghep_cua_toi |
| Smart Room dashboard | smart_room_dashboard.html:797/802/1347-1395 | Link terminal/quan_ly_* đúng Admin; link chi_tiet_phong:1060 là public hợp lệ, không phải sai vai trò |
| Smart Access Control | smart_access_control.html:630/633/1261 | Đúng quản trị; POST Face nhận diện vào face_id_xac_thuc đang chỉ Admin |
| Chi tiết FaceProfile | chi_tiet_face_profile.html:1/578/764/1134 | Layout tenant dùng cho Admin, hành động quản trị có điều kiện la_admin_smart_room; camera chung cần tách User/Admin |

Không phát hiện link quản trị được chủ động đưa vào menu User thường qua các nhánh role đã đọc trong base.html; User truy cập URL quản trị trực tiếp vẫn bị guard la_admin. Các flyout tenant/Admin nằm trong cùng DOM cần giữ đúng nhánh hiển thị; bảo mật phải nằm tại view/queryset, không dựa vào ẩn menu.

Menu User mục tiêu: phòng, tài khoản/đặt phòng, hợp đồng/gia hạn/PDF, người cùng, ghép (đã gửi/yêu cầu vào phòng), hóa đơn/lịch sử thanh toán, Face của tôi, quyền của tôi, lịch sử ra vào của tôi, sửa chữa, thông báo, chính sách. Menu Admin mục tiêu: vận hành, tài chính, dịch vụ, Smart Room, audit, inbox nhận; tách tạo thủ công vào hỗ trợ.

## 7. URL/view/template cần tạo mới (chỉ dự kiến)

Template dưới đây nằm trong templates/core. Endpoint POST/JSON không có trang riêng. Giữ tên route cũ nơi phù hợp để giảm gãy link; không dùng /admin/ cho trang nghiệp vụ mới vì Django admin đã chiếm prefix.

| Vai trò/nghiệp vụ | URL dự kiến | View/route name dự kiến | Template dự kiến |
|---|---|---|---|
| User chi tiết đặt phòng | /dat-phong-cua-toi/<int:id>/ | chi_tiet_dat_phong_cua_toi | chi_tiet_dat_phong_cua_toi.html |
| User chuyển cọc | /dat-phong-cua-toi/<int:id>/thanh-toan-coc/ | thanh_toan_coc_cua_toi | thanh_toan_coc_cua_toi.html |
| Admin đối soát cọc | /quan-ly-dat-phong/<int:id>/doi-soat-coc/ | doi_soat_coc_dat_phong | POST, về chi_tiet_dat_phong.html |
| Admin xác nhận + hợp đồng | /quan-ly-dat-phong/<int:id>/xac-nhan/ | xac_nhan_dat_phong_va_tao_hop_dong | POST, từ chi_tiet_dat_phong.html |
| User danh sách người cùng | /nguoi-o-cung-cua-toi/ | nguoi_o_cung_cua_toi | nguoi_o_cung_cua_toi.html |
| User khai báo | /nguoi-o-cung-cua-toi/khai-bao/ | khai_bao_nguoi_o_cung | khai_bao_nguoi_o_cung.html |
| User chi tiết/chỉnh yêu cầu khai báo | /khai-bao-nguoi-o-cung/<int:id>/ | chi_tiet_khai_bao_nguoi_o_cung | chi_tiet_khai_bao_nguoi_o_cung.html |
| User hủy khai báo | /khai-bao-nguoi-o-cung/<int:id>/huy/ | huy_khai_bao_nguoi_o_cung | POST, không riêng |
| Admin danh sách khai báo | /smart-room/khai-bao-nguoi-o-cung/ | quan_ly_khai_bao_nguoi_o_cung | quan_ly_khai_bao_nguoi_o_cung.html |
| Admin chi tiết/xác minh khai báo | /smart-room/khai-bao-nguoi-o-cung/<int:id>/ | chi_tiet_khai_bao_nguoi_o_cung_admin | chi_tiet_khai_bao_nguoi_o_cung_admin.html |
| Admin xử lý khai báo | /smart-room/khai-bao-nguoi-o-cung/<int:id>/xu-ly/ | xu_ly_khai_bao_nguoi_o_cung | POST, không riêng |
| Admin quản lý ghép | /quan-ly-yeu-cau-ghep/ | quan_ly_yeu_cau_ghep | quan_ly_yeu_cau_ghep.html |
| Admin chi tiết ghép | /quan-ly-yeu-cau-ghep/<int:id>/ | chi_tiet_yeu_cau_ghep_admin | chi_tiet_yeu_cau_ghep_admin.html |
| Admin xác minh ghép | /quan-ly-yeu-cau-ghep/<int:id>/xu-ly/ | xu_ly_yeu_cau_ghep_admin | POST, không riêng |
| Chủ hợp đồng phản hồi ghép | /yeu-cau-ghep/<int:id>/phan-hoi/ | chu_phong_phan_hoi_ghep | POST, từ chi_tiet_yeu_cau_ghep.html |
| Người gửi hủy ghép | /yeu-cau-ghep/<int:id>/huy/ | huy_yeu_cau_ghep_cua_toi | POST, không riêng |
| User Face của tôi | /face-id-cua-toi/ | face_profile_cua_toi | face_profile_cua_toi.html |
| User chụp lại/đăng ký | /face-id-cua-toi/dang-ky/ | dang_ky_face_id_cua_toi | POST/JSON, không riêng |
| User quyền của tôi | /quyen-ra-vao-cua-toi/ | quyen_ra_vao_cua_toi | quyen_ra_vao_cua_toi.html |
| User lịch sử ra vào | /lich-su-ra-vao-cua-toi/ | lich_su_ra_vao_cua_toi | lich_su_ra_vao_cua_toi.html |
| User lịch sử thanh toán | /lich-su-thanh-toan-cua-toi/ | lich_su_thanh_toan_cua_toi | lich_su_thanh_toan_cua_toi.html |
| User hủy sửa chữa | /yeu-cau-sua-chua-cua-toi/<int:id>/huy/ | huy_yeu_cau_sua_chua_cua_toi | POST, không riêng |
| Admin phiếu nội bộ | /quan-ly-sua-chua/tao-noi-bo/ | tao_phieu_su_co_noi_bo | tao_phieu_su_co_noi_bo.html |
| Admin inbox | /thong-bao-admin/ | thong_bao_admin | thong_bao_admin.html |
| Admin chi tiết inbox | /thong-bao-admin/<int:id>/ | chi_tiet_thong_bao_admin | chi_tiet_thong_bao_admin.html |
| Admin đánh dấu đọc | /thong-bao-admin/<int:id>/doc/ | doc_thong_bao_admin | POST, không riêng |
| User đánh dấu đọc | /thong-bao-cua-toi/<int:id>/doc/ | doc_thong_bao_cua_toi | POST, không riêng |
| Admin tài khoản riêng | /tai-khoan-admin/ | tai_khoan_admin | tai_khoan_admin.html |

Cần thiết kế account binding/mời người cùng trước khi chốt endpoint nhận lời hoặc Face người cùng. Không giả định có thể tự ánh xạ tài khoản người gửi ghép sang NguoiOCungPhong bằng CCCD. Trang Face phải resolve đúng chủ thể và hợp đồng hợp lệ từ account.

## 8. URL/view/template cần đổi nghĩa hoặc tách

| Hiện tại | Đích thiết kế | Tương thích |
|---|---|---|
| yeu_cau_ghep_cua_toi + template | Giữ User; Admin có bộ ba quản lý riêng | Chuyển cả hai link Admin trong base sau khi có route |
| chi_tiet_yeu_cau_ghep | User người gửi/chủ xem; Admin dùng chi_tiet_yeu_cau_ghep_admin | Kiểm tra dữ liệu/field nhạy cảm theo vai trò |
| xu_ly_yeu_cau_ghep | Hai endpoint chủ phản hồi và Admin xác minh | Endpoint cũ không còn được duyệt cuối thay Admin |
| tao_hop_dong/tao_hop_dong.html | Gộp luồng thường vào xác nhận đơn; hỗ trợ đơn cũ/ngoại lệ | Không tự tạo hợp đồng cho đơn đã duyệt trước đây khi mở GET |
| tao_nguoi_o_cung | Hỗ trợ đặc biệt; User khai báo qua yêu cầu | Không rename ngay khi chưa có model yêu cầu |
| chi_tiet_face_profile/chi_tiet_face_profile.html | Admin chi_tiet_face_profile_admin.html; User Face riêng | Helper ownership phải hỗ trợ account người cùng đã xác minh |
| face_id_dang_ky | Camera User lưu chờ; Admin hỗ trợ tách riêng có lý do | Không cấp quyền trước Admin; chụp lại không tự mở khóa |
| xu_ly_face_profile | Xác minh/từ chối/vô hiệu rõ; cập nhật quyền hậu xử lý | Không dùng dropdown đổi sang da_xac_thuc như quyết định đủ điều kiện |
| tao_face_profile | Giữ tạo thủ công hồ sơ trống cho hỗ trợ | System tạo thường khi User bắt đầu |
| tao_sua_chua/tao_sua_chua.html | Phiếu sự cố nội bộ + nguồn ghi nhận | Legacy route chỉ chuyển sau cập nhật link/test; schema hiện chưa đủ khu chung |
| quan_ly_thong_bao | Quản lý gửi tách inbox nhận | Không đổi da_doc User khi Admin đọc inbox |
| quan_ly_lich_su_ra_vao | Giữ quản trị, thêm người/thời gian; User riêng | Chặn sửa/xóa cả Django admin/cascade; không tái dùng template cũ mù context |

## 9. Luồng hiện tại và mục tiêu

| Luồng | Hiện tại đọc từ source | Mục tiêu |
|---|---|---|
| Đặt phòng/hợp đồng | User thông tin cơ bản -> đơn cho_duyet -> Admin duyệt -> đơn da_duyet -> Admin tạo hợp đồng qua form -> User xem/PDF -> User đăng ký Face nếu hợp đồng hiện hành | User đầy đủ số người/người cùng/ghép/điều khoản -> System tạo yêu cầu giữ tạm -> User chuyển cọc/báo chuyển -> gửi hoàn tất -> Admin đối soát/kiểm tra -> xác nhận & sinh hợp đồng atomic -> User xem -> Face. Muốn thanh toán trước gửi cần có draft/reference trước QR; không thu tiền khi chưa có định danh và chính sách giữ/hoàn |
| Face ID | User chính tạo hồ sơ -> chụp -> tự da_xac_thuc -> cấp/đồng bộ quyền. Admin có thể thao tác hồ sơ/chụp | User chụp -> chờ xác minh (chưa có quyền mới hoạt động) -> Admin đối chiếu/xác minh hoặc từ chối -> System resolve hợp đồng/cấp quyền hợp lệ. Từ chối -> User chụp lại -> chờ |
| Người cùng | Admin nhập -> dang_o -> profile trống -> Admin chụp (người cùng không có ownership account) | Chủ thuê khai báo -> Admin xác minh -> tạo người cùng + binding account -> người cùng tự đăng ký Face -> Admin xác minh Face -> System cấp quyền |
| Ở ghép | Người khác gửi -> chủ HOẶC Admin duyệt -> tạo người cùng/profile/quyền hoat_dong | Người khác gửi -> chủ đồng ý -> Admin xác minh -> System tạo người cùng/account binding -> người cùng đăng ký Face -> Admin xác minh Face -> quyền; không mặc định chủ đồng ý là xác minh danh tính |
| Hóa đơn | User QR/tiền mặt + báo -> cho_xac_nhan -> Admin xác nhận -> lịch sử + da_thanh_toan | Giữ; thêm đối soát thất bại -> từ chối có lý do -> User báo lại; Admin ghi nhận tiền mặt là hành động thu tiền riêng |
| Sửa chữa | User gửi/xem -> Admin đổi trạng thái/chi phí | Thêm User hủy trước tiếp nhận; Admin tiếp nhận/xử lý/hoàn thành/từ chối; phiếu nội bộ phân nguồn |
| Gia hạn | User gửi -> Admin duyệt/từ chối -> đổi ngày và hạn quyền; User hủy chờ | Giữ; xác minh hợp lệ ngày/giá/đồng ý thay đổi; cập nhật quyền giữ khóa/thu hồi, log đúng stay |
| Thông báo | System gửi người thuê -> User đọc; Admin quản lý tất cả | Sự kiện -> recipient User/Admin riêng -> inbox theo account -> POST đọc -> trạng thái riêng, chống trùng |

Không coi tự gán ngay_ky=timezone.now() trong tạo hợp đồng là bằng chứng User đã ký/chấp thuận; mục tiêu phải phân biệt Admin phát hành, User chấp thuận điều khoản và thời điểm hiệu lực.

## 10. Dependency, rủi ro và thứ tự triển khai an toàn

| Dependency/rủi ro | Điều kiện cần chốt trước code |
|---|---|
| Đơn -> hợp đồng | Dữ liệu số người/người cùng/ghép/điều khoản/cọc hiện chưa có ở đơn. Snapshot tại thời điểm gửi, không lấy giá phòng mới để thay giá đã chấp thuận |
| Cọc -> giữ phòng -> xác nhận | Cọc dự kiến không phải đã trả; có mã giao dịch/bằng chứng/người đối soát/hạn giữ/hoàn khi từ chối-hủy-hết hạn. Không xác nhận hợp đồng khi tiền chưa được xác minh |
| NguoiThue/account -> người cùng -> Face | Người cùng hiện không có account; liên kết phải được xác minh, không chỉ dựa CCCD/tên. User chính không sở hữu sinh trắc học người cùng |
| Face -> quyền | Chất lượng ảnh/encoding tách quyết định Admin. Từ chối/vô hiệu/chụp lại có quy tắc quyền cũ: không cho encoding mới sử dụng quyền trước duyệt, không tự mở khóa |
| Quyền -> hợp đồng/phòng/nguồn | Giữ contract_is_current, permission_binding_is_valid, eligible_permissions. Nguồn face_id/duyet_ghep/thu_cong có provenance, legacy_unknown không tự đoán hoặc hồi sinh |
| Hạn quyền -> vòng đời | Ngày hết không vượt hợp đồng; rời/hủy/hết hạn/vô hiệu thu hồi mọi quyền liên quan kể cả tam_khoa. Gia hạn không mở lại khóa/thu hồi; profile cũ không tự cấp cho stay mới |
| Sức chứa -> dữ liệu người | Phong tính người thực tế từ người cùng dang_o; HopDong.so_nguoi_o có thể khác số khai báo. Chốt "khai báo/chờ xác minh/đang ở" và kiểm tra transaction khi chuyển trạng thái |
| Concurrent workflow | Hai Admin xác nhận, hai yêu cầu ghép hoặc Face trùng cạnh tranh: unique/idempotency, thứ tự khóa phòng -> đơn/hợp đồng -> yêu cầu/quyền thống nhất; SQLite không bảo đảm select_for_update như DB có khóa dòng |
| Sinh số hợp đồng | Max chuỗi không bảo đảm tuần tự (đặc biệt vượt 999) và cạnh tranh nhiều phòng; cần bộ đếm/unique+retry, không dựa số preview form |
| Audit và cascade | Không hard-delete lịch sử; Django admin LichSuRaVao chưa chặn sửa/xóa, xóa người cùng có cascade FaceProfile và SET_NULL lịch sử, Phong cascade lịch sử. Có bản ghi điều chỉnh thay xóa |
| Tác dụng phụ GET | Dashboard/quản lý/chi tiết gọi cập nhật vòng đời; tao_hop_dong có thể sửa ngày trả trong GET; tạo Face qua GET; đọc thông báo GET ghi da_doc. Chuyển ghi sang POST/job rõ ràng sau test |
| Command -> views.py | dong_bo_hop_dong import helper từ core.views; hiện không tách file. Thiết kế service sau khi ổn luồng, tránh circular import và tải Face/PDF không cần thiết |
| Notification | nguoi_nhan_user đã có nhưng chưa dùng; quyết định recipient/sự kiện/mã chống trùng; gửi sau commit. Không gộp trạng thái đọc của nhiều Admin/người thuê |
| Terminal | Endpoint hiện chỉ Admin; nếu triển khai terminal cần credential/phòng được phép/CSRF-session hoặc cơ chế xác thực thiết bị phù hợp. Không biến endpoint thành public bằng cách bỏ guard |
| Chuyển tiếp dữ liệu cũ | Không tự biến da_xac_thuc cũ thành "Admin đã duyệt"; không auto tạo hợp đồng/cấp quyền từ hồ sơ thiếu provenance. Thiết kế đánh dấu legacy và kiểm tra theo từng stay |

Thứ tự triển khai đề xuất cho các bước sau:

1. Backup mới + snapshot DB riêng; dùng DB test để kiểm tra truy cập/ownership, lifecycle, audit và tuyến Django admin. Chốt invariants/states/dữ liệu chuyển tiếp trước triển khai.
2. Khép các đường audit sửa/xóa và đồng nhất guard User/Admin; tạo trang quản lý ghép Admin riêng, chuyển link sau khi trang có route. Giữ hành vi cũ cho tới khi state hai bước sẵn sàng.
3. Thiết kế/migrate có kiểm soát yêu cầu đầy đủ, snapshot điều khoản/giá, số người/người cùng/cọc và account binding; audit dữ liệu thiếu, không tự đoán.
4. Hoàn thiện đặt phòng/cọc/đối soát; gộp xác nhận & tạo hợp đồng atomic/idempotent; chuyển form hợp đồng riêng sang hỗ trợ.
5. Luồng khai báo người cùng và ghép hai bước, gắn tài khoản; kiểm tra sức chứa và xác minh Admin trước chuyển dang_o.
6. Tách Face User/Admin; trạng thái chờ/từ chối, quyết định Admin; dịch vụ cấp/thu hồi/hạn quyền theo đúng hợp đồng. Kiểm thử chụp lại/khóa/vô hiệu/gia hạn/chuyển stay.
7. Tạo trang chỉ đọc quyền/lịch sử cá nhân và lịch sử thanh toán; thêm hủy sửa chữa/ghép, phiếu nội bộ và nhánh từ chối báo thanh toán.
8. Inbox Admin/thông báo sự kiện; lập lịch command vòng đời/quá hạn, tách terminal xác thực nếu cần. Hoàn thiện menu theo route đã có và test end-to-end theo vai trò.
9. Chỉ cân nhắc tách views.py sau khi luồng/quyền ổn định và test regression bảo vệ; tách service trước, giữ tên route/import tương thích. Không xóa template/file cũ trong Bước 2.

Đây là thứ tự dependency; lỗi audit/ownership/cấp quyền cần ưu tiên trước mở luồng mới. Test sau này phải kiểm tra người gửi/chủ/người cùng/Admin khác nhau, User đổi id truy cập người khác, double-submit, từ chối/chụp lại, khóa/thu hồi, hợp đồng chưa bắt đầu/hết hạn và ghi lịch sử đúng nguồn.

## 11. Kiểm chứng Bước 2

Lệnh bắt buộc: .\venv\Scripts\python.exe manage.py check

Kết quả: System check identified no issues (0 silenced). Exit code 0.

Đối chiếu SHA-256 trước/sau của 148 file trong core, motel_management, templates, static, manage.py và db.sqlite3 (không tính __pycache__): không có file thay đổi/thêm/xóa trong tập kiểm tra. File mới của bước này chỉ là tài liệu này.

Phân tích là source tĩnh; không thao tác trên dữ liệu để thử luồng, không chạy migrate hoặc command đồng bộ ghi DB. manage.py check không chứng minh luồng nghiệp vụ/ownership hoạt động đúng; các phát hiện ở trên dựa guard/queryset/nhánh ghi/template đang có.
