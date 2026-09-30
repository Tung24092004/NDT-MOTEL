# Báo cáo UI Module 08 - Admin Dashboard

Ngày: 2026-09-27  
Trạng thái: **PASS**. Chỉ thực hiện Module 08; chưa bắt đầu Module 09.

## Phạm vi và backup

- Baseline đầu vào: full suite `310/310` PASS; live `86/10/6/3/0/20`; gallery `86/86`, mismatch `0`; artifact root `0`; source `__pycache__` `0`.
- Baseline live chỉ đọc trước sửa: phòng `86` (`trống 78 / đã đặt 3 / đang thuê 5 / bảo trì 0`), đặt phòng `10` (`chờ duyệt 1 / đã duyệt 9 / từ chối 0 / đã hủy 0`), hợp đồng `6` (`đang hiệu lực 5 / sắp hết hạn 0 / chờ hiệu lực 0 / đã hết hạn 0`), người thuê `20`.
- Backup trước sửa: `luu_tru/ban_sao_luu/before_module08_ui_20260927_142308` (16 file liên quan).
- Không sửa model, view, URL, quyền, query, endpoint, payload, CSRF, transaction hoặc quy tắc tính số liệu.

## Audit code đang chạy

### Route, quyền và vòng đời request

- Route thật: `/dashboard-admin/`, name `dashboard_admin`, tại `motel_management/urls.py:421-425`.
- View tại `core/views_quan_tri.py:204-364`: khách chưa đăng nhập về `dang_nhap`; tài khoản không phải Admin về `tai_khoan` (`204-216`). `la_admin` yêu cầu authenticated và `is_staff` hoặc `is_superuser` tại `core/dich_vu/phan_quyen.py:5-11`.
- Test quyền/navigation hiện có ở `core/tests/test_phan_quyen.py:656-720,778-798`; test UI tập trung mới ở `core/tests/test_giao_dien.py:498-565`.
- Giới hạn backend cần lưu ý: GET dashboard không thuần đọc. Trước khi thống kê, view tải mọi hợp đồng chưa hủy (`222-231`), gọi `cap_nhat_trang_thai_hop_dong` (`233-237`) rồi `cap_nhat_trang_thai_phong_theo_hop_dong` (`243-247`). Module UI giữ nguyên hành vi này; baseline live được đo trực tiếp bằng ORM, không gọi route dashboard.

### Nguồn từng chỉ số và bảng

| Nội dung | Context/query thật |
| --- | --- |
| Tổng phòng | `Phong.objects.count()` (`core/views_quan_tri.py:253`) |
| Phòng trống / đã đặt / đang thuê / bảo trì | `Phong.trang_thai = trong / da_dat / dang_thue / bao_tri` (`255-269`) |
| Người thuê | `NguoiThue.objects.count()` (`275`) |
| Tổng đặt phòng | `DatPhong.objects.count()` (`281`) |
| Đặt phòng chờ duyệt / đã duyệt / từ chối / đã hủy | `DatPhong.trang_thai = cho_duyet / da_duyet / tu_choi / da_huy` (`283-297`) |
| Tổng hợp đồng | `HopDong.objects.count()` (`303`) |
| Hợp đồng đang hiệu lực / sắp hết hạn / chờ hiệu lực / đã hết hạn | `HopDong.trang_thai = dang_hieu_luc / sap_het_han / cho_hieu_luc / da_het_han` (`305-319`) |
| 5 đặt phòng gần nhất | `select_related(nguoi_thue, phong, phong__co_so).order_by('-id')[:5]` (`325-333`) |

Tất cả số trong template tiếp tục lấy từ context `core/views_quan_tri.py:335-358`; không có số baseline/demo hardcode. Bảng dùng dữ liệu booking thật, tiền cọc thật, `get_trang_thai_display` và route detail thật. Các shortcut đều dùng URL name đang resolve: quản lý phòng, đặt phòng, hợp đồng, hóa đơn, người thuê, sửa chữa, thông báo và Smart Room (`templates/core/dashboard_admin.html:60-67`).

Audit template cũ phát hiện lỗi hiển thị thuộc dashboard: model lưu status chữ thường tại `core/models.py:739-744`, nhưng template backup so sánh `DA_DUYET/CHO_DUYET/TU_CHOI/DA_HUY` chữ hoa tại `.../before_module08_ui_20260927_142308/templates/core/dashboard_admin.html:1251-1257`. Template mới so sánh đúng giá trị model và hiển thị nhãn choices tại `templates/core/dashboard_admin.html:55`.

## UI migration và file

Dashboard được chuyển sang Foundation V1 với PageHeader, 4 KPI chính, phân bổ phòng, hàng đợi xử lý, chỉ số phụ, bảng booking gần nhất, empty state và shortcut có route thật. Giao diện sáng, teal chủ đạo, vàng chỉ dùng cho cảnh báo; responsive bằng CSS, không có JS dashboard và không thêm search/widget giả.

Đã sửa/thêm đúng 4 file:

- `templates/core/dashboard_admin.html`
- `static/css/admin_dashboard.css` (mới)
- `core/tests/test_giao_dien.py` (thêm 1 regression test, không tách nhỏ suite)
- `core/tests/visual_module08_dashboard_audit.py` (script QA explicit, không thuộc normal discovery)

`base.html` không thay đổi. Không sửa gallery hoặc module khác.

## Test và visual QA

- `manage.py check`: PASS, 0 issue.
- `makemigrations --check --dry-run`: PASS, `No changes detected`.
- Regression dashboard: PASS `1/1`; đối chiếu toàn bộ context với ORM sau GET, thứ tự 5 booking, nhãn trạng thái và route links.
- Full suite cuối: PASS `311/311`, 65.574 giây; DB `test_ndt_motel` đã hủy sau chạy.
- Visual QA có đăng nhập: PASS `1 màn dashboard x 4 viewport = 4 ca` tại `1440x900`, `1024x768`, `768x900`, `390x844`; ca bị chặn cuối cùng `0`.
- Mỗi ca: HTTP 200, overflow ngang cấp trang false, broken image 0, console/page error 0, đủ 5 dòng booking. 11 giá trị render được đối chiếu và khớp context/backend test thật (`6/3/1/1/1`, người thuê `2`, booking `5`, đã duyệt `2`, hợp đồng `1`, đang hiệu lực `1`); không dùng số demo để kết luận.
- Mọi `href` trong dashboard đều không rỗng và resolve được. Ảnh 1440 và 390 đã được kiểm tra trực tiếp; không thấy overlap, clipping ngoài vùng cuộn bảng hoặc nhãn sai.
- Playwright lần đầu trong sandbox bị `WinError 5` khi tạo subprocess; rerun ngoài sandbox PASS. Bằng chứng cuối: `luu_tru/kiem_thu/module_08/dashboard_qa/results.json` và 4 PNG (5 file).

## Xác nhận cuối và giới hạn

- Live data: `Phong/DatPhong/HopDong/LichSuThanhToan/ThanhToanCocDatPhong/NguoiThue = 86/10/6/3/0/20`.
- Gallery: `86/86`, mismatch `0`.
- Artifact root: `0`.
- Source `__pycache__` dưới `core`, `templates`, `static`, `motel_management`, `tools`: `0`.
- Dashboard vẫn là snapshot tổng số, chưa có phạm vi thời gian hoặc trend; không tự thêm query/widget ngoài backend hiện có.
- GET dashboard vẫn có side effect đồng bộ trạng thái hợp đồng/phòng như audit ở trên. Đây là giới hạn backend hiện hữu, không thay trong lượt UI.

**Kết luận: Module 08 PASS. Dừng trước Module 09.**
