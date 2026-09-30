# Phase 5 - Tenant booking UI

Date: 2026-09-18. Scope: tenant booking and deposit reporting only; STOP before phase 6.

## Inputs and backup

- Based on INVENTORY_AUDIT_20260918.md, ROLE_WORKFLOW_AUDIT_20260918.md,
  lich_su_audit/PHASE3_ROLE_ACCESS_TESTS.md and lich_su_audit/PHASE4_BOOKING_DEPOSIT_DATA.md.
- Pre-edit backup: `backup_phase5_tenant_booking_ui_20260918_193052`.
  Includes source, templates, static, docs, manage.py, requirements, db.sqlite3
  and `mysql_before_phase5.sql` (180092 bytes).
- Active database is MariaDB/MySQL `ndt_motel`, NOT db.sqlite3.
- No new migration or schema change. Legacy fingerprint comparison confirmed
  all original fields/rows of 22 models unchanged after implementation/tests.

## Routes and ownership

| URL | Handler | Template | Access |
| --- | --- | --- | --- |
| /phong/<id>/dat/ | dat_phong | create.html | Tenant |
| /dat-phong-cua-toi/ | dat_phong_cua_toi | list.html | Own bookings |
| /dat-phong-cua-toi/<id>/ | chi_tiet_dat_phong_cua_toi | detail.html | Owner only |
| /dat-phong-cua-toi/<id>/thanh-toan-coc/ | thanh_toan_coc_cua_toi | deposit_payment.html | Owner only |
| /dat-phong-cua-toi/<id>/huy/ | huy_dat_phong_cua_toi | Redirect to detail | Owner POST only |

`core/views_dat_phong.py` owns the tenant workflow; `core/views.py` retains
thin compatibility wrappers for creation/cancellation. The old raw cancellation
URL `/tai-khoan/dat-phong/<id>/huy/` still works through the same writer, with
route name `huy_dat_phong_cua_toi_legacy`. The canonical reverse name now uses
the new cancellation URL. No other existing route was removed.
Guests redirect to login. Staff and superusers cannot submit tenant actions.
Foreign booking/payment IDs return 404 before any mutation.

## Six-step workflow

1. Read-only room and backend price/capacity/availability.
2. Read-only current tenant identity. Existing mandatory fields: name, valid
   12-digit CCCD and phone. Other profile fields remain optional; no profile edit.
3. Check-in, rental months 1-36, people count, sharing choice and note.
4. Exactly people count minus one companions; primary tenant counts as one.
   CCCD, duplication and model validation are server-side. Formset limit is 100
   for bounded request processing. No-JS preparation POST creates form rows only.
5. Full approved server terms and acceptance checkbox; deposit and expected net
   refund displayed before confirmation.
6. Confirm then atomically create booking, companions and one deposit attempt;
   redirect to payment, not an approved-booking success message.

Models: DatPhong, KhaiBaoNguoiOCungDatPhong, ThanhToanCocDatPhong,
Phong, CoSo, NguoiThue; existing HopDong is read for cancellation eligibility.
ThongBao and NhatKyHeThong record notifications/audit. No resident, contract,
room-access permission or refund transfer is created by this tenant workflow.

## Server policy and payment

`motel_management/cau_hinh_dat_phong.py` contains the exact ten clauses approved by
the user, default snapshot rate 80, hold window 24 hours and public bank config:
Techcombank / TCB / 19075135295011 / NGHIEM DINH TUNG.
Booking snapshots copy terms and rate from server configuration, never hidden
inputs or POST values. Acceptance sends only agreement state.
Policy distinguishes 80% no agreement, 100% landlord/system fault and 0% false
information/no arrival after contract/fraud. These are explanations and snapshot
defaults, NOT automatic refund execution or automatic eligibility decisions.

New transfer content is backend-generated `NDTMOTEL COC <ma_yeu_cau> <attempt suffix>`.
The suffix distinguishes retried attempts. Full unique payment reference stays
in its own field. Existing transfer content is not rewritten.
Amount, bank, account and content for VietQR all come from backend records/config.
GET payment/refresh never creates a deposit. A rejected attempt is retried only
by POST and retains history. Expired, cancelled and legacy unconsented bookings
cannot report payment. QR failure is visible instead of showing a fake QR.
Reporting transfer changes payment to pending verification, never confirms funds
or booking and never creates a contract. Repeated reports are idempotent under
room/booking/payment locks. Active staff/superuser accounts receive individually
addressed, deduplicated notifications; no new Admin inbox/menu was introduced.

## Cancellation

- GET is read-only and redirects to detail.
- Unpaid cancellation retains booking/deposit/companion history, cancels the
  unpaid attempt and releases the booking hold through existing state logic.
- Pending/confirmed deposits record a deduplicated Admin cancellation request
  and audit reason; booking/payment state and money remain unchanged.
- Approved bookings or bookings with a contract cannot be cancelled here.
- No hard delete, automatic reimbursement, Admin approval or payment-confirmation
  UI is implemented in phase 5.

## Files

Main new code: views_dat_phong.py, bieu_mau_dat_phong.py,
services/thong_bao_dat_phong.py and cau_hinh_dat_phong.py.
Templates: `templates/core/tenant/booking/` with base, create, list, detail,
deposit_payment, success and components. success.html is reserved, not routed;
the active submit flow goes to payment/detail. Old templates were retained.
Assets: `static/css/tenant/booking.css`, `static/js/tenant/booking.js`.
Only tenant navigation gained a booking link; Admin navigation is unchanged.

Existing source files edited: core/views.py, core/models.py,
core/dich_vu/dat_phong.py, core/dich_vu/tien_coc.py,
motel_management/settings.py, motel_management/urls.py,
templates/core/tenant_base.html, core/tests.py and core/test_tenant_ui.py.
No unrelated Face, Smart Room, roommate, invoice or Admin workflow refactor.

## Verification and test compatibility

- `manage.py check`: 0 issues.
- `manage.py makemigrations --check --dry-run`: No changes detected.
- New tenant UI tests: 20 passed. New deposit UI tests: 12 passed.
- Final `manage.py test core -v 2`: 235 passed in 36.794 seconds.
  All 203 pre-existing test methods remain, plus 32 new methods; no skips/deletions.
- Existing booking test payloads gained required acceptance/count/formset fields.
  The old UI success expectation now asserts redirect to the payment page, as
  required by phase 5 rather than approval on submit.
- The first full run exposed a CSS-basename template discovery assumption:
  booking.css incorrectly implied core/booking.html. Template compilation now
  explicitly maps booking.css to all five booking pages; all other checks remain.
  These compatibility changes reflect the requested route/form/template contract,
  not removal of security assertions or unsupported passing expectations.
- Browser: existing Playwright/Edge, synthetic test snapshots, widths 1440/390.
  Seven states at each width: 14 checks, no horizontal overflow or JS errors.
  Actual VietQR loaded in payment and pending states at both widths. Companion
  add/remove, wizard steps, acceptance and long escaped input exercised.
  Screenshots/results: `artifacts/phase5-booking/`; browser helper:
  `tools/phase5_booking_browser_audit.py`. No real user/payment was created.

## Remaining boundaries

Phase 6 must separately implement authorized Admin reconciliation/approval,
contract creation and manual refund records (amount, reason, timestamp, actor).
Existing phase 4 services are not exposed as new Admin actions in phase 5.
Profile identity displayed later is current profile data, not an invented personal
snapshot field. Large histories may warrant database-level filtering/pagination;
the current tenant list filters owned bookings before paginating in memory.
Do not remove backups, old templates or uncertain files in this step. Backup,
synthetic artifacts and browser logs should stay outside the final submission
package; keep test source and documentation for reproducibility.

Local test URL: http://127.0.0.1:8005/dat-phong-cua-toi/ (existing tenant login).
