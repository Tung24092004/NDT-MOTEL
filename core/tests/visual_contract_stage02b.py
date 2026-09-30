"""Audit trình duyệt cô lập cho Chặng 2B: hợp đồng của User."""

import json
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.models import CoSo, DatPhong, HopDong, NguoiThue, Phong, YeuCauGiaHanHopDong


class ContractStage02BVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user("stage02b-admin", is_staff=True)
        self.user = User.objects.create_user("stage02b-tenant")
        self.empty_user = User.objects.create_user("stage02b-empty")
        self.other_user = User.objects.create_user("stage02b-other")
        self.tenant = self._tenant(self.user, "Nguyen Minh Anh", "000000003001")
        self._tenant(self.empty_user, "Le An Nhien", "000000003002")
        self.other_tenant = self._tenant(self.other_user, "Tran Gia Han", "000000003003")
        self.facility = CoSo.objects.create(
            ten_co_so="NDT Motel Hoa Xuan",
            dia_chi="125 Nguyen Phuoc Lan",
            quan="Cam Le",
        )

        self.active = self._contract("B301", -60, 120, "dang_hieu_luc", Decimal("3400000"))
        self.renewable = self._contract("B302", -160, 20, "sap_het_han", Decimal("3600000"))
        self.pending = self._contract("B303", -170, 10, "sap_het_han", Decimal("3750000"))
        self.upcoming = self._contract("B304", 15, 195, "cho_hieu_luc", Decimal("3900000"))
        self.expired = self._contract("B305", -190, -10, "da_het_han", Decimal("3200000"))
        self.cancelled = self._contract("B306", -90, 90, "da_huy", Decimal("3500000"))
        self.other_contract = self._contract(
            "B399", -30, 150, "dang_hieu_luc", Decimal("4100000"), self.other_tenant
        )

        YeuCauGiaHanHopDong.objects.create(
            hop_dong=self.pending,
            nguoi_yeu_cau=self.tenant,
            so_thang_gia_han=3,
            ngay_ket_thuc_cu=self.pending.ngay_ket_thuc,
            ngay_ket_thuc_de_xuat=self.pending.ngay_ket_thuc + timedelta(days=92),
            ly_do="Tiep tuc thue phong de lam viec tai Da Nang.",
            trang_thai="cho_duyet",
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

    def _contract(self, room_number, start_delta, end_delta, status, rent, tenant=None):
        tenant = tenant or self.tenant
        room = Phong.objects.create(
            co_so=self.facility,
            so_phong=room_number,
            tang=3,
            loai_phong="phong_cao_cap",
            gia_thue=rent,
            dien_tich=Decimal("30"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("700000"),
            trang_thai="trong",
        )
        booking = DatPhong.objects.create(
            nguoi_thue=tenant,
            phong=room,
            ngay_nhan_phong=self.today + timedelta(days=start_delta),
            ngay_tra_du_kien=self.today + timedelta(days=end_delta),
            so_thang_thue=6,
            so_nguoi_o=2,
            trang_thai="da_duyet",
        )
        return HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong=f"HD-{room_number}-STAGE02B",
            ngay_bat_dau=self.today + timedelta(days=start_delta),
            ngay_ket_thuc=self.today + timedelta(days=end_delta),
            tien_coc=Decimal("700000"),
            tien_thue_thang=rent,
            ngay_thanh_toan_hang_thang=5,
            phuong_thuc_thanh_toan="chuyen_khoan",
            so_nguoi_o=2,
            cho_phep_ghep=False,
            tien_phat_tre_han=Decimal("100000"),
            dieu_khoan="Thanh toan tien phong dung han. Bao truoc cho quan ly khi thay doi nguoi o.",
            ghi_chu="Hop dong duoc tao tu fixture kiem thu co lap.",
            trang_thai=status,
            nguoi_tao=self.admin,
        )

    @staticmethod
    def _cookie(user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    @staticmethod
    def _metrics(page):
        return page.evaluate(
            """() => {
                const visible = element => {
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden'
                        && rect.width > 0 && rect.height > 0;
                };
                const actions = [...document.querySelectorAll('.contract-management a[href], .contract-management button')]
                    .filter(visible)
                    .map(element => ({
                        text: (element.innerText || element.getAttribute('aria-label') || '').trim(),
                        href: element.getAttribute('href'),
                        type: element.getAttribute('type'),
                    }));
                const controls = [...document.querySelectorAll('.contract-management input, .contract-management select, .contract-management textarea')]
                    .filter(element => element.type !== 'hidden' && visible(element));
                const unlabeled = controls.filter(element => {
                    if (element.getAttribute('aria-label') || element.getAttribute('aria-labelledby')) return false;
                    if (element.closest('label')) return false;
                    return !element.id || !document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
                }).map(element => element.name || element.id);
                const buttons = [...document.querySelectorAll('.contract-management button, .contract-management .ndt-button')]
                    .filter(visible);
                return {
                    client_width: document.documentElement.clientWidth,
                    scroll_width: document.documentElement.scrollWidth,
                    broken_images: [...document.images].filter(image => image.complete && image.naturalWidth === 0).length,
                    contract_count: document.querySelectorAll('.contract-card').length,
                    actions,
                    unlabeled,
                    small_buttons: buttons.filter(element => {
                        const rect = element.getBoundingClientRect();
                        return rect.width < 44 || rect.height < 44;
                    }).map(element => (element.innerText || element.getAttribute('aria-label') || '').trim()),
                };
            }"""
        )

    def test_stage02b_visual_routes_states_and_permissions(self):
        label = os.environ.get("NDT_CONTRACT_STAGE02B_LABEL", "before")
        output = Path(settings.BASE_DIR) / "luu_tru" / "kiem_thu" / "uiux_stage_02b_contract" / label
        output.mkdir(parents=True, exist_ok=True)
        screens = (
            ("contract_list_many", self.user, reverse("hop_dong_cua_toi")),
            ("contract_list_empty", self.empty_user, reverse("hop_dong_cua_toi")),
            ("contract_detail_active", self.user, reverse("chi_tiet_hop_dong_cua_toi", args=[self.active.pk])),
            ("contract_detail_renewable", self.user, reverse("chi_tiet_hop_dong_cua_toi", args=[self.renewable.pk])),
            ("contract_detail_pending", self.user, reverse("chi_tiet_hop_dong_cua_toi", args=[self.pending.pk])),
            ("contract_detail_expired", self.user, reverse("chi_tiet_hop_dong_cua_toi", args=[self.expired.pk])),
        )
        viewports = (("1440", 1440, 900), ("1024", 1024, 768), ("768", 768, 900), ("390", 390, 844))
        cookies = {user.pk: self._cookie(user) for _, user, _ in screens}
        admin_cookie = self._cookie(self.admin)
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        results = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for screen, user, path in screens:
                for viewport, width, height in viewports:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.add_cookies([{
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": cookies[user.pk],
                        "url": self.live_server_url,
                    }])
                    page = context.new_page()
                    errors = []
                    page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
                    page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                    response = page.goto(self.live_server_url + path, wait_until="networkidle")
                    dialog_check = None
                    if screen == "contract_detail_pending" and viewport == "390":
                        trigger = page.locator("[data-contract-confirm] button[type=submit]")
                        trigger.focus()
                        trigger.click()
                        dialog = page.locator("[data-ndt-dialog]")
                        dialog.wait_for(state="visible")
                        dialog_check = {
                            "opened": dialog.is_visible(),
                            "confirm_focused": page.locator("[data-ndt-dialog-confirm]").evaluate("el => el === document.activeElement"),
                        }
                        page.keyboard.press("Escape")
                        dialog.wait_for(state="hidden")
                        dialog_check["closed"] = dialog.is_hidden()
                        dialog_check["focus_returned"] = trigger.evaluate("el => el === document.activeElement")
                    page.keyboard.press("Tab")
                    focus_visible = page.evaluate(
                        """() => {
                            const style = getComputedStyle(document.activeElement);
                            return document.activeElement !== document.body
                                && (style.outlineStyle !== 'none' || style.boxShadow !== 'none');
                        }"""
                    )
                    page.evaluate("window.scrollTo(0, 0)")
                    metrics = self._metrics(page)
                    screenshot = output / f"{screen}_{viewport}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    results.append({
                        "case": screen,
                        "viewport": f"{width}x{height}",
                        "path": path,
                        "status": response.status if response else None,
                        "overflow": metrics["scroll_width"] > metrics["client_width"],
                        "broken_images": metrics["broken_images"],
                        "contract_count": metrics["contract_count"],
                        "actions": metrics["actions"],
                        "unlabeled": metrics["unlabeled"],
                        "small_buttons": metrics["small_buttons"],
                        "errors": errors,
                        "focus_visible": focus_visible,
                        "dialog": dialog_check,
                        "screenshot": screenshot.name,
                    })
                    context.close()

            protected = (
                ("guest-list", None, reverse("hop_dong_cua_toi"), reverse("dang_nhap")),
                ("admin-list", self.admin, reverse("hop_dong_cua_toi"), reverse("dashboard_admin")),
                ("guest-detail", None, reverse("chi_tiet_hop_dong_cua_toi", args=[self.active.pk]), reverse("dang_nhap")),
                ("admin-detail", self.admin, reverse("chi_tiet_hop_dong_cua_toi", args=[self.active.pk]), reverse("dashboard_admin")),
            )
            for case, user, path, expected in protected:
                context = browser.new_context()
                if user:
                    context.add_cookies([{
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": admin_cookie,
                        "url": self.live_server_url,
                    }])
                page = context.new_page()
                response = page.goto(self.live_server_url + path, wait_until="networkidle")
                results.append({
                    "case": case,
                    "status": response.status if response else None,
                    "path": path,
                    "final_path": urlsplit(page.url).path,
                    "expected_path": expected,
                })
                context.close()
            browser.close()

        (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

        for result in results:
            self.assertEqual(result["status"], 200, result)
            if "expected_path" in result:
                self.assertEqual(result["final_path"], result["expected_path"], result)
                continue
            self.assertFalse(result["overflow"], result)
            self.assertEqual(result["broken_images"], 0, result)
            self.assertEqual(result["errors"], [], result)
            self.assertEqual(result["unlabeled"], [], result)
            self.assertTrue(result["focus_visible"], result)
            if result["dialog"]:
                self.assertEqual(
                    result["dialog"],
                    {"opened": True, "confirm_focused": True, "closed": True, "focus_returned": True},
                    result,
                )

        main = next(result for result in results if result["case"] == "contract_list_many")
        self.assertEqual(main["contract_count"], 6, main)
        empty = next(result for result in results if result["case"] == "contract_list_empty")
        self.assertEqual(empty["contract_count"], 0, empty)
        client = Client()
        client.force_login(self.user)
        self.assertEqual(
            client.get(reverse("chi_tiet_hop_dong_cua_toi", args=[self.other_contract.pk])).status_code,
            404,
        )
