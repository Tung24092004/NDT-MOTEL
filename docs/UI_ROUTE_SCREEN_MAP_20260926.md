# UI Route And Screen Map

Ngay audit: 2026-09-26. Tai lieu nay chi mo ta hien trang, khong thay doi route hay runtime.

## Tong quan resolver

| Nhom | So luong | Ghi chu |
|---|---:|---|
| Tat ca route | 256 | Bao gom Django admin va media development route |
| Route ung dung tuy bien | 106 | Public, tenant, admin nghiep vu va Smart Room |
| Django admin tu sinh | 149 | Khong phai custom UI cua project |
| Media development route | 1 | `^media/...` |
| Ten route trung | 0 | Khong phat hien qua Django resolver |

## Public va xac thuc

| URL | Ten route | View | Man hinh / hanh vi | Trang thai |
|---|---|---|---|---|
| `/` | `home` | `views_quan_tri.home` | Trang chu | ACTIVE |
| `/phong/` | `danh_sach_phong` | `views_phong.danh_sach_phong` | Danh sach phong | ACTIVE |
| `/phong/<id>/` | `chi_tiet_phong` | `views_phong.chi_tiet_phong` | Chi tiet phong | ACTIVE |
| `/phong/<id>/dat/` | `dat_phong` | `views_dat_phong.dat_phong` | Booking wizard | ACTIVE |
| `/phong/<id>/dang-ky-ghep/` | `dang_ky_ghep_phong` | `views_o_ghep.dang_ky_ghep_phong` | Dang ky o ghep | ACTIVE |
| `/dang-ky/` | `dang_ky` | `views_dang_nhap.dang_ky` | Dang ky tai khoan | ACTIVE |
| `/dang-nhap/` | `dang_nhap` | `views_dang_nhap.dang_nhap` | Dang nhap | ACTIVE |
| `/dang-xuat/` | `dang_xuat` | `views_dang_nhap.dang_xuat` | Hanh dong dang xuat | ACTIVE |
| `/chinh-sach-ho-tro/` | `chinh_sach_ho_tro` | `views_chinh_sach.chinh_sach_ho_tro` | Chinh sach cong khai | ACTIVE |

## Tenant portal

| URL / nhom URL | View module | Man hinh | Vai tro |
|---|---|---|---|
| `/tai-khoan/` | `views_tai_khoan` | Tong quan tai khoan | Tenant |
| `/tai-khoan/cap-nhat/`, `/tai-khoan/doi-mat-khau/` | `views_tai_khoan` | Ho so va bao mat | Tenant |
| `/cap-nhat-thong-tin/` | `RedirectView` | Redirect legacy sang route tai khoan | Tenant |
| `/dat-phong-cua-toi/` | `views_dat_phong` | Danh sach booking | Tenant |
| `/dat-phong-cua-toi/<id>/` | `views_dat_phong` | Chi tiet booking | Tenant |
| `/dat-phong-cua-toi/<id>/thanh-toan-coc/` | `views_dat_phong` | Thanh toan coc | Tenant |
| `/hop-dong-cua-toi/`, `/hop-dong-cua-toi/<id>/` | `views_hop_dong` | Hop dong | Tenant |
| `/hoa-don-cua-toi/`, `/hoa-don-cua-toi/<id>/` | `views_hoa_don` | Hoa don | Tenant |
| `/hoa-don-cua-toi/<id>/thanh-toan/` | `views_thanh_toan` | Thanh toan hoa don | Tenant |
| `/thong-bao-cua-toi/`, `/thong-bao-cua-toi/<id>/` | `views_thong_bao` | Thong bao | Tenant |
| `/yeu-cau-sua-chua-cua-toi/` va cac route con | `views_sua_chua` | Danh sach/tao/chi tiet sua chua | Tenant |
| `/yeu-cau-ghep-cua-toi/`, `/yeu-cau-ghep/<id>/` | `views_o_ghep` | Yeu cau o ghep | Tenant |
| `/tai-khoan/nhan-dien-su-dung-phong/` | `views_smart_room` | Nhan dien su dung phong | Tenant |

## Admin nghiep vu

| URL / nhom URL | View module | Man hinh |
|---|---|---|
| `/dashboard-admin/` | `views_quan_tri` | Dashboard |
| `/quan-ly-phong/` va `tao`, `<id>/sua` | `views_phong` | Danh sach/form phong |
| `/quan-ly-dat-phong/` va `<id>/` | `views_quan_tri_dat_phong` | Danh sach/chi tiet booking |
| `/quan-ly-hop-dong/` va cac route con | `views_hop_dong`, `views_gia_han` | Hop dong va gia han |
| `/quan-ly-nguoi-thue/` va `<id>/` | `views_nguoi_thue` | Nguoi thue |
| `/quan-ly-hoa-don/` va cac route con | `views_hoa_don`, `views_thanh_toan` | Hoa don |
| `/quan-ly-sua-chua/` va `<id>/` | `views_sua_chua` | Sua chua |
| `/quan-ly-chinh-sach/` va cac route con | `views_chinh_sach` | Chinh sach |
| `/quan-ly-thong-bao/` va cac route con | `views_thong_bao` | Soan va quan ly thong bao |
| `/quan-ly-co-so/` va cac route con | `views_quan_tri` | Co so |
| `/quan-ly-yeu-cau-ghep/` | `views_o_ghep` | Duyet o ghep |
| `/thong-bao-admin/` va cac route con | `views_thong_bao` | Hop thu admin |
| `/nhat-ky-thao-tac/` va `<id>/` | `views_nhat_ky` | Audit log |

## Smart Room

| URL / nhom URL | Man hinh | View |
|---|---|---|
| `/smart-room/` | Dashboard Smart Room | `smart_room_dashboard` |
| `/smart-room/access-control/` | Dieu khien truy cap | `smart_access_control` |
| `/smart-room/nguoi-o-cung/` va cac route con | Nguoi o cung | `views_smart_room` |
| `/smart-room/face-profile/` va cac route con | Ho so Face ID | `views_smart_room` |
| `/smart-room/face-id/` | Xac thuc Face ID | `views_smart_room` |
| `/smart-room/quyen-ra-vao/` va cac route con | Quyen ra vao | `views_smart_room` |
| `/smart-room/lich-su-ra-vao/` va cac route con | Lich su ra vao | `views_smart_room` |

## Endpoint hanh dong

Khong nen xem cac route sau la man hinh doc lap trong sitemap: huy booking, bat/tat ghep, gui/huy gia han, xoa phong, xac nhan/tu choi booking va coc, xu ly hop dong/hoa don/sua chua/chinh sach/thong bao/co so, danh dau thong bao, dang ky/xac thuc Face ID, va cac route `*/xu-ly/`. UI audit ghi nhan 35 lenh dang dung browser `confirm()` va can mot confirmation component chung.

## Luong dieu huong chinh

1. Public: trang chu -> danh sach phong -> chi tiet phong -> dat phong -> booking cua toi -> thanh toan coc.
2. Tenant: tai khoan -> booking -> hop dong -> hoa don -> thanh toan; nhanh phu gom thong bao, sua chua, o ghep va Smart Room.
3. Admin: dashboard -> danh sach nghiep vu -> chi tiet -> xu ly; cac module dung chung shell nhung chua co page-header, filter va table pattern thong nhat.

## Diem can chu y

- Bon template co dau hieu khong con route/view render truc tiep: `dat_phong.html`, `dat_phong_thanh_cong.html`, `lich_su_ra_vao.html`, `tenant/booking/success.html`.
- `hop_dong_pdf.html` la ACTIVE do duoc view PDF tham chieu dong.
- Co logic booking admin cu trong `views_quan_tri.py`, trong khi route hien tai tro sang `views_quan_tri_dat_phong.py`; can xac minh truoc khi don code.
- Browser audit chi truy cap duoc public/auth khi khong co credential. Man hinh tenant/admin duoc audit tinh tu template, CSS, JS, view va route; chua xac nhan runtime sau dang nhap.
