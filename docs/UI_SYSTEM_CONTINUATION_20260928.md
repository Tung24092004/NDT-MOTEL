# UI system continuation - 2026-09-28

## Scope

Continued from the 2026-09-27 module reports. This pass targeted the items still visible in screenshots after Module 10:

- Tenant account navigation repeated a large five-column strip on User screens.
- Tenant invoice detail felt narrow and small at `/hoa-don-cua-toi/<id>/`.
- Tenant invoice list could use the available page width better.
- Public room detail rendered the Admin edit action as a plain text link.

No model, URL, permission, POST payload, CSRF, transaction, payment state, invoice calculation, booking flow, gallery resolver, or live media file was changed.

## Route Matrix

| Area | Routes checked | Status | Notes |
| --- | --- | --- | --- |
| Foundation / tenant shell | All `tenant_base.html` consumers in visual audit | Updated | Tenant nav is now compact chip navigation on desktop and collapsible details on mobile. |
| Tenant invoices | `/hoa-don-cua-toi/`, `/hoa-don-cua-toi/<id>/`, `/hoa-don-cua-toi/<id>/thanh-toan/` | Updated / checked | List and detail use wider containers, stronger amount/status hierarchy, and mobile stacks without workflow changes. Payment page checked by visual audit and tests. |
| Room detail | `/phong/<id>/` | Updated / checked | Admin "Sửa thông tin phòng" now uses button styling; tenant booking/gallery behavior unchanged. |
| Tenant booking | `/dat-phong-cua-toi/`, detail, deposit, empty state | Checked | No source change in this pass; visual audit PASS. |
| Tenant sharing | `/yeu-cau-ghep-cua-toi/`, `/phong/<id>/dang-ky-ghep/` | Checked | No source change in this pass; visual audit PASS. |
| Admin room management | `/quan-ly-phong/`, create, edit | Checked | No source change in this pass; visual audit PASS. |
| Admin dashboard | `/dashboard-admin/` | Checked | No source change in this pass; visual audit PASS. |
| Remaining visual audit screens | Admin booking, contracts, tenants, invoices, repair, notifications, Smart Room, account, password | Checked | No source change in this pass; visual audit PASS across the captured matrix. |

## Files Changed

Foundation / shell:

- `static/css/tenant/components.css`
- `static/css/ui-system.css`

User:

- `static/css/tenant/hoa_don_cua_toi.css`
- `static/css/tenant/chi_tiet_hoa_don_cua_toi.css`

Public room detail:

- `templates/core/chi_tiet_phong.html`

Report:

- `docs/UI_SYSTEM_CONTINUATION_20260928.md`

## Visual Evidence

Before screenshots already existed in:

- `luu_tru/kiem_thu/system_ui_upgrade/before/`

After screenshots and machine-readable audit:

- `luu_tru/kiem_thu/system_ui_upgrade/after/results.json`
- `luu_tru/kiem_thu/system_ui_upgrade/after/invoice_tenant_detail_1440.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/invoice_tenant_detail_390.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/invoice_tenant_list_1440.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/invoice_tenant_list_390.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/m05_tenant_sharing_list_1440.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/m05_tenant_sharing_list_390.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/m02_tenant_room_detail_1440.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/m02_tenant_room_detail_390.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/m01_admin_room_list_1440.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/m01_admin_room_edit_1440.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/m08_admin_dashboard_1440.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/m10_tenant_account_1440.png`
- `luu_tru/kiem_thu/system_ui_upgrade/after/m10_tenant_account_390.png`

## Verification

- `py -3.12 manage.py check`: PASS, 0 issues.
- `py -3.12 manage.py makemigrations --check --dry-run`: PASS, `No changes detected`.
- Focused tenant/invoice/room tests: PASS, 40/40.
- Full suite after final CSS change: PASS, 311/311.
- Visual audit after final CSS change: PASS, 41 screens x 4 viewports = 164 cases.

Visual audit counters:

- Bad HTTP status: 0
- Horizontal overflow: 0
- Broken images: 0
- Console/page errors: 0
- Mojibake: 0
- Raw enum text: 0
- Unlabeled visible controls: 0
- Unnamed visible actions: 0

## Data

Live data was only read after the pass:

- `Phong/DatPhong/HopDong/HoaDon/LichSuThanhToan/ThanhToanCocDatPhong/NguoiThue = 86/10/6/6/3/0/20`

No live data, gallery records, media files, or production image mappings were changed. Browser visual QA used isolated `test_ndt_motel` data. Face ID with a real webcam remains a manual device blocker, unchanged from Module 09/10 notes.

