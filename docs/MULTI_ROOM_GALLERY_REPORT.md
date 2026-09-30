# Bao cao multi-room gallery

Ngay hoan tat: 2026-09-26

## BACKUP TRUOC

- Source hop le: `luu_tru/ban_sao_luu/backup_before_multi_room_gallery_20260926_212625` (421 file).
- Media hop le: `luu_tru/ban_sao_luu/backup_media_before_multi_room_gallery_20260926_212625` (25 file, SHA-256 khop 25/25).
- MySQL: `luu_tru/ban_sao_luu/backup_before_multi_room_gallery.sql` (186,692 byte, co schema va INSERT data).
- Hai ban copy luc `20260926_212436` bi phang cap thu muc do PowerShell da duoc giu nguyen, khong dung lam ban rollback chinh.

## AUDIT 20 ANH CU

- KEEP: 0.
- REPLACE: 20.
- Ly do: cac anh trong moi nhom cu den tu nhieu listing/buoi chup, khong dong nhat giuong, tu, san, cua, WC va bang mau.
- Khong xoa file va khong xoa 20 record cu. Engine moi bo qua asset legacy trong `phong_mau/` khi xet anh rieng.
- Chi tiet: `docs/ROOM_GALLERY_AUDIT.md`.

## SO GALLERY VA ANH

- Tong: 15 gallery, 75 anh that, moi gallery 5 anh.
- TC: TC01-TC05, 25 anh.
- CC: CC01-CC04, 20 anh.
- GL: GL01-GL03, 15 anh.
- CH: CH01-CH03, 15 anh.
- 75/75 anh doc duoc, kich thuoc toi thieu dat 1200x700, khong co file trung SHA-256.
- Nguon chinh xac tung file: `media/phong_mau/SOURCES.md`.

## MAPPING LIVE

| Gallery | So phong |
|---|---:|
| TC01 | 8 |
| TC02 | 8 |
| TC03 | 8 |
| TC04 | 7 |
| TC05 | 7 |
| CC01 | 5 |
| CC02 | 5 |
| CC03 | 5 |
| CC04 | 4 |
| GL01 | 5 |
| GL02 | 5 |
| GL03 | 4 |
| CH01 | 5 |
| CH02 | 5 |
| CH03 | 5 |

Mapping 86 phong duoc co dinh trong config theo id; phong moi dung cong thuc on dinh dua tren loai, co so va so phong.

## P401

- URL: `/phong/9/`.
- Mapping: `TC01`.
- So anh: 5.
- Same-room consistency: PASS.
- Anh chinh va 5 thumbnail cung series 6447377-6447382; thao tac thumbnail da duoc kiem tra bang trinh duyet.

## DATABASE TRUOC/SAU

| Model | Truoc | Sau |
|---|---:|---:|
| Phong | 86 | 86 |
| HinhAnhPhong | 20 | 20 |
| DatPhong | 10 | 10 |
| HopDong | 6 | 6 |
| LichSuThanhToan | 3 | 3 |
| NguoiThue | 20 | 20 |

Khong co create/update/delete database trong task nay.

## KIEM TRA

- CHECK: PASS, 0 issue.
- TEST: PASS, 12/12 `core.tests.test_gallery_phong`.
- MAKEMIGRATIONS: PASS, `No changes detected`.
- N+1: PASS cho gallery. `/phong/` co 1 query `HinhAnhPhong` cho ca trang 12 card; `/phong/9/` co 1 query anh. Catalog file khong query DB theo tung phong va khong scan filesystem theo tung card.
- DESKTOP QA: PASS, 16 phong (du 15 gallery va P401), viewport 1440x900.
- MOBILE QA: PASS, 16 phong, viewport 390x844.
- Tat ca page HTTP 200, 5/5 anh load, thumbnail doi dung anh lon, khong horizontal overflow.
- SAME ROOM CONSISTENCY: PASS 15/15 gallery sau khi doi chieu contact sheet va anh chup browser.

## THAY DOI HE THONG

- MIGRATION: Khong.
- SCHEMA CHANGE: Khong.
- WORKFLOW CHANGE: Khong.
- Admin upload anh rieng van override gallery style; xoa het anh rieng se quay lai mapping.
- Thu tu fallback: anh rieng that -> gallery mapped -> gallery mac dinh cua loai -> placeholder.
- `gallery_hien_thi` va `anh_dai_dien_hien_thi` duoc giu nguyen cho template hien tai.

## FILE CODE DA SUA

- `core/dich_vu/gallery_phong.py`
- `core/dich_vu/room_gallery_mapping.py`
- `core/tests/test_gallery_phong.py`
- `docs/ROOM_GALLERY_AUDIT.md`
- `docs/MULTI_ROOM_GALLERY_REPORT.md`
- `media/phong_mau/SOURCES.md`

## FILE ANH

- Da them 75 file trong 15 thu muc `media/phong_mau/<loai>/<ma>/`.
- Da loai/xoa: 0 file.
- 20 file legacy va 20 record legacy duoc giu de rollback.

## PLACEHOLDER VA RUI RO CON LAI

- Live con placeholder: Khong; 86/86 phong co gallery mapped hoac anh rieng.
- Placeholder van hoat dong neu toan bo gallery cua loai bi mat.
- Anh Pexels la anh dai dien, khong phai anh chup thuc te cua tung phong; can ghi ro voi nguoi dung neu dung trong moi truong thuong mai.
- Bang override gan voi id cua 86 phong hien tai. Phong moi co fallback on dinh, nhung nen them mapping explicit khi muon can bang lai tong the.
- Trang `/phong/` hien co 21 query tong do cac truy van nghiep vu hop dong/trang thai san co; phan gallery chi chiem 1 query va khong tao N+1.

## BACKUP HOAN CHINH

- `luu_tru/ban_sao_luu/backup_multi_room_gallery_complete_20260926_214353`.

## BO SUNG: DISPLAY COVER CONSISTENCY

Ngay kiem tra: 2026-09-26.

Nguyen nhan bug: `templates/core/home.html` van dung property legacy
`anh_dai_dien`. Vi vay P101 hien collage cu tu DB va cac phong khong co record
legacy hien `Chua co hinh anh`, trong khi list/detail da dung multi-gallery.

Khac phuc:

- Homepage chuan bi gallery bang cung `chuan_bi_gallery_hien_thi`.
- Hero va room card homepage dung `anh_dai_dien_hien_thi`.
- `/phong/`, detail va booking tiep tuc dung cung display cover tu resolver.
- Khong xoa 20 `HinhAnhPhong` legacy; chung la record mau trong
  `phong_mau/`, khong phai anh rieng Admin upload.

| Phong | Card | Detail main | Booking | Gallery | Nguon | Match |
|---|---|---|---|---|---|---|
| P101, Cam Le, id 1 | `TC01/01_toan_canh.jpg` | `TC01/01_toan_canh.jpg` | `TC01/01_toan_canh.jpg` | TC01 | STYLE | YES |
| P102, Cam Le, id 2 | `TC02/01_toan_canh.jpg` | `TC02/01_toan_canh.jpg` | `TC02/01_toan_canh.jpg` | TC02 | STYLE | YES |
| P103, Cam Le, id 13 | `TC03/01_toan_canh.jpg` | `TC03/01_toan_canh.jpg` | `TC03/01_toan_canh.jpg` | TC03 | STYLE | YES |
| P401, Cam Le, id 9 | `TC01/01_toan_canh.jpg` | `TC01/01_toan_canh.jpg` | `TC01/01_toan_canh.jpg` | TC01 | STYLE | YES |

Audit render live toan bo 86 phong:

- CARD CO ANH: 86.
- DETAIL CO ANH: 86.
- CARD = DETAIL MAIN: 86.
- CARD != DETAIL MAIN: 0.
- DETAIL CO ANH NHUNG CARD KHONG CO: 0.
- CARD = DETAIL = BOOKING = DISPLAY COVER: 86/86.
- Chrome DOM QA P101: homepage/list/detail cung URL, anh tai thanh cong.
- Test gallery: 13/13 PASS.
