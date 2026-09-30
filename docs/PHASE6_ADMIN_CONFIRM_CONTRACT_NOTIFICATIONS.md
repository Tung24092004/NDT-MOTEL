# Phase 6 - Admin confirm deposit, contract and notifications

## Final pre-demo verification

- Invoice settlement was rechecked alongside the Phase 6 deposit workflow.
- Admin can mark an invoice paid only after the tenant report has placed that exact invoice in `cho_xac_nhan`.
- An unpaid or overdue invoice cannot be settled directly from the Admin URL, and the Admin detail page does not expose the confirmation control for those states.
- This hardening does not change deposit confirmation, contract creation, notification deduplication or Smart Room data.

Date: 2026-09-18. Scope: Admin booking reconciliation, atomic contract creation,
contract document download, global toast and role-scoped notification inbox.

## Backup

- Existing pre-edit backup found: `backup_phase6_admin_confirm_contract_notifications_20260918_200425`.
- Continuation source backup created after this work:
  `backup_phase6_admin_confirm_contract_notifications_continued_20260918_202200_clean`.
- Closeout source backup created after the final Phase 6 checks:
  `backup_phase6_closeout_20260918_202910_clean`.
- Active database is MariaDB/MySQL `ndt_motel`; no schema migration was added in this continuation.
- MySQL dump for this continuation was not created because `mysqldump` is not available in PATH.
- Workspace is not a git repository, so status/diff is based on file inspection and tests.

## Routes and modules

New/active modules:

- `core/views_quan_tri_dat_phong.py`: Admin booking list, detail and POST actions.
- `core/dich_vu/hop_dong.py`: deposit confirmation, contract creation and rejection state machine.
- `core/dich_vu/thong_bao_quan_tri.py`: Admin business notification wrapper.
- `core/views_thong_bao.py`: Admin inbox, read actions and polling endpoints.
- `templates/core/components/toast_container.html`, `static/css/components/toast.css`,
  `static/js/components/toast.js`: global flash/business toast.

Routes:

- `/quan-ly-dat-phong/` -> `quan_ly_dat_phong`
- `/quan-ly-dat-phong/<id>/` -> `chi_tiet_dat_phong`
- `/quan-ly-dat-phong/<id>/xac-nhan-va-tao-hop-dong/`
  -> `xac_nhan_dat_phong_va_tao_hop_dong`
- `/quan-ly-dat-phong/<id>/tu-choi-coc/` -> `tu_choi_thanh_toan_coc`
- `/quan-ly-dat-phong/<id>/tu-choi-yeu-cau/` -> `tu_choi_yeu_cau_dat_phong`
- `/thong-bao-admin/`, `/thong-bao-admin/<id>/`,
  `/thong-bao-admin/<id>/doc/`, `/thong-bao-admin/doc-tat-ca/`
- `/thong-bao-admin/kiem-tra-moi/`
- `/thong-bao-cua-toi/kiem-tra-moi/`

The old `tao_hop_dong` route remains for legacy/manual support, but the normal
Phase 6 flow uses the Admin confirmation endpoint above.

## State Transition

Admin can confirm only when:

- `DatPhong.trang_thai` is `cho_duyet` or `da_duyet`.
- There is one active `ThanhToanCocDatPhong` with `trang_thai="cho_xac_nhan"`.
- Deposit amount equals `DatPhong.tien_coc_du_kien`.
- The booking has accepted terms, rent/deposit snapshots, rental duration and valid capacity.
- No `HopDong` already exists for the booking.
- The room/facility is still available and no overlapping contract exists.

Rejecting a deposit requires a reason, updates only the active pending deposit
to `tu_choi`, does not create a contract and does not cancel/refund the booking.
Rejecting the booking requires a reason, refuses only eligible bookings without
a contract and leaves refund/accounting for a later workflow.

## Transaction

`confirm_deposit_and_create_contract()` runs under `transaction.atomic()` and:

1. Checks Admin role.
2. Locks `DatPhong`.
3. Checks idempotency by existing `HopDong`.
4. Validates booking state and snapshots.
5. Locks room and active deposit.
6. Confirms the deposit.
7. Moves booking to `da_duyet`.
8. Creates `HopDong` from booking snapshots, not POST data.
9. Marks declared companions as `da_xac_minh` only in the booking declaration table.
10. Creates `LichSuHopDong`, User notification, Admin notification and `NhatKyThaoTac`.
11. Synchronizes room status.

Double submit returns the existing contract and does not create a second contract
or duplicate User/Admin business notification.

## DatPhong To HopDong Mapping

- `ngay_bat_dau` <- `DatPhong.ngay_nhan_phong`
- `ngay_ket_thuc` <- `DatPhong.ngay_tra_du_kien`
- `tien_coc` <- `DatPhong.tien_coc_du_kien`
- `tien_thue_thang` <- `DatPhong.gia_thue_thang_tai_thoi_diem_dat`
- `phuong_thuc_thanh_toan` <- confirmed deposit method
- `so_nguoi_o` <- `DatPhong.so_nguoi_o`
- `cho_phep_ghep` <- `DatPhong.dong_y_nhan_yeu_cau_ghep`
- `dieu_khoan` <- `DatPhong.noi_dung_dieu_khoan_snapshot`
- `ghi_chu` records booking/deposit references.

Declared companions are shown in contract detail/PDF, but are not converted into
`NguoiOCungPhong`, FaceProfile or active access permissions in this phase.

## PDF

The existing ReportLab PDF endpoint is kept. It now loads declared companions
from `DatPhong.nguoi_di_cung_khai_bao` and includes them in a repeatable table.
Admin can download any contract; a tenant can download only their own contract.
Filename remains `HopDong_<so_hop_dong>.pdf`.

## Toast And Notifications

Flash messages use Django messages and render through one shared toast container
included in `base.html`.

Business notifications are stored in `ThongBao`:

- User notifications use `nguoi_thue`.
- Admin notifications use `nguoi_nhan_user` per Admin account.
- Polling returns unread count plus up to five latest unread items.
- Polling/toast display does not mark notifications as read.
- Read endpoints are POST-only and scoped to the current recipient.

Admin bell links now point to `thong_bao_admin`; the service menu still keeps
`quan_ly_thong_bao` for composing/managing broadcast notifications.

## Tests

Phase 6 tests:

- `core.test_phase6_admin_booking_contract`
- `core.test_phase6_notifications_toasts`
- `core.test_phase6_contract_pdf`
- `tools.audit.phase6_closeout_browser_audit` is a manual closeout browser audit module,
  not a `test_*.py` module; it is run explicitly when browser subprocesses are allowed.

Current focused results:

- `python -B ...` is not available from PATH in this shell; commands were run with
  `.\venv\Scripts\python.exe -B ...`.
- `manage.py check`: pass, 0 issues.
- `manage.py makemigrations --check --dry-run`: pass, no changes detected.
- Phase 6 focused tests: 14 passed.
- Full `manage.py test core -v 2`: 249 passed.
- Browser/Playwright closeout audit was attempted against a Django test database,
  but skipped because Windows blocked the Playwright subprocess with
  `WinError 5 Access is denied`. No production data was submitted or mutated.

Additional closeout assertions added:

- Admin business notifications for contract creation, deposit rejection and booking
  rejection are per-admin, deduplicated and carry the Admin detail link.
- Empty Admin polling returns `{"so_chua_doc": 0, "items": []}` safely.
- Confirming a Phase 6 booking does not create `NguoiOCungPhong`, `FaceProfile`
  or `QuyenRaVao`.

## Files Changed In This Continuation

- `core/dich_vu/thong_bao_quan_tri.py`
- `core/dich_vu/thong_bao_dat_phong.py`
- `core/dich_vu/hop_dong.py`
- `core/views.py`
- `tools/audit/phase6_closeout_browser_audit.py`
- `templates/core/base.html`
- `templates/core/chi_tiet_hop_dong.html`
- `core/test_phase6_admin_booking_contract.py`
- `core/test_phase6_notifications_toasts.py`
- `core/test_phase6_contract_pdf.py`
- this document.

## Deferred

- No roommate two-step official resident conversion.
- No shared-room workflow changes.
- No Face ID verification or access permission creation.
- No automatic refund.
- No WebSocket or new frontend framework.
