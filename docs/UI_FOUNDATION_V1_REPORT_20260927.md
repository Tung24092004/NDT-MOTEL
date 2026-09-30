# UI Foundation V1 Report - 2026-09-27

## BACKUP

Source: `luu_tru/ban_sao_luu/backup_before_ui_foundation_v1_20260927_000820`

Verified: YES. The backup contains 433 source files and a 433-entry SHA-256 manifest at `SOURCE_MANIFEST_SHA256.txt`.

## FOUNDATION FILES

Tokens: `static/css/foundation/tokens.css`

Typography: `static/css/foundation/typography.css`

Components: `static/css/foundation/components.css`

Utilities: `static/css/foundation/utilities.css`

JS: `static/js/foundation/dialog.js`

Shared templates:

- `templates/core/foundation/page_header.html`
- `templates/core/foundation/empty_state.html`
- `templates/core/foundation/dialog_root.html`

The foundation is opt-in through `.ndt-foundation`. It was not added to `base.html`, so non-pilot pages do not receive component styling in V1.

## TOKENS

Brand: existing NDT teal `#08798a` with hover/active tones; lotus yellow `#e7bd42` remains a restrained accent.

Semantic: success, warning, danger, info, canvas, surface, muted surface, text, secondary text, muted text, border, and strong border.

Typography: 12, 14, 16, 20, 24, 32, and 40px semantic scale; Arial/Helvetica system stack; weights 400/500/600/700 supported by the contract.

Spacing: 4, 8, 12, 16, 24, 32, and 48px.

Radius: 4, 8, 12, and 999px.

Shadow: light surface, dropdown, and modal elevations only.

## COMPONENTS CREATED

Button: primary, secondary, danger, ghost, icon-only, compact, disabled, focus-visible, and loading-ready (`aria-busy`) states. Default control height is 44px.

Badge: neutral, info, success, warning, and danger tones with readable labels and a non-color dot cue.

Form: label, required marker, input/select/textarea, helper, error, invalid, disabled, readonly, checkbox/radio, and file contracts.

PageHeader: shared partial and CSS contract for breadcrumb, title, subtitle, and optional primary action; stacks on mobile.

FilterBar: title, responsive form, field, control, action, and reset-compatible contracts.

Table: horizontal-scroll wrapper, 13-14px body, 12px header, minimum 44px row content target, actions, badge, and empty-state compatibility.

EmptyState: shared partial and CSS contract for optional icon, title, description, and CTA.

Dialog: infrastructure only. Promise-based confirm API, default/danger action, cancel, focus return, Tab focus trap, Escape, overlay, labels, and mobile action layout. No existing `confirm()` or `alert()` was migrated.

Card: surface, card, header, body, and footer contracts with a light border and restrained elevation.

Utilities: page padding, stack, cluster, grid, action wrapping, horizontal scroll, visually hidden text, touch target, and limited mobile visibility helpers.

Accessibility: shared `:focus-visible`, 44px controls/touch targets, disabled states, semantic dialog labels, icon-button accessible-name contract, and reduced-motion fallback.

## PILOT

Public page: `/phong/` (`templates/core/danh_sach_phong.html`).

Admin page: `/quan-ly-phong/` (`templates/core/quan_ly_phong.html`).

Files migrated:

- Public room list: PageHeader, FilterBar, form controls, buttons, badges, cards, empty state, typography, spacing, focus, and responsive behavior.
- Admin room list: PageHeader, FilterBar, form controls, metric cards, table wrapper/table, badges, action buttons, and empty state.

Preserved contracts: room cover resolver, image data, room content, filter names/behavior, query parameters, pagination, URLs, permissions, CSRF, edit/delete actions, and existing delete confirmation.

## LEGACY COMPATIBILITY

Conflicts: pilot-specific layout classes remain in place for room grid, image anatomy, statistics, and table widths. Foundation classes own reusable presentation while local classes retain business-layout details. `ui-system.css` continues to load globally without selector collisions found in QA.

`!important` count: 0 in all new foundation CSS, JS, and shared templates. Existing legacy `!important` declarations were not cleaned or expanded.

Known issues:

- Foundation assets are intentionally loaded only by the two pilots; module migration must opt in explicitly.
- Admin visual behavior was not browser-tested because no valid authenticated browser session was available.
- Legacy admin page CSS remains verbose and contains older overrides; V1 does not remove it.
- Dialog infrastructure is not loaded or used by existing pages yet, so all inventoried browser dialogs remain unchanged.

## TEST

Django check: PASS, no issues.

Migration check: PASS, `No changes detected`.

Gallery: PASS, 13/13, exit code 0, clean teardown.

UI tests: PASS, 24/24, exit code 0, clean teardown.

Foundation tests: PASS, 4/4, exit code 0. Coverage includes asset/partial availability, required component contracts, dialog keyboard infrastructure, public pilot render, admin pilot permissions/actions, status presentation, and gallery cover regression.

## DATA

Phong: 86

Booking: 10

Contract: 6

Payment history: 3

Deposit: 0

Tenant: 20

Changed: NO

## GALLERY

Card: 86

Detail: 86

Mismatch: 0

Consistency: CARD = DETAIL MAIN = BOOKING/DISPLAY COVER 86/86.

No resolver, mapping, media, or gallery architecture changed.

## VISUAL QA

1440x900: PASS.

1024x768: PASS.

768x900: PASS.

390x844: PASS after correcting the mobile FilterBar field flex basis found during the first visual pass.

Public pilot evidence: HTTP 200 at all four viewports, four foundation stylesheets loaded, no page overflow, no broken images, no JavaScript/console errors, visible keyboard focus, 44px primary action height, and direct screenshot review of hierarchy, spacing, typography, cards, statuses, images, controls, and responsive layout.

Admin: NOT TESTED visually because no authenticated browser session or approved credentials were available. The admin pilot passed authenticated Django render tests without changing production data.

Screenshots: `luu_tru/kiem_thu/foundation_v1/ui_foundation_v1_qa/` contains four before images, four after images, and `qa_results.json`.

## NEW REGRESSIONS

Count: 0 remaining.

Details: the initial 390px FilterBar fields inherited a 220px flex basis when stacked. The mobile component rule now resets fields to content height; all four viewports were recaptured and passed.

## FILES MODIFIED

Runtime/source:

- `static/css/foundation/tokens.css`
- `static/css/foundation/typography.css`
- `static/css/foundation/components.css`
- `static/css/foundation/utilities.css`
- `static/js/foundation/dialog.js`
- `templates/core/foundation/page_header.html`
- `templates/core/foundation/empty_state.html`
- `templates/core/foundation/dialog_root.html`
- `templates/core/danh_sach_phong.html`
- `templates/core/quan_ly_phong.html`
- `core/tests/test_ui_foundation.py`

Evidence/report:

- `luu_tru/kiem_thu/foundation_v1/ui_foundation_v1_qa/`
- `docs/UI_FOUNDATION_V1_REPORT_20260927.md`

## DATABASE

NONE

## MIGRATION

NONE

## WORKFLOW

NONE

## FOUNDATION V1 STATUS

PASS

## READY FOR MODULE MIGRATION

YES

## RECOMMENDED FIRST MODULE

Complete the room-management module next: migrate the room create/edit forms and related admin room surfaces onto the established PageHeader, Form, Button, Card, and feedback contracts. This follows the proven room-list pilot, keeps gallery ownership unchanged, and provides a contained path to validate form/error/loading states before moving into higher-risk booking, payment, and contract workflows.

Recommendation only. No additional module migration was started.
