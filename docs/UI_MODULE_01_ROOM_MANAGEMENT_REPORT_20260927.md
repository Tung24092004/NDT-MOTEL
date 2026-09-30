# UI Module 01 - Room Management Report - 2026-09-27

## BACKUP

Source: `luu_tru/ban_sao_luu/backup_before_room_management_ui_20260927_002300`

Verified: YES. The backup contains 443 source files and a 443-entry SHA-256 manifest.

## ROUTES

List: `/quan-ly-phong/` (`quan_ly_phong`)

Create: `/quan-ly-phong/tao/` (`tao_phong`)

Edit: `/quan-ly-phong/<int:id>/sua/` (`sua_phong`)

Other:

- Delete: `/quan-ly-phong/<int:id>/xoa/` (`xoa_phong`), POST-only and unchanged.
- Public detail: `/phong/<int:id>/` (`chi_tiet_phong`), linked from the admin list but not redesigned in this module.

## TEMPLATES

- `templates/core/quan_ly_phong.html`
- `templates/core/tao_phong.html`
- `templates/core/sua_phong.html`

Shared module stylesheet: `static/css/room_management.css`.

No URL, view, model, permission, gallery, or business-service code changed.

## BEFORE

Issues:

- List contained dashboard-like KPI cards, duplicated inline CSS, overlapping overrides, and dense three-action rows.
- List columns emphasized area/location while omitting room type and floor from the main scan path.
- Only `q` and `trang_thai` filters exist in the backend; no type/facility filter could be safely presented.
- Create used six visually separate cards and its own CSS vocabulary.
- Edit used a second, unrelated page/panel/sidebar vocabulary.
- Create and edit therefore looked like different products despite sharing the same field contract.
- Form validation is implemented manually in the views through Django messages, not `ModelForm` field errors. Field-level backend errors could not be introduced without changing validation architecture.

## FOUNDATION COMPONENTS USED

PageHeader: shared Foundation partial on list, create, and edit.

FilterBar: list search and real status filter only; reset appears only for active filters.

Table: seven-column desktop table with horizontal-scroll wrapper on narrow screens.

Badge: success = Trống, warning = Đã đặt, info = Đang thuê, danger = Bảo trì.

Button: primary, secondary, ghost, compact, disabled/focus contracts from Foundation V1.

Form: shared label/control/helper/required/choice/file contracts, 44px controls, and native required semantics.

Card: restrained module sections and image items; no nested decorative card layout.

EmptyState: distinct copy and CTA for no filter result versus an empty database.

Dialog: not migrated. The existing delete `confirm()` remains unchanged to avoid expanding destructive workflow scope.

## ROOM LIST

Changes:

- Removed KPI cards from the operational list page.
- Reused PageHeader with a clear `+ Thêm phòng` action.
- Kept only working backend filters: keyword and status.
- Added a real reset action without adding fake filters.
- Standardized columns to Phòng, Cơ sở, Loại, Tầng, Giá thuê, Trạng thái, and Thao tác.
- Kept view, edit, and delete actions with their original URLs and POST/CSRF behavior.
- Preserved delete confirmation and permission checks.
- Differentiated filtered-empty and database-empty messaging.

## CREATE

Sections:

- Thông tin cơ bản
- Giá và chi phí
- Tiện ích và mô tả
- Hình ảnh

Changes:

- Two-column desktop form and one-column mobile form.
- Labels, required markers, unit suffixes, helpers, upload preview, and a stable action bar now share Foundation contracts.
- POST values are retained in controls when manual backend validation returns the form.
- All original field names, multipart upload behavior, accepted image types, and initial-status restrictions remain intact.

## EDIT

Sections:

- Thông tin cơ bản
- Giá và chi phí
- Trạng thái vận hành
- Tiện ích và mô tả
- Hình ảnh

Changes:

- Uses the same visual and responsive form contract as create.
- Preserves automatic business-status handling and the existing maintenance toggle behavior.
- Preserves `anh_dai_dien_id`, `xoa_anh`, multi-image upload, existing image display, and client-side preview.
- Keeps gallery fallback behavior explicit when no private images exist.
- Uses the same cancel/save hierarchy as create.

## STATUS

Mapping:

- `trong` -> Trống -> success
- `da_dat` -> Đã đặt -> warning
- `dang_thue` -> Đang thuê -> info
- `bao_tri` -> Bảo trì -> danger

No raw enum is rendered as a room-status label. Database values and synchronization rules remain unchanged.

## RESPONSIVE

1440: Designed for full seven-column table and two-column forms.

1024: Filter wraps deliberately; table remains in its scroll shell; forms retain two columns where useful.

768: Horizontal table scroll remains the safe baseline; form sections retain readable spacing.

390: Header/actions and filters stack; forms become one column; upload/image controls and action buttons fill available width.

Admin browser screenshots were not produced because no authenticated browser session was available. These behaviors were verified by CSS contract and authenticated Django render tests, not claimed as browser visual PASS.

## ACCESSIBILITY

- Every form control has a visible associated label.
- Required controls use native `required` plus a visible marker.
- Foundation focus-visible states remain active.
- Buttons retain explicit accessible names; delete controls include contextual `aria-label` and `title`.
- Statuses always include readable text and do not rely only on color.
- Table headers use `scope="col"`; the action-column label is available to screen readers.
- Mobile controls use the Foundation 44px target baseline.
- Existing backend validation messages remain visible. True field-level server errors require a later form-validation architecture task rather than duplicated client logic.

## LEGACY CSS

Removed:

- All module-specific inline `<style>` blocks from list, create, and edit templates.
- Duplicate room-list CTA/filter overrides and the separate create/edit visual systems.

Retained:

- Global `static/css/style.css` rules, because selectors such as `.admin-primary-btn` have consumers outside this module.
- Existing global shell/sidebar/topbar CSS and JavaScript.
- Existing delete confirmation and form image-preview/maintenance JavaScript behavior.

Reason: only CSS proven to be owned by these three templates was consolidated. Shared legacy assets were not mass-cleaned.

## TESTS

Django: PASS, no issues.

Migration: PASS, `No changes detected`.

Gallery: PASS, 13/13, exit code 0.

UI: PASS, 24/24, exit code 0.

Foundation: PASS, 4/4, exit code 0.

Room module: PASS, 5/5, exit code 0. Coverage includes list/filter/status/actions, create/edit shared contract, asset loading, permissions, and invalid create/edit POSTs with unchanged test data.

## DATA

Before: Phong 86; Booking 10; Contract 6; Payment history 3; Deposit 0; Tenant 20.

After: Phong 86; Booking 10; Contract 6; Payment history 3; Deposit 0; Tenant 20.

Changed: NO

## GALLERY

Consistency: 86/86.

Mismatch: 0.

No resolver, mapping, media file, display-cover logic, or legacy image record changed.

## VISUAL QA

Admin: NOT TESTED.

Reason: no valid authenticated browser session or approved credential was available. No live account/session was created for screenshots. Authenticated Django test-client rendering passed for list, create, and edit.

## !IMPORTANT

Count: 0 across Foundation CSS, `room_management.css`, and the three migrated templates.

## NEW REGRESSIONS

Count: 0 detected by available automated checks.

Details: one attempted parallel test invocation collided on the shared MySQL test database; suites were rerun sequentially and all passed. This was test orchestration, not an application defect.

## FILES MODIFIED

- `static/css/room_management.css`
- `templates/core/quan_ly_phong.html`
- `templates/core/tao_phong.html`
- `templates/core/sua_phong.html`
- `core/tests/test_room_management_ui.py`
- `core/tests/test_ui_foundation.py`
- `docs/UI_MODULE_01_ROOM_MANAGEMENT_REPORT_20260927.md`

## DATABASE

NONE

## MIGRATION

NONE

## WORKFLOW

NONE

## MODULE STATUS

PASS

## RECOMMENDED NEXT MODULE

Module 02 should address admin booking management (`/quan-ly-dat-phong/`) using the established PageHeader, FilterBar, Table, Badge, and action contracts. It is the next operational list already stabilized at P0, but its approval/cancellation/payment-adjacent actions require a separate scoped migration and workflow regression plan.

Recommendation only. Module 02 was not started.
