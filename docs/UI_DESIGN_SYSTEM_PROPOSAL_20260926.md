# UI Design System Proposal

Ngay de xuat: 2026-09-26. Day la dinh huong audit, chua duoc trien khai vao runtime.

## Nguyen tac

- Giu nhan dien NDT Motel hien co: teal lam mau thuong hieu, vang sen lam diem nhan.
- Uu tien kha nang doc, thao tac lap lai va mat do thong tin cua mot he thong van hanh nha tro.
- Khong thay doi workflow, quyen, URL, du lieu hay nghiep vu khi chuan hoa giao dien.
- Tao component nho, co the ap dung tung module; khong rewrite toan bo mot lan.

## Design tokens de xuat

### Mau sac

| Token | Gia tri | Muc dich |
|---|---|---|
| `--color-brand-600` | `#08798A` | Primary action, active state |
| `--color-brand-700` | `#075D68` | Hover/pressed |
| `--color-brand-050` | `#EDF7F7` | Nen thong tin nhe |
| `--color-accent` | `#E7BD42` | Diem nhan thuong hieu co kiem soat |
| `--color-ink` | `#123338` | Noi dung chinh |
| `--color-muted` | `#61777C` | Metadata, helper text |
| `--color-line` | `#D6E3E5` | Border/divider |
| `--color-canvas` | `#F7FAFA` | Nen ung dung |
| `--color-surface` | `#FFFFFF` | Panel/modal/table |
| `--color-success` | `#176A59` | Thanh cong |
| `--color-warning` | `#805A16` | Canh bao |
| `--color-danger` | `#B64141` | Loi/huy/xoa |

Can kiem tra WCAG contrast tren tung cap foreground/background truoc khi dua vao runtime, dac biet voi badge va text vang.

### Typography

Dung mot system stack khong them dependency: `Arial, Helvetica, sans-serif` de phu hop hien trang. Thang de xuat: 12px metadata, 14px noi dung compact, 16px body/form, 20px heading nho, 24px section heading, 32px page title, 40px chi danh cho hero. Line-height 1.4-1.6; khong dung text 8-10px cho du lieu nghiep vu.

### Spacing, radius va shadow

| Nhom | Scale |
|---|---|
| Spacing | `4, 8, 12, 16, 24, 32, 48px` |
| Radius | `4px` nho, `8px` control/card, `12px` modal/panel, `999px` pill |
| Shadow 1 | border + shadow rat nhe cho sticky/table surface |
| Shadow 2 | dropdown/popover |
| Shadow 3 | modal |

## Component contract

### Button

- Variants: primary, secondary, danger, ghost, icon-only.
- Chieu cao: 36px compact, 44px mac dinh, 48px mobile primary.
- Icon-only co `aria-label` va tooltip; loading giu nguyen kich thuoc, khoa submit lap.
- Mot action chi co mot mau theo ngu nghia; khong tao them mau rieng theo tung trang.

### Form

- Label 13-14px, control 44px, body 14-16px; helper va error nam ngay duoi field.
- Chia form dai thanh section co heading; action bar on dinh o cuoi.
- Trang thai focus, disabled, invalid, loading va success phai hien ro bang ca mau va text/icon.

### Table

- Header 12-13px, cell 13-14px, row cao toi thieu 44px.
- Desktop co sticky header khi danh sach dai; actions gom vao menu khi qua 2 lenh.
- Mobile: horizontal scroll cho bang can so sanh; chuyen card/list chi khi khong lam mat quan he cot.
- Empty, loading va error state dung cung mot table-state component.

### Badge va status

- Mot mapping trung tam tu domain status sang label, tone va icon.
- Badge toi thieu 12px, khong hien raw enum nhu `cho_xac_minh`.
- Khong dua trang thai chi bang mau; label luon bat buoc.

### Feedback va overlay

- Toast cho ket qua ngan; inline alert cho van de can doc; modal xac nhan cho hanh dong nghiem trong.
- Thay 35 browser `confirm()` va 13 `alert()` bang component co noi dung, muc do nguy hiem, focus trap va nut huy mac dinh.
- Poll notification khong cap nhat text gay nhay giao dien khi khong co thay doi.

### Page shell

- `PageHeader`: title, breadcrumb, primary action va optional metadata.
- `FilterBar`: search, status, date, facility, reset; responsive thanh hai hang.
- `EmptyState`: icon nhe, mo ta ngan, mot CTA neu co quyen.
- Sidebar desktop giu rong on dinh; mobile dung drawer va nut quen thuoc.

## Responsive baseline

| Moc | Dinh huong |
|---|---|
| 390px | Mobile nho, mot cot, target toi thieu 44px |
| 768px | Tablet, form co the 2 cot co chon loc |
| 1024px | Sidebar + noi dung, bang van co wrapper |
| 1440px | Desktop rong, gioi han dong doc va tang mat do bang hop ly |

Khong scale font theo viewport. Moi board, toolbar, thumbnail va icon button can kich thuoc on dinh de tranh layout shift.

## Lo trinh trien khai de xuat

1. P0: sua hai file mojibake; nang typography admin len muc doc duoc; dat token co ban ma khong thay workflow.
2. P1: tao button, status badge, form field, page header, table wrapper, empty state va confirm modal dung chung.
3. P2: ap dung vao booking, phong, hop dong, hoa don, nguoi thue; QA 390/768/1024/1440 va cac role.
4. P3: chuan hoa Smart Room, notification polling, loai bo template/logic legacy sau khi xac minh usage.

## Tieu chi nghiem thu

- Khong con text nghiep vu duoi 12px; body/form chinh toi thieu 14px.
- Khong co overflow ngang ngoai table wrapper; khong co control quan trong duoi 44px tren mobile.
- Moi status co label tieng Viet de hieu, khong raw enum.
- Moi hanh dong nguy hiem co confirmation accessible; moi submit co loading/disabled state.
- Keyboard focus thay duoc, modal trap focus, anh co alt, icon-only co accessible name.
- Khong thay doi ket qua nghiep vu, permission, route va du lieu trong qua trinh chuan hoa.
