# UI Module 02 - Tenant Booking Experience

Date: 2026-09-27

## BACKUP

- `luu_tru/ban_sao_luu/backup_before_tenant_booking_ui_20260927_005900`
- Verified: 21 files, 21 SHA-256 results, 185379 bytes.
- Runtime edits started only after the booking template directory was confirmed in the backup.

## FLOW DISCOVERED

Routes:

- `/phong/` -> room discovery.
- `/phong/<id>/` -> public room detail and availability CTA.
- `/phong/<id>/dat/` -> tenant-only six-step booking request.
- `/dat-phong-cua-toi/` -> owned booking list and status filter.
- `/dat-phong-cua-toi/<id>/` -> owned booking detail.
- `/dat-phong-cua-toi/<id>/thanh-toan-coc/` -> deposit instructions, VietQR, report transfer or retry.
- `/dat-phong-cua-toi/<id>/huy/` -> owned booking cancellation/request, POST mutation only.

Views: public room screens use `core.views_phong`; tenant booking uses `core.views_dat_phong`.

Templates: `danh_sach_phong.html`, `chi_tiet_phong.html`, and active templates under `templates/core/tenant/booking/`.

CSS: public room CSS remains unchanged; tenant booking uses Foundation V1 plus `static/css/tenant/booking.css` for module layout only.

JS: `static/js/tenant/booking.js`; Foundation dialog infrastructure is loaded by the booking shell.

Status/action: all labels and actions are derived from the existing `payment_state()` context and `can_pay`, `can_view_qr`, `can_cancel`, `can_request_cancel`, and `contract` conditions.

## FOUNDATION USED

Typography, Button, Badge, Form, PageHeader, Card, EmptyState, Dialog, focus states and responsive tokens/utilities are reused. The module shell loads Foundation locally; `base.html` was not changed.

## ROOM LIST

The already-passing `/phong/` pilot was retained. No gallery, filter, metadata or CTA workflow was changed.

## ROOM DETAIL

The existing conversion layout, gallery, price hierarchy, availability explanation and booking CTA were retained. Public visual QA confirms stable gallery and responsive behavior.

## BOOKING FLOW

Actual steps:

1. Verify selected room.
2. Verify current tenant identity.
3. Enter stay information.
4. Declare companions.
5. Review costs and server policy snapshot, then accept terms.
6. Confirm request and continue to deposit payment.

The stepper reflects these six real steps. Submission still creates a pending booking and deposit attempt atomically, then redirects to deposit payment. It does not approve a booking or create a contract.

## BOOKING FORM

Labels, nearby field errors, required acceptance, server validation and no-JS companion preparation remain intact. Field names, POST actions and validation rules were not changed.

## ROOM SUMMARY

The compact summary keeps room, facility, type, capacity, rent and deposit. It still uses `phong.anh_dai_dien_hien_thi`, preserving the display-cover contract.

## DEPOSIT / PAYMENT

The payment screen now separates deposit amount, bank, account, account holder, transfer content, QR and deadline. It explicitly states that deposit is not total rent and reporting a transfer only enters pending verification.

## QR

VietQR backend data and URL generation are unchanged. CSS preserves intrinsic ratio, caps desktop width and fits at 390px. A load failure exposes the existing safe fallback message.

## PAYMENT STATUS

Rendered labels distinguish unpaid, pending, confirmed, rejected, cancelled, refunded and legacy states. Raw enum values are used only in server/template conditions and are not displayed.

## REFUND POLICY

Create/detail screens continue to render backend `refund`, `expected_refund`, and booking snapshot values. No percentage was introduced as a template constant.

## MY BOOKINGS

The list uses Foundation PageHeader, filter bar, cards, badges and EmptyState. Each row emphasizes one state-derived next action instead of exposing every possible action.

## BOOKING DETAIL

Information is grouped into status, room/stay, tenant, companions, deposit snapshot, policy and eligible actions. It does not dump model fields or raw enums.

## CANCEL FLOW

Dialog migrated: YES.

Reason: the Foundation dialog safely confirms the existing POST form without changing endpoint, CSRF token, reason field or backend eligibility. It supports Escape, focus trap and focus restoration. Without JS, the original POST form remains usable.

## RESPONSIVE

- 1440: PASS, public room list/detail, no overflow or broken image.
- 1024: PASS, public room list/detail, no overflow or broken image.
- 768: PASS, public room list/detail, no overflow or broken image.
- 390: PASS, public room list/detail, no overflow or broken image.
- Booking-specific CSS stacks summary, forms, actions, QR and detail columns at mobile breakpoints. Authenticated browser verification is recorded separately below.

## ACCESSIBILITY

Foundation focus-visible styles, semantic headings, labelled fields, named buttons, QR alt text, live copy feedback, ordered step indicators and accessible dialog behavior are present. Touch controls retain Foundation minimum heights.

## LEGACY CSS

Removed: duplicate booking button, badge, form, PageHeader, card and empty-state styling from the former 899-line booking stylesheet.

Retained: booking-only wizard, room summary, record layout, detail grouping, payment/QR and responsive specialization.

`!important`: 0 in Foundation and booking CSS.

## TESTS

- Django: PASS, 0 issues.
- Migration: PASS, `No changes detected`.
- Gallery: PASS, 13/13.
- UI: PASS, 24/24.
- Foundation: PASS, 4/4.
- Room module: PASS, 5/5.
- Existing tenant booking: PASS, 20/20.
- Existing deposit/payment: PASS, 12/12.
- Tenant booking Module 02: PASS, 5/5.

All tests used Django's isolated `test_ndt_motel` database and ran sequentially.

## LIVE DATA

Before: Phong 86; Booking 10; Contract 6; Payment history 3; Deposit transaction 0; Tenant 20.

After: Phong 86; Booking 10; Contract 6; Payment history 3; Deposit transaction 0; Tenant 20.

Changed: NO.

## GALLERY

Consistency: CARD = DETAIL MAIN = BOOKING SUMMARY = DISPLAY COVER, 86/86.

Mismatch: 0.

No resolver, TC/CC/GL/CH mapping or production `HinhAnhPhong` logic changed.

## VISUAL QA

Public: PASS at 1440, 1024, 768 and 390 for `/phong/` and `/phong/1/`; all responses 200, horizontal overflow 0, broken images 0, console/page errors 0. Evidence: `luu_tru/kiem_thu/module_02/ui_tenant_booking_qa/`.

Tenant authenticated: NOT TESTED. No valid isolated browser session was available; no credential was guessed and no live booking/user/payment was created for screenshots.

## !IMPORTANT

Count: 0.

## NEW REGRESSIONS

Count: 0 detected.

Details: required focused and cross-module suites pass; public browser audit is clean.

## FILES MODIFIED

- `templates/core/tenant/booking/base.html`
- `templates/core/tenant/booking/list.html`
- `templates/core/tenant/booking/detail.html`
- `templates/core/tenant/booking/deposit_payment.html`
- `static/css/tenant/booking.css`
- `static/js/tenant/booking.js`
- `core/tests/test_tenant_booking_ui.py`
- `tools/audit_tenant_booking_visual.py`
- `docs/UI_MODULE_02_TENANT_BOOKING_REPORT_20260927.md`
- `luu_tru/kiem_thu/module_02/ui_tenant_booking_qa/` visual evidence

## DATABASE

NONE.

## MIGRATION

NONE.

## WORKFLOW

NONE. Business state transitions, permissions, URLs, payment/deposit rules, cancellation eligibility and contract creation remain unchanged.

## MODULE STATUS

PASS, with authenticated visual QA explicitly NOT TESTED.

## RECOMMENDED NEXT MODULE

Admin Booking Management is the logical next candidate because it shares booking states and reconciliation terminology. Recommendation only; it was not implemented.
