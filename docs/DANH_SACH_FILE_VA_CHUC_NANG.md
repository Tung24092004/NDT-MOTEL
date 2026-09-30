# Danh sách file và chức năng

Cấu trúc hiện tại có **94 file Python** trong source, test nằm riêng tại `core/tests/`, fixture tại `core/du_lieu_test/`. Môi trường local ở `D:\NDT_MOTEL_ENV`, không nằm trong source giao nộp. Không đổi tên hàm, URL, route name, template, context hoặc quyền truy cập.

## Tên cần giữ

Giữ `manage.py`, `models.py`, `admin.py`, `apps.py`, `settings.py`, `urls.py`, `wsgi.py`, `asgi.py`, `__init__.py` theo quy ước/cấu hình Django. Giữ `migrations/` và tất cả tên migration vì dependency theo tên file. Giữ `templatetags/` (không đổi thành `the_tags/`) và `management/commands/` vì Django tự tìm chúng. Giữ `booking_identifiers.py` (không đổi thành `dinh_danh_dat_phong.py`) vì migration 0021 lưu đường dẫn callable của module. Những tên này không phải file rác.

`dich_vu/` và `du_lieu_test/` đã được đổi tên ở lượt trước, không đổi lại. Các test đã gom theo nghiệp vụ, không tái tạo file Phase 4/5/6 hoặc làm giảm assertion.

## Toàn bộ file Python hiện tại

| File/thư mục | Tác dụng | Website có dùng không | Có cần giữ không |
| --- | --- | --- | --- |
| `core/__init__.py` | Đánh dấu package Python để import và discovery. | Có | Có |
| `core/admin.py` | Đăng ký và bảo vệ thao tác quản trị Django. | Có | Có |
| `core/apps.py` | Khai báo ứng dụng core cho Django. | Có | Có |
| `core/bieu_mau_dat_phong.py` | Kiểm tra dữ liệu biểu mẫu đặt phòng và người đi cùng. | Có | Có |
| `core/bo_xu_ly_bo_cuc.py` | Cấp dữ liệu thông báo theo vai trò cho header. | Có | Có |
| `core/booking_identifiers.py` | Sinh mã đặt phòng/cọc và chuẩn hóa CCCD; migration 0021 tham chiếu callable theo đường dẫn này. | Có | Có |
| `core/dich_vu/__init__.py` | Đánh dấu package Python để import và discovery. | Có | Có |
| `core/dich_vu/dat_phong.py` | Dịch vụ kiểm tra, tạo/hủy đặt phòng và hạn giữ phòng. | Có | Có |
| `core/dich_vu/hop_dong.py` | Dịch vụ duyệt cọc/tạo hợp đồng trong transaction. | Có | Có |
| `core/dich_vu/ngay_thue.py` | Helper tính ngày kết thúc theo tháng lịch; giữ tên hàm cũ. | Có | Có |
| `core/dich_vu/phan_quyen.py` | Helper la_admin dùng chung cho các view. | Có | Có |
| `core/dich_vu/thong_bao_dat_phong.py` | Thông báo sự kiện đặt phòng tới Admin. | Có | Có |
| `core/dich_vu/thong_bao_quan_tri.py` | Thông báo nghiệp vụ quản trị, tránh gửi lặp. | Có | Có |
| `core/dich_vu/tien_coc.py` | Dịch vụ giao dịch cọc, báo/duyệt/từ chối và dữ liệu VietQR. | Có | Có |
| `core/du_lieu_test/__init__.py` | Đánh dấu package Python để import và discovery. | Không; chỉ test | Có |
| `core/du_lieu_test/du_lieu_test_dat_phong.py` | Fixture và payload đặt phòng/cọc. | Không; chỉ test | Có |
| `core/du_lieu_test/du_lieu_test_nghiep_vu.py` | Fixture chung, chặn ghi ngoài database test_ndt_motel. | Không; chỉ test | Có |
| `core/du_lieu_test/du_lieu_test_phan_quyen.py` | Fixture nhiều vai trò và đối chiếu dữ liệu. | Không; chỉ test | Có |
| `core/du_lieu_test/gia_lap_views.py` | Mock dependency tại module view thật; giữ hiệu lực các test render và cập nhật đồng thời. | Không; chỉ test | Có |
| `core/du_lieu_test/tap_hop_views.py` | Namespace chỉ dùng trong test để giữ cách gọi helper trước khi tách view. | Không; chỉ test | Có |
| `core/management/__init__.py` | Đánh dấu package Python để import và discovery. | Không; lệnh quản trị | Có |
| `core/management/commands/__init__.py` | Đánh dấu package Python để import và discovery. | Không; lệnh quản trị | Có |
| `core/management/commands/chuan_hoa_phong.py` | Lệnh quản trị chuan hoa phong; chỉ chạy khi được gọi thủ công. | Không; lệnh quản trị | Có |
| `core/management/commands/dong_bo_hoa_don_qua_han.py` | Lệnh quản trị dong bo hoa don qua han; chỉ chạy khi được gọi thủ công. | Không; lệnh quản trị | Có |
| `core/management/commands/dong_bo_hop_dong.py` | Lệnh quản trị dong bo hop dong; chỉ chạy khi được gọi thủ công. | Không; lệnh quản trị | Có |
| `core/management/commands/kiem_tra_toan_ven_du_lieu.py` | Lệnh quản trị kiem tra toan ven du lieu; chỉ chạy khi được gọi thủ công. | Không; lệnh quản trị | Có |
| `core/management/commands/tao_du_lieu_phong_demo.py` | Lệnh quản trị tao du lieu phong demo; chỉ chạy khi được gọi thủ công. | Không; lệnh quản trị | Có |
| `core/migrations/0001_initial.py` | Migration 0001: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0002_nguoithue.py` | Migration 0002: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0003_datphong.py` | Migration 0003: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0004_hopdong.py` | Migration 0004: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0005_hoadon.py` | Migration 0005: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0006_yeucausuachua.py` | Migration 0006: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0007_chinhsachhotro.py` | Migration 0007: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0008_chinhsachhotro_doi_tuong_khac_and_more.py` | Migration 0008: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0009_thongbao.py` | Migration 0009: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0010_nguoithue_tai_khoan.py` | Migration 0010: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0011_alter_chinhsachhotro_options_alter_coso_options_and_more.py` | Migration 0011: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0012_nguoiocungphong_quyenravao_lichsuravao_faceprofile.py` | Migration 0012: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0013_hopdong_cho_phep_ghep_yeucaughepnguoi.py` | Migration 0013: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0014_lichsuhopdong_lichsusuachua_lichsuthanhtoan_and_more.py` | Migration 0014: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0015_faceprofile_face_encoding.py` | Migration 0015: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0016_datphong_so_thang_thue.py` | Migration 0016: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0017_yeucaugiahanhopdong.py` | Migration 0017: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0018_hinhanhphong.py` | Migration 0018: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0019_alter_hoadon_trang_thai.py` | Migration 0019: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0020_quyenravao_contract_provenance.py` | Migration 0020: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/0021_booking_deposit_foundation.py` | Migration 0021: lịch sử schema/dữ liệu; giữ nguyên tên, nội dung và dependency. | Không theo request; migrate | Có |
| `core/migrations/__init__.py` | Đánh dấu package Python để import và discovery. | Không theo request; migrate | Có |
| `core/models.py` | Định nghĩa bảng, quan hệ và ràng buộc dữ liệu. | Có | Có |
| `core/quy_tac_nghiep_vu.py` | Quy tắc ngày thuê, trạng thái và ràng buộc quyền ra vào. | Có | Có |
| `core/templatetags/__init__.py` | Đánh dấu package Python để import và discovery. | Có | Có |
| `core/templatetags/bo_loc.py` | Bộ lọc vnd cho template; template vẫn load bo_loc. | Có | Có |
| `core/tests/__init__.py` | Đánh dấu package Python để import và discovery. | Không; chỉ test | Có |
| `core/tests/test_dat_phong.py` | Test hồi quy dat phong: BookingTests, BookingDepositModelTests, BookingDepositMigrationTests, BookingDepositServiceTests, TenantBookingUITests. | Không; chỉ test | Có |
| `core/tests/test_duong_dan.py` | Test hồi quy duong dan: Phase8B2RouteRegressionTests. | Không; chỉ test | Có |
| `core/tests/test_gia_han.py` | Test hồi quy gia han: RenewalTests. | Không; chỉ test | Có |
| `core/tests/test_giao_dien.py` | Test hồi quy giao dien: Phase8B3AdminDetailRenderTests, Phase8B4AdminFormRenderTests, Phase8B5TenantUIRegressionTests, TenantUITests. | Không; chỉ test | Có |
| `core/tests/test_hoa_don.py` | Test hồi quy hoa don: InvoiceTests. | Không; chỉ test | Có |
| `core/tests/test_hop_dong.py` | Test hồi quy hop dong: ContractTests, LifecycleAuthorizationTests, Phase6AdminBookingContractTests, Phase6ContractPdfTests. | Không; chỉ test | Có |
| `core/tests/test_kiem_tra_toan_ven.py` | Test hồi quy kiem tra toan ven: CrudHardeningTests, StateConsistencyTests, AdminWorkflowTests, WriterGuardTests, HistoricalAccessTests, LockOrderTests, PaymentAtomicTests, LegacyDiagnosticTests, PermissionMigrationTests. | Không; chỉ test | Có |
| `core/tests/test_o_ghep.py` | Test hồi quy o ghep: RoommateTests. | Không; chỉ test | Có |
| `core/tests/test_phan_quyen.py` | Test hồi quy phan quyen: RoleAccessMatrixTests, AuditAdminAccessTests, LinkCollector, RoleUiPaymentAuditTests. | Không; chỉ test | Có |
| `core/tests/test_phong.py` | Test hồi quy phong: CapacityTests. | Không; chỉ test | Có |
| `core/tests/test_phong_thong_minh.py` | Test hồi quy phong thong minh: AccessTests, ManualResidentTests, AccessSimulationTests. | Không; chỉ test | Có |
| `core/tests/test_thanh_toan.py` | Test hồi quy thanh toan: DepositPaymentUITests. | Không; chỉ test | Có |
| `core/tests/test_thong_bao.py` | Test hồi quy thong bao: Phase6NotificationsToastsTests. | Không; chỉ test | Có |
| `core/tien_ich.py` | Ghi nhật ký thao tác, bảo vệ nghiệp vụ khi ghi log lỗi. | Có | Có |
| `core/views.py` | Module tương thích nhỏ: re-export các hàm đã chuyển và giữ hai hàm chuyển tiếp đặt phòng; URL, service và test hiện tại không import module này. | Không trong import hiện tại; tương thích | Có |
| `core/views_chinh_sach.py` | Xử lý request chinh sach; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_dang_nhap.py` | Xử lý request dang nhap; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_dat_phong.py` | Xử lý request dat phong; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_gia_han.py` | Xử lý request gia han; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_hoa_don.py` | Xử lý request hoa don; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_hop_dong.py` | Xử lý request hop dong; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_nguoi_thue.py` | Xử lý request nguoi thue; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_nhat_ky.py` | Xử lý request nhat ky; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_o_ghep.py` | Xử lý request o ghep; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_phong.py` | Xử lý request phong; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_quan_tri.py` | Xử lý request quan tri; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_quan_tri_dat_phong.py` | Xử lý request quan tri dat phong; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_smart_room.py` | Xử lý request smart room; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_sua_chua.py` | Xử lý request sua chua; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_tai_khoan.py` | Xử lý request tai khoan; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_thanh_toan.py` | Xử lý request thanh toan; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `core/views_thong_bao.py` | Xử lý request thong bao; giữ nguyên tên hàm, quyền, context và template. | Có | Có |
| `manage.py` | Điểm chạy lệnh Django; tắt bytecode khi chạy test. | Có | Có |
| `motel_management/__init__.py` | Đánh dấu package Python để import và discovery. | Có | Có |
| `motel_management/asgi.py` | Điểm chạy server ASGI theo cấu hình Django. | Có | Có |
| `motel_management/cau_hinh_dat_phong.py` | Cấu hình ngân hàng, thời hạn giữ phòng và điều khoản cọc. | Có | Có |
| `motel_management/settings.py` | Cấu hình Django, MySQL ndt_motel, template, static, media và runner test. | Có | Có |
| `motel_management/trinh_chay_test.py` | Runner dùng media tạm ngoài project và tự dọn khi kết thúc. | Không; chỉ test | Có |
| `motel_management/urls.py` | Import view theo nhóm nghiệp vụ; giữ nguyên toàn bộ urlpatterns, tên route và tham số. | Có | Có |
| `motel_management/wsgi.py` | Điểm chạy server WSGI theo cấu hình Django. | Có | Có |

## Từng hàm trong views.py đã chuyển đi đâu

111 hàm của monolith được bảo toàn: 109 hàm chuyển nguyên nội dung sang module nghiệp vụ/helper, hai hàm chuyển tiếp giữ trong views.py. Bảng dưới ghi vị trí định nghĩa, không phải alias re-export.

| Hàm | File định nghĩa |
| --- | --- |
| `tinh_ngay_ket_thuc_theo_thang` | `core/dich_vu/ngay_thue.py` |
| `la_admin` | `core/dich_vu/phan_quyen.py` |
| `cap_nhat_trang_thai_hop_dong` | `core/views_hop_dong.py` |
| `cap_nhat_trang_thai_phong_theo_hop_dong` | `core/views_hop_dong.py` |
| `home` | `core/views_quan_tri.py` |
| `danh_sach_phong` | `core/views_phong.py` |
| `chi_tiet_phong` | `core/views_phong.py` |
| `dat_phong` | `core/views.py` |
| `dang_ky` | `core/views_dang_nhap.py` |
| `dang_nhap` | `core/views_dang_nhap.py` |
| `dang_xuat` | `core/views_dang_nhap.py` |
| `doi_mat_khau` | `core/views_tai_khoan.py` |
| `cap_nhat_thong_tin` | `core/views_tai_khoan.py` |
| `tai_khoan` | `core/views_tai_khoan.py` |
| `huy_dat_phong_cua_toi` | `core/views.py` |
| `dashboard_admin` | `core/views_quan_tri.py` |
| `quan_ly_dat_phong` | `core/views_quan_tri.py` |
| `chi_tiet_dat_phong` | `core/views_quan_tri.py` |
| `xu_ly_dat_phong` | `core/views_quan_tri.py` |
| `quan_ly_phong` | `core/views_phong.py` |
| `xoa_phong` | `core/views_phong.py` |
| `tao_phong` | `core/views_phong.py` |
| `sua_phong` | `core/views_phong.py` |
| `quan_ly_hop_dong` | `core/views_hop_dong.py` |
| `chi_tiet_hop_dong` | `core/views_hop_dong.py` |
| `xu_ly_yeu_cau_gia_han` | `core/views_gia_han.py` |
| `tao_hop_dong` | `core/views_hop_dong.py` |
| `sua_hop_dong` | `core/views_hop_dong.py` |
| `xu_ly_hop_dong` | `core/views_hop_dong.py` |
| `hoa_don_cua_toi` | `core/views_hoa_don.py` |
| `chi_tiet_hoa_don_cua_toi` | `core/views_hoa_don.py` |
| `thanh_toan_hoa_don_cua_toi` | `core/views_thanh_toan.py` |
| `hop_dong_cua_toi` | `core/views_hop_dong.py` |
| `chi_tiet_hop_dong_cua_toi` | `core/views_hop_dong.py` |
| `gui_yeu_cau_gia_han` | `core/views_gia_han.py` |
| `huy_yeu_cau_gia_han` | `core/views_gia_han.py` |
| `xuat_hop_dong_pdf` | `core/views_hop_dong.py` |
| `quan_ly_nguoi_thue` | `core/views_nguoi_thue.py` |
| `quan_ly_yeu_cau_ghep_admin` | `core/views_o_ghep.py` |
| `chi_tiet_nguoi_thue` | `core/views_nguoi_thue.py` |
| `quan_ly_hoa_don` | `core/views_hoa_don.py` |
| `chi_tiet_hoa_don` | `core/views_hoa_don.py` |
| `xu_ly_hoa_don` | `core/views_thanh_toan.py` |
| `_lay_trang_thai_sua_chua_hop_le` | `core/views_sua_chua.py` |
| `_lay_loai_su_co_hop_le` | `core/views_sua_chua.py` |
| `_lay_muc_do_hop_le` | `core/views_sua_chua.py` |
| `_lay_nguoi_thue_dang_dang_nhap` | `core/views_tai_khoan.py` |
| `_lay_phong_dang_thue_cua_nguoi_thue` | `core/views_sua_chua.py` |
| `quan_ly_sua_chua` | `core/views_sua_chua.py` |
| `chi_tiet_sua_chua` | `core/views_sua_chua.py` |
| `xu_ly_sua_chua` | `core/views_sua_chua.py` |
| `tao_sua_chua` | `core/views_sua_chua.py` |
| `yeu_cau_sua_chua_cua_toi` | `core/views_sua_chua.py` |
| `tao_yeu_cau_sua_chua` | `core/views_sua_chua.py` |
| `chi_tiet_yeu_cau_sua_chua_cua_toi` | `core/views_sua_chua.py` |
| `quan_ly_chinh_sach` | `core/views_chinh_sach.py` |
| `chi_tiet_chinh_sach` | `core/views_chinh_sach.py` |
| `quan_ly_thong_bao` | `core/views_thong_bao.py` |
| `chi_tiet_thong_bao` | `core/views_thong_bao.py` |
| `thong_bao_cua_toi` | `core/views_thong_bao.py` |
| `chi_tiet_thong_bao_cua_toi` | `core/views_thong_bao.py` |
| `tao_thong_bao` | `core/views_thong_bao.py` |
| `xu_ly_thong_bao` | `core/views_thong_bao.py` |
| `quan_ly_co_so` | `core/views_quan_tri.py` |
| `chi_tiet_co_so` | `core/views_quan_tri.py` |
| `tao_chinh_sach` | `core/views_chinh_sach.py` |
| `tao_co_so` | `core/views_quan_tri.py` |
| `tao_hoa_don` | `core/views_hoa_don.py` |
| `xu_ly_chinh_sach` | `core/views_chinh_sach.py` |
| `xu_ly_co_so` | `core/views_quan_tri.py` |
| `bat_tat_cho_phep_ghep` | `core/views_o_ghep.py` |
| `dang_ky_ghep_phong` | `core/views_o_ghep.py` |
| `yeu_cau_ghep_cua_toi` | `core/views_o_ghep.py` |
| `chi_tiet_yeu_cau_ghep` | `core/views_o_ghep.py` |
| `xu_ly_yeu_cau_ghep` | `core/views_o_ghep.py` |
| `smart_room_dashboard` | `core/views_smart_room.py` |
| `smart_access_control` | `core/views_smart_room.py` |
| `quan_ly_nguoi_o_cung` | `core/views_smart_room.py` |
| `chi_tiet_nguoi_o_cung` | `core/views_smart_room.py` |
| `tao_nguoi_o_cung` | `core/views_smart_room.py` |
| `xu_ly_nguoi_o_cung` | `core/views_smart_room.py` |
| `_face_load_models` | `core/views_smart_room.py` |
| `_face_image_from_base64` | `core/views_smart_room.py` |
| `_face_detect` | `core/views_smart_room.py` |
| `_face_feature` | `core/views_smart_room.py` |
| `_face_feature_to_text` | `core/views_smart_room.py` |
| `_face_feature_from_text` | `core/views_smart_room.py` |
| `_face_compare` | `core/views_smart_room.py` |
| `_smart_room_hop_dong_hop_le_cua_face_profile` | `core/views_smart_room.py` |
| `_smart_room_hop_dong_cua_quyen` | `core/views_smart_room.py` |
| `_smart_room_user_co_quyen_voi_face_profile` | `core/views_smart_room.py` |
| `_smart_room_dong_bo_quyen_sau_dang_ky` | `core/views_smart_room.py` |
| `nhan_dien_su_dung_phong` | `core/views_smart_room.py` |
| `quan_ly_face_profile` | `core/views_smart_room.py` |
| `chi_tiet_face_profile` | `core/views_smart_room.py` |
| `tao_face_profile` | `core/views_smart_room.py` |
| `face_id_dang_ky` | `core/views_smart_room.py` |
| `trang_xac_thuc_face_id` | `core/views_smart_room.py` |
| `_quyen_co_hop_dong_hien_tai` | `core/views_smart_room.py` |
| `face_id_xac_thuc` | `core/views_smart_room.py` |
| `xu_ly_face_profile` | `core/views_smart_room.py` |
| `quan_ly_quyen_ra_vao` | `core/views_smart_room.py` |
| `chi_tiet_quyen_ra_vao` | `core/views_smart_room.py` |
| `tao_quyen_ra_vao` | `core/views_smart_room.py` |
| `xu_ly_quyen_ra_vao` | `core/views_smart_room.py` |
| `quan_ly_lich_su_ra_vao` | `core/views_smart_room.py` |
| `chi_tiet_lich_su_ra_vao` | `core/views_smart_room.py` |
| `tao_lich_su_ra_vao` | `core/views_smart_room.py` |
| `xu_ly_lich_su_ra_vao` | `core/views_smart_room.py` |
| `nhat_ky_thao_tac` | `core/views_nhat_ky.py` |
| `chi_tiet_nhat_ky_thao_tac` | `core/views_nhat_ky.py` |

Các hàm đã tách trước đây trong `views_dat_phong.py`, `views_quan_tri_dat_phong.py`, `views_thong_bao.py`, `views_chinh_sach.py` được giữ nguyên. Hai view quản trị đặt phòng cũ trong `views_quan_tri.py` có tên giống view mới ở `views_quan_tri_dat_phong.py`; không gộp logic của chúng. URL quản trị dùng đúng alias Admin như trước.

## File khác và backup

| File/thư mục | Tác dụng | Website có dùng không | Có cần giữ không |
| --- | --- | --- | --- |
| `templates/` | HTML Django, tên và nội dung giao diện giữ nguyên | Có | Có |
| `static/` | CSS, JavaScript, font, ảnh và favicon | Có | Có |
| `media/` | File người dùng | Có | Có, không xóa |
| `models/*.onnx` | Model YuNet/SFace được views_smart_room.py load | Có | Có |
| `requirements.txt` | Package để tạo lại môi trường local | Khi cài đặt | Có |
| `db.sqlite3` | SQLite được giữ để bảo toàn dữ liệu; runtime cấu hình MySQL | Không theo settings hiện tại | Có |
| `luu_tru/ban_sao_luu/before_0020_20260916_125505.sql` | SQL backup gốc | Không | Có |
| `docs/` | Tài liệu trình bày, kiểm kê và nghiệp vụ | Không | Có |
| `luu_tru/ban_sao_luu/backup_to_chuc_views_20260918_232833_clean/` | Backup source sạch tạo sau khi suite module mới pass, trước khi rút gọn monolith; chứa views.py nguyên bản để phục hồi | Không | Có, backup sạch duy nhất |
| `D:\NDT_MOTEL_ENV/` | Python và package local ngoài source | Có khi chạy local | Có cho phát triển |

Backup chứa bản sao các file source/config/template/static/model/docs/requirements và SQLite/SQL gốc; không có môi trường venv, cache hoặc artifact. Các file Python trong backup là bản phục hồi, không tham gia import hay discovery của website hiện tại.

## Kiểm tra và chính sách output

Chạy `D:\NDT_MOTEL_ENV\Scripts\python.exe -B manage.py test core --noinput -v 2`. Giữ ít nhất 257 test; không dùng `--keepdb` mặc định. Runner tự dọn media ngoài project và Django xóa database test sau chạy. Không tạo screenshot/log/HTML/JSON audit trong source. `manage.py test` tắt ghi bytecode. Không xóa migration, media hoặc dữ liệu runtime.
