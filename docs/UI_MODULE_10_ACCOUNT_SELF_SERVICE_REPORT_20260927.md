# UI Module 10 - Account Self-Service

Ngày: 2026-09-27

Trạng thái: **PASS**

## Phạm vi

- Tenant account hub: `/tai-khoan/`, template `templates/core/tai_khoan.html`.
- Tenant profile update: `/tai-khoan/cap-nhat/`, template `templates/core/cap_nhat_thong_tin.html`.
- Password change: `/tai-khoan/doi-mat-khau/` and admin route `/doi-mat-khau/`, shared template `templates/core/doi_mat_khau.html`.

Không thay đổi các màn đã thuộc Module 02, 04, 05, 06, 07 và 09. Không thay đổi auth public, validation, session handling, model, URL hoặc workflow.

## Backup

Backup trước sửa:

`luu_tru/ban_sao_luu/before_module10_account_ui_20260927_180956`

Nội dung gồm 7 file: 3 template, 3 CSS tenant và `core/views_tai_khoan.py`.

## Thay đổi

- Ba template Module 10 đã opt-in foundation bằng `tokens.css`, `typography.css`, `components.css`, `utilities.css`.
- `tai_khoan.html` dùng PageHeader, surface/card, button, badge và empty-state foundation; giữ nguyên các URL dịch vụ, trạng thái đặt phòng, form hủy đặt phòng và dữ liệu context.
- `cap_nhat_thong_tin.html` dùng form contract `ndt-field`, `ndt-label`, `ndt-control`, `ndt-required` và action button foundation.
- `doi_mat_khau.html` dùng card/form/button foundation cho cả tenant và admin. Giữ DOM contract cũ `<h1>Đổi mật khẩu</h1>` để không phá test hiện hữu.
- CSS của ba màn được thu gọn còn layout đặc thù của Module 10; không còn hệ button/form/card riêng trùng foundation.

## Gate

- `manage.py check`: PASS, 0 issue.
- `makemigrations --check --dry-run`: PASS, `No changes detected`.
- Focused route/UI/permission tests: PASS `57/57`.
- Full suite: PASS `311/311`.
- Live Django client render audit with `HTTP_HOST=localhost`: PASS.
  - Tenant `/tai-khoan/`: 200, foundation assets present, `ndt-foundation` present.
  - Tenant `/tai-khoan/cap-nhat/`: 200, foundation assets present, `ndt-foundation` present.
  - Tenant `/tai-khoan/doi-mat-khau/`: 200, foundation assets present, `ndt-foundation` present.
  - Admin `/doi-mat-khau/`: 200, foundation assets present, `ndt-foundation` present.

## Files modified

- `templates/core/tai_khoan.html`
- `templates/core/cap_nhat_thong_tin.html`
- `templates/core/doi_mat_khau.html`
- `static/css/tenant/tai_khoan.css`
- `static/css/tenant/cap_nhat_thong_tin.css`
- `static/css/tenant/doi_mat_khau.css`

## Database

NONE

## Module 09 note

Module 09 conclusion is unchanged: automated and mock-camera gates pass, but physical webcam/person recognition remains a manual blocker and is not treated as complete by Module 10.
