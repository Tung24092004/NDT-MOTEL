# UI Module 06 - Sửa chữa và gia hạn

Date: 2026-09-27

## Scope

Chỉ hoàn thiện Module 06. Không bắt đầu Module 07. Không đổi business logic, endpoint, payload, CSRF, quyền, transaction hoặc workflow backend.

Backup đã dùng để đối chiếu: `luu_tru/ban_sao_luu/before_module06_ui_20260927_130447`.

## Files

Runtime Module 06:

- `templates/core/quan_ly_sua_chua.html`
- `templates/core/chi_tiet_sua_chua.html`
- `templates/core/tao_sua_chua.html`
- `templates/core/yeu_cau_sua_chua_cua_toi.html`
- `templates/core/tao_yeu_cau_sua_chua.html`
- `templates/core/chi_tiet_yeu_cau_sua_chua_cua_toi.html`
- `templates/core/chi_tiet_hop_dong.html`
- `templates/core/chi_tiet_hop_dong_cua_toi.html`
- `templates/core/partials/repair_status_badge.html`
- `templates/core/partials/repair_priority_badge.html`
- `templates/core/partials/renewal_status_badge.html`
- `static/css/repair.css`
- Deleted obsolete tenant CSS: `static/css/tenant/yeu_cau_sua_chua_cua_toi.css`
- Deleted obsolete tenant CSS: `static/css/tenant/tao_yeu_cau_sua_chua.css`
- Deleted obsolete tenant CSS: `static/css/tenant/chi_tiet_yeu_cau_sua_chua_cua_toi.css`

Verification-only file:

- `core/tests/visual_module06_repair_audit.py`

## Verification

- Working tree: no `.git` repository; compared current source to backup by file hash.
- Removed CSS references: PASS, no references to the three deleted tenant repair CSS files in `templates`, `static`, `core`, `docs`, or `tools`.
- `manage.py check`: PASS, 0 issues.
- Focused regression rerun: PASS, 94/94 tests for `test_giao_dien`, `test_phan_quyen`, `test_hop_dong`, `test_gia_han`. No complete prior 74-test result was present, so this expanded group was rerun on isolated `test_ndt_motel`.
- Migration dry-run: PASS, `makemigrations --check --dry-run` reported no changes.
- Full suite: PASS, `manage.py test core --noinput -v 2`, 308/308 tests, then rerun on final source state with `manage.py test core --noinput`, 308/308 tests in 24.509s.

## Visual QA

Initial browser run inside sandbox failed with Windows `PermissionError [WinError 5]` while Playwright spawned its subprocess. Rerun outside sandbox completed successfully.

Visual QA PASS on isolated `test_ndt_motel`: 8 screens x 4 viewports = 32 checked cases.

Screens checked:

- Admin repair list
- Admin repair detail
- Admin repair create
- Tenant repair list
- Tenant repair detail
- Tenant repair create
- Admin contract detail with pending renewal
- Tenant contract detail with pending renewal

Viewports checked: `1440x900`, `1024x768`, `768x900`, `390x844`.

Assertions: HTTP 200, horizontal overflow false, broken images 0, console/page errors 0. Evidence: `luu_tru/kiem_thu/module_06/repair_contract_qa/results.json` and 32 screenshots.

## Data Checks

- Live counts: `Phong/DatPhong/HopDong/LichSuThanhToan/ThanhToanCocDatPhong/NguoiThue = 86/10/6/3/0/20`.
- Gallery resolver: `86/86`, mismatch `0`.
- Artifact files at project root: `0`.
- Source `__pycache__` under `core`, `templates`, `static`, `motel_management`, `tools`: `0`.

## Backend Limits

- Repair workflow still uses existing backend constraints: Admin-created repair requests require a tenant and a room tied to an active contract; no new common-area or empty-room repair backend was added.
- Tenant repair detail remains view-only; no cancel endpoint was added.
- Renewal logic, eligibility, approval/rejection, access extension, notification behavior and transaction rollback remain unchanged.

Status: PASS for Module 06. Module 07 was not started.
