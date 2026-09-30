# UI Module 04 - Contract Management

Date: 2026-09-27

## Scope

Chỉ thực hiện Module 04 - Contract Management. Không triển khai Module 05. Không đổi endpoint, POST payload, CSRF, phân quyền, transaction hoặc workflow.

Checkpoint tên chính xác `NDT MOTEL – UI/UX MIGRATION CHECKPOINT` không có trong cây dự án khi tìm bằng `rg --files` và `rg`. Nguồn nền đã đọc và bám theo:

- `docs/UI_FOUNDATION_V1_REPORT_20260927.md`
- `docs/UI_MODULE_03_ADMIN_BOOKING_PAYMENT_REPORT_20260927.md`
- Các báo cáo Module 01/02 hiện có trong `docs/`

## Backup

- Source backup: `luu_tru/ban_sao_luu/backup_before_contract_management_ui_20260927_020000/`
- DB file backup: `luu_tru/ban_sao_luu/backup_before_contract_management_ui_20260927_020000.sqlite3`

Lưu ý: live app cấu hình MySQL `ndt_motel` trong `motel_management/settings.py:104`; file SQLite trong repo chỉ có bảng auth/Django cơ bản. Baseline live được đo bằng ORM sau khi cài dependencies.

## Contract Flow Audit

Routes đang dùng:

- Tenant list/detail/gia hạn/PDF: `motel_management/urls.py:336`, `motel_management/urls.py:342`, `motel_management/urls.py:352`, `motel_management/urls.py:368`.
- Atomic deposit confirmation tạo hợp đồng: `motel_management/urls.py:518`.
- Manual contract form còn tồn tại: `motel_management/urls.py:542`.
- Admin list/detail/edit/action/gia hạn: `motel_management/urls.py:552`, `motel_management/urls.py:558`, `motel_management/urls.py:564`, `motel_management/urls.py:570`, `motel_management/urls.py:577`.

Models/trạng thái/chống trùng:

- `DatPhong.ma_yeu_cau` unique: `core/models.py:724`.
- `ThanhToanCocDatPhong` có trạng thái cọc và mã tham chiếu/nội dung chuyển khoản unique: `core/models.py:1028`, `core/models.py:1030`, `core/models.py:1034`, `core/models.py:1035`.
- `HopDong.TRANG_THAI`: `core/models.py:1086`.
- `HopDong.dat_phong` là `OneToOneField`, chống tạo trùng theo booking: `core/models.py:1094`.
- `HopDong.so_hop_dong` unique: `core/models.py:1100`, `core/models.py:1102`.
- Gia hạn dùng `YeuCauGiaHanHopDong`: `core/models.py:1403`.

Cọc tạo hợp đồng trong transaction:

- Service authoritative là `confirm_deposit_and_create_contract()`: `core/dich_vu/hop_dong.py:106`, `core/dich_vu/hop_dong.py:107`.
- Lock booking bằng `select_for_update`: `core/dich_vu/hop_dong.py:110`.
- Chặn idempotent nếu booking đã có hợp đồng: `core/dich_vu/hop_dong.py:114`.
- Validate booking/snapshot/terms/capacity: `core/dich_vu/hop_dong.py:57`, `core/dich_vu/hop_dong.py:118`.
- Lock phòng và chặn hợp đồng trùng thời gian: `core/dich_vu/hop_dong.py:89`, `core/dich_vu/hop_dong.py:90`, `core/dich_vu/hop_dong.py:94`.
- Lock giao dịch cọc và chỉ nhận `cho_xac_nhan`: `core/dich_vu/hop_dong.py:74`, `core/dich_vu/hop_dong.py:76`, `core/dich_vu/hop_dong.py:82`.
- Khi xác nhận: cọc -> `da_xac_nhan`, booking -> `da_duyet`, tạo `HopDong`: `core/dich_vu/hop_dong.py:124`, `core/dich_vu/hop_dong.py:129`, `core/dich_vu/hop_dong.py:133`.
- Ghi lịch sử và thông báo: `core/dich_vu/hop_dong.py:155`, `core/dich_vu/hop_dong.py:183`.

Manual route còn thật:

- `tao_hop_dong()` vẫn render `core/tao_hop_dong.html` và tạo hợp đồng cho booking `da_duyet` chưa có hợp đồng: `core/views_hop_dong.py:605`, `core/views_hop_dong.py:698`, `core/views_hop_dong.py:901`.
- View kiểm tra booking đã có hợp đồng trước khi render/tạo: `core/views_hop_dong.py:629`, `core/views_hop_dong.py:825`.

Admin actions:

- List admin cập nhật trạng thái và render `core/quan_ly_hop_dong.html`: `core/views_hop_dong.py:324`, `core/views_hop_dong.py:357`, `core/views_hop_dong.py:523`.
- Detail admin render `core/chi_tiet_hop_dong.html`: `core/views_hop_dong.py:530`, `core/views_hop_dong.py:592`.
- Edit admin render `core/sua_hop_dong.html` và không sửa ngày/trạng thái: `core/views_hop_dong.py:1018`, `core/views_hop_dong.py:1076`, `core/views_hop_dong.py:1378`.
- Action kích hoạt/hủy dùng transaction và lock phòng/hợp đồng: `core/views_hop_dong.py:1460`, `core/views_hop_dong.py:1487`, `core/views_hop_dong.py:1512`, `core/views_hop_dong.py:1681`.

Tenant xem hợp đồng:

- List tenant lấy hợp đồng theo `dat_phong__nguoi_thue`: `core/views_hop_dong.py:1921`, `core/views_hop_dong.py:1961`, render tại `core/views_hop_dong.py:2012`.
- Detail tenant filter đúng người thuê: `core/views_hop_dong.py:2031`, `core/views_hop_dong.py:2051`, render tại `core/views_hop_dong.py:2113`.

PDF:

- PDF không dùng `hop_dong_pdf.html`; view sinh bằng ReportLab: `core/views_hop_dong.py:19`, `core/views_hop_dong.py:2121`, `core/views_hop_dong.py:2224`.
- `Content-Disposition` được set khi export: `core/views_hop_dong.py:2182`.
- Lịch sử xuất PDF ghi ở cuối flow: `core/views_hop_dong.py:3072`.

Kết luận audit: implementation hiện tại là chuẩn. Không đổi business logic để khớp tài liệu cũ.

## Files Modified

- `templates/core/quan_ly_hop_dong.html`
- `templates/core/chi_tiet_hop_dong.html`
- `templates/core/tao_hop_dong.html`
- `templates/core/sua_hop_dong.html`
- `templates/core/hop_dong_cua_toi.html`
- `templates/core/chi_tiet_hop_dong_cua_toi.html`
- `templates/core/partials/contract_status_badge.html`
- `static/css/contract_management.css`
- `static/js/contract_management.js`
- `core/tests/visual_contract_management_audit.py`
- `docs/UI_MODULE_04_CONTRACT_MANAGEMENT_REPORT_20260927.md`

## UI Migration

Admin:

- List: PageHeader, stats, FilterBar, Table, badges, manual-create panel only for real `don_chua_co_hop_dong`, empty state.
- Detail: overview, status badges, facts, terms, declared companions, PDF/print, edit CTA, status action, renewal action.
- Manual create/edit: Foundation form controls/cards/buttons/dialog confirmation; field names and POST action unchanged.

Tenant:

- List/detail migrated because they are part of the same contract flow.
- Tenant detail keeps PDF, invoice link, renewal request, pending renewal cancellation and print action.

Foundation V1 reused: PageHeader, FilterBar, Table, Badge, Button, Form, Card/Surface, EmptyState, Dialog. `base.html` and endpoints were not changed.

## CSS / JS

- New CSS: `static/css/contract_management.css`.
- New JS: `static/js/contract_management.js`.
- `!important` count in new Module 04 runtime files: 0.
- Inline browser `confirm()` removed from migrated contract forms; Foundation Dialog is used via `data-contract-confirm`.

## Data Baseline

Before live baseline via ORM:

- Phong 86
- Booking 10
- HopDong 6
- LichSuThanhToan 3
- ThanhToanCocDatPhong 0
- NguoiThue 20

After live baseline via ORM:

- Phong 86
- Booking 10
- HopDong 6
- LichSuThanhToan 3
- ThanhToanCocDatPhong 0
- NguoiThue 20

Changed: NO.

## Gallery

Final resolver check:

- Rooms: 86
- Prepared cover: 86
- Missing cover: 0
- Mismatch: 0

No gallery resolver, mapping, media, or room gallery code changed.

## Commands / Tests

Dependency note:

- Initial Python 3.14 run exposed Django 4.2 test-client context copy incompatibility. Tests were rerun on installed Python 3.12, which is present on the machine.

Results:

- `py -3.12 manage.py check`: PASS, `System check identified no issues (0 silenced).`
- `py -3.12 manage.py makemigrations --check --dry-run`: PASS, `No changes detected`.
- Required combined suites: PASS, 89/89.
  Command: `py -3.12 manage.py test core.tests.test_gallery_phong core.tests.test_ui_foundation core.tests.test_giao_dien core.tests.test_phong core.tests.test_tenant_booking_ui core.tests.test_thanh_toan core.tests.test_hop_dong core.tests.test_admin_booking_payment_ui`.
- Module 04 visual audit: PASS, 1/1.
  Command: `py -3.12 manage.py test core.tests.visual_contract_management_audit`.

Covered categories in the 89-test run:

- Gallery
- Foundation
- UI route/render
- Room
- Tenant booking
- Payment
- Contract
- Module 03 admin booking/payment regression

## Visual QA

Environment: isolated Django test database `test_ndt_motel`. No live account or live record was created.

Screens captured in `luu_tru/kiem_thu/module_04/ui_contract_management_qa/`:

- Admin list
- Admin detail
- Tenant list
- Tenant detail

Viewports:

- 1440x900: PASS
- 1024x768: PASS
- 768x900: PASS
- 390x844: PASS

For every captured page/viewport: HTTP 200, page overflow false, broken images 0, console/page errors 0. Evidence JSON: `luu_tru/kiem_thu/module_04/ui_contract_management_qa/results.json`.

## Database / Migration / Workflow

- Database: no schema/data mutation intended.
- Migration: none.
- Workflow: none.
- Business logic: unchanged.

## Remaining Risks

- Existing code still updates contract/room statuses when admin/tenant contract pages are opened. This was pre-existing behavior in `core/views_hop_dong.py` and was not changed.
- Manual contract form remains because the real route/workflow still exists; it should be treated as legacy/support workflow, not the primary deposit-confirmation path.
- Report text uses current implementation as source of truth. Missing explicit checkpoint file was recorded above.

## Module Status

PASS.
