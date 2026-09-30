"""Explicit isolated browser audit for Module 11; excluded from normal discovery."""

import json
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.dich_vu.dat_phong import create_booking
from core.dich_vu.tien_coc import get_or_create_deposit, report_paid
from core.models import (
    CoSo,
    DatPhong,
    FaceProfile,
    HoaDon,
    HopDong,
    LichSuRaVao,
    NguoiOCungPhong,
    NguoiThue,
    Phong,
    QuyenRaVao,
    ThongBao,
    YeuCauGhepNguoi,
    YeuCauSuaChua,
)


class Module11FinalVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        today = timezone.localdate()
        self.admin = User.objects.create_user("module11-admin", is_staff=True)
        self.tenant_user = User.objects.create_user("module11-tenant")
        self.booking_user = User.objects.create_user("module11-booking")
        self.visitor_user = User.objects.create_user("module11-visitor")
        self.empty_user = User.objects.create_user("module11-empty")

        self.tenant = self._tenant(
            self.tenant_user, "Nguyen Minh Module 11", "000000001101"
        )
        self.booking_tenant = self._tenant(
            self.booking_user, "Tran An Dat Phong", "000000001102"
        )
        self.visitor = self._tenant(
            self.visitor_user, "Le Gia O Ghep", "000000001103"
        )
        self._tenant(self.empty_user, "Pham An Trong", "000000001104")

        self.facility = CoSo.objects.create(
            ten_co_so="NDT Motel Module 11",
            dia_chi="Du lieu kiem thu co lap",
            quan="Cam Le",
        )
        self.room = Phong.objects.create(
            co_so=self.facility,
            so_phong="M11-01",
            loai_phong="phong_tieu_chuan",
            gia_thue=Decimal("3200000"),
            dien_tich=Decimal("28"),
            so_nguoi_toi_da=4,
            tien_coc_mac_dinh=Decimal("500000"),
            trang_thai="dang_thue",
        )
        self.available_room = Phong.objects.create(
            co_so=self.facility,
            so_phong="M11-02",
            loai_phong="phong_cao_cap",
            gia_thue=Decimal("3600000"),
            dien_tich=Decimal("31"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("600000"),
            trang_thai="trong",
        )
        self.account_room = Phong.objects.create(
            co_so=self.facility,
            so_phong="M11-03",
            loai_phong="phong_gac_lung",
            gia_thue=Decimal("3400000"),
            dien_tich=Decimal("30"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("550000"),
            trang_thai="trong",
        )
        active_booking = DatPhong.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            ngay_nhan_phong=today - timedelta(days=120),
            ngay_tra_du_kien=today + timedelta(days=60),
            so_thang_thue=6,
            trang_thai="da_duyet",
        )
        self.contract = HopDong.objects.create(
            dat_phong=active_booking,
            so_hop_dong="M11-ACTIVE",
            ngay_bat_dau=today - timedelta(days=120),
            ngay_ket_thuc=today + timedelta(days=60),
            tien_thue_thang=Decimal("3200000"),
            tien_coc=Decimal("500000"),
            trang_thai="dang_hieu_luc",
            so_nguoi_o=2,
            cho_phep_ghep=True,
        )
        self.account_booking = DatPhong.objects.create(
            nguoi_thue=self.tenant,
            phong=self.account_room,
            ngay_nhan_phong=today + timedelta(days=14),
            ngay_tra_du_kien=today + timedelta(days=104),
            so_thang_thue=3,
            trang_thai="cho_duyet",
        )
        self.pending_booking = create_booking(
            actor=self.booking_user,
            room_id=self.available_room.pk,
            checkin=today + timedelta(days=7),
            months=3,
            people=1,
            companions=[],
            accept_terms=True,
            note="Du lieu visual QA Module 11.",
        )
        payment = get_or_create_deposit(
            actor=self.booking_user, booking_id=self.pending_booking.pk
        )
        report_paid(
            actor=self.booking_user,
            payment_id=payment.pk,
            bank_transaction="M11-BANK-001",
        )

        self.resident = NguoiOCungPhong.objects.create(
            hop_dong=self.contract,
            ho_ten="Vo Hoang Nam",
            cccd="000000001105",
            so_dien_thoai="0900001105",
            quan_he="Ban be",
            ngay_vao=today - timedelta(days=30),
        )
        self.sharing = YeuCauGhepNguoi.objects.create(
            hop_dong=self.contract,
            nguoi_dang_ky=self.visitor,
            ho_ten=self.visitor.ho_ten,
            cccd=self.visitor.cccd,
            so_dien_thoai=self.visitor.so_dien_thoai,
            quan_he="Dong nghiep",
            ngay_du_kien_vao=today + timedelta(days=5),
        )
        self.repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            tieu_de="Dieu hoa khong lanh",
            noi_dung="Dieu hoa van chay nhung khong lam lanh.",
            loai_su_co="thiet_bi",
            muc_do="cao",
            trang_thai="dang_xu_ly",
            nguoi_xu_ly="To ky thuat",
        )
        self.invoice = HoaDon.objects.create(
            hop_dong=self.contract,
            thang=today.month,
            nam=today.year,
            tien_phong=Decimal("3200000"),
            tien_dien=Decimal("180000"),
            tien_nuoc=Decimal("90000"),
            tien_dich_vu=Decimal("120000"),
            han_thanh_toan=today + timedelta(days=7),
        )
        self.notice = ThongBao.objects.create(
            nguoi_thue=self.tenant,
            tieu_de="Lich bao tri dinh ky",
            noi_dung="Ky thuat vien se kiem tra thiet bi theo lich.",
            loai="bao_tri",
            muc_do="quan_trong",
        )
        self.admin_notice = ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Can doi soat dat coc",
            noi_dung="Co giao dich moi dang cho quan tri xac nhan.",
            loai="thanh_toan",
            muc_do="quan_trong",
        )
        self.face = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
        )
        self.permission = QuyenRaVao.objects.create(
            phong=self.room,
            nguoi_thue=self.tenant,
            loai_quyen="chu_phong",
            trang_thai="hoat_dong",
            ngay_bat_dau=today - timedelta(days=120),
            ngay_ket_thuc=today + timedelta(days=60),
            hop_dong=self.contract,
            nguon_cap="thu_cong",
            nguoi_tao=self.admin,
        )
        self.access_log = LichSuRaVao.objects.create(
            quyen_ra_vao=self.permission,
            phong=self.room,
            nguoi_thue=self.tenant,
            ten_nguoi=self.tenant.ho_ten,
            loai_su_kien="vao",
            nguon="camera",
            thoi_diem=timezone.now(),
        )

    @staticmethod
    def _tenant(user, name, cccd):
        return NguoiThue.objects.create(
            tai_khoan=user,
            ho_ten=name,
            cccd=cccd,
            so_dien_thoai="09" + cccd[-8:],
            email=f"{user.username}@example.com",
        )

    @staticmethod
    def _cookie(user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def _screens(self):
        admin = self.admin
        tenant = self.tenant_user
        booking = self.booking_user
        visitor = self.visitor_user
        empty = self.empty_user
        return [
            ("m08_admin_dashboard", admin, reverse("dashboard_admin")),
            ("m01_admin_room_list", admin, reverse("quan_ly_phong")),
            ("m01_admin_room_create", admin, reverse("tao_phong")),
            ("m01_admin_room_edit", admin, reverse("sua_phong", args=[self.room.pk])),
            ("m02_tenant_room_list", tenant, reverse("danh_sach_phong")),
            ("m02_tenant_room_detail", tenant, reverse("chi_tiet_phong", args=[self.available_room.pk])),
            ("m02_tenant_booking_create", tenant, reverse("dat_phong", args=[self.available_room.pk])),
            ("m02_tenant_booking_list", booking, reverse("dat_phong_cua_toi")),
            ("m02_tenant_booking_detail", booking, reverse("chi_tiet_dat_phong_cua_toi", args=[self.pending_booking.pk])),
            ("m02_tenant_deposit", booking, reverse("thanh_toan_coc_cua_toi", args=[self.pending_booking.pk])),
            ("m02_tenant_booking_empty", empty, reverse("dat_phong_cua_toi")),
            ("m03_admin_booking_list", admin, reverse("quan_ly_dat_phong")),
            ("m03_admin_booking_detail", admin, reverse("chi_tiet_dat_phong", args=[self.pending_booking.pk])),
            ("m04_admin_contract_list", admin, reverse("quan_ly_hop_dong")),
            ("m04_admin_contract_detail", admin, reverse("chi_tiet_hop_dong", args=[self.contract.pk])),
            ("m04_tenant_contract_list", tenant, reverse("hop_dong_cua_toi")),
            ("m04_tenant_contract_detail", tenant, reverse("chi_tiet_hop_dong_cua_toi", args=[self.contract.pk])),
            ("m05_admin_tenant_list", admin, reverse("quan_ly_nguoi_thue")),
            ("m05_admin_resident_list", admin, reverse("quan_ly_nguoi_o_cung")),
            ("m05_admin_sharing_list", admin, reverse("quan_ly_yeu_cau_ghep")),
            ("m05_tenant_sharing_list", tenant, reverse("yeu_cau_ghep_cua_toi")),
            ("m05_tenant_sharing_register", empty, reverse("dang_ky_ghep_phong", args=[self.room.pk])),
            ("invoice_admin_list", admin, reverse("quan_ly_hoa_don")),
            ("invoice_admin_detail", admin, reverse("chi_tiet_hoa_don", args=[self.invoice.pk])),
            ("invoice_tenant_list", tenant, reverse("hoa_don_cua_toi")),
            ("invoice_tenant_detail", tenant, reverse("chi_tiet_hoa_don_cua_toi", args=[self.invoice.pk])),
            ("m06_admin_repair_list", admin, reverse("quan_ly_sua_chua")),
            ("m06_admin_repair_detail", admin, reverse("chi_tiet_sua_chua", args=[self.repair.pk])),
            ("m06_tenant_repair_list", tenant, reverse("yeu_cau_sua_chua_cua_toi")),
            ("m06_tenant_repair_create", tenant, reverse("tao_yeu_cau_sua_chua")),
            ("m07_admin_notification_list", admin, reverse("quan_ly_thong_bao")),
            ("m07_admin_notification_empty", admin, reverse("quan_ly_thong_bao") + "?q=khong-co-ket-qua"),
            ("m07_tenant_notification_list", tenant, reverse("thong_bao_cua_toi")),
            ("m07_tenant_notification_empty", empty, reverse("thong_bao_cua_toi")),
            ("m09_admin_smart_dashboard", admin, reverse("smart_room_dashboard")),
            ("m09_admin_face_terminal", admin, reverse("trang_xac_thuc_face_id")),
            ("m09_tenant_face_unavailable", empty, reverse("nhan_dien_su_dung_phong")),
            ("m10_tenant_account", tenant, reverse("tai_khoan")),
            ("m10_tenant_profile", tenant, reverse("cap_nhat_thong_tin")),
            ("m10_tenant_password", tenant, reverse("doi_mat_khau_user")),
            ("m10_admin_password", admin, reverse("doi_mat_khau")),
        ]

    def test_final_visual_audit(self):
        label = os.environ.get("NDT_SYSTEM_UI_AUDIT_LABEL", "current")
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru"
            / "kiem_thu"
            / "system_ui_upgrade"
            / label
        )
        output.mkdir(parents=True, exist_ok=True)
        viewports = {
            "1440": (1440, 900),
            "1024": (1024, 768),
            "768": (768, 900),
            "390": (390, 844),
        }
        screens = self._screens()
        users = {user.pk: user for _, user, _ in screens}
        cookies = {pk: self._cookie(user) for pk, user in users.items()}
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        results = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for screen, user, path in screens:
                for viewport, (width, height) in viewports.items():
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.add_cookies([{
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": cookies[user.pk],
                        "url": self.live_server_url,
                    }])
                    page = context.new_page()
                    errors = []
                    page.on(
                        "console",
                        lambda message: errors.append(
                            f"console:{message.type}:{message.text}"
                        ) if message.type == "error" else None,
                    )
                    page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                    page.on("dialog", lambda dialog: errors.append(f"native-dialog:{dialog.type}"))
                    response = page.goto(self.live_server_url + path, wait_until="networkidle")
                    dialog_keyboard = None
                    dialog_selector = None
                    if viewport == "390" and screen == "m01_admin_room_list":
                        dialog_selector = "[data-ndt-confirm-form] button[type=submit]"
                    elif viewport == "390" and screen == "m10_tenant_account":
                        dialog_selector = "[data-cancel-booking-form] button[type=submit]"
                    if dialog_selector:
                        trigger = page.locator(dialog_selector).first
                        trigger.focus()
                        trigger.click()
                        dialog = page.locator("[data-ndt-dialog]")
                        dialog_keyboard = {
                            "opened": dialog.is_visible(),
                            "focused_confirm": page.locator("[data-ndt-dialog-confirm]").evaluate(
                                "element => element === document.activeElement"
                            ),
                        }
                        page.keyboard.press("Escape")
                        dialog_keyboard["closed_with_escape"] = dialog.is_hidden()
                        dialog_keyboard["focus_returned"] = trigger.evaluate(
                            "element => element === document.activeElement"
                        )
                    page.keyboard.press("Tab")
                    metrics = page.evaluate(
                        """() => {
                            const visible = element => {
                                const style = getComputedStyle(element);
                                const rect = element.getBoundingClientRect();
                                return style.display !== 'none' && style.visibility !== 'hidden'
                                    && rect.width > 0 && rect.height > 0;
                            };
                            const controls = [...document.querySelectorAll('input, select, textarea')]
                                .filter(element => element.type !== 'hidden' && visible(element));
                            const unlabeled = controls.filter(element => {
                                if (element.getAttribute('aria-label') || element.getAttribute('aria-labelledby') || element.title) return false;
                                if (element.closest('label')) return false;
                                return !element.id || !document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
                            }).map(element => element.name || element.id || element.tagName);
                            const unnamedActions = [...document.querySelectorAll('button, a[href]')]
                                .filter(visible)
                                .filter(element => !(element.innerText || '').trim()
                                    && !element.getAttribute('aria-label') && !element.title
                                    && !element.querySelector('img[alt]'))
                                .map(element => element.outerHTML.slice(0, 160));
                            const badHrefs = [...document.querySelectorAll('a[href]')]
                                .map(element => element.getAttribute('href'))
                                .filter(href => !href || href === '#' || href.startsWith('javascript:'));
                            const text = document.body.innerText;
                            const rawEnums = text.match(/\b(?:cho_duyet|da_duyet|tu_choi|da_huy|dang_hieu_luc|sap_het_han|dang_xu_ly|chua_thanh_toan|cho_xac_nhan|da_xac_thuc|tam_khoa|bi_thu_hoi)\b/g) || [];
                            const mojibake = text.match(/(?:Ã[\u0080-\u00bf]|Â[· ]|Ä[\u0080-\u00bf]|Æ[\u0080-\u00bf]|áº|á»|â€|ï¿½)/g) || [];
                            const active = document.activeElement;
                            const focusStyle = active ? getComputedStyle(active) : null;
                            return {
                                cw: document.documentElement.clientWidth,
                                sw: document.documentElement.scrollWidth,
                                broken: [...document.images].filter(image => image.complete && image.naturalWidth === 0).length,
                                unlabeled,
                                unnamedActions,
                                badHrefs,
                                rawEnums: [...new Set(rawEnums)],
                                mojibake: [...new Set(mojibake)],
                                focusTag: active ? active.tagName : null,
                                focusVisible: !!active && active !== document.body && focusStyle
                                    && (focusStyle.outlineStyle !== 'none' || focusStyle.boxShadow !== 'none'),
                                foundation: !!document.querySelector('.ndt-foundation'),
                                title: document.title,
                            };
                        }"""
                    )
                    screenshot = output / f"{screen}_{viewport}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    results.append({
                        "screen": screen,
                        "role": "admin" if user.is_staff else "tenant",
                        "path": path,
                        "viewport": f"{width}x{height}",
                        "status": response.status if response else None,
                        "overflow": metrics["sw"] > metrics["cw"],
                        "broken_images": metrics["broken"],
                        "errors": errors,
                        "unlabeled_controls": metrics["unlabeled"],
                        "unnamed_actions": metrics["unnamedActions"],
                        "bad_hrefs": metrics["badHrefs"],
                        "raw_enums": metrics["rawEnums"],
                        "mojibake": metrics["mojibake"],
                        "focus_tag": metrics["focusTag"],
                        "focus_visible": metrics["focusVisible"],
                        "dialog_keyboard": dialog_keyboard,
                        "foundation_root": metrics["foundation"],
                        "title": metrics["title"],
                        "screenshot": screenshot.name,
                    })
                    context.close()
            browser.close()

        summary = {
            "screen_count": len(screens),
            "case_count": len(results),
            "viewports": [f"{w}x{h}" for w, h in viewports.values()],
            "cases": results,
        }
        (output / "results.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        self.assertEqual(len(results), len(screens) * len(viewports))
        for result in results:
            self.assertEqual(result["status"], 200, result)
            self.assertFalse(result["overflow"], result)
            self.assertEqual(result["broken_images"], 0, result)
            self.assertEqual(result["errors"], [], result)
            self.assertEqual(result["mojibake"], [], result)
            self.assertEqual(result["raw_enums"], [], result)
            if result["dialog_keyboard"] is not None:
                self.assertEqual(
                    result["dialog_keyboard"],
                    {
                        "opened": True,
                        "focused_confirm": True,
                        "closed_with_escape": True,
                        "focus_returned": True,
                    },
                    result,
                )

