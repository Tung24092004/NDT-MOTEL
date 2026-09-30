# UI Phase 1 P0 Report - 2026-09-26

BACKUP SOURCE: `luu_tru/ban_sao_luu/backup_before_ui_phase1_20260926_233247`

BACKUP DATABASE: `luu_tru/ban_sao_luu/backup_before_ui_phase1.sql`

BACKUP VERIFIED: YES. Source snapshot has 432 files; SQL dump is 186,692 bytes.

CHECKPOINT RESUMED: YES

RUNTIME CHANGES FOUND BEFORE RESUME: NONE. Current runtime source matched backup snapshot before edits. Current folder is not a Git repository.

BASELINE SCREENSHOT:
- desktop: `luu_tru/kiem_thu/giai_doan_1/ui_phase1_baseline/*_1440x900.png`
- laptop: `luu_tru/kiem_thu/giai_doan_1/ui_phase1_baseline/*_1024x768.png`
- mobile: `luu_tru/kiem_thu/giai_doan_1/ui_phase1_baseline/*_390x844.png`

ENCODING:
- issues: mojibake in audited templates plus verified user-facing create/edit templates.
- files fixed: `sua_hop_dong.html`, `tao_nguoi_o_cung.html`, `tao_face_profile.html`, `tao_quyen_ra_vao.html`, `tao_thong_bao.html`, `tao_phong.html`, `tao_hoa_don.html`, `sua_phong.html`, `tao_chinh_sach.html`, `tao_lich_su_ra_vao.html`, `static/css/style.css`.
- before/after: examples fixed from `Báº¡n cÃ³ cháº¯c...` to `Bạn có chắc...`, `ThÃªm ngÆ°á»i á»Ÿ cÃ¹ng` to `Thêm người ở cùng`, `ÄANG TRá»NG` to `ĐANG TRỐNG`.
- remaining scan: only CSS comments in `static/css/style.css` still contain mojibake markers.

RAW STATUS:
- statuses: companion verification (`cho_xac_minh`, `da_xac_minh`) and deposit status (`chua_thanh_toan`, `cho_xac_nhan`, `da_xac_nhan`, `tu_choi`, `da_huy`, `da_hoan_tien`).
- files fixed: `core/templatetags/bo_loc.py`, `templates/core/tenant/booking/detail.html`, `templates/core/chi_tiet_dat_phong.html`, `templates/core/chi_tiet_hop_dong.html`, `core/views_hop_dong.py`.
- DB values changed: NO

TYPOGRAPHY:
- P0 cases: admin booking/room/contract/invoice list table text and metadata at 8-10px.
- fixed: page-local CSS overrides lift table/header/badge/action/meta text to 12-14px and action targets to about 36px minimum.
- files: `quan_ly_dat_phong.html`, `quan_ly_phong.html`, `quan_ly_hop_dong.html`, `quan_ly_hoa_don.html`.

RESPONSIVE TABLE:
- audited: admin booking, room, contract and invoice list tables.
- fixed: preserved existing horizontal scroll wrappers; added `-webkit-overflow-scrolling: touch` and avoided table-to-card conversion.

CONFIRM:
- total: remaining inventory still uses browser confirms; Phase 1 did not replace the dialog system.
- high risk: booking approve/reject/cancel, contract state changes, invoice cancellation, delete/revoke actions.
- replaced: 0

ALERT:
- total: remaining alert inventory still exists; Phase 1 did not replace the dialog system.
- replaced: 0

TOUCH TARGET:
- issues: tiny admin row actions and pagination controls.
- fixed: list action buttons/page buttons in the touched admin pages now have larger minimum heights.

GALLERY:
- card images: 86
- detail images: 86
- mismatch: 0
- consistency: CARD = DETAIL MAIN = BOOKING/DISPLAY COVER 86/86
- tests: 13/13 assertions passed; command exits nonzero during temp directory cleanup on Windows `PermissionError`.

DATA:
- Phong before/after: 86 / 86
- Booking before/after: 10 / 10
- Contract before/after: 6 / 6
- Payment history before/after: 3 / 3
- Deposit transaction before/after: 0 / 0
- Tenant before/after: 20 / 20

CHECK: `D:\NDT_MOTEL_ENV\Scripts\python.exe manage.py check` passed.

TEST: `D:\NDT_MOTEL_ENV\Scripts\python.exe manage.py test core.tests.test_gallery_phong` ran 13 tests OK, then failed cleanup with Windows `PermissionError` deleting `ndt-motel-tests-*`.

MAKEMIGRATIONS: `D:\NDT_MOTEL_ENV\Scripts\python.exe manage.py makemigrations --check --dry-run` passed with `No changes detected`.

DESKTOP QA: Baseline screenshots verified present. Post-change browser screenshot run was not executed in this pass.

TABLET QA: Baseline 1024 screenshots verified present. Post-change browser screenshot run was not executed in this pass.

MOBILE QA: Baseline 390 screenshots verified present. Post-change browser screenshot run was not executed in this pass.

RUNTIME FILES MODIFIED:
- `core/templatetags/bo_loc.py`
- `core/views_hop_dong.py`
- `static/css/style.css`
- `templates/core/chi_tiet_dat_phong.html`
- `templates/core/chi_tiet_hop_dong.html`
- `templates/core/quan_ly_dat_phong.html`
- `templates/core/quan_ly_hoa_don.html`
- `templates/core/quan_ly_hop_dong.html`
- `templates/core/quan_ly_phong.html`
- `templates/core/sua_hop_dong.html`
- `templates/core/sua_phong.html`
- `templates/core/tao_chinh_sach.html`
- `templates/core/tao_face_profile.html`
- `templates/core/tao_hoa_don.html`
- `templates/core/tao_lich_su_ra_vao.html`
- `templates/core/tao_nguoi_o_cung.html`
- `templates/core/tao_phong.html`
- `templates/core/tao_quyen_ra_vao.html`
- `templates/core/tao_thong_bao.html`
- `templates/core/tenant/booking/detail.html`

DATABASE CHANGES: NONE

MIGRATION: NONE

WORKFLOW CHANGE: NONE

FOUNDATION PLAN: `docs/UI_FOUNDATION_IMPLEMENTATION_PLAN_20260926.md`

RỦI RO CÒN LẠI:
- Browser confirm/alert system remains for Phase 3.
- Some CSS comments still contain mojibake but do not render.
- Post-change visual browser screenshots were not rerun.
- Test runner cleanup has a Windows permission issue after successful gallery assertions.
