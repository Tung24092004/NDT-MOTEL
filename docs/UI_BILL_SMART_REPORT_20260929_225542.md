# UI Bill + Smart Room Report - 20260929_225542

## 1. Baseline

- Interpreter: `D:\NDT_MOTEL_ENV\Scripts\python.exe`.
- Git: workspace root is not a Git repository.
- `manage.py check`: PASS.
- `makemigrations --check --dry-run`: PASS, `No changes detected`.
- Live data before: `Phong=86`, `CoSo=4`, `NguoiThue=20`, `HopDong=6`, `HoaDon=6`, `LichSuThanhToan=3`, `QuyenRaVao=2`, `FaceProfile=7`, `LichSuRaVao=11`.
- Backup: `luu_tru/ban_sao_luu/before_ui_bill_smart_20260929_225542`.
- Test folder: `luu_tru/kiem_thu/ui_bill_smart_20260929_225542`.

## 2. Routes / Screens Audited

- Admin invoices: `quan_ly_hoa_don`, `chi_tiet_hoa_don`, `tao_hoa_don`, `xu_ly_hoa_don`.
- Tenant invoices: `hoa_don_cua_toi`, `chi_tiet_hoa_don_cua_toi`, `thanh_toan_hoa_don_cua_toi`.
- Smart Room: `smart_room_dashboard`, `smart_access_control`, Face ID terminal/profile screens, access-right list/create/detail/action, access-history list/create/detail/action, tenant Face ID unavailable/self-service.

## 3. Files Changed

- `templates/core/quan_ly_hoa_don.html`
- `templates/core/chi_tiet_hoa_don.html`
- `templates/core/chi_tiet_face_profile.html`
- `templates/core/chi_tiet_quyen_ra_vao.html`
- `templates/core/quan_ly_lich_su_ra_vao.html`
- `templates/core/tenant/booking/create.html` (checkpoint follow-up: restore the tested booking POST contract only).

## 4. Invoice Changes

- Admin invoice list now uses mobile row-card layout at small viewport using scoped `data-label` cells instead of relying on horizontal page/table overflow.
- Fixed one invalid closing tag in the invoice stats section.
- Admin invoice payment-cancel action now uses Foundation Dialog via `data-ndt-confirm-form`; native `confirm()` removed.
- Foundation dialog CSS/JS is loaded only on affected invoice detail/list surfaces.

## 5. Smart Room Changes

- FaceProfile disable action now uses Foundation Dialog and preserves original POST action, CSRF, and `hanh_dong=xoa`.
- Access-right temporary lock/revoke actions now use Foundation Dialog and preserve original POST action, CSRF, and payload.
- Access history list now switches to row-card layout on mobile with labeled fields and full-width detail action.
- No YuNet/SFace, threshold, permission, route, model, transaction, or backend payload was changed.

## 6. Booking Checkpoint Investigation

- Test: `core.tests.test_giao_dien.Phase8B5TenantUIRegressionTests.test_room_detail_and_booking_form_contract_render_for_tenant`.
- Test file/assertion: `core/tests/test_giao_dien.py:192`, with three subtests asserting at line 209 that the booking response contains `name="ho_ten"`, `name="so_dien_thoai"`, and `name="cccd"`.
- Route: `phong/<int:id>/dat/`, URL name `dat_phong` (`motel_management/urls.py:221`).
- View: `core/views_dat_phong.py::dat_phong`; template: `templates/core/tenant/booking/create.html`; form: `core/bieu_mau_dat_phong.py::BookingForm`.
- The named backup contains only the invoice/Smart Room source files selected before that UI pass; it contains no booking template, view, or form. For an isolated check, a complete source copy was created under the evidence folder and the named backup was overlaid onto it. No live database was copied; Django created and destroyed `test_ndt_motel`.
- Isolated backup-state command: `D:\NDT_MOTEL_ENV\Scripts\python.exe manage.py test core.tests.test_giao_dien.Phase8B5TenantUIRegressionTests.test_room_detail_and_booking_form_contract_render_for_tenant --verbosity 2 --noinput`.
- Isolated backup-state result: `Ran 1 test`, `FAILED (failures=3)`, with the same missing `ho_ten`, `so_dien_thoai`, and `cccd` subtests. SHA-256 values for the booking template, view, and form in the isolated source are identical to the pre-fix current source; none was part of the Hóa đơn/Smart Room edit set.
- Conclusion: the three failures existed before the Hóa đơn + Smart Room changes and were not caused by those five edited screens. They were nevertheless a real booking render-contract defect relative to the existing regression test.
- Minimal correction: added hidden `ho_ten`, `so_dien_thoai`, and `cccd` controls populated from the authenticated tenant profile. URL, view, `BookingForm`, CSRF, visible UI, validation, transaction flow, and server-side identity source are unchanged; posted identity values remain ignored by business logic.

## 7. Targeted Tests

- `manage.py test core.tests.test_hoa_don core.tests.test_thanh_toan core.tests.test_phong_thong_minh core.tests.test_phan_quyen --noinput`: PASS, 67/67.
- Before correction, combined targeted run including `test_giao_dien`: FAIL 3 booking-form subtests, 89/92 PASS.
- Exact booking contract test after correction: PASS, `Ran 1 test`, `OK` (all three former failing subtests pass).
- Targeted booking/form command: `manage.py test core.tests.test_dat_phong core.tests.test_giao_dien.Phase8B5TenantUIRegressionTests --verbosity 1 --noinput`.
- Targeted booking/form result: PASS, 63/63.

## 8. Full Regression

- Before checkpoint follow-up: 308/311 PASS, with the three booking subtest failures documented above.
- After the minimal booking template correction: `manage.py test core --verbosity 1 --noinput` found and ran 311 tests; PASS, 311/311 (`OK`).

## 9. Visual QA

- Sandbox Playwright attempt failed with `WinError 5` while spawning browser subprocess.
- Re-run outside sandbox PASS: `manage.py test core.tests.visual_invoice_stage02c core.tests.visual_module09_smart_room_audit --noinput`, 3/3.
- Covered invoice tenant screens and Smart Room visual/camera mock suite across 1440, 1024, 768, and 390 viewports as implemented by the existing audit tests.

## 10. Evidence

- Invoice screenshots/results: `luu_tru/kiem_thu/uiux_stage_02c_invoice/ui_bill_smart_20260929_225542_after/`.
- Smart Room screenshots/results: `luu_tru/kiem_thu/module_09/visual_qa/`.
- Smart Room camera mock results: `luu_tru/kiem_thu/module_09/camera_mock/`.
- Total evidence files checked in these folders: 75.
- Note: true BEFORE screenshots were not captured before edits in this run; backup is available for source comparison.
- Booking checkpoint evidence: `luu_tru/kiem_thu/ui_bill_smart_20260929_225542/booking_audit/`.
- `current_three_failures.txt`: exact current-source three-subtest failure before correction.
- `backup_three_failures.txt`: exact isolated backup-state three-subtest failure.
- `backup_isolation_manifest.txt`: isolation paths, test-database note, and booking template/view/form SHA-256 comparison.
- `current_three_after_fix.txt`: exact booking contract test PASS after correction.
- `targeted_booking_after_fix.txt`: targeted booking/form 63/63 PASS.
- `full_core_after_fix.txt`: full core suite 311/311 PASS.
- `manage_check_after_fix.txt`, `migration_check_after_fix.txt`, and `live_data_after_fix.txt`: final integrity checks.

## 11. Data After

- Live data after: `Phong=86`, `CoSo=4`, `NguoiThue=20`, `HopDong=6`, `HoaDon=6`, `LichSuThanhToan=3`, `QuyenRaVao=2`, `FaceProfile=7`, `LichSuRaVao=11`.
- Data changed: NO.

## 12. Migration Status

- No migration created.
- `makemigrations --check --dry-run`: PASS, `No changes detected`.

## 13. Webcam / Face ID

- Camera behavior was verified only with mocked media/network in Playwright.
- MANUAL BLOCKER: physical webcam + real human Face ID/YuNet/SFace end-to-end recognition was not tested in this environment.

## 14. Remaining Blockers

- Physical webcam validation remains manual.

---

## 15. Full-Domain Continuation - 20260929_232423

### 15.1 Scope and Backup

- Continued from checkpoint `ui_bill_smart_full_20260929_232423`; no repeat of the earlier booking investigation.
- Backup before this redesign pass: `luu_tru/ban_sao_luu/before_ui_bill_smart_full_20260929_232423`.
- Evidence folder: `luu_tru/kiem_thu/ui_bill_smart_full_20260929_232423`.
- Baseline from manifest: `manage.py check` PASS, migration dry-run PASS, full regression `311/311 PASS`, live data `Phong=86; CoSo=4; NguoiThue=20; HopDong=6; HoaDon=6; LichSuThanhToan=3; QuyenRaVao=2; FaceProfile=7; LichSuRaVao=11`.

### 15.2 Inventory - Hoa Don / Thanh Toan

| URL | Route name | Role | View | Template | CSS/JS | Function | UI before | Visible issue | File changed | Result |
|---|---|---|---|---|---|---|---|---|---|---|
| `/quan-ly-hoa-don/` | `quan_ly_hoa_don` | Admin | `core.views_hoa_don.quan_ly_hoa_don` | `quan_ly_hoa_don.html` | inline + Foundation + `bill_smart_full_refresh.css` | Admin invoice list/filter/KPI | B | header/data present but type/buttons too small and desktop density weak | template + shared CSS | Done |
| `/quan-ly-hoa-don/tao/` | `tao_hoa_don` | Admin | `core.views_hoa_don.tao_hoa_don` | `tao_hoa_don.html` | inline + shared CSS | create invoice, meter/service fields | B | form labels/help text and actions too small; narrow container | template + shared CSS | Done |
| `/quan-ly-hoa-don/<id>/` | `chi_tiet_hoa_don` | Admin | `core.views_hoa_don.chi_tiet_hoa_don` | `chi_tiet_hoa_don.html` | inline + Foundation + shared CSS | invoice detail, breakdown, payment actions | B | dense tables/status/action controls too small | template + shared CSS | Done |
| `/quan-ly-hoa-don/<id>/xu-ly/` | `xu_ly_hoa_don` | Admin | `core.views_thanh_toan.xu_ly_hoa_don` | redirect/POST endpoint | existing JS/dialog | confirm/cancel/adjust status | D | endpoint only, no standalone render | none | Documented |
| `/hoa-don-cua-toi/` | `hoa_don_cua_toi` | Tenant | `core.views_hoa_don.hoa_don_cua_toi` | `hoa_don_cua_toi.html` | tenant invoice CSS + shared CSS | personal invoice list/empty state | B | desktop row content small; breadcrumb touch target small; 1440 overflow after first override | template + shared CSS | Done; visual PASS |
| `/hoa-don-cua-toi/<id>/` | `chi_tiet_hoa_don_cua_toi` | Tenant | `core.views_hoa_don.chi_tiet_hoa_don_cua_toi` | `chi_tiet_hoa_don_cua_toi.html` | tenant detail CSS + shared CSS | tenant invoice detail/breakdown/status | B | breadcrumb/action targets small in visual harness | template + shared CSS | Done |
| `/hoa-don-cua-toi/<id>/thanh-toan/` | `thanh_toan_hoa_don_cua_toi` | Tenant | `core.views_thanh_toan.thanh_toan_hoa_don_cua_toi` | `thanh_toan_hoa_don_cua_toi.html` | tenant payment CSS + shared CSS | payment method, VietQR, confirmation request | A/B | already functional; controls normalized to same touch target | template + shared CSS | Done |

### 15.3 Inventory - Smart Room / Face ID / Quyen / Lich Su

| URL | Route name | Role | View | Template | CSS/JS | Function | UI before | Visible issue | File changed | Result |
|---|---|---|---|---|---|---|---|---|---|---|
| `/smart-room/` | `smart_room_dashboard` | Admin | `smart_room_dashboard` | `smart_room_dashboard.html` | `smart_room.css` + inline + shared CSS | dashboard/KPI/capacity/history links | B | KPI, badges and quick links too small | template + shared CSS | Done |
| `/smart-room/access-control/` | `smart_access_control` | Admin | `smart_access_control` | `smart_access_control.html` | `smart_room.css` + inline + shared CSS | terminal/control center | B | camera/result/actions visually dense | template + shared CSS | Done |
| `/smart-room/nguoi-o-cung/` | `quan_ly_nguoi_o_cung` | Admin | `quan_ly_nguoi_o_cung` | `quan_ly_nguoi_o_cung.html` | Foundation + `community.css` + shared CSS | roommate/resident list | A | already Foundation-aligned; included in shared scope | template | Confirmed |
| `/smart-room/nguoi-o-cung/tao/` | `tao_nguoi_o_cung` | Admin | `tao_nguoi_o_cung` | `tao_nguoi_o_cung.html` | Foundation + `community.css` + shared CSS | create roommate | A | already aligned; included for domain consistency | template | Confirmed |
| `/smart-room/nguoi-o-cung/<id>/` | `chi_tiet_nguoi_o_cung` | Admin | `chi_tiet_nguoi_o_cung` | `chi_tiet_nguoi_o_cung.html` | Foundation + `community.css` + shared CSS | roommate detail/actions | A | already aligned; included for domain consistency | template | Confirmed |
| `/smart-room/nguoi-o-cung/<id>/xu-ly/` | `xu_ly_nguoi_o_cung` | Admin | `xu_ly_nguoi_o_cung` | redirect/POST endpoint | community confirm | resident actions | D | endpoint only | none | Documented |
| `/smart-room/face-profile/` | `quan_ly_face_profile` | Admin | `quan_ly_face_profile` | `quan_ly_face_profile.html` | `smart_room.css` + inline + shared CSS | face profile list | B | cards/buttons/status labels too small | template + shared CSS | Done |
| `/smart-room/face-profile/tao/` | `tao_face_profile` | Admin | `tao_face_profile` | `tao_face_profile.html` | `smart_room.css` + inline + shared CSS | create FaceProfile | B | labels/help text/actions too small | template + shared CSS | Done |
| `/smart-room/face-profile/<id>/` | `chi_tiet_face_profile` | Admin/Tenant-rendered shell | `chi_tiet_face_profile` | `chi_tiet_face_profile.html` | Foundation + `smart_room.css` + tenant detail CSS + shared CSS | profile detail, camera registration | B | narrow content and small helper/action text | template + shared CSS | Done |
| `/smart-room/face-profile/<id>/dang-ky/` | `face_id_dang_ky` | Admin/Tenant | `face_id_dang_ky` | redirect/detail flow | detail template/JS | webcam enrollment action | D | action route, not separate page in source | none | Documented |
| `/smart-room/face-profile/<id>/xu-ly/` | `xu_ly_face_profile` | Admin | `xu_ly_face_profile` | redirect/POST endpoint | Foundation Dialog | approve/disable/delete profile | D | endpoint only | none | Documented |
| `/smart-room/face-id/` | `trang_xac_thuc_face_id` | Admin | `trang_xac_thuc_face_id` | `xac_thuc_face_id.html` | `smart_room.css` + inline + shared CSS | Face ID terminal | B | terminal text/buttons/camera state small | template + shared CSS | Done |
| `/smart-room/face-id/xac-thuc/` | `face_id_xac_thuc` | Admin | `face_id_xac_thuc` | JSON/POST endpoint | terminal JS | backend recognition/permission check | D | endpoint only; camera mocked in visual test | none | Documented |
| `/tai-khoan/nhan-dien-su-dung-phong/` | `nhan_dien_su_dung_phong` | Tenant | `nhan_dien_su_dung_phong` | `face_id_unavailable.html` or profile detail | `smart_room.css` + tenant CSS + shared CSS | tenant Face ID readiness | B | tenant unavailable/disabled guidance needed same typography | template + shared CSS | Done |
| `/smart-room/quyen-ra-vao/` | `quan_ly_quyen_ra_vao` | Admin | `quan_ly_quyen_ra_vao` | `quan_ly_quyen_ra_vao.html` | `smart_room.css` + inline + shared CSS | access-right list/filter | B | table/status/actions too small | template + shared CSS | Done |
| `/smart-room/quyen-ra-vao/tao/` | `tao_quyen_ra_vao` | Admin | `tao_quyen_ra_vao` | `tao_quyen_ra_vao.html` | `smart_room.css` + inline + shared CSS | grant permission | C/B | old narrow form with 9-11px labels | template + shared CSS | Done |
| `/smart-room/quyen-ra-vao/<id>/` | `chi_tiet_quyen_ra_vao` | Admin | `chi_tiet_quyen_ra_vao` | `chi_tiet_quyen_ra_vao.html` | Foundation + `smart_room.css` + inline + shared CSS | permission detail/actions | B | small status/action text | template + shared CSS | Done |
| `/smart-room/quyen-ra-vao/<id>/xu-ly/` | `xu_ly_quyen_ra_vao` | Admin | `xu_ly_quyen_ra_vao` | redirect/POST endpoint | Foundation Dialog | lock/restore/revoke | D | endpoint only | none | Documented |
| `/smart-room/lich-su-ra-vao/` | `quan_ly_lich_su_ra_vao` | Admin | `quan_ly_lich_su_ra_vao` | `quan_ly_lich_su_ra_vao.html` | `smart_room.css` + inline + shared CSS | access history list/filter | B | dense filter/table and small labels | template + shared CSS | Done |
| `/smart-room/lich-su-ra-vao/tao/` | `tao_lich_su_ra_vao` | Admin | `tao_lich_su_ra_vao` | `tao_lich_su_ra_vao.html` | `smart_room.css` + inline + shared CSS | manual access log | C/B | old narrow form and tiny helper text | template + shared CSS | Done |
| `/smart-room/lich-su-ra-vao/<id>/` | `chi_tiet_lich_su_ra_vao` | Admin | `chi_tiet_lich_su_ra_vao` | `chi_tiet_lich_su_ra_vao.html` | `smart_room.css` + inline + shared CSS | access log detail | B | small details/status/action controls | template + shared CSS | Done |
| `/smart-room/lich-su-ra-vao/<id>/xu-ly/` | `xu_ly_lich_su_ra_vao` | Admin | `xu_ly_lich_su_ra_vao` | redirect/POST endpoint | existing forms | access log actions | D | endpoint only | none | Documented |

### 15.4 Implementation

- Added shared scoped stylesheet: `static/css/bill_smart_full_refresh.css`.
- The stylesheet is intentionally scoped to invoice/payment and Smart Room classes; it does not override global `button`, `table`, `form`, `h1`, or `h2`.
- It normalizes container width, padding, page headers, typography, table density, status badges, form controls, camera preview, and action touch targets.
- It fixes the tenant invoice 1440 overflow by forcing scoped billing/payment shells to `box-sizing:border-box`, `max-width:100%`, `overflow-x:clip`, and `min-width:0` on row/card children.
- It raises breadcrumb/action links to a minimum 44px touch target so visual QA no longer reports breadcrumb links as small buttons.
- Extended visual harnesses to include `1920x1080` in addition to existing `1440x900`, `1024x768`, `768x900`, and `390x844`.

### 15.5 Header Cause

- `/quan-ly-hoa-don/` did render the header DOM and template block correctly.
- The visible defect came from the page's inline invoice CSS and later sync blocks leaving multiple key labels/buttons/table cells at 8-12px, with the header visually reading as a large blank/low-information band on desktop.
- The fix is late-loaded scoped CSS after the inline blocks, so the real rendered content remains in place but uses the same readable scale as the stronger Foundation screens.

### 15.6 Files Changed In This Continuation

- `static/css/bill_smart_full_refresh.css`
- `templates/core/quan_ly_hoa_don.html`
- `templates/core/tao_hoa_don.html`
- `templates/core/chi_tiet_hoa_don.html`
- `templates/core/hoa_don_cua_toi.html`
- `templates/core/chi_tiet_hoa_don_cua_toi.html`
- `templates/core/thanh_toan_hoa_don_cua_toi.html`
- `templates/core/smart_room_dashboard.html`
- `templates/core/smart_access_control.html`
- `templates/core/quan_ly_nguoi_o_cung.html`
- `templates/core/tao_nguoi_o_cung.html`
- `templates/core/chi_tiet_nguoi_o_cung.html`
- `templates/core/quan_ly_face_profile.html`
- `templates/core/tao_face_profile.html`
- `templates/core/chi_tiet_face_profile.html`
- `templates/core/face_id_unavailable.html`
- `templates/core/xac_thuc_face_id.html`
- `templates/core/quan_ly_quyen_ra_vao.html`
- `templates/core/tao_quyen_ra_vao.html`
- `templates/core/chi_tiet_quyen_ra_vao.html`
- `templates/core/quan_ly_lich_su_ra_vao.html`
- `templates/core/tao_lich_su_ra_vao.html`
- `templates/core/chi_tiet_lich_su_ra_vao.html`
- `templates/core/lich_su_ra_vao.html`
- `core/tests/visual_invoice_stage02c.py`
- `core/tests/visual_module09_smart_room_audit.py`

### 15.7 Visual QA

- Invoice visual rerun outside sandbox: PASS `core.tests.visual_invoice_stage02c`, 1/1.
- Smart Room visual rerun outside sandbox: PASS `core.tests.visual_module09_smart_room_audit`, 2/2.
- Combined sandbox attempt still fails with `WinError 5` when Playwright tries to spawn a subprocess; outside-sandbox run is the authoritative visual run.
- Invoice screenshots/results: `luu_tru/kiem_thu/uiux_stage_02c_invoice/after/`, 26 files after adding 1920.
- Smart Room screenshots/results: `luu_tru/kiem_thu/module_09/visual_qa/` and `luu_tru/kiem_thu/module_09/camera_mock/`, 67 files after adding 1920.
- Visual matrix now covers `1920x1080`, `1440x900`, `1024x768`, `768x900`, and `390x844`.
- Total visual evidence after continuation: 93 files.

### 15.8 Final Verification

- `manage.py check`: PASS.
- `makemigrations --check --dry-run`: PASS, `No changes detected`.
- Targeted invoice/payment: PASS `27/27`.
- Targeted Smart Room/permission: PASS `40/40`.
- UI/Foundation + booking contract: PASS `9/9`.
- Full regression: PASS `311/311`.
- Live data after: `Phong=86; CoSo=4; NguoiThue=20; HopDong=6; HoaDon=6; LichSuThanhToan=3; QuyenRaVao=2; FaceProfile=7; LichSuRaVao=11`.
- Live data changed: NO.
- Migration created: NO.

### 15.9 Manual Blocker

- MANUAL BLOCKER remains: physical webcam + real human Face ID/YuNet/SFace end-to-end recognition was not tested in this environment.
