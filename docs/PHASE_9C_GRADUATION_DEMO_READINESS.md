# PHASE 9C - Graduation Demo Readiness

Date: 2026-09-16
Scope: read-only graduation presentation runbook. No production code, tests, migrations, UI, or database data were modified.

Verified baseline from Phase 9A:

- `manage.py check`: PASS
- `manage.py test`: PASS, 154 tests
- `manage.py makemigrations --check --dry-run`: PASS, no changes detected
- Phase 9A verdict: ready for local graduation/demo use

## 1. Recommended 8-12 Minute Demo Flow

Use two browser profiles or two browsers:

- Browser A: admin account
- Browser B: tenant account

Recommended timebox: about 10 minutes.

| Time | Role | Screen / Route | Action | Why this is strong |
| --- | --- | --- | --- | --- |
| 0:00-0:45 | Admin | `/dang-nhap/` -> `/dashboard-admin/` | Log in and show dashboard. | Establishes role-based admin area. |
| 0:45-1:30 | Admin | `/quan-ly-co-so/`, `/quan-ly-phong/` | Show facility and room list/detail. | Demonstrates motel structure and room inventory. |
| 1:30-2:30 | Tenant | `/dang-nhap/`, `/phong/`, `/phong/<id>/`, `/phong/<id>/dat/` | Show room browsing and an existing pending booking, or submit one only if a spare room is prepared. | Shows tenant self-service without going straight to admin. |
| 2:30-3:30 | Admin | `/quan-ly-dat-phong/`, `/quan-ly-dat-phong/<id>/` | Inspect pending booking and approve/reject only if using disposable demo data. | Shows booking workflow and admin decision point. |
| 3:30-4:30 | Admin | `/quan-ly-hop-dong/`, `/quan-ly-hop-dong/<id>/` | Show active contract and, if useful, export PDF via `/hop-dong/<id>/xuat-pdf/`. | Shows contract lifecycle and current tenant-room binding. |
| 4:30-6:00 | Tenant + Admin | Tenant `/hoa-don-cua-toi/<id>/thanh-toan/`; Admin `/quan-ly-hoa-don/<id>/` | Tenant sends payment request; admin confirms it. | Strongest business flow: tenant cannot directly mark invoice paid. |
| 6:00-6:45 | Tenant + Admin | `/yeu-cau-sua-chua-cua-toi/tao/`, `/quan-ly-sua-chua/` | Show a prepared repair request; process only if duplicate demo data exists. | Shows service workflow after move-in. |
| 6:45-7:30 | Tenant + Admin | `/thong-bao-cua-toi/`, `/quan-ly-thong-bao/` | Show tenant notification and admin notification management. | Shows communication and tenant scoping. |
| 7:30-9:30 | Tenant + Admin | `/tai-khoan/nhan-dien-su-dung-phong/`, `/smart-room/face-id/`, `/smart-room/lich-su-ra-vao/` | FaceProfile enrollment or stored profile; admin camera verification; access history. | Highest-value technical feature, but hardware-dependent. |
| 9:30-10:30 | Admin | `/nhat-ky-thao-tac/` | Show audit log and summarize tests/transactions. | Ends with reliability and accountability. |

Do not include routes that are not currently implemented. The removed legacy admin payment route `thanh_toan_hoa_don` should not be demonstrated.

## 2. Demo Data Requirements

Prepare data before the presentation. Do not rely on creating all records live.

### Accounts

| Record | Required state | Purpose |
| --- | --- | --- |
| Admin account | `is_staff=True` or `is_superuser=True` | Admin dashboard, management, confirmations, Smart Room terminal |
| Tenant A account | Linked to `NguoiThue`, active | Main tenant demo |
| Tenant B account | Linked to another `NguoiThue`, active | Authorization example and denied access explanation |

### Facility And Rooms

| Record | Required state | Purpose |
| --- | --- | --- |
| Facility | At least one `CoSo` | Facility/room management |
| Available room | `Phong.trang_thai="trong"` and capacity configured | Optional live booking request |
| Occupied room | Bound to Tenant A active contract | Contract, invoice, repair, Smart Room |
| Optional maintenance room | `Phong.trang_thai="bao_tri"` if present | Explain room availability rules, not required |

### Booking And Contract

| Record | Required state | Purpose |
| --- | --- | --- |
| Pending booking | `DatPhong.trang_thai="cho_duyet"` | Admin booking approval demo |
| Approved booking with contract | `DatPhong.trang_thai="da_duyet"` and `HopDong` exists | Main tenant contract demo |
| Active contract | `HopDong.trang_thai="dang_hieu_luc"` or `sap_het_han`, date includes demo day | Tenant contract, invoice, Face ID permission |
| Optional renewal request | `YeuCauGiaHanHopDong.trang_thai="cho_duyet"` | Only if contract renewal is part of the demo |

### Billing

Prepare separate invoices so one state-changing action does not destroy the whole script.

| Record | Required state | Purpose |
| --- | --- | --- |
| Unpaid invoice A | `HoaDon.trang_thai="chua_thanh_toan"` or `qua_han`, owned by Tenant A | Tenant payment request demo |
| Pending invoice B | `HoaDon.trang_thai="cho_xac_nhan"` | Admin confirmation demo if live tenant step fails |
| Paid invoice C | `HoaDon.trang_thai="da_thanh_toan"` with `LichSuThanhToan` | Show payment history |
| Optional cancelled invoice | `HoaDon.trang_thai="huy"` | Explain blocked payment states if asked |

### Repair, Notification, Smart Room

| Record | Required state | Purpose |
| --- | --- | --- |
| Repair request | `YeuCauSuaChua.trang_thai="moi"` or `dang_xu_ly`, Tenant A room | Tenant/admin repair workflow |
| Tenant notification | `ThongBao.nguoi_thue=Tenant A`, read/unread as desired | Tenant notification page |
| FaceProfile | Tenant A profile, ideally `trang_thai="da_xac_thuc"` with image/encoding | Face ID fallback and detail page |
| Access permission | `QuyenRaVao.trang_thai="hoat_dong"`, `nguon_cap="face_id"` or `thu_cong`, bound to Tenant A active contract | Smart Room authorization |
| Access history | At least one `LichSuRaVao` record with `nguon="camera"` or `thu_cong` | Fallback if camera fails |
| Optional roommate | `NguoiOCungPhong.trang_thai="dang_o"` with profile/permission | Co-occupant behavior explanation |

## 3. Safe Demo Order For State-Changing Actions

Use this order so state is not consumed too early.

| Step | Before state | Action | After state | Reset needed? |
| --- | --- | --- | --- | --- |
| Tenant payment request | Invoice A is `chua_thanh_toan` or `qua_han` | Tenant opens invoice detail and submits payment request | Invoice A becomes `cho_xac_nhan` | Yes, if repeating the exact same invoice. Keep Invoice B/C for backup. |
| Admin payment confirmation | Invoice B or newly pending Invoice A is `cho_xac_nhan` | Admin confirms payment | Invoice becomes `da_thanh_toan`; payment history created | Yes, if needing to repeat pending confirmation. |
| Booking approval | Pending booking is `cho_duyet`; room still available | Admin approves | Booking becomes `da_duyet`; room/contract path may change | Yes, use disposable booking/room or keep one untouched pending booking. |
| Contract activation/cancel | Contract is prepared in a safe state | Show detail; avoid cancel unless using disposable record | Contract state may change | Avoid destructive changes in main demo. |
| Repair processing | Repair is `moi` | Admin moves to `dang_xu_ly` or `hoan_thanh` | Repair state changes | Yes, keep one spare request if repeating. |
| Notification detail | Tenant notification unread | Tenant opens detail | May become read | No critical reset; prepare another unread notification if needed. |
| FaceProfile bootstrap | Tenant has active contract; maybe no profile | Tenant opens self-service Face ID route | A FaceProfile may be created/opened | No if idempotent; but use a known tenant. |
| Face ID enrollment | FaceProfile exists and is not `bi_vo_hieu` | Browser captures face and submits | Profile becomes `da_xac_thuc`; access may sync | Yes, if repeating enrollment from blank profile is required. |
| Face ID authentication | Active permission exists | Admin terminal captures face | Access history record created | No reset needed; history grows. |

Best practice: demonstrate one live state change in billing, then use prepared records for the remaining screens.

## 4. Manual Browser Test Checklist

Run this before presentation day and again quickly on the presentation machine.

### Admin Pages

| Page | Route | Checklist |
| --- | --- | --- |
| Login | `/dang-nhap/` | [ ] route opens [ ] no server error [ ] layout correct [ ] login works [ ] wrong credentials handled |
| Dashboard | `/dashboard-admin/` | [ ] route opens [ ] no server error [ ] stats/data correct [ ] navigation works [ ] desktop/tablet acceptable |
| Facilities | `/quan-ly-co-so/` | [ ] route opens [ ] list data correct [ ] detail opens [ ] create/edit buttons visible [ ] admin-only |
| Rooms | `/quan-ly-phong/` | [ ] route opens [ ] filters/list correct [ ] detail/edit/create routes open [ ] room status correct |
| Booking management | `/quan-ly-dat-phong/` | [ ] route opens [ ] pending booking visible [ ] detail opens [ ] approve/reject controls work on disposable record |
| Contracts | `/quan-ly-hop-dong/` | [ ] route opens [ ] active contract visible [ ] detail opens [ ] PDF export works if used |
| Invoices | `/quan-ly-hoa-don/` | [ ] route opens [ ] pending invoice visible [ ] detail opens [ ] confirm button works on chosen invoice [ ] payment history visible |
| Repairs | `/quan-ly-sua-chua/` | [ ] route opens [ ] request visible [ ] detail opens [ ] processing controls work on disposable request |
| Notifications | `/quan-ly-thong-bao/` | [ ] route opens [ ] create route opens [ ] detail opens [ ] tenant recipient shown correctly |
| Smart Room dashboard | `/smart-room/` | [ ] route opens [ ] cards/data correct [ ] navigation to Face Profile/Permission/History works |
| Face Profiles | `/smart-room/face-profile/` | [ ] route opens [ ] profile visible [ ] detail opens [ ] enrollment UI available where expected |
| Face ID terminal | `/smart-room/face-id/` | [ ] route opens [ ] camera permission prompt appears [ ] video displays [ ] submit works |
| Access permissions | `/smart-room/quyen-ra-vao/` | [ ] route opens [ ] active permission visible [ ] detail opens [ ] status correct |
| Access history | `/smart-room/lich-su-ra-vao/` | [ ] route opens [ ] latest event visible [ ] detail opens [ ] result notes readable |
| Audit log | `/nhat-ky-thao-tac/` | [ ] route opens [ ] recent actions visible [ ] filters/back navigation acceptable |

### Tenant Pages

| Page | Route | Checklist |
| --- | --- | --- |
| Login | `/dang-nhap/` | [ ] route opens [ ] tenant login works [ ] redirects to account/home as expected |
| Account | `/tai-khoan/` | [ ] route opens [ ] profile data correct [ ] booking/contract/invoice/repair summaries visible |
| Profile update | `/cap-nhat-thong-tin/` | [ ] route opens [ ] form fields correct [ ] CSRF present [ ] do not save unless using disposable data |
| Room list | `/phong/` | [ ] route opens [ ] available room shown [ ] responsive acceptable |
| Room detail | `/phong/<id>/` | [ ] route opens [ ] price/status/capacity correct [ ] booking CTA correct |
| Booking form | `/phong/<id>/dat/` | [ ] route opens [ ] required fields present [ ] submit only on disposable room |
| Contracts | `/hop-dong-cua-toi/` | [ ] route opens [ ] active contract visible [ ] detail route opens |
| Contract detail | `/hop-dong-cua-toi/<id>/` | [ ] route opens [ ] tenant owns record [ ] data correct [ ] PDF/export link if shown works |
| Invoice list | `/hoa-don-cua-toi/` | [ ] route opens [ ] invoice states correct [ ] CTA matches status |
| Invoice detail | `/hoa-don-cua-toi/<id>/` | [ ] route opens [ ] total correct [ ] payment button appears only when eligible |
| Payment request | `/hoa-don-cua-toi/<id>/thanh-toan/` | [ ] route opens [ ] confirmation step works [ ] invoice moves to `cho_xac_nhan` |
| Repair list | `/yeu-cau-sua-chua-cua-toi/` | [ ] route opens [ ] tenant-only records visible |
| Repair create | `/yeu-cau-sua-chua-cua-toi/tao/` | [ ] route opens [ ] room choices correct [ ] submit only if demo data allows |
| Notification list | `/thong-bao-cua-toi/` | [ ] route opens [ ] filters work [ ] unread/read counts acceptable |
| Notification detail | `/thong-bao-cua-toi/<id>/` | [ ] route opens [ ] marks read if expected [ ] back navigation works |
| FaceProfile self-service | `/tai-khoan/nhan-dien-su-dung-phong/` -> `/smart-room/face-profile/<id>/` | [ ] route opens [ ] tenant can access own profile [ ] camera enrollment button/page works |
| Roommate request pages | `/yeu-cau-ghep-cua-toi/`, `/yeu-cau-ghep/<id>/` | [ ] route opens if using roommate demo [ ] owner/other tenant permission correct |

## 5. Billing Demo Script

Use this exact intended flow.

### Tenant Side

1. Open `/hoa-don-cua-toi/`.
2. Choose Invoice A with `trang_thai="chua_thanh_toan"` or `qua_han`.
3. Open `/hoa-don-cua-toi/<id>/`.
4. Click/send payment request via `/hoa-don-cua-toi/<id>/thanh-toan/`.
5. Confirm the request.
6. Expected result: invoice becomes `cho_xac_nhan`; tenant sees "waiting for confirmation" style state.

What to say:

"Nguoi thue khong duoc tu danh dau hoa don da thanh toan. He thong chi tao yeu cau xac nhan, sau do quan tri vien kiem tra va xac nhan."

### Admin Side

1. Open `/quan-ly-hoa-don/`.
2. Filter or select pending invoice with `trang_thai="cho_xac_nhan"`.
3. Open `/quan-ly-hoa-don/<id>/`.
4. Inspect invoice, tenant, room, payment method.
5. Submit admin confirmation through `/quan-ly-hoa-don/<id>/xu-ly/`.
6. Expected result: invoice becomes `da_thanh_toan`, `ngay_thanh_toan` and `nguoi_xac_nhan` are set, payment history is visible.

Technical point:

- `HoaDon` is unique per contract/month/year.
- Tenant request and admin confirmation are separate responsibilities.
- Critical updates are protected with database transactions and row locking in the payment flow.
- Overdue status is synchronized by the explicit command `dong_bo_hoa_don_qua_han`, not by page views.

## 6. Booking And Contract Demo

Actual lifecycle implemented:

1. Tenant browses rooms: `/phong/`.
2. Tenant opens detail: `/phong/<id>/`.
3. Tenant submits booking request: `/phong/<id>/dat/`.
4. Booking starts as `DatPhong.trang_thai="cho_duyet"`.
5. Admin reviews: `/quan-ly-dat-phong/<id>/`.
6. Admin approves/rejects/cancels through `/quan-ly-dat-phong/<id>/xu-ly/`.
7. If approved, booking state becomes `da_duyet`.
8. Admin can create contract: `/quan-ly-dat-phong/<id>/tao-hop-dong/`.
9. Contract starts as `HopDong.trang_thai="cho_hieu_luc"` and can be processed into active lifecycle states.
10. Tenant views contract at `/hop-dong-cua-toi/` and `/hop-dong-cua-toi/<id>/`.

Safe demo sequence:

- Prefer showing an already prepared pending booking and active contract.
- If doing a live booking, use an available spare room and a tenant without a conflicting active booking for that room.
- Do not cancel the main active contract during the demo.
- Do not approve the only pending booking before showing it on both list and detail pages.

Technical points to explain:

- Booking approval re-checks room status and capacity.
- Contract binds one approved booking to one contract.
- Room, booking, and contract state are synchronized by model logic and management commands.
- Tests cover duplicate approval, stale room capacity, conflicting activation, and lifecycle date boundaries.

## 7. Smart Room / Face ID Manual Test

This is the highest-priority manual verification because hardware/browser behavior cannot be fully proven by unit tests.

### Code/Test Verified

- Face ID enrollment endpoint requires authentication, authorization, POST, active contract resolution, image input, quality checks, duplicate face checks, and transaction handling.
- Admin Face ID terminal requires admin access and POST.
- Permission eligibility uses bound contract/room/subject and date/status filters before access is allowed.
- Access history records are created for allowed and denied attempts.
- Tests cover wrong room, inactive/expired/future permission, legacy/unknown denial, valid permission with history, and current contract binding.

### Manually Verified Checklist

Do not mark these as PASS until tested on the actual presentation machine.

| Item | Status |
| --- | --- |
| [ ] Browser camera permission prompt appears | Manual |
| [ ] Browser camera permission can be allowed | Manual |
| [ ] Camera starts on `/smart-room/face-id/` | Manual |
| [ ] Video element displays live image | Manual |
| [ ] Capture button works | Manual |
| [ ] Tenant FaceProfile route opens from `/tai-khoan/nhan-dien-su-dung-phong/` | Manual |
| [ ] Face Profile detail page opens for correct tenant | Manual |
| [ ] FaceProfile enrollment capture submits successfully | Manual |
| [ ] FaceProfile becomes `da_xac_thuc` | Manual |
| [ ] Stored profile image appears | Manual |
| [ ] Access permission is created or remains active for correct contract/room | Manual |
| [ ] Admin authentication request works on `/smart-room/face-id/` | Manual |
| [ ] Authorized tenant is allowed for correct room | Manual |
| [ ] Wrong room or unauthorized person is denied, if reproducible | Manual |
| [ ] `LichSuRaVao` record is created after authentication attempt | Manual |
| [ ] Admin sees the access history in `/smart-room/lich-su-ra-vao/` | Manual |
| [ ] Tenant sees appropriate own Smart Room/FaceProfile information | Manual |
| [ ] Co-occupant behavior works if included in demo data | Manual |

### Co-Occupant / Permission Behavior

Only demonstrate this if data is prepared:

- `NguoiOCungPhong.trang_thai="dang_o"`.
- FaceProfile linked to roommate, not tenant.
- `QuyenRaVao.loai_quyen="nguoi_o_cung"`.
- Permission bound to the same contract and room.
- Access history uses roommate subject.

If this data is not prepared, explain it verbally rather than clicking through live.

## 8. Face ID Failure Fallback

If camera/device/browser fails during the defense, do not fake success.

Show these existing screens instead:

| Fallback screen | Route | What it proves |
| --- | --- | --- |
| Face profile list/detail | `/smart-room/face-profile/`, `/smart-room/face-profile/<id>/` | Stored enrolled users/profiles exist. |
| Access permissions | `/smart-room/quyen-ra-vao/`, `/smart-room/quyen-ra-vao/<id>/` | The system models room access rights with contract and subject binding. |
| Access history | `/smart-room/lich-su-ra-vao/`, `/smart-room/lich-su-ra-vao/<id>/` | Access events are persisted for audit. |
| Tenant FaceProfile detail | `/smart-room/face-profile/<id>/` from tenant self-service | Tenant can view own profile only. |
| Tests/report | Phase 9A and test suite result | Business authorization and persistence paths are regression-tested. |

Safe explanation:

"Phan nhan dien khuon mat phu thuoc vao quyen camera cua trinh duyet va thiet bi trinh chieu. Neu camera khong hoat dong trong phong bao ve, em se trinh bay cac man hinh ho so khuon mat, quyen ra vao va lich su ra vao da luu trong he thong. Em khong khang dinh lan nhan dien live thanh cong neu chua chay duoc tren thiet bi nay."

Do not claim:

- That live recognition passed on the defense machine if it did not.
- That the system has anti-spoofing/liveness detection unless it is actually implemented.
- That RFID/PIN/physical lock integration is complete unless separately built.

## 9. Security / Permission Demo

Good examples to explain or demonstrate carefully:

| Example | How to show | Recommendation |
| --- | --- | --- |
| Tenant cannot access another tenant invoice | Log in as Tenant B and try Tenant A invoice detail URL. | Explain verbally or test before demo; avoid showing raw error too long. |
| Tenant cannot access another tenant repair/notification | Tenant B tries Tenant A repair or notification detail URL. | Good short verbal security example. |
| Admin-only management routes | Tenant tries `/quan-ly-hoa-don/` or `/dashboard-admin/`. | Mention that views check login and `la_admin(request)`. |
| Smart Room owner checks | Tenant can open own FaceProfile but not another profile. | Good if using prepared IDs. |

Technical explanation:

- Tenant-private views resolve `NguoiThue` from `request.user`.
- Detail queries filter by tenant owner, not by URL id alone.
- Admin routes require authenticated admin checks.
- Mutating routes generally require POST and CSRF-protected forms.

## 10. Responsive Checks

Check at three widths:

- Desktop: 1366px or presentation projector width
- Tablet-ish: about 768px
- Mobile: about 390px

Priority pages:

| Area | Desktop | Tablet | Mobile |
| --- | --- | --- | --- |
| Admin dashboard `/dashboard-admin/` | [ ] cards/tables readable | [ ] layout wraps | [ ] no overlap |
| Room list/detail `/phong/`, `/phong/<id>/` | [ ] room cards/list readable | [ ] filters usable | [ ] CTA visible |
| Tenant invoice detail `/hoa-don-cua-toi/<id>/` | [ ] totals/status clear | [ ] sections stack | [ ] buttons fit |
| Tenant payment `/hoa-don-cua-toi/<id>/thanh-toan/` | [ ] form clear | [ ] confirmation readable | [ ] submit button visible |
| Admin forms `/quan-ly-phong/tao/`, `/quan-ly-hoa-don/tao/` | [ ] fields align | [ ] labels readable | [ ] no horizontal breakage |
| Smart Room FaceProfile detail | [ ] status/actions clear | [ ] image/status readable | [ ] action buttons fit |
| Face ID terminal `/smart-room/face-id/` | [ ] video visible | [ ] controls reachable | [ ] camera area not clipped |

For the live defense, prioritize desktop/projector and the actual browser zoom level.

## 11. Presentation Script

### Step 1 - Login And Overview

Screen: `/dang-nhap/`, then `/dashboard-admin/`

Action: Admin logs in and opens dashboard.

What to say:

"Day la he thong quan ly nha tro NDT Motel. He thong co hai nhom nguoi dung chinh: quan tri vien va nguoi thue. Quan tri vien quan ly phong, dat phong, hop dong, hoa don, sua chua, thong bao va Smart Room."

Technical point:

Authentication uses Django users; admin pages are protected by admin-role checks.

Expected result:

Dashboard opens with admin navigation and summary data.

### Step 2 - Facility And Room Inventory

Screen: `/quan-ly-co-so/`, `/quan-ly-phong/`, room detail/edit if needed

Action: Show facility and room list.

What to say:

"Moi phong thuoc mot co so. Phong co trang thai, gia thue, suc chua va thong tin phuc vu dat phong."

Technical point:

Room number is unique inside a facility; room status is synchronized with booking/contract state.

Expected result:

Facility and room data display correctly.

### Step 3 - Tenant Booking

Screen: Tenant `/phong/`, `/phong/<id>/`, `/phong/<id>/dat/`

Action: Show room detail and booking request form, or submit only with a disposable room.

What to say:

"Nguoi thue co the xem phong trong va gui yeu cau dat phong. Yeu cau ban dau o trang thai cho duyet, khong tu dong tao hop dong."

Technical point:

Booking creation re-checks room availability and tenant data in a transaction.

Expected result:

Booking form works or prepared pending booking is visible.

### Step 4 - Admin Booking And Contract

Screen: `/quan-ly-dat-phong/`, `/quan-ly-dat-phong/<id>/`, `/quan-ly-hop-dong/<id>/`

Action: Admin inspects pending booking and shows an active contract.

What to say:

"Quan tri vien kiem tra yeu cau dat phong, sau do moi tao va kich hoat hop dong. Hop dong la lien ket chinh giua nguoi thue, phong va cac nghiep vu sau nay."

Technical point:

One booking maps to one contract; contract state and dates protect later billing and access control.

Expected result:

Booking and contract details open correctly.

### Step 5 - Billing Payment Request

Screen: Tenant `/hoa-don-cua-toi/<id>/`, `/hoa-don-cua-toi/<id>/thanh-toan/`

Action: Tenant sends payment request.

What to say:

"Nguoi thue chi gui yeu cau xac nhan thanh toan. He thong khong cho nguoi thue tu chuyen hoa don sang da thanh toan."

Technical point:

Tenant payment request changes state to `cho_xac_nhan` inside a transaction; admin remains the confirmer.

Expected result:

Invoice enters pending confirmation state.

### Step 6 - Admin Payment Confirmation

Screen: Admin `/quan-ly-hoa-don/<id>/`

Action: Admin confirms pending invoice.

What to say:

"Quan tri vien kiem tra yeu cau va xac nhan. Khi xac nhan, he thong luu nguoi xac nhan, thoi diem thanh toan va lich su thanh toan."

Technical point:

This separates request from settlement and gives an audit trail.

Expected result:

Invoice becomes `da_thanh_toan`; payment history appears.

### Step 7 - Repair And Notification

Screen: Tenant repair list/create, admin repair detail, tenant notifications

Action: Show prepared repair request and notification.

What to say:

"Sau khi co hop dong, nguoi thue co the gui yeu cau sua chua va nhan thong bao. Moi nguoi thue chi thay du lieu cua minh."

Technical point:

Tenant-private pages filter records by the logged-in tenant.

Expected result:

Repair and notification screens open and show correct tenant data.

### Step 8 - Smart Room / Face ID

Screen: Tenant FaceProfile detail, admin `/smart-room/face-id/`, `/smart-room/lich-su-ra-vao/`

Action: Enroll or show stored profile; perform live camera authentication only if pre-tested.

What to say:

"Smart Room gom ho so khuon mat, quyen ra vao gan voi hop dong/phong, va lich su ra vao. Khi nhan dien thanh cong, he thong ghi lai su kien ra vao."

Technical point:

Access is allowed only when permission, contract, room, subject, status, and dates are all valid.

Expected result:

Either live authorization succeeds and history is created, or fallback screens show stored profile/permission/history.

### Step 9 - Audit And Reliability

Screen: `/nhat-ky-thao-tac/`, mention tests

Action: Show audit log and summarize test baseline.

What to say:

"Ngoai giao dien, em co bo test tu dong bao ve cac nghiep vu quan trong: dat phong, hop dong, thanh toan, phan quyen, Smart Room va giao dien tenant/admin. Hien tai 154 test dang pass."

Technical point:

Transactions, row locks, ownership filters, and tests reduce data integrity and permission risks.

Expected result:

Audit log opens; presentation closes with readiness evidence.

## 12. Likely Teacher Questions And Answer Notes

| Question | Concise answer |
| --- | --- |
| Why Django? | Django provides routing, ORM, authentication, templates, migrations, admin tooling, and testing in one framework, which fits a data-heavy motel management system. |
| How does authorization work? | Views check `request.user.is_authenticated`; admin routes additionally check `la_admin(request)`. Tenant routes load `NguoiThue` from the logged-in user and filter records by that tenant. |
| How is tenant ownership protected? | Detail views query by both object id and tenant owner, for example invoice/repair/notification pages only return records owned by the current tenant. Tests cover cross-tenant blocking. |
| Why cannot tenant directly mark invoice paid? | To avoid fraud or accidental settlement. Tenant sends a request, state becomes `cho_xac_nhan`, and admin confirms after checking. |
| How does payment confirmation work? | Admin opens pending invoice and confirms through `xu_ly_hoa_don`; the system stores paid state, confirmation metadata, and payment history. |
| How is overdue invoice synchronized? | The command `dong_bo_hoa_don_qua_han` updates unpaid invoices past due. It is explicit so page views do not unexpectedly mutate billing state. |
| Why use a management command? | Date-based lifecycle changes should be predictable and schedulable. A command can be run manually for demo or scheduled in production. |
| How is contract/room integrity protected? | Booking and contract flows re-check room state, capacity, dates, and current contract state, often inside transactions with row locking. |
| How does Smart Room work? | A FaceProfile is linked to a tenant or roommate. Access permission is bound to room and contract. Camera recognition compares the face and then validates permission eligibility before allowing access. |
| How is access history stored? | Each access attempt creates a `LichSuRaVao` record with room, subject, event type, source such as `camera`, time, and notes like allowed/denied. |
| How are database transactions handled? | Critical mutation flows use `transaction.atomic()` and selected rows use `select_for_update()` to avoid double-submit and stale-state races. |
| How do tests protect the system? | The suite covers booking, contract lifecycle, payment states, cross-tenant authorization, Smart Room permission binding, migrations, and UI render contracts. Current baseline is 154 passing tests. |
| What must change for production deployment? | Set `DEBUG=False`, move `SECRET_KEY` and database credentials to environment variables, configure `ALLOWED_HOSTS`, static/media serving, real email backend, backups, HTTPS, scheduled lifecycle commands, and monitoring/logging. |
| Does Face ID include anti-spoofing? | Do not overclaim. The current flow uses camera capture, detection, feature extraction/comparison, and permission validation. Liveness/anti-spoofing should be future work unless separately implemented. |
| What happens if camera fails during defense? | Show stored FaceProfile, access permission, and access history screens, and state clearly that live camera behavior depends on device/browser permissions. |

## 13. Final Presentation-Day Checklist

### Environment

- [ ] Correct project folder opened: `D:\NDT_MOTEL`
- [ ] Virtual environment available: `.\venv\Scripts\python.exe`
- [ ] Database service running
- [ ] Correct demo database selected
- [ ] Static files and media files accessible in development server
- [ ] No unrelated migration prompt

### Baseline Commands

- [ ] `.\venv\Scripts\python.exe manage.py check`
- [ ] `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run`
- [ ] `.\venv\Scripts\python.exe manage.py test`
- [ ] Optional data integrity check: `.\venv\Scripts\python.exe manage.py kiem_tra_toan_ven_du_lieu`
- [ ] If demonstrating date-sensitive states: `.\venv\Scripts\python.exe manage.py dong_bo_hop_dong`
- [ ] If demonstrating overdue invoices: `.\venv\Scripts\python.exe manage.py dong_bo_hoa_don_qua_han`

### Server And Browser

- [ ] Start server: `.\venv\Scripts\python.exe manage.py runserver`
- [ ] Open local URL in browser
- [ ] Admin browser profile logged out before starting
- [ ] Tenant browser profile logged out before starting
- [ ] Browser zoom set to 100% or projector-friendly value
- [ ] Camera permission allowed for local site
- [ ] If using LAN/projector URL, `ALLOWED_HOSTS` is handled for that environment

### Accounts

- [ ] Admin username/password known
- [ ] Tenant A username/password known
- [ ] Tenant B username/password known
- [ ] Admin can access `/dashboard-admin/`
- [ ] Tenant can access `/tai-khoan/`
- [ ] Tenant cannot access admin route

### Demo Data

- [ ] Facility exists
- [ ] Available room exists
- [ ] Occupied room exists
- [ ] Pending booking exists
- [ ] Active contract exists for Tenant A
- [ ] Unpaid invoice exists for Tenant A
- [ ] Pending-confirmation invoice exists as backup
- [ ] Paid invoice and payment history exist
- [ ] Repair request exists
- [ ] Tenant notification exists
- [ ] FaceProfile exists or can be created for Tenant A
- [ ] Active access permission exists for Smart Room
- [ ] Access history exists or can be created live
- [ ] Spare records exist for destructive/state-changing demo steps

### Demo Order

- [ ] Admin login/dashboard
- [ ] Facility/room management
- [ ] Tenant room/booking
- [ ] Admin booking/contract
- [ ] Tenant invoice/payment request
- [ ] Admin payment confirmation/history
- [ ] Repair request
- [ ] Notifications
- [ ] Smart Room FaceProfile/terminal/history
- [ ] Audit log/tests/deployment notes

### Backup And Fallback

- [ ] Backup/snapshot of demo database available
- [ ] Screenshots or stored records available if camera fails
- [ ] Know which invoice/booking records are safe to mutate
- [ ] Know which records must remain untouched
- [ ] Face ID fallback explanation ready

## 14. Final Notes

This project is ready to present as a local graduation demo if the manual browser and camera checklist passes on the actual machine. The strongest story is:

1. Tenant self-service request.
2. Admin-controlled approval/confirmation.
3. Contract-centered room and billing integrity.
4. Smart Room access controlled by current contract and permission.
5. Audit trail and tests protecting the workflows.

Keep claims realistic. The project demonstrates a working motel management system with strong business workflow coverage; it is not yet a hardened public production deployment.

