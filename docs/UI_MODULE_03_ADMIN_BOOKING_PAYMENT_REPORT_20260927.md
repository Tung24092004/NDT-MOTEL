# UI Module 03 - Admin Booking and Deposit/Payment Management

Date: 2026-09-27

## BACKUP

- `luu_tru/ban_sao_luu/backup_before_admin_booking_payment_ui_20260927_012536`
- Verified before runtime edits: 8 files, 8 SHA-256 results, 148368 bytes.

## WORKFLOW DISCOVERED

User booking: the tenant six-step flow creates a pending `DatPhong` and one deposit attempt, then redirects to deposit instructions.

Payment: the tenant reports a transfer through the existing deposit endpoint. This changes the active `ThanhToanCocDatPhong` to `cho_xac_nhan`; it does not confirm money, approve booking or create a contract.

Admin confirmation: `confirm_deposit_and_create_contract()` validates permissions, snapshots, amount, room availability and pending deposit inside one atomic transaction. It confirms the deposit, moves booking to approved and creates one contract.

Contract eligibility: the UI uses the existing `co_the_xac_nhan_coc_va_tao_hop_dong` condition. The service remains authoritative and revalidates every rule. Contract creation is never automatic on tenant payment report.

## ROUTES

- `/quan-ly-dat-phong/` -> Admin booking/deposit queue.
- `/quan-ly-dat-phong/<id>/` -> review detail.
- `/quan-ly-dat-phong/<id>/xac-nhan-va-tao-hop-dong/` -> POST atomic confirmation/contract creation.
- `/quan-ly-dat-phong/<id>/tu-choi-coc/` -> POST deposit rejection.
- `/quan-ly-dat-phong/<id>/tu-choi-yeu-cau/` -> POST booking rejection.
- `/quan-ly-dat-phong/<id>/xu-ly/` -> retained legacy booking actions.
- `/quan-ly-dat-phong/<id>/tao-hop-dong/` -> retained manual contract form route.

No URL changed.

## VIEWS

`core.views_quan_tri_dat_phong` owns the active list/detail and Phase 6 actions. `core.views_quan_tri.xu_ly_dat_phong` remains the existing legacy booking action handler. Only Vietnamese presentation labels/messages were corrected; conditions and writers were not changed.

## TEMPLATES

- `templates/core/quan_ly_dat_phong.html`
- `templates/core/chi_tiet_dat_phong.html`

The former inline design systems and duplicate detail action areas were replaced by one Foundation-based list and one review detail.

## CSS / JS

- `static/css/admin_booking.css`: module layout and responsive specialization only.
- `static/js/admin_booking.js`: Foundation Dialog binding for existing forms.
- Foundation dialog/CSS assets are loaded locally by these two screens. `base.html` was not changed.

## FOUNDATION USED

PageHeader, FilterBar, Table, Badge, Button, Form, Card/Surface, EmptyState, Dialog, typography, spacing, responsive behavior and focus states.

## BOOKING LIST

The list answers which item needs attention through priority ordering already supplied by the backend, a subtle pending row treatment, separate booking/payment badges and one contextual action. The table is reduced to request, tenant, room, dates, deposit, payment, booking and action.

## FILTERS

Only backend-supported filters are present:

- `q`: request code, tenant identity/contact, room and facility.
- `trang_thai`: booking status.
- `coc`: deposit/payment status including no transaction.
- `hop_dong`: contract presence.

Reset and pagination preserve all active query parameters.

## STATUS MAPPING

Booking:

- `cho_duyet` -> Chờ duyệt / warning.
- `da_duyet` -> Đã duyệt / success.
- `tu_choi` -> Từ chối / danger.
- `da_huy` -> Đã hủy / danger.

Payment:

- `chua_thanh_toan` -> Chờ thanh toán / info.
- `cho_xac_nhan` -> Chờ đối soát / warning.
- `da_xac_nhan` -> Đã xác nhận cọc / success.
- `tu_choi` -> Cọc bị từ chối / danger.
- `da_huy` -> Đã hủy giao dịch / danger.
- `da_hoan_tien` -> Đã hoàn tiền / success.
- no record -> Chưa có giao dịch / info.

Raw values remain condition keys only and are not rendered.

## BOOKING DETAIL

The review page groups status overview, tenant, room, stay details, deposit/payment history, policy snapshot, declared companions and eligible actions. It avoids model-field dumping and limits tenant PII to existing fields needed for review.

## PAYMENT REVIEW

Each real deposit attempt shows amount, localized payment method, transfer content, payment reference, bank transaction reference, tenant report time, Admin confirmation time, status and rejection reason when present. No evidence or timeline event is invented.

## ACTION HIERARCHY

Pending reconciliation emphasizes one primary action: `Xác nhận cọc và tạo hợp đồng`. Deposit rejection and booking rejection are danger actions with required reasons. Other states expose review/detail or the retained legacy/manual action only when its existing condition allows it.

## DIALOG MIGRATION

Confirm before: direct submit on Phase 6 actions and browser `confirm()` on legacy detail actions.

Confirm after: Foundation Dialog with Escape, focus trap, focus restoration and explicit effect wording.

Actions migrated: atomic deposit confirmation/contract creation, deposit rejection, booking rejection, legacy booking approval/rejection/cancellation, and the list quick confirmation. Request methods, endpoints, field names, CSRF and permission checks are unchanged.

## CONTRACT CTA

Rule: the primary atomic CTA appears only when the current deposit is pending reconciliation, booking state is eligible and no contract exists. The backend revalidates amount, terms snapshots, capacity, room availability and overlapping contract rules.

Presentation: wording explicitly states that confirming cọc also approves the booking and creates the contract. Existing contracts show `Xem hợp đồng`. The retained manual form is shown only for an approved booking without a contract.

## RESPONSIVE

- 1440: PASS, list/detail/payment/dialog inspected.
- 1024: PASS, list table remains usable in its scroll container.
- 768: PASS, filter and layout collapse cleanly.
- 390: PASS, filter/detail/actions/dialog stack; table scroll is contained and page overflow is zero.

## ACCESSIBILITY

Visible labels, named buttons, semantic headings, status text beyond color, Foundation focus-visible states, keyboard-capable dialog, Escape handling, required reason fields and mobile touch targets are retained. The scrollable table has a stable bounded container.

## TESTS

- Django: PASS, 0 issues.
- Migration: PASS, `No changes detected`.
- Gallery: PASS, 13/13.
- UI: PASS, 24/24.
- Foundation: PASS, 4/4.
- Room: PASS, 5/5.
- Tenant Booking Module 02: PASS, 5/5.
- Existing Tenant Booking: PASS, 20/20.
- Payment: PASS, 12/12.
- Existing Phase 6 Admin Booking: PASS, 6/6.
- Admin Booking Module 03: PASS, 6/6.
- Isolated authenticated browser audit: PASS, 1/1.

All automated mutation tests used `test_ndt_motel` and ran sequentially.

## LIVE DATA

Before: Phong 86; Booking 10; Contract 6; Payment history 3; Deposit transaction 0; Tenant 20.

After: Phong 86; Booking 10; Contract 6; Payment history 3; Deposit transaction 0; Tenant 20.

Changed: NO.

## GALLERY

Consistency: CARD = DETAIL MAIN = BOOKING SUMMARY = DISPLAY COVER, 86/86.

Mismatch: 0.

Admin room summary uses `anh_dai_dien_hien_thi`; resolver, style mapping and `HinhAnhPhong` production logic were not changed.

## VISUAL QA

Admin: PASS.

Environment: ISOLATED TEST.

`StaticLiveServerTestCase` failed closed unless the active DB name was `test_ndt_motel`. It created synthetic Admin/tenant/booking/payment records only in that database, authenticated with a Django test-client session cookie, ran headless Chrome, then destroyed the test database. No live account or record was created.

Evidence: `luu_tru/kiem_thu/module_03/ui_admin_booking_payment_qa/` contains list screenshots at 1440/1024/768/390, detail and payment review at 1440/390, dialog at 390, and JSON results. All checked pages returned 200 with page overflow 0, broken images 0 and JS/console errors 0.

## !IMPORTANT

Count: 0 in Foundation and Module 03 CSS.

## RAW ENUM

Count: 0 rendered.

## MOJIBAKE

Count: 0 in modified runtime files.

## NEW REGRESSIONS

Count: 0 detected.

Details: all required prior-module, payment and Admin workflow suites pass after migration.

## FILES MODIFIED

- `core/views_quan_tri_dat_phong.py`
- `templates/core/quan_ly_dat_phong.html`
- `templates/core/chi_tiet_dat_phong.html`
- `static/css/admin_booking.css`
- `static/js/admin_booking.js`
- `core/tests/test_admin_booking_payment_ui.py`
- `core/tests/visual_admin_booking_audit.py`
- `docs/UI_MODULE_03_ADMIN_BOOKING_PAYMENT_REPORT_20260927.md`
- `luu_tru/kiem_thu/module_03/ui_admin_booking_payment_qa/` evidence

## DATABASE

NONE.

## MIGRATION

NONE.

## WORKFLOW

NONE. Booking/deposit state machines, calculations, VietQR, refund rules, permissions, notifications and contract transaction remain unchanged.

## MODULE STATUS

PASS.

## RECOMMENDED NEXT MODULE

Contract Management is the logical next migration because the current atomic Admin action ends at contract detail. Recommendation only; it was not implemented.
