# Audit gallery phong truoc khi thiet ke lai

Ngay audit: 2026-09-26

## Pham vi va nguyen tac

- Da kiem tra 20 file trong `media/phong_mau/` va 20 record `HinhAnhPhong` tuong ung.
- `KEEP` chi duoc dung khi nhieu anh co the xac nhan la cung mot can/phong va cung phong cach.
- `REPLACE` co nghia la khong dua vao gallery hien thi moi. File va record cu van duoc giu nguyen de rollback.
- Khong co file hong, thieu, hoac khong doc duoc.

## Ket qua tong quan

| Nhom cu | So anh | KEEP | REPLACE | Ket luan |
|---|---:|---:|---:|---|
| Phong tieu chuan | 5 | 0 | 5 | Mot anh collage noi bo; 4 anh con lai la bon khong gian/nguon khac nhau. |
| Phong cao cap | 5 | 0 | 5 | Mau sac, vat lieu, bo cuc va anh sang thay doi ro ret giua tung anh. |
| Phong gac lung | 5 | 0 | 5 | Co dac trung gac lung nhung khong cung cau truc, noi that hay bo anh. |
| Can ho mini | 5 | 0 | 5 | Dung chu de studio/mini nhung bep, giuong, WC va ban an khong thuoc cung can. |
| **Tong** | **20** | **0** | **20** | Can thay bang cac series cung mot listing/buoi chup. |

## Inventory va nguon

| File | Loai | Phong mau | Kich thuoc | Nguon |
|---|---|---|---:|---|
| `phong_tieu_chuan/01_toan_canh.png` | Tieu chuan | P101 (id 1) | 1536x1024 | Asset project: `media/phong/2026/09/ChatGPT_Image_19_44_18_15_thg_9_2026.png` |
| `phong_tieu_chuan/02_khu_ngu.jpg` | Tieu chuan | P101 (id 1) | 1600x1096 | https://www.pexels.com/photo/28843338/ |
| `phong_tieu_chuan/03_tien_nghi.jpg` | Tieu chuan | P101 (id 1) | 1600x1067 | https://www.pexels.com/photo/17495856/ |
| `phong_tieu_chuan/04_wc.jpg` | Tieu chuan | P101 (id 1) | 1600x1200 | https://www.pexels.com/photo/35505456/ |
| `phong_tieu_chuan/05_cua_so.jpg` | Tieu chuan | P101 (id 1) | 1600x1067 | https://www.pexels.com/photo/26571203/ |
| `phong_cao_cap/01_toan_canh.jpg` | Cao cap | P104 (id 14) | 1600x1068 | https://www.pexels.com/photo/6444255/ |
| `phong_cao_cap/02_khu_ngu.jpg` | Cao cap | P104 (id 14) | 1600x1068 | https://www.pexels.com/photo/7061330/ |
| `phong_cao_cap/03_tiep_khach.jpg` | Cao cap | P104 (id 14) | 1600x1068 | https://www.pexels.com/photo/7195595/ |
| `phong_cao_cap/04_wc.jpg` | Cao cap | P104 (id 14) | 1600x1067 | https://www.pexels.com/photo/29252363/ |
| `phong_cao_cap/05_tien_nghi.jpg` | Cao cap | P104 (id 14) | 1600x1200 | https://www.pexels.com/photo/18651510/ |
| `phong_gac_lung/01_toan_canh.jpg` | Gac lung | P201 (id 3) | 1600x1060 | https://www.pexels.com/photo/30580543/ |
| `phong_gac_lung/02_tang_duoi.jpg` | Gac lung | P201 (id 3) | 1600x2133 | https://www.pexels.com/photo/16451357/ |
| `phong_gac_lung/03_khu_ngu_gac.jpg` | Gac lung | P201 (id 3) | 1600x1068 | https://www.pexels.com/photo/7746954/ |
| `phong_gac_lung/04_wc.jpg` | Gac lung | P201 (id 3) | 1600x1067 | https://www.pexels.com/photo/28683056/ |
| `phong_gac_lung/05_cau_thang.jpg` | Gac lung | P201 (id 3) | 1600x1067 | https://www.pexels.com/photo/29252604/ |
| `can_ho_mini/01_toan_canh.jpg` | Can ho mini | P301 (id 5) | 1600x1068 | https://www.pexels.com/photo/6527062/ |
| `can_ho_mini/02_khu_ngu.jpg` | Can ho mini | P301 (id 5) | 1600x1103 | https://www.pexels.com/photo/6487938/ |
| `can_ho_mini/03_bep.jpg` | Can ho mini | P301 (id 5) | 1600x1068 | https://www.pexels.com/photo/7173664/ |
| `can_ho_mini/04_wc.jpg` | Can ho mini | P301 (id 5) | 1600x1067 | https://www.pexels.com/photo/26925303/ |
| `can_ho_mini/05_ban_an.jpg` | Can ho mini | P301 (id 5) | 1600x1068 | https://www.pexels.com/photo/6444249/ |

## Danh gia tung anh

| File | Danh gia | Ly do |
|---|---|---|
| `phong_tieu_chuan/01_toan_canh.png` | REPLACE | Collage nhieu goc co tinh nhat quan noi bo, nhung khong phai anh don va khong cung bo voi 4 anh con lai. |
| `phong_tieu_chuan/02_khu_ngu.jpg` | REPLACE | Phong ngu go toi, phong cach cao cap hon anh tong quan. |
| `phong_tieu_chuan/03_tien_nghi.jpg` | REPLACE | Ban/tu xanh va bo cuc rieng, khong trung vat lieu hoac do noi that. |
| `phong_tieu_chuan/04_wc.jpg` | REPLACE | WC sang mau, khong co dau hieu xac nhan thuoc cung can. |
| `phong_tieu_chuan/05_cua_so.jpg` | REPLACE | Phong ngu xam voi cua so/canh quan khac han cac anh truoc. |
| `phong_cao_cap/01_toan_canh.jpg` | REPLACE | Phong ngu xam hien dai, la mot listing rieng. |
| `phong_cao_cap/02_khu_ngu.jpg` | REPLACE | Phong ngu kem sang, dau giuong va tu khong trung anh 01. |
| `phong_cao_cap/03_tiep_khach.jpg` | REPLACE | Can studio xanh la, khong trung bang mau hay mat bang. |
| `phong_cao_cap/04_wc.jpg` | REPLACE | WC be/go, khong the doi chieu voi cac phong ngu. |
| `phong_cao_cap/05_tien_nghi.jpg` | REPLACE | Khu an/bep sang trong cua mot can ho khac. |
| `phong_gac_lung/01_toan_canh.jpg` | REPLACE | Loft mo voi cau thang va sofa tim, khong trung cac anh con lai. |
| `phong_gac_lung/02_tang_duoi.jpg` | REPLACE | Goc tren cao, tuong gach va noi that cua mat bang khac. |
| `phong_gac_lung/03_khu_ngu_gac.jpg` | REPLACE | Phong ngu doc lap, khong the hien lien he voi tang gac. |
| `phong_gac_lung/04_wc.jpg` | REPLACE | WC trang hien dai, khong co chi tiet chung voi listing loft. |
| `phong_gac_lung/05_cau_thang.jpg` | REPLACE | Loft cong nghiep co vong, cau thang va vat lieu khac anh 01/02. |
| `can_ho_mini/01_toan_canh.jpg` | REPLACE | Studio bep/ban an, la listing rieng. |
| `can_ho_mini/02_khu_ngu.jpg` | REPLACE | Giuong gan cua so va bep, mat bang/noi that khong trung anh 01. |
| `can_ho_mini/03_bep.jpg` | REPLACE | Bep/ban an nhieu mau, khong trung he tu bep cac anh khac. |
| `can_ho_mini/04_wc.jpg` | REPLACE | WC trang cua nguon rieng, khong co dau hieu lien ket. |
| `can_ho_mini/05_ban_an.jpg` | REPLACE | Bep xam va ban an hien dai, khong trung listing anh 01/03. |

## Quyet dinh

1. Khong xoa 20 record `HinhAnhPhong` va khong xoa 20 file cu trong giai do trien khai.
2. Gallery moi dung thu muc rieng theo ma `TC01..TC05`, `CC01..CC04`, `GL01..GL03`, `CH01..CH03`.
3. Cac anh cu trong `phong_mau/phong_*` duoc xem la gallery mau legacy, khong phai anh rieng do admin upload cho mot phong.
4. Chi anh upload rieng ngoai cay `phong_mau/` moi override gallery phong cach.
