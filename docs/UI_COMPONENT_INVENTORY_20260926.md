# UI Component Inventory

Ngay audit: 2026-09-26. Tat ca status ben duoi la audit-only; khong file runtime nao duoc sua.

## Layout hierarchy

| Layer | File | Consumer | CSS/JS | Status |
|---|---|---|---|---|
| Global shell | `core/base.html` | public + admin + tenant indirectly | `style.css`, `ui-system.css`, toast CSS/JS, `ui-system.js`, 3 local style/script blocks | ACTIVE |
| Tenant shell | `core/tenant_base.html` | auth + tenant pages | `tenant/components.css`, `tenant.js` | ACTIVE |
| Booking shell | `core/tenant/booking/base.html` | booking create/list/detail/payment/success | `tenant/booking.css`, `tenant/booking.js` | ACTIVE |
| PDF standalone | `core/hop_dong_pdf.html` | PDF generator path | local print CSS | ACTIVE, dynamically referenced |
| Toast partial | `core/components/toast_container.html` | base include | toast CSS/JS + inline seed script | ACTIVE |

Base templates: 3 web inheritance layers, 1 PDF standalone.  
Sidebar implementations: global role-aware sidebar in `base.html`; tenant secondary navigation in `tenant_base.html`.  
Topbar implementations: global topbar/mobile trigger in `base.html`; page-local headers repeat in most screens.

## Page/template inventory

Legend: `I` = substantial inline `<style>`; `E` = external page CSS; `J` = page JS; `U` = possibly unused.

### PUBLIC / AUTH

| Page | URL | Role | Template | View | Base | CSS/JS | Status |
|---|---|---|---|---|---|---|---|
| Home | `/` | Public | `home.html` | `views_quan_tri.home` | base | I+J | ACTIVE |
| Tim phong | `/phong/` | Public | `danh_sach_phong.html` | `views_phong.danh_sach_phong` | base | I | ACTIVE |
| Chi tiet phong | `/phong/<id>/` | Public | `chi_tiet_phong.html` | `views_phong.chi_tiet_phong` | base | `room_detail.css` + inline J | ACTIVE |
| Chinh sach ho tro | `/chinh-sach-ho-tro/` | Public | `chinh_sach_ho_tro.html` | `views_chinh_sach.chinh_sach_ho_tro` | tenant | E | ACTIVE |
| Dang nhap | `/dang-nhap/` | Public | `dang_nhap.html` | `views_dang_nhap.dang_nhap` | tenant | E+J | ACTIVE |
| Dang ky | `/dang-ky/` | Public | `dang_ky.html` | `views_dang_nhap.dang_ky` | tenant | E+J | ACTIVE |
| Dat phong legacy | no current render | User | `dat_phong.html` | superseded | tenant | E+J | POSSIBLY UNUSED |
| Dat phong thanh cong legacy | no current render | User | `dat_phong_thanh_cong.html` | superseded | tenant | E | POSSIBLY UNUSED |

### TENANT / USER

| Page group | URL(s) | Template(s) | View module | Base | Assets | Status |
|---|---|---|---|---|---|---|
| Booking | `/phong/<id>/dat/`, `/dat-phong-cua-toi/`, detail, coc | `tenant/booking/{create,list,detail,deposit_payment}.html` | `views_dat_phong` | booking | booking CSS/JS | ACTIVE |
| Booking result partial | no route found | `tenant/booking/success.html` | none found | booking | booking CSS | POSSIBLY UNUSED |
| Booking components | include only | `room_summary`, `tenant_information`, `companion_row` | include | booking | booking CSS/JS | ACTIVE |
| Tai khoan | `/tai-khoan/` | `tai_khoan.html` | `views_tai_khoan` | tenant | E | ACTIVE |
| Cap nhat thong tin | `/tai-khoan/cap-nhat/` | `cap_nhat_thong_tin.html` | `views_tai_khoan` | tenant | E | ACTIVE |
| Doi mat khau | `/tai-khoan/doi-mat-khau/`, legacy `/doi-mat-khau/` | `doi_mat_khau.html` | `views_tai_khoan` | tenant | E | ACTIVE |
| Hop dong cua toi | list/detail/gia han/PDF | `hop_dong_cua_toi.html`, `chi_tiet_hop_dong_cua_toi.html`, `hop_dong_pdf.html` | `views_hop_dong`, `views_gia_han` | tenant/PDF | E | ACTIVE |
| Hoa don cua toi | list/detail/payment | `hoa_don_cua_toi`, `chi_tiet_hoa_don_cua_toi`, `thanh_toan_hoa_don_cua_toi` | `views_hoa_don`, `views_thanh_toan` | tenant | E+J payment | ACTIVE |
| Thong bao cua toi | list/detail | `thong_bao_cua_toi`, `chi_tiet_thong_bao_cua_toi` | `views_thong_bao` | tenant | E | ACTIVE |
| Sua chua cua toi | list/create/detail | `yeu_cau_sua_chua_cua_toi`, `tao_yeu_cau_sua_chua`, `chi_tiet_yeu_cau_sua_chua_cua_toi` | `views_sua_chua` | tenant | E | ACTIVE |
| O ghep | register/list/detail | `dang_ky_ghep_phong`, `yeu_cau_ghep_cua_toi`, `chi_tiet_yeu_cau_ghep` | `views_o_ghep` | tenant | E + confirm | ACTIVE |
| Face ID unavailable | conditional Face ID | `face_id_unavailable.html` | `views_smart_room` | tenant | E | ACTIVE |
| Face profile detail tenant-like | Smart Room detail | `chi_tiet_face_profile.html` | `views_smart_room` | tenant | I+J | ACTIVE |

### ADMIN - CORE OPERATIONS

| Domain | URL prefix | Templates | View | CSS/JS | Status |
|---|---|---|---|---|---|
| Dashboard | `/dashboard-admin/` | `dashboard_admin.html` | `views_quan_tri.dashboard_admin` | I+J | ACTIVE |
| Phong | `/quan-ly-phong/` | `quan_ly_phong`, `tao_phong`, `sua_phong` | `views_phong` | I+J | ACTIVE |
| Co so | `/quan-ly-co-so/` | `quan_ly_co_so`, `chi_tiet_co_so`, `tao_co_so` | `views_quan_tri` | I | ACTIVE |
| Dat phong | `/quan-ly-dat-phong/` | `quan_ly_dat_phong`, `chi_tiet_dat_phong` | `views_quan_tri_dat_phong` | I+J/confirm | ACTIVE |
| Hop dong | `/quan-ly-hop-dong/` | `quan_ly_hop_dong`, `chi_tiet_hop_dong`, `tao_hop_dong`, `sua_hop_dong` | `views_hop_dong` | I+J/confirm | ACTIVE |
| Nguoi thue | `/quan-ly-nguoi-thue/` | `quan_ly_nguoi_thue`, `chi_tiet_nguoi_thue` | `views_nguoi_thue` | I | ACTIVE |
| Hoa don | `/quan-ly-hoa-don/` | `quan_ly_hoa_don`, `chi_tiet_hoa_don`, `tao_hoa_don` | `views_hoa_don`, `views_thanh_toan` | I+J/confirm | ACTIVE |
| Sua chua | `/quan-ly-sua-chua/`, `/tao-sua-chua/` | `quan_ly_sua_chua`, `chi_tiet_sua_chua`, `tao_sua_chua` | `views_sua_chua` | I | ACTIVE |
| Chinh sach | `/quan-ly-chinh-sach/` | `quan_ly_chinh_sach`, `chi_tiet_chinh_sach`, `tao_chinh_sach` | `views_chinh_sach` | I/confirm | ACTIVE |
| Thong bao | `/quan-ly-thong-bao/` | `quan_ly_thong_bao`, `chi_tiet_thong_bao`, `tao_thong_bao` | `views_thong_bao` | I/confirm | ACTIVE |
| Admin inbox | `/thong-bao-admin/` | `thong_bao_admin`, `chi_tiet_thong_bao_admin` | `views_thong_bao` | base/local | ACTIVE |
| Nhat ky | `/nhat-ky-thao-tac/` | `nhat_ky_thao_tac`, `chi_tiet_nhat_ky_thao_tac` | `views_nhat_ky` | I | ACTIVE |

All admin templates above extend `core/base.html`.

### SMART ROOM / FACE ID

| Page | URL | Template | View | Assets | Status |
|---|---|---|---|---|---|
| Smart dashboard | `/smart-room/` | `smart_room_dashboard.html` | `views_smart_room.smart_room_dashboard` | I+J | ACTIVE |
| Access control | `/smart-room/access-control/` | `smart_access_control.html` | same module | I+J/alert/fetch | ACTIVE |
| Nguoi o cung list/detail/create | `/smart-room/nguoi-o-cung/...` | `quan_ly_nguoi_o_cung`, `chi_tiet_nguoi_o_cung`, `tao_nguoi_o_cung` | same module | I; create mostly inline | ACTIVE |
| Face profile list/detail/create | `/smart-room/face-profile/...` | `quan_ly_face_profile`, `chi_tiet_face_profile`, `tao_face_profile` | same module | I+J | ACTIVE |
| Face verify | `/smart-room/face-id/` | `xac_thuc_face_id.html` | same module | I+J/fetch | ACTIVE |
| Quyen ra vao list/detail/create | `/smart-room/quyen-ra-vao/...` | `quan_ly_quyen_ra_vao`, `chi_tiet_quyen_ra_vao`, `tao_quyen_ra_vao` | same module | I+J/confirm | ACTIVE |
| Lich su ra vao list/detail/create | `/smart-room/lich-su-ra-vao/...` | `quan_ly_lich_su_ra_vao`, `chi_tiet_lich_su_ra_vao`, `tao_lich_su_ra_vao` | same module | I+J | ACTIVE |
| Entry history legacy | no route found | `lich_su_ra_vao.html` | superseded | I | POSSIBLY UNUSED |

### Other templates

| Template | Purpose | Status |
|---|---|---|
| `chi_tiet_chinh_sach.html` | Admin policy detail/actions | ACTIVE |
| `chi_tiet_co_so.html` | Facility detail/table | ACTIVE |
| `chi_tiet_dat_phong.html` | Admin booking workflow | ACTIVE |
| `chi_tiet_hoa_don.html` | Admin invoice/payment history | ACTIVE |
| `chi_tiet_hop_dong.html` | Admin contract workflow | ACTIVE |
| `chi_tiet_nguoi_thue.html` | Tenant profile + related tables | ACTIVE |
| `chi_tiet_sua_chua.html` | Repair workflow | ACTIVE |
| `tao_thong_bao.html` | Notification composer | ACTIVE |
| `tao_lich_su_ra_vao.html` | Manual entry event | ACTIVE |
| `tao_quyen_ra_vao.html` | Access grant | ACTIVE |
| `tao_face_profile.html` | Face profile | ACTIVE |
| `tao_nguoi_o_cung.html` | Companion/occupant | ACTIVE |

## Component inventory and consolidation candidates

| Component family | Current implementations | Candidate |
|---|---:|---|
| Page header/breadcrumb/actions | page-local on most templates | `page_header` include/component |
| Sidebar/topbar/account box | global base + tenant secondary nav | shell regions with role config |
| Buttons | dozens of class prefixes | `.ui-button` variants/size/icon |
| Form field | page-local label/input/error/help | field include + CSS contract |
| Table | 21 template implementations | table shell, toolbar, mobile strategy |
| Badge/status | room/booking/contract/invoice/repair/access local classes | semantic status registry/component |
| Card/panel | room, KPI, record, notice, policy, face, access | 3 card roles: item/panel/metric |
| Empty state | raw row, text block, icon+CTA | empty-state component |
| Confirm/modal | base modal, page overlays, 35 browser confirms | one accessible dialog primitive |
| Toast/alert | Django messages, toast, inline note, alert() | feedback primitives + severity map |
| Pagination/filter | repeated per management page | list toolbar + pagination include |
| Gallery | room list/detail/booking resolver | retain current centralized gallery contract |
| Icon | SVG, Unicode glyph, text symbol | one icon source + accessible-label rule |

## CSS and JS ownership

- Global: `style.css`, `ui-system.css`, `components/toast.css`.
- Tenant shared: `tenant/components.css`; 21 tenant page CSS files.
- Booking: `tenant/booking.css` and `tenant/booking.js`.
- Room detail: `room_detail.css`.
- Admin: mostly embedded CSS in each template; this is the largest consolidation opportunity.
- JS: only 4 external files, but 25 inline blocks remain. Face ID, Smart Access, dashboard and large detail pages own substantial local scripts.

