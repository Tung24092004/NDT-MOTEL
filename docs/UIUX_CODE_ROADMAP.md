# UI/UX Code Roadmap - NDT MOTEL
Tài liệu này theo dõi các màn hình đang render thật và bằng chứng nghiệm thu theo từng chặng. Chặng 2C chỉ hoàn tất hai màn User `/hoa-don-cua-toi/` và `/hoa-don-cua-toi/<id>/`; không đánh dấu màn thanh toán hoặc màn Admin.
## Bảng route UI/UX
| Nhóm chức năng | Route | View | Template | CSS/JS | Hành động chính | Vấn đề bố cục/nút | Ưu tiên | Trạng thái |
|---|---|---|---|---|---|---|---|---|
| Public/Tìm phòng | `/` | `core.views_quan_tri.home` | `templates/core/home.html` | `static/css/style.css`, `static/js/ui-system.js` | Vào trang chủ, đi tới tìm phòng/đăng nhập | Cần kiểm sau vì dùng chung base lớn | Cao | Chưa làm |
| Public/Tìm phòng | `/phong/` | `core.views_phong.danh_sach_phong` | `templates/core/danh_sach_phong.html` | Foundation V1, `room_management.css` liên quan card phòng | Lọc, xem chi tiết, vào đặt phòng | Đã có foundation nhưng chưa audit lại toàn bộ trong chặng này | Cao | Chưa làm |
| Public/User/Admin - Chi tiết phòng | `/phong/<id>/` | `core.views_phong.chi_tiet_phong` | `templates/core/chi_tiet_phong.html` | `static/css/room_detail.css`, `static/js/room_detail.js`, Foundation V1 button/badge | Xem ảnh, thông số, giá, cơ sở; User/khách đặt phòng; Admin sửa phòng | Baseline cũ lãng phí chiều ngang, nội dung nhỏ/rời rạc, Admin thấy hành động đặt phòng không phù hợp | Cao | Đã làm Chặng 1 |
| User - Đặt phòng | `/phong/<id>/dat/` | `core.views_dat_phong.dat_phong` | `templates/core/tenant/booking/create.html` | `static/css/tenant/booking.css`, `static/js/tenant/booking.js` | Gửi yêu cầu đặt phòng, người đi cùng, đồng ý điều khoản | Template có nhiều dòng dồn, cần tách tiếp ở chặng sau | Cao | Chưa làm |
| User - Đặt phòng của tôi | `/dat-phong-cua-toi/` | `core.views_dat_phong.dat_phong_cua_toi` | `templates/core/tenant/booking/list.html` | `static/css/tenant/booking.css` | Xem/lọc danh sách đặt phòng | Đã audit list nhiều mục/rỗng, quyền khách/Admin, trạng thái cọc và CTA thanh toán/xem chi tiết | Cao | Đã làm Chặng 2A |
| User - Chi tiết đặt phòng | `/dat-phong-cua-toi/<id>/` | `core.views_dat_phong.chi_tiet_dat_phong_cua_toi` | `templates/core/tenant/booking/detail.html` | `static/css/tenant/booking.css` | Xem trạng thái, thanh toán cọc, hủy khi được phép | Đã tách bố cục, thêm timeline quy trình, kiểm nút thanh toán/hủy theo trạng thái thật | Cao | Đã làm Chặng 2A |
| User - Thanh toán cọc | `/dat-phong-cua-toi/<id>/thanh-toan-coc/` | `core.views_dat_phong.thanh_toan_coc_cua_toi` | `templates/core/tenant/booking/deposit_payment.html` | `static/css/tenant/booking.css` | Xem QR, báo đã chuyển khoản | Cần kiểm trạng thái/nút theo từng cọc | Cao | Chưa làm |
| Admin - Dashboard | `/dashboard-admin/` | `core.views_quan_tri.dashboard_admin` | `templates/core/dashboard_admin.html` | `static/css/admin_dashboard.css` | Xem tổng quan phòng, đặt phòng, hóa đơn, sửa chữa | Đã có module trước nhưng chưa thuộc chặng này | Cao | Chưa làm |
| Admin - Quản lý phòng | `/quan-ly-phong/`, `/quan-ly-phong/tao/`, `/quan-ly-phong/<id>/sua/` | `core.views_phong.quan_ly_phong`, `tao_phong`, `sua_phong` | `quan_ly_phong.html`, `tao_phong.html`, `sua_phong.html` | `static/css/room_management.css`, inline JS trong form | Thêm/sửa/xóa phòng, upload gallery | Đã audit đủ danh sách, tạo và sửa ở 4 viewport; không ghi nhận lỗi tự động hoặc lỗi nhìn thấy sau khi kiểm tra ảnh | Cao | Đã audit Foundation V2 Module 03 |
| Admin - Quản lý đặt phòng | `/quan-ly-dat-phong/`, `/quan-ly-dat-phong/<id>/` | `core.views_quan_tri_dat_phong.*` | `quan_ly_dat_phong.html`, `chi_tiet_dat_phong.html` | `static/css/admin_booking.css`, `static/js/admin_booking.js` | Đối soát cọc, xác nhận/từ chối yêu cầu | Cần kiểm rõ trạng thái và hành động chính | Cao | Chưa làm |
| Admin/User - Hợp đồng | `/quan-ly-hop-dong/`, `/hop-dong-cua-toi/` | `core.views_hop_dong.*` | `quan_ly_hop_dong.html`, `chi_tiet_hop_dong.html`, `hop_dong_cua_toi.html`, `chi_tiet_hop_dong_cua_toi.html` | `static/css/contract_management.css`, `static/js/contract_management.js` | Tạo/sửa/xử lý hợp đồng, gia hạn, xuất PDF | User list/detail đã audit Chặng 2B; Admin chưa thuộc phạm vi | Cao | Đã làm User Chặng 2B |
| User - Hóa đơn của tôi | `/hoa-don-cua-toi/`, `/hoa-don-cua-toi/<id>/` | `core.views_hoa_don.hoa_don_cua_toi`, `core.views_hoa_don.chi_tiet_hoa_don_cua_toi` | `templates/core/hoa_don_cua_toi.html`, `templates/core/chi_tiet_hoa_don_cua_toi.html` | `static/css/tenant/hoa_don_cua_toi.css`, `static/css/tenant/chi_tiet_hoa_don_cua_toi.css` | Xem kỳ thu, phí, tổng tiền, trạng thái; mở luồng thanh toán/VietQR khi được phép | Đã audit danh sách nhiều/rỗng, chi tiết chưa thanh toán/chờ xác nhận/đã thanh toán, CTA và quyền User; route thanh toán chỉ được kiểm liên kết/nghiệp vụ, không thuộc màn hoàn tất | Cao | Đã làm Chặng 2C |
| User/Admin - Ở ghép | `/phong/<id>/dang-ky-ghep/`, `/hop-dong/<id>/bat-tat-ghep/`, `/yeu-cau-ghep-cua-toi/`, `/quan-ly-yeu-cau-ghep/` | `core.views_o_ghep.*` | `dang_ky_ghep_phong.html`, `yeu_cau_ghep_cua_toi.html`, `chi_tiet_yeu_cau_ghep.html` | `static/css/community.css` | Đăng ký/duyệt/từ chối ở ghép | Nhiều template dồn một dòng, cần tách | Trung bình | Chưa làm |
| User - Sửa chữa của tôi | `/yeu-cau-sua-chua-cua-toi/`, `/yeu-cau-sua-chua-cua-toi/tao/`, `/yeu-cau-sua-chua-cua-toi/<id>/` | `core.views_sua_chua.yeu_cau_sua_chua_cua_toi`, `core.views_sua_chua.tao_yeu_cau_sua_chua`, `core.views_sua_chua.chi_tiet_yeu_cau_sua_chua_cua_toi` | `yeu_cau_sua_chua_cua_toi.html`, `tao_yeu_cau_sua_chua.html`, `chi_tiet_yeu_cau_sua_chua_cua_toi.html` | `static/css/repair.css`, `static/js/repair.js` | Tạo, xem danh sách, xem chi tiết yêu cầu sửa chữa của chính User | Đã chuyển danh sách sang card, form giữ dữ liệu khi lỗi, lỗi sát trường, chống gửi lặp; Admin sửa chữa không thuộc phạm vi chặng này | Trung bình | Đã làm User Chặng 2D |
| Admin - Sửa chữa | `/quan-ly-sua-chua/`, `/quan-ly-sua-chua/<id>/`, `/tao-sua-chua/` | `core.views_sua_chua.*` | `quan_ly_sua_chua.html`, `chi_tiet_sua_chua.html`, `tao_sua_chua.html` | `static/css/repair.css` | Tiếp nhận, tạo nội bộ, xử lý yêu cầu sửa chữa | Đã redesign theo Foundation V2; giữ nguyên nghiệp vụ, URL, POST, CSRF, quyền, validation và trạng thái | Trung bình | Đã làm Foundation V2 Module 02 |
| User/Admin - Thông báo | `/thong-bao-cua-toi/`, `/thong-bao-admin/`, `/quan-ly-thong-bao/` | `core.views_thong_bao.*` | `thong_bao_cua_toi.html`, `thong_bao_admin.html`, `quan_ly_thong_bao.html` | `static/css/notification.css` | Xem/đọc/tạo/xử lý thông báo | Có nhiều dòng HTML dồn một dòng | Trung bình | Chưa làm |
| Admin/User - Face ID/Smart Room | `/smart-room/`, `/smart-room/face-profile/`, `/tai-khoan/nhan-dien-su-dung-phong/` | `core.views_smart_room.*` | `smart_room_dashboard.html`, `quan_ly_face_profile.html`, `chi_tiet_face_profile.html`, `face_id_unavailable.html` | `static/css/smart_room.css`, tenant CSS Face ID | Quản lý nhận diện, quyền ra vào, lịch sử | Module lớn, nhiều view, cần chặng riêng | Cao | Chưa làm |
Các trang trên dùng component chung của Foundation V1 qua `templates/core/base.html`, `templates/core/foundation/page_header.html`, `templates/core/foundation/empty_state.html`, `static/css/foundation/*.css`, `ndt-button`, `ndt-badge`, `ndt-surface`, `ndt-table`, `ndt-filter-bar`. Riêng workflow tenant booking dùng `templates/core/tenant/booking/base.html` và component con trong `templates/core/tenant/booking/components/`.
## Backlog dễ đọc mã
| File | Ví dụ xác minh | Vấn đề | Đề xuất |
|---|---|---|---|
| `templates/core/base.html` | Nhiều flyout/nav nằm một dòng quanh các block account/support/smart | File base quá lớn, khó dò menu theo vai trò | Tách flyout/header/sidebar thành partial sau khi có chặng riêng |
| `templates/core/tenant/booking/list.html` | Dòng option/filter và footer record dài > 400 ký tự | HTML dồn một dòng, khó review điều kiện trạng thái | Tách từng record/filter thành block nhiều dòng hoặc component |
| `templates/core/tenant/booking/detail.html` | Các section trạng thái/phòng/cọc dài > 700 ký tự | Logic hiển thị nghiệp vụ trộn nhiều trong template | Tách partial status/payment/cancel |
| `templates/core/tenant/booking/deposit_payment.html` | QR/bank panel/report form dài > 900 ký tự | Khó kiểm nút theo trạng thái thanh toán | Tách panel QR, panel ngân hàng, form báo chuyển khoản |
| `templates/core/tenant/booking/create.html` | Các bước form và companion formset có dòng dài | Logic form nhiều bước trộn trong template | Tách thêm partial cho step, giữ JS hiện có |
| `templates/core/tao_phong.html`, `templates/core/sua_phong.html` | Form field và JS preview ảnh có dòng dài | Form quản lý phòng khó bảo trì | Tách JS preview ảnh ra file tĩnh chung ở chặng quản lý phòng |
| `static/css/room_management.css` | Một số media query dài > 2500 ký tự | CSS minified thủ công một phần, khó sửa mobile | Format lại theo block, không đổi selector |
| `static/css/admin_dashboard.css`, `admin_booking.css`, `contract_management.css` | Nhiều rule dài > 180 ký tự | Khó đọc khi bảo vệ UI | Format dần theo module khi chạm tới |
| `core/views_phong.py` | File chứa list/detail/create/edit/delete phòng | Một file nhiều chức năng, nhưng nghiệp vụ liên quan chặt | Chỉ tách helper/form nếu module quản lý phòng tiếp tục lớn |
| `core/views_smart_room.py` | Nhiều view FaceProfile/quyền/lịch sử trong một file | File rất lớn, khó tìm workflow Face ID | Tách theo nhóm FaceProfile, quyền ra vào, lịch sử ở chặng Smart Room |
| `core/views_dat_phong.py` | Điều kiện đặt phòng, tạo booking, cọc, QR trong cùng file | Logic nghiệp vụ và render còn gần nhau | Đưa tạo QR/kiểm điều kiện sang service khi làm chặng booking |
## Tìm code để vấn đáp
| Chủ đề | Vị trí xác minh được | Ghi chú |
|---|---|---|
| Tổng số phòng/dashboard | `core.views_quan_tri.dashboard_admin`, template `templates/core/dashboard_admin.html` | Dashboard admin lấy số liệu live từ các model, không dùng mock |
| Danh sách/chi tiết phòng | `core.views_phong.danh_sach_phong`, `core.views_phong.chi_tiet_phong`, `core.dich_vu.gallery_phong.chuan_bi_gallery_hien_thi` | Gallery hiển thị từ ảnh riêng hoặc thư mục `media/phong_mau` |
| Sinh mã thanh toán/đặt phòng | `core/booking_identifiers.py`, `core/dich_vu/tien_coc.py`, `motel_management/cau_hinh_dat_phong.py` | Dùng cho mã yêu cầu và nội dung thanh toán cọc |
| Lưu/xác nhận thanh toán cọc | `core.views_dat_phong.thanh_toan_coc_cua_toi`, `core.views_quan_tri_dat_phong.tu_choi_thanh_toan_coc`, `xac_nhan_dat_phong_va_tao_hop_dong` | Luồng xác nhận nằm phía Admin booking |
| Đặt phòng | `core.views_dat_phong.dat_phong`, `core.dich_vu.dat_phong.create_booking`, `templates/core/tenant/booking/create.html` | User gửi yêu cầu, backend chặn Admin và phòng không hợp lệ |
| Hợp đồng | `core.views_hop_dong.hop_dong_cua_toi`, `core.views_hop_dong.chi_tiet_hop_dong_cua_toi`, `core.views_gia_han.gui_yeu_cau_gia_han`, `core.views_gia_han.huy_yeu_cau_gia_han`, `core.views_hop_dong.xuat_hop_dong_pdf`, templates `templates/core/hop_dong_cua_toi.html`, `templates/core/chi_tiet_hop_dong_cua_toi.html`, CSS `static/css/contract_management.css`, JS `static/js/contract_management.js` | Chặng 2B xác minh User list/detail, gia hạn chỉ POST khi đủ điều kiện, hủy yêu cầu chờ duyệt, PDF chỉ hợp đồng của chính người thuê hoặc Admin |
| Hóa đơn User | `core.views_hoa_don.hoa_don_cua_toi`, `core.views_hoa_don.chi_tiet_hoa_don_cua_toi`, `core.views_thanh_toan.thanh_toan_hoa_don_cua_toi`, model `core.models.HoaDon`, templates `templates/core/hoa_don_cua_toi.html`, `templates/core/chi_tiet_hoa_don_cua_toi.html`, CSS `static/css/tenant/hoa_don_cua_toi.css`, `static/css/tenant/chi_tiet_hoa_don_cua_toi.css` | User chỉ xem hóa đơn của chính mình; `chua_thanh_toan`/`qua_han` mới mở thanh toán; báo chuyển khoản chỉ sang `cho_xac_nhan`, Admin xác nhận mới sang `da_thanh_toan` |
| Thông báo | `core.views_thong_bao`, `core.dich_vu.thong_bao_dat_phong`, `core.dich_vu.thong_bao_quan_tri` | Có thông báo User và Admin |
| Face ID | `core.views_smart_room`, model `core.models.FaceProfile`, templates `quan_ly_face_profile.html`, `chi_tiet_face_profile.html`, `chi_tiet_face_profile.html` | Quản lý hồ sơ nhận diện, quyền ra vào và lịch sử |
## Bằng chứng Chặng 1
| Loại bằng chứng | Vị trí |
|---|---|
| Baseline trước sửa | `luu_tru/kiem_thu/uiux_stage_01_room_detail/before/room_detail_tenant_1440.png`, `room_detail_tenant_768.png`, `room_detail_tenant_390.png`, `results.json` |
| Ảnh sau sửa | Đã ghi tại `luu_tru/kiem_thu/uiux_stage_01_room_detail/after/room_detail_tenant_1440.png`, `room_detail_tenant_768.png`, `room_detail_tenant_390.png`, `results.json` |
| Trang được đánh dấu hoàn tất | Chỉ `/phong/<id>/` |
## Bằng chứng Chặng 2A
| Loại bằng chứng | Vị trí |
|---|---|
| Baseline trước sửa | `luu_tru/kiem_thu/uiux_stage_02a_booking/current/booking_list_many_1440.png`, `booking_list_many_1024.png`, `booking_list_many_768.png`, `booking_list_many_390.png`, `booking_list_empty_*.png`, `booking_detail_unpaid_*.png`, `booking_detail_pending_*.png`, `results.json` |
| Ảnh sau vòng nghiệm thu | `luu_tru/kiem_thu/uiux_stage_02a_booking/after_review_02/booking_list_many_1440.png`, `booking_list_many_1024.png`, `booking_list_many_768.png`, `booking_list_many_390.png`, `booking_detail_pending_1440.png`, `booking_detail_pending_1024.png`, `booking_detail_pending_768.png`, `booking_detail_pending_390.png`, `booking_detail_unpaid_1440.png`, `booking_detail_unpaid_390.png`, `results.json` |
| Trang được đánh dấu hoàn tất | Chỉ `/dat-phong-cua-toi/` và `/dat-phong-cua-toi/<id>/` |
## Bằng chứng Chặng 2B
| Loại bằng chứng | Vị trí |
|---|---|
| Baseline trước sửa | `luu_tru/kiem_thu/uiux_stage_02b_contract/before/contract_list_many_1440.png`, `contract_list_many_1024.png`, `contract_list_many_768.png`, `contract_list_many_390.png`, `contract_list_empty_*.png`, `contract_detail_active_*.png`, `contract_detail_renewable_*.png`, `contract_detail_pending_*.png`, `contract_detail_expired_*.png`, `results.json` |
| Ảnh sau sửa | `luu_tru/kiem_thu/uiux_stage_02b_contract/after/contract_list_many_1440.png`, `contract_list_many_1024.png`, `contract_list_many_768.png`, `contract_list_many_390.png`, `contract_list_empty_*.png`, `contract_detail_active_*.png`, `contract_detail_renewable_*.png`, `contract_detail_pending_*.png`, `contract_detail_expired_*.png`, `results.json` |
| Trang được đánh dấu hoàn tất | Chỉ `/hop-dong-cua-toi/` và `/hop-dong-cua-toi/<id>/` |
## Bằng chứng Chặng 2C
| Loại bằng chứng | Vị trí |
|---|---|
| Baseline trước sửa | `luu_tru/kiem_thu/uiux_stage_02c_invoice/before/invoice_list_many_*.png`, `invoice_list_empty_*.png`, `invoice_detail_unpaid_*.png`, `invoice_detail_pending_*.png`, `invoice_detail_paid_*.png`, `results.json` |
| Ảnh sau sửa | `luu_tru/kiem_thu/uiux_stage_02c_invoice/after/invoice_list_many_*.png`, `invoice_list_empty_*.png`, `invoice_detail_unpaid_*.png`, `invoice_detail_pending_*.png`, `invoice_detail_paid_*.png`, `results.json` |
| Trang được đánh dấu hoàn tất | Chỉ `/hoa-don-cua-toi/` và `/hoa-don-cua-toi/<id>/` |
## Bằng chứng Chặng 2D
| Loại bằng chứng | Vị trí |
|---|---|
| Route đã xử lý | Chỉ User: `/yeu-cau-sua-chua-cua-toi/`, `/yeu-cau-sua-chua-cua-toi/tao/`, `/yeu-cau-sua-chua-cua-toi/<id>/` |
| View/template/CSS/JS | `core/views_sua_chua.py`; `templates/core/yeu_cau_sua_chua_cua_toi.html`; `templates/core/tao_yeu_cau_sua_chua.html`; `templates/core/chi_tiet_yeu_cau_sua_chua_cua_toi.html`; `static/css/repair.css`; `static/js/repair.js` |
| Baseline trước sửa | `luu_tru/kiem_thu/uiux_stage_02d_repair/before/repair_list_many_*.png`, `repair_list_empty_*.png`, `repair_create_*.png`, `repair_detail_*.png`, `results.json` |
| Ảnh sau sửa | `luu_tru/kiem_thu/uiux_stage_02d_repair/after/repair_list_many_1440.png`, `repair_list_many_390.png`, `repair_create_1440.png`, `repair_create_390.png`, `repair_list_empty_390.png`, `repair_detail_processing_390.png`, `results.json` |
| Visual audit 4 viewport | `1440x900`, `1024x768`, `768x900`, `390x844`; 40 case PASS; status 200; không overflow; 0 broken image; không console/page error; focus-visible đạt; guest redirect `/dang-nhap/`; admin redirect `/quan-ly-sua-chua/` |
| Test đã chạy | `manage.py check`; `makemigrations --check --dry-run`; `TenantUITests.test_repair_roommate_and_payment_pages_render`; `Phase8B5TenantUIRegressionTests.test_other_tenant_cannot_view_private_repair_or_notification`; `TenantUITests.test_account_and_core_service_pages_render_shared_shell`; `RoleAccessMatrixTests.test_idor_matrix_is_symmetric_and_preserves_all_business_data`; `RoleAccessMatrixTests.test_owner_can_open_private_pages_and_pdf`; `RoleAccessMatrixTests.test_other_user_list_contexts_do_not_contain_foreign_data`; `RoleAccessMatrixTests.test_admin_cannot_use_tenant_only_business_routes_even_with_tenant_profile` |
| Test contract cũ cần backlog | `Phase8B5TenantUIRegressionTests.test_room_detail_and_booking_form_contract_render_for_tenant` vẫn fail đúng 3 assertion thiếu `name="ho_ten"`, `name="so_dien_thoai"`, `name="cccd"` ở `core/tests/test_giao_dien.py:209`; đây là contract cũ của form đặt phòng, không phải regression Chặng 2D. Nghiệp vụ hiện tại lấy identity từ hồ sơ User, không lấy từ POST; không thêm input giả/hidden để làm xanh test. |
| Trang được đánh dấu hoàn tất | Chỉ User sửa chữa: list/create/detail. Không ghi toàn bộ UI User/Admin hoàn tất. |
## Foundation V2 - Khảo sát và nguyên tắc triển khai
Foundation V2 được triển khai theo từng module, không thay đồng loạt giao diện đang chạy. Mỗi module chỉ được đánh dấu hoàn tất sau khi có ảnh BEFORE/AFTER ở `1440x900`, `1024x768`, `768x900`, `390x844`, đã mở ảnh kiểm tra bằng mắt và đã kiểm tra quyền, trạng thái, empty state, overflow, lỗi trình duyệt, ảnh hỏng và focus-visible.
| Nhóm | URL | View | Template | CSS/JS | User/Admin | Tình trạng hiện tại |
|---|---|---|---|---|---|---|
| Khám phá phòng | `/`, `/phong/`, `/phong/<id>/` | `views_quan_tri.home`, `views_phong.*` | `home.html`, `danh_sach_phong.html`, `chi_tiet_phong.html` | `style.css`, `room_detail.css`, `room_detail.js` | Public/User/Admin | Chi tiết phòng đã qua Chặng 1; home và danh sách chưa audit V2 |
| Đặt phòng User | `/phong/<id>/dat/`, `/dat-phong-cua-toi/`, `/dat-phong-cua-toi/<id>/`, route thanh toán cọc | `views_dat_phong.*` | `tenant/booking/*` | `tenant/booking.css`, `tenant/booking.js` | User | List/detail đã qua Chặng 2A; create và thanh toán cọc chưa audit V2 |
| Đặt phòng Admin | `/quan-ly-dat-phong/`, `/quan-ly-dat-phong/<id>/` và ba route POST xử lý | `views_quan_tri_dat_phong.*` | `quan_ly_dat_phong.html`, `chi_tiet_dat_phong.html` | `admin_booking.css`, `admin_booking.js`, Foundation | Admin | Ưu tiên đầu tiên của V2: bảng bị cắt ở màn hẹp, hành động xử lý nằm quá thấp |
| Phòng/cơ sở Admin | `/quan-ly-phong/*`, `/quan-ly-co-so/*` | `views_phong.*`, `views_quan_tri.*` | `quan_ly_phong.html`, form phòng, template cơ sở | `room_management.css`, JS form hiện hữu | Admin | Admin phòng đã có 12/12 case tự động PASS ở 4 viewport và đã kiểm tra ảnh thực tế; phần cơ sở riêng chưa mở rộng trong module này |
| Hợp đồng | `/hop-dong-cua-toi/*`, `/quan-ly-hop-dong/*` | `views_hop_dong.*`, `views_gia_han.*` | template hợp đồng User/Admin | `contract_management.css/js` | User/Admin | User đã qua Chặng 2B; Admin chưa audit V2 |
| Hóa đơn/thanh toán | `/hoa-don-cua-toi/*`, `/quan-ly-hoa-don/*` | `views_hoa_don.*`, `views_thanh_toan.*` | template hóa đơn User/Admin | CSS hóa đơn tenant/admin | User/Admin | User list/detail đã qua Chặng 2C; thanh toán và Admin chưa audit V2 |
| Sửa chữa | `/yeu-cau-sua-chua-cua-toi/*`, `/quan-ly-sua-chua/*`, `/tao-sua-chua/` | `views_sua_chua.*` | template sửa chữa User/Admin | `repair.css`, `repair.js` | User/Admin | User đã qua Chặng 2D; Admin đã hoàn tất Foundation V2 Module 02 |
| Ở ghép/người ở cùng | route `dang-ky-ghep`, `yeu-cau-ghep-cua-toi`, `quan-ly-yeu-cau-ghep`, `quan-ly-nguoi-o-cung` | `views_o_ghep.*`, `views_quan_tri.*` | template ở ghép/người ở cùng | `community.css` | User/Admin | Trạng thái và form xử lý còn dàn đều; chưa audit V2 |
| Thông báo | `/thong-bao-cua-toi/`, `/thong-bao-admin/`, `/quan-ly-thong-bao/*` | `views_thong_bao.*` | template thông báo User/Admin | `notification.css` | User/Admin | Bộ lọc và thống kê chiếm nhiều chiều cao trên mobile; chưa audit V2 |
| Smart Room/Face ID | `/smart-room/*`, `/tai-khoan/nhan-dien-su-dung-phong/` | `views_smart_room.*` | dashboard, Face profile, quyền và lịch sử ra vào | `smart_room.css`, CSS/JS Face ID | User/Admin | Module lớn, nhiều màn và trạng thái; cần một chặng riêng sau khi V2 được kiểm chứng |
| Tài khoản/xác thực | `/tai-khoan/`, cập nhật hồ sơ, đổi mật khẩu, đăng nhập/đăng ký | `views_dang_nhap.*`, `views_quan_tri.*` | template tài khoản/xác thực | `account.css`, CSS auth dùng chung | User/Admin | Đã có audit cũ; chưa đối chiếu đầy đủ theo V2 |
| Dashboard/nhật ký/chính sách | `/dashboard-admin/`, route nhật ký, route chính sách hỗ trợ | `views_quan_tri.*`, `views_nhat_ky.*` | dashboard, nhật ký, chính sách | CSS module tương ứng | User/Admin | Nhiều vùng số liệu và bảng; chưa audit V2 |
### Cấu trúc và thứ bậc V2
1. Trang đi theo thứ tự breadcrumb, tiêu đề và mô tả, hành động chính, vùng tóm tắt quan trọng, nội dung chính, bước tiếp theo.
2. Tiêu đề, số liệu và trạng thái có cấp độ rõ; label đứng cạnh ngữ cảnh; nội dung phụ nhẹ hơn; lỗi và cảnh báo có tương phản và biểu đạt bằng cả màu lẫn chữ.
3. Nút chính có màu nổi bật; nút phụ có border; nút nguy hiểm dùng màu cảnh báo. Icon-only phải có nền, border, tooltip và `aria-label`. Mọi nút có hover, focus-visible, disabled và loading.
4. Trạng thái dùng badge/pill có text rõ, không truyền nghĩa chỉ bằng màu.
5. Mọi ngày giờ nghiệp vụ có nhãn cụ thể như “Ngày gửi”, “Cập nhật lúc”, “Hạn thanh toán”, “Thời gian xử lý”.
6. Desktop tận dụng chiều ngang; tablet đổi grid theo nội dung; mobile một cột. Bảng nhiều cột phải chuyển thành list/card nếu người dùng cần đọc và thao tác, không ép cuộn ngang.
7. Card chỉ nhóm một đối tượng, một quyết định hoặc một cụm thông tin có quan hệ; section và khoảng trắng không mặc định biến thành card.
### Module thí điểm V2
Chọn **Admin - Quản lý đặt phòng** làm module đầu tiên. Ảnh baseline cho thấy bảng 8 cột mất trạng thái và thao tác tại `1024`, `768` và `390`; trang chi tiết đặt toàn bộ quyết định sau hồ sơ dài, đặc biệt bất lợi trên mobile. Module này kiểm chứng được page header, summary, status, ngày giờ, responsive list và action hierarchy mà không cần thay đổi URL, field POST, CSRF, quyền, validation hay trạng thái nghiệp vụ. Phạm vi chỉ gồm hai màn GET và giao diện của ba form POST hiện hữu; không mở rộng sang module thứ hai.
## Bằng chứng Foundation V2 - Module 02 Admin sửa chữa
| Loại bằng chứng | Kết quả |
|---|---|
| Phạm vi | Chỉ Admin sửa chữa: danh sách, trạng thái rỗng/bộ lọc, tạo mới, chi tiết nhiều trạng thái và form cập nhật gắn với chi tiết |
| Route / view | `/quan-ly-sua-chua/`, `/quan-ly-sua-chua/<id>/`, `/tao-sua-chua/`; giữ nguyên view, URL, quyền, validation, trạng thái và POST contract |
| Template / CSS / JS | `templates/core/quan_ly_sua_chua.html`; `templates/core/chi_tiet_sua_chua.html`; `templates/core/tao_sua_chua.html`; `static/css/repair.css`; không sửa User sửa chữa |
| BEFORE | `luu_tru/kiem_thu/foundation_v2_admin_repair/before/` với list nhiều yêu cầu, empty state, create và detail nhiều trạng thái ở đủ `1440x900`, `1024x768`, `768x900`, `390x844` |
| Lỗi nhìn thấy ở BEFORE | Bảng ngang nhiều cột làm nội dung trạng thái, chi phí và thao tác bị khuất trên mobile; tiêu đề/ngày/nút bị bẻ chữ; trạng thái chưa là trung tâm; action detail nằm thấp; form chưa thể hiện lỗi sát field |
| Foundation V2 đã áp dụng | Danh sách chuyển sang task cards responsive; status, phòng, vấn đề, mức độ, ngày giờ và bước tiếp theo được ưu tiên; action chính đặt gần vùng status; detail có hierarchy rõ; form tạo/cập nhật có label, lỗi và vùng hành động phân cấp; mobile không cần cuộn ngang |
| AFTER | `luu_tru/kiem_thu/foundation_v2_admin_repair/after/` với list nhiều/rỗng, create và detail các trạng thái `Mới`, `Đang xử lý`, `Chờ thay thế`, `Hoàn thành`, `Từ chối` ở đủ bốn viewport |
| Visual audit | Harness `core.tests.visual_foundation_v2_admin_repair` PASS; status 200; không overflow; không ảnh hỏng; không console/page error; guest, User thường, staff Admin và superuser không is_staff được kiểm tra đúng contract |
| Kiểm tra code | `manage.py check` PASS; `makemigrations --check --dry-run` PASS |
| Test liên quan | 6/6 test Admin/User/quyền sửa chữa PASS |
| Lỗi test ngoài phạm vi | Bộ test rộng 53 test có 50 PASS và 3 FAIL tại contract cũ của form đặt phòng User (`ho_ten`, `so_dien_thoai`, `cccd`); không sửa trong Module 02 vì không thuộc Admin sửa chữa |
| Trạng thái hoàn tất | Hoàn tất Foundation V2 Module 02 Admin sửa chữa; không đánh dấu toàn bộ Foundation V2 hoàn tất |
| Module tiếp theo | Chỉ chuyển sang module khác sau khi người dùng xác nhận; không mở rộng trong Module 02 |
## Bằng chứng Foundation V2 - Module 01 Admin đặt phòng
| Loại bằng chứng | Kết quả |
|---|---|
| Phạm vi | Chỉ `/quan-ly-dat-phong/`, `/quan-ly-dat-phong/<id>/` và phần hiển thị của các action POST đã tồn tại |
| Route / view | `motel_management/urls.py`; `core.views_quan_tri_dat_phong.quan_ly_dat_phong`; `core.views_quan_tri_dat_phong.chi_tiet_dat_phong`; ba view POST xác nhận cọc, từ chối cọc và từ chối booking; workflow cũ `xu_ly_dat_phong` vẫn giữ nguyên |
| Template / CSS / JS | `templates/core/quan_ly_dat_phong.html`; `templates/core/chi_tiet_dat_phong.html`; `static/css/foundation/v2.css`; `static/css/admin_booking.css`; `static/js/admin_booking.js` |
| BEFORE | `luu_tru/kiem_thu/foundation_v2_admin_booking/before/booking_list_*.png`; `booking_detail_pending_*.png` tại đủ `1440x900`, `1024x768`, `768x900`, `390x844` |
| Lỗi nhìn thấy ở BEFORE | Bảng 8 cột bị cắt tại 1024/768/390 nên trạng thái và thao tác biến mất; nhãn ngày không nhất quán; trang chi tiết dài và hành động quyết định nằm dưới toàn bộ hồ sơ; ba action cùng độ nặng thị giác |
| Foundation V2 đã áp dụng | Header rõ cấp độ; summary số liệu; list công việc thay bảng ngang; badge có text; mọi ngày giờ có nhãn; “Bước tiếp theo” và CTA chính nổi bật; action panel chuyển lên đầu; thao tác từ chối nằm trong vùng mở có label sát field; tablet/mobile đổi grid theo chiều rộng thực |
| AFTER chính | `luu_tru/kiem_thu/foundation_v2_admin_booking/after/booking_list_1440.png`, `booking_list_1024.png`, `booking_list_768.png`, `booking_list_390.png`; `booking_detail_pending_1440.png`, `booking_detail_pending_1024.png`, `booking_detail_pending_768.png`, `booking_detail_pending_390.png` |
| Trạng thái bổ sung | `after/booking_detail_waiting_390.png`; `after/booking_list_empty_390.png` |
| Visual audit | 10/10 case PASS trong `after/results.json`: HTTP 200, không overflow, 0 broken image, không console/page error, control đều có label, focus-visible đạt. Guest chuyển tới đăng nhập; User thường chuyển về tài khoản; Admin xem được hai màn |
| Kiểm tra code | `manage.py check` PASS; `makemigrations --check --dry-run` PASS; `AdminBookingPaymentUITests` 6/6 PASS; visual test PASS |
| Lỗi test ngoài phạm vi | Lần chạy rộng 29 test có 27 PASS và 2 ERROR cùng nguyên nhân tại route Admin sửa chữa: `core/views_sua_chua.py:580` tham chiếu `repair_errors` chưa được định nghĩa. Không sửa ở chặng này vì thuộc module tiếp theo |
| Trạng thái hoàn tất | Chỉ module Admin đặt phòng list/detail. Không đánh dấu toàn bộ Foundation V2 hoặc UI User/Admin hoàn tất |
| Module tiếp theo đề xuất | Chưa chốt trong tài liệu này; chỉ bắt đầu module tiếp theo sau khi kiểm tra phạm vi, contract và lập baseline riêng |
## Bằng chứng Foundation V2 - Module 03 Admin quản lý phòng
| Loại bằng chứng | Kết quả |
|---|---|
| Phạm vi | Chỉ danh sách phòng, tạo phòng và sửa phòng của Admin; không mở rộng sang User/public phòng hoặc quản lý cơ sở riêng |
| Route / view | `/quan-ly-phong/`, `/quan-ly-phong/tao/`, `/quan-ly-phong/<id>/sua/`; giữ nguyên URL, quyền, validation, field POST, CSRF và nghiệp vụ |
| Visual audit | 12/12 case Admin PASS: danh sách 4 viewport, tạo phòng 4 viewport, sửa phòng 4 viewport |
| Viewport | `1440x900`, `1024x768`, `768x900`, `390x844` |
| Kiểm tra tự động | HTTP 200; không overflow; 0 ảnh hỏng; không lỗi trình duyệt; không thiếu label/action; không bad href; không raw enum; không mojibake; focus-visible PASS |
| Ảnh bằng chứng | `luu_tru/kiem_thu/module_11/visual_qa/m01_admin_room_list_*.png`; `m01_admin_room_create_*.png`; `m01_admin_room_edit_*.png`; kết quả tại `luu_tru/kiem_thu/module_11/visual_qa/results.json` |
| Trạng thái | Đã audit Foundation V2 Module 03; không redesign lại phần đã có bằng chứng PASS |
| Lưu ý phạm vi | Quản lý cơ sở riêng và các thay đổi giao diện mới chỉ được mở khi có contract và baseline riêng |