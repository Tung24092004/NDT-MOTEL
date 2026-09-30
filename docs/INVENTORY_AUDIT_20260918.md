# NDT_MOTEL - Bao cao kiem ke source

Ngay lap: 2026-09-18

Pham vi: kiem ke project Django tai `D:\NDT_MOTEL`. Chua xoa, chua sua logic nghiep vu, chua trien khai chuc nang moi.

## Backup

Da tao backup source truoc khi kiem ke:

- `backup_inventory_audit_20260918_163543`

Backup nay gom source/app chinh va tai lieu lien quan, khong copy `venv`, `media`, cac backup cu de tranh phinh du lieu.

## File chinh

| Nhom | File/thu muc | Vai tro |
|---|---|---|
| Django project | `manage.py`, `motel_management/settings.py`, `motel_management/urls.py`, `motel_management/asgi.py`, `motel_management/wsgi.py` | Khoi dong, cau hinh, URL goc |
| App nghiep vu | `core/models.py`, `core/views.py`, `core/views_chinh_sach.py`, `core/admin.py`, `core/tien_ich.py`, `core/quy_tac_nghiep_vu.py`, `core/bo_xu_ly_bo_cuc.py` | Model, view, admin, rule nghiep vu, helper |
| Template | `templates/core/*.html` | UI public, user, admin, smart room |
| Static | `static/css/style.css`, `static/css/tenant/*.css`, `static/js/tenant.js` | CSS/JS giao dien |
| Database dev | `db.sqlite3` | Du lieu local/dev |
| Migration/command | `core/migrations/*.py`, `core/management/commands/*.py` | Lich su schema va lenh dong bo/kiem tra |

## Model

Co 22 model trong `core/models.py`:

`CoSo`, `Phong`, `HinhAnhPhong`, `NguoiThue`, `DatPhong`, `HopDong`, `LichSuHopDong`, `YeuCauGhepNguoi`, `YeuCauGiaHanHopDong`, `HoaDon`, `LichSuThanhToan`, `YeuCauSuaChua`, `LichSuSuaChua`, `ChinhSachHoTro`, `ThongBao`, `LichSuThongBao`, `NguoiOCungPhong`, `FaceProfile`, `QuyenRaVao`, `LichSuRaVao`, `NhatKyThaoTac`, `LichSuTrangThai`.

## Bang chuc nang

| Nghiep vu | URL chinh | View xu ly | Template | Model lien quan | Quyen | Tinh trang |
|---|---|---|---|---|---|---|
| Trang chu/tim phong | `/`, `/phong/`, `/phong/<id>/` | `home`, `danh_sach_phong`, `chi_tiet_phong` | `home.html`, `danh_sach_phong.html`, `chi_tiet_phong.html` | `Phong`, `CoSo`, `HinhAnhPhong`, `HopDong` | Public/User/Admin | Dang dung |
| Dat phong | `/phong/<id>/dat/`, `/tai-khoan/dat-phong/<id>/huy/` | `dat_phong`, `huy_dat_phong_cua_toi` | `dat_phong.html`, `dat_phong_thanh_cong.html`, `tai_khoan.html` | `DatPhong`, `NguoiThue`, `Phong`, `ThongBao` | User | Dang dung |
| Tai khoan/xac thuc | `/dang-ky/`, `/dang-nhap/`, `/dang-xuat/`, `/tai-khoan/`, `/doi-mat-khau/`, `/cap-nhat-thong-tin/` | `dang_ky`, `dang_nhap`, `dang_xuat`, `tai_khoan`, `doi_mat_khau`, `cap_nhat_thong_tin` | `dang_ky.html`, `dang_nhap.html`, `tai_khoan.html`, `doi_mat_khau.html`, `cap_nhat_thong_tin.html` | `User`, `NguoiThue`, `DatPhong`, `HopDong`, `HoaDon` | User | Dang dung |
| Hop dong cua toi | `/hop-dong-cua-toi/`, `/hop-dong-cua-toi/<id>/`, `/hop-dong-cua-toi/<id>/gia-han/`, `/yeu-cau-gia-han/<id>/huy/`, `/hop-dong/<id>/xuat-pdf/` | `hop_dong_cua_toi`, `chi_tiet_hop_dong_cua_toi`, `gui_yeu_cau_gia_han`, `huy_yeu_cau_gia_han`, `xuat_hop_dong_pdf` | `hop_dong_cua_toi.html`, `chi_tiet_hop_dong_cua_toi.html` | `HopDong`, `YeuCauGiaHanHopDong`, `LichSuHopDong` | User | Dang dung |
| Hoa don cua toi | `/hoa-don-cua-toi/`, `/hoa-don-cua-toi/<id>/`, `/hoa-don-cua-toi/<id>/thanh-toan/` | `hoa_don_cua_toi`, `chi_tiet_hoa_don_cua_toi`, `thanh_toan_hoa_don_cua_toi` | `hoa_don_cua_toi.html`, `chi_tiet_hoa_don_cua_toi.html`, `thanh_toan_hoa_don_cua_toi.html` | `HoaDon`, `LichSuThanhToan`, `HopDong` | User | Dang dung |
| Thong bao cua toi | `/thong-bao-cua-toi/`, `/thong-bao-cua-toi/<id>/` | `thong_bao_cua_toi`, `chi_tiet_thong_bao_cua_toi` | `thong_bao_cua_toi.html`, `chi_tiet_thong_bao_cua_toi.html` | `ThongBao`, `LichSuThongBao` | User | Dang dung |
| Yeu cau sua chua cua toi | `/yeu-cau-sua-chua-cua-toi/`, `/yeu-cau-sua-chua-cua-toi/tao/`, `/yeu-cau-sua-chua-cua-toi/<id>/` | `yeu_cau_sua_chua_cua_toi`, `tao_yeu_cau_sua_chua`, `chi_tiet_yeu_cau_sua_chua_cua_toi` | `yeu_cau_sua_chua_cua_toi.html`, `tao_yeu_cau_sua_chua.html`, `chi_tiet_yeu_cau_sua_chua_cua_toi.html` | `YeuCauSuaChua`, `HopDong`, `Phong` | User | Dang dung |
| O ghep | `/phong/<id>/dang-ky-ghep/`, `/hop-dong/<id>/bat-tat-ghep/`, `/yeu-cau-ghep-cua-toi/`, `/yeu-cau-ghep/<id>/`, `/yeu-cau-ghep/<id>/xu-ly/` | `dang_ky_ghep_phong`, `bat_tat_cho_phep_ghep`, `yeu_cau_ghep_cua_toi`, `chi_tiet_yeu_cau_ghep`, `xu_ly_yeu_cau_ghep` | `dang_ky_ghep_phong.html`, `yeu_cau_ghep_cua_toi.html`, `chi_tiet_yeu_cau_ghep.html` | `YeuCauGhepNguoi`, `HopDong`, `NguoiOCungPhong`, `QuyenRaVao`, `ThongBao` | User/Admin tuy hanh dong | Dang dung |
| Chinh sach ho tro public | `/chinh-sach-ho-tro/` | `views_chinh_sach.chinh_sach_ho_tro` | `chinh_sach_ho_tro.html` | `ChinhSachHoTro` | Public/User | Dang dung |
| Dashboard admin | `/dashboard-admin/` | `dashboard_admin` | `dashboard_admin.html` | Tong hop nhieu model | Admin | Dang dung |
| Nhat ky thao tac | `/nhat-ky-thao-tac/`, `/nhat-ky-thao-tac/<id>/` | `nhat_ky_thao_tac`, `chi_tiet_nhat_ky_thao_tac` | `nhat_ky_thao_tac.html`, `chi_tiet_nhat_ky_thao_tac.html` | `NhatKyThaoTac` | Admin | Dang dung |
| Quan ly phong | `/quan-ly-phong/`, `/quan-ly-phong/tao/`, `/quan-ly-phong/<id>/sua/`, `/quan-ly-phong/<id>/xoa/` | `quan_ly_phong`, `tao_phong`, `sua_phong`, `xoa_phong` | `quan_ly_phong.html`, `tao_phong.html`, `sua_phong.html` | `Phong`, `CoSo`, `HinhAnhPhong` | Admin | Dang dung |
| Quan ly dat phong | `/quan-ly-dat-phong/`, `/quan-ly-dat-phong/<id>/`, `/quan-ly-dat-phong/<id>/xu-ly/`, `/quan-ly-dat-phong/<dat_phong_id>/tao-hop-dong/` | `quan_ly_dat_phong`, `chi_tiet_dat_phong`, `xu_ly_dat_phong`, `tao_hop_dong` | `quan_ly_dat_phong.html`, `chi_tiet_dat_phong.html`, `tao_hop_dong.html` | `DatPhong`, `Phong`, `NguoiThue`, `HopDong` | Admin | Dang dung |
| Quan ly hop dong | `/quan-ly-hop-dong/`, `/quan-ly-hop-dong/<id>/`, `/quan-ly-hop-dong/<id>/sua/`, `/quan-ly-hop-dong/<id>/xu-ly/`, `/quan-ly-hop-dong/yeu-cau-gia-han/<id>/xu-ly/` | `quan_ly_hop_dong`, `chi_tiet_hop_dong`, `sua_hop_dong`, `xu_ly_hop_dong`, `xu_ly_yeu_cau_gia_han` | `quan_ly_hop_dong.html`, `chi_tiet_hop_dong.html`, `sua_hop_dong.html` | `HopDong`, `LichSuHopDong`, `YeuCauGiaHanHopDong`, `QuyenRaVao` | Admin | Dang dung |
| Quan ly hoa don | `/quan-ly-hoa-don/`, `/quan-ly-hoa-don/tao/`, `/quan-ly-hoa-don/<id>/`, `/quan-ly-hoa-don/<id>/xu-ly/` | `quan_ly_hoa_don`, `tao_hoa_don`, `chi_tiet_hoa_don`, `xu_ly_hoa_don` | `quan_ly_hoa_don.html`, `tao_hoa_don.html`, `chi_tiet_hoa_don.html` | `HoaDon`, `HopDong`, `LichSuThanhToan` | Admin | Dang dung |
| Quan ly sua chua | `/quan-ly-sua-chua/`, `/quan-ly-sua-chua/<id>/`, `/quan-ly-sua-chua/<id>/xu-ly/`, `/tao-sua-chua/` | `quan_ly_sua_chua`, `chi_tiet_sua_chua`, `xu_ly_sua_chua`, `tao_sua_chua` | `quan_ly_sua_chua.html`, `chi_tiet_sua_chua.html`, `tao_sua_chua.html` | `YeuCauSuaChua`, `LichSuSuaChua`, `Phong`, `NguoiThue` | Admin | Dang dung |
| Quan ly chinh sach | `/quan-ly-chinh-sach/`, `/quan-ly-chinh-sach/tao/`, `/quan-ly-chinh-sach/<id>/`, `/quan-ly-chinh-sach/<id>/xu-ly/` | `quan_ly_chinh_sach`, `tao_chinh_sach`, `chi_tiet_chinh_sach`, `xu_ly_chinh_sach` | `quan_ly_chinh_sach.html`, `tao_chinh_sach.html`, `chi_tiet_chinh_sach.html` | `ChinhSachHoTro` | Admin | Dang dung |
| Quan ly thong bao | `/quan-ly-thong-bao/`, `/quan-ly-thong-bao/tao/`, `/quan-ly-thong-bao/<id>/`, `/quan-ly-thong-bao/<id>/xu-ly/` | `quan_ly_thong_bao`, `tao_thong_bao`, `chi_tiet_thong_bao`, `xu_ly_thong_bao` | `quan_ly_thong_bao.html`, `tao_thong_bao.html`, `chi_tiet_thong_bao.html` | `ThongBao`, `LichSuThongBao`, `NguoiThue`, `User` | Admin | Dang dung |
| Quan ly co so | `/quan-ly-co-so/`, `/quan-ly-co-so/tao/`, `/quan-ly-co-so/<id>/`, `/quan-ly-co-so/<id>/xu-ly/` | `quan_ly_co_so`, `tao_co_so`, `chi_tiet_co_so`, `xu_ly_co_so` | `quan_ly_co_so.html`, `tao_co_so.html`, `chi_tiet_co_so.html` | `CoSo`, `Phong` | Admin | Dang dung |
| Smart Room dashboard | `/smart-room/`, `/smart-room/access-control/` | `smart_room_dashboard`, `smart_access_control` | `smart_room_dashboard.html`, `smart_access_control.html` | `Phong`, `HopDong`, `FaceProfile`, `QuyenRaVao`, `LichSuRaVao` | Admin | Dang dung |
| Smart Room nguoi o cung | `/smart-room/nguoi-o-cung/`, `/smart-room/nguoi-o-cung/tao/`, `/smart-room/nguoi-o-cung/<id>/`, `/smart-room/nguoi-o-cung/<id>/xu-ly/` | `quan_ly_nguoi_o_cung`, `tao_nguoi_o_cung`, `chi_tiet_nguoi_o_cung`, `xu_ly_nguoi_o_cung` | `quan_ly_nguoi_o_cung.html`, `tao_nguoi_o_cung.html`, `chi_tiet_nguoi_o_cung.html` | `NguoiOCungPhong`, `HopDong`, `QuyenRaVao`, `FaceProfile` | Admin | Dang dung |
| Smart Room Face ID/Profile | `/smart-room/face-profile/`, `/smart-room/face-profile/tao/`, `/smart-room/face-profile/<id>/`, `/smart-room/face-profile/<id>/xu-ly/`, `/smart-room/face-profile/<id>/dang-ky/`, `/smart-room/face-id/`, `/smart-room/face-id/xac-thuc/`, `/tai-khoan/nhan-dien-su-dung-phong/` | `quan_ly_face_profile`, `tao_face_profile`, `chi_tiet_face_profile`, `xu_ly_face_profile`, `face_id_dang_ky`, `trang_xac_thuc_face_id`, `face_id_xac_thuc`, `nhan_dien_su_dung_phong` | `quan_ly_face_profile.html`, `tao_face_profile.html`, `chi_tiet_face_profile.html`, `xac_thuc_face_id.html` | `FaceProfile`, `QuyenRaVao`, `LichSuRaVao`, `NguoiThue`, `NguoiOCungPhong` | Admin/User tuy man hinh | Dang dung |
| Smart Room quyen ra vao | `/smart-room/quyen-ra-vao/`, `/smart-room/quyen-ra-vao/tao/`, `/smart-room/quyen-ra-vao/<id>/`, `/smart-room/quyen-ra-vao/<id>/xu-ly/` | `quan_ly_quyen_ra_vao`, `tao_quyen_ra_vao`, `chi_tiet_quyen_ra_vao`, `xu_ly_quyen_ra_vao` | `quan_ly_quyen_ra_vao.html`, `tao_quyen_ra_vao.html`, `chi_tiet_quyen_ra_vao.html` | `QuyenRaVao`, `HopDong`, `Phong`, `FaceProfile` | Admin | Dang dung |
| Smart Room lich su ra vao | `/smart-room/lich-su-ra-vao/`, `/smart-room/lich-su-ra-vao/tao/`, `/smart-room/lich-su-ra-vao/<id>/`, `/smart-room/lich-su-ra-vao/<id>/xu-ly/` | `quan_ly_lich_su_ra_vao`, `tao_lich_su_ra_vao`, `chi_tiet_lich_su_ra_vao`, `xu_ly_lich_su_ra_vao` | `quan_ly_lich_su_ra_vao.html`, `tao_lich_su_ra_vao.html`, `chi_tiet_lich_su_ra_vao.html` | `LichSuRaVao`, `QuyenRaVao`, `Phong` | Admin | Dang dung |
| Django Admin | `/admin/` | `admin.site.urls` | Django admin templates | Model da register trong `core/admin.py` | Staff/Superuser | Dang dung |

## Kiem ke URL

Tong cong 89 `path(...)` trong `motel_management/urls.py`, bao gom `/admin/` va 88 route ung dung. Nhom URL chinh da duoc liet ke trong bang chuc nang. Khi `DEBUG=True`, Django con phuc vu media qua `settings.MEDIA_URL`.

## Template

Co 70 template trong `templates/core`.

Dang render truc tiep hoac duoc code tham chieu: 66 template nghiep vu.

Template layout khong render truc tiep nhung dang dung:

- `templates/core/base.html`
- `templates/core/tenant_base.html`

Template nghi khong con duoc URL su dung:

- `templates/core/lich_su_ra_vao.html`: khong co view render; route hien tai dung `quan_ly_lich_su_ra_vao.html`, `chi_tiet_lich_su_ra_vao.html`, `tao_lich_su_ra_vao.html`.
- `templates/core/hop_dong_pdf.html`: khong thay view render template; `xuat_hop_dong_pdf` dang tao PDF bang ReportLab.

Khong phat hien template bi code render nhung thieu file.

## CSS/JavaScript

Dang dung:

- `static/css/style.css`: nap tu `templates/core/base.html`.
- `static/css/tenant/components.css`: nap tu `templates/core/tenant_base.html`.
- `static/js/tenant.js`: nap tu `templates/core/tenant_base.html`.
- Cac file `static/css/tenant/*.css` duoc nap theo tung template user/tenant: `dang_nhap`, `dang_ky`, `dat_phong`, `hoa_don_cua_toi`, `hop_dong_cua_toi`, `thong_bao_cua_toi`, `yeu_cau_ghep_cua_toi`, `yeu_cau_sua_chua_cua_toi`, `chi_tiet_*`, `tai_khoan`, `doi_mat_khau`, `cap_nhat_thong_tin`, `thanh_toan_hoa_don_cua_toi`.

CSS/JS khong thay reference truc tiep:

- Chua thay file JS nao khac ngoai `tenant.js`.
- Cac style admin/smart room dang nam inline trong template hoac qua `style.css`, khong co CSS rieng trong `static/css/tenant`.

## Code trung ten / trung logic

Ket qua quet function trong `core/*.py`:

- Khong co trung ten view cap module cho `tao_thong_bao()`, `xu_ly_thong_bao()`, `chi_tiet_yeu_cau_ghep()`.
- Khong co view Smart Room bi khai bao lap ten.
- Cac ten trung hop le/do pham vi class-test: `__str__`, `clean`, `save`, `setUp`, `payload`.
- `render_form` xuat hien nhieu lan la nested helper ben trong cac view form, khong phai view bi trung ten.

Vi tri cac ham can chu y:

- `tao_thong_bao`: `core/views.py:12065`
- `xu_ly_thong_bao`: `core/views.py:12201`
- `chi_tiet_yeu_cau_ghep`: `core/views.py:14454`
- Cum Smart Room: `core/views.py:15017` den gan cuoi file.

Nhan xet: tuy khong trung ten, `core/views.py` qua lon, gom ca public/user/admin/smart room/face id/PDF. Trung logic co kha nang nam o validation, redirect, tao thong bao, ghi lich su, cap quyen ra vao, nhung can tach co test bao ve truoc.

## File co the loai khoi ban nop

Nen loai khoi ban nop neu yeu cau nop source sach:

- `venv/`
- `__pycache__/`, `core/**/__pycache__/`, `motel_management/**/__pycache__/`
- Cac thu muc backup cu: `backup_*`
- `legacy_archive/`
- `artifacts/`
- `face_test/`
- `media/` neu khong can nop du lieu upload/demo
- `models/*.onnx` neu bai nop khong yeu cau chay Face ID offline; neu co demo Face ID thi giu lai
- `luu_tru/ban_sao_luu/before_0020_20260916_125505.sql` neu khong can nop snapshot database
- `test_camera.py`, `test_face_id.py` neu chi nop web app, khong nop demo camera rieng

## File test

Dang co:

- `core/tests.py`
- `core/test_business_hardening.py`
- `core/test_contract_lifecycle.py`
- `core/test_phase8b2_routes.py`
- `core/test_phase8b3_admin_detail_ui.py`
- `core/test_phase8b4_admin_form_ui.py`
- `core/test_phase8b5_tenant_ui.py`
- `core/test_tenant_ui.py`
- `test_camera.py`
- `test_face_id.py`

Nen giu cac test trong `core/` neu tiep tuc refactor. Hai file test camera/face id o root can xac minh lai muc dich nop bai.

## File chua chac chan thi giu lai

- `db.sqlite3`: giu neu project can du lieu demo khi cham/nop.
- `media/`: giu neu demo can anh phong/face profile da upload.
- `models/*.onnx`: giu neu chuc nang Face ID/camera nam trong yeu cau demo.
- `tools/*.py`: giu neu quy trinh audit/migrate/UI demo con dung.
- `docs/*.md`: giu neu can lich su audit/giai trinh tien do.
- `run_dong_bo_hop_dong.bat`: giu neu demo can lenh dong bo hop dong nhanh.
- `3_module_template.txt`, `hoa_don_template.txt`: chua ro con dung de tham khao/noi dung mau; neu nop source gon co the loai, nhung nen giu den khi xac nhan.

## Rui ro neu tach `views.py`

- URL import truc tiep rat nhieu view tu `core.views`; tach file se phai sua import trong `motel_management/urls.py` va co nguy co sai ten route.
- Nhieu helper dang nam trong `views.py` va duoc nhieu view goi: `la_admin`, `cap_nhat_trang_thai_hop_dong`, `cap_nhat_trang_thai_phong_theo_hop_dong`, cac helper sua chua, helper Face ID/Smart Room. Tach sai module de gay circular import.
- Face ID phu thuoc `cv2`, `numpy`, file ONNX va xu ly base64; tach khong kheo de loi runtime hoac cham import server.
- Cac luong nghiep vu tao thong bao/ghi lich su/cap quyen ra vao rai trong nhieu view; tach ma khong co test regression de tao thong bao trung, sai trang thai phong/hop dong, sai quyen ra vao.
- Nhieu template form dung nested helper `render_form`; tach can giu context va message flow y het.
- PDF hop dong dung ReportLab truc tiep, khong qua template; tach can giu font/response header.
- Khong co git repo tai `D:\NDT_MOTEL`, nen nen backup thu muc truoc moi buoc refactor va chay test sau tung cum.

## Ket luan ngan

Chinh sach hien tai: test nam trong `core/tests/`, fixture trong `core/du_lieu_test/`. `manage.py test` tat ghi bytecode. `CleanTestRunner` luu media test trong thu muc tam ngoai project va tu xoa khi ket thuc. Khong ghi screenshot/HTML/JSON/log audit vao source. Mac dinh khong dung `--keepdb` de Django xoa database test sau moi lan chay. Audit mot lan chay ngoai project va tu don output. Khong tao backup moi cho moi luot sua; giu toi da mot backup source sach.

Moi truong local duoc chuyen sang `D:\NDT_MOTEL_ENV`; dung `D:\NDT_MOTEL_ENV\Scripts\python.exe -B manage.py runserver` va `python.exe -m pip` (launcher pip cu co the giu duong dan truoc khi di chuyen). `requirements.txt` ghi package hien tai. Tao lai bang `python -m venv venv`, sau do `venv\Scripts\python.exe -m pip install -r requirements.txt`. Khong dua venv vao ban nop.

Source chinh de nop/chay nam o `manage.py`, `motel_management/`, `core/`, `templates/`, `static/`, kem `db.sqlite3/media/models` tuy yeu cau demo. Phan co the loai khoi ban nop la `venv`, `__pycache__`, backup cu, `legacy_archive`, `artifacts`, va cac file demo/test camera neu khong bat buoc. Hien tai chua nen xoa `hop_dong_pdf.html`, `lich_su_ra_vao.html`, `models/*.onnx`, `media/`, `tools/` cho den khi chot tieu chi nop bai/demo.
