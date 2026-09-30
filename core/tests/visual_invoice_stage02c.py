"""Audit trinh duyet co lap cho Chang 2C: hoa don cua User."""

import json
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.models import (
    CoSo,
    DatPhong,
    HoaDon,
    HopDong,
    LichSuThanhToan,
    NguoiThue,
    Phong,
)


class InvoiceStage02CVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user("stage02c-admin", is_staff=True)
        self.user = User.objects.create_user("stage02c-tenant")
        self.empty_user = User.objects.create_user("stage02c-empty")
        self.other_user = User.objects.create_user("stage02c-other")
        self.tenant = self._tenant(self.user, "Nguyen Minh Anh", "000000004001")
        self._tenant(self.empty_user, "Le An Nhien", "000000004002")
        self.other_tenant = self._tenant(self.other_user, "Tran Gia Han", "000000004003")
        self.facility = CoSo.objects.create(
            ten_co_so="NDT Motel Hoa Xuan",
            dia_chi="125 Nguyen Phuoc Lan",
            quan="Cam Le",
        )
        self.contract = self._contract("C401", self.tenant)
        self.other_contract = self._contract("C499", self.other_tenant)

        self.unpaid = self._invoice(9, 2026, "chua_thanh_toan", 5)
        self.pending = self._invoice(8, 2026, "cho_xac_nhan", -2)
        self.paid = self._invoice(7, 2026, "da_thanh_toan", -32)
        self.overdue = self._invoice(6, 2026, "qua_han", -62)
        self.cancelled = self._invoice(5, 2026, "huy", -92)
        self.foreign_invoice = self._invoice(
            9,
            2026,
            "chua_thanh_toan",
            5,
            contract=self.other_contract,
        )
        LichSuThanhToan.objects.create(
            hoa_don=self.paid,
            so_tien=self.paid.tong_tien,
            phuong_thuc="chuyen_khoan",
            ma_giao_dich="TCB-STAGE02C-001",
            noi_dung="Quan tri vien da doi soat va xac nhan tien ve.",
            nguoi_thuc_hien=self.admin,
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

    def _contract(self, room_number, tenant):
        room = Phong.objects.create(
            co_so=self.facility,
            so_phong=room_number,
            tang=4,
            loai_phong="phong_cao_cap",
            gia_thue=Decimal("3500000"),
            dien_tich=Decimal("30"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("700000"),
            trang_thai="dang_thue",
        )
        booking = DatPhong.objects.create(
            nguoi_thue=tenant,
            phong=room,
            ngay_nhan_phong=self.today - timedelta(days=180),
            ngay_tra_du_kien=self.today + timedelta(days=180),
            so_thang_thue=12,
            so_nguoi_o=2,
            trang_thai="da_duyet",
        )
        return HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong=f"HD-{room_number}-STAGE02C",
            ngay_bat_dau=self.today - timedelta(days=180),
            ngay_ket_thuc=self.today + timedelta(days=180),
            tien_coc=Decimal("700000"),
            tien_thue_thang=Decimal("3500000"),
            ngay_thanh_toan_hang_thang=5,
            phuong_thuc_thanh_toan="chuyen_khoan",
            so_nguoi_o=2,
            trang_thai="dang_hieu_luc",
            nguoi_tao=self.admin,
        )

    def _invoice(self, month, year, status, due_delta, contract=None):
        return HoaDon.objects.create(
            hop_dong=contract or self.contract,
            thang=month,
            nam=year,
            tien_phong=Decimal("3500000"),
            tien_dien=Decimal("286000"),
            tien_nuoc=Decimal("120000"),
            tien_dich_vu=Decimal("180000"),
            phi_khac=Decimal("75000"),
            chi_tiet_phi="Phi khac: ve sinh may lanh dinh ky.",
            han_thanh_toan=self.today + timedelta(days=due_delta),
            trang_thai=status,
            nguoi_lap=self.admin,
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
                const root = document.querySelector('.billing-page, .invoice-page');
                const controls = [...document.querySelectorAll('input, select, textarea')]
                    .filter(element => element.type !== 'hidden' && visible(element));
                const unlabeled = controls.filter(element => {
                    if (element.getAttribute('aria-label') || element.getAttribute('aria-labelledby')) return false;
                    if (element.closest('label')) return false;
                    return !element.id || !document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
                }).map(element => element.name || element.id);
                const buttons = [...document.querySelectorAll('a[href], button')]
                    .filter(element => root && root.contains(element) && visible(element));
                return {
                    client_width: document.documentElement.clientWidth,
                    scroll_width: document.documentElement.scrollWidth,
                    broken_images: [...document.images].filter(image => image.complete && image.naturalWidth === 0).length,
                    invoice_count: document.querySelectorAll('.invoice-row').length,
                    actions: buttons.map(element => ({
                        text: (element.innerText || element.getAttribute('aria-label') || '').trim(),
                        href: element.getAttribute('href'),
                        type: element.getAttribute('type'),
                    })),
                    unlabeled,
                    small_buttons: buttons.filter(element => {
                        const rect = element.getBoundingClientRect();
                        return rect.width < 44 || rect.height < 44;
                    }).map(element => (element.innerText || element.getAttribute('aria-label') || '').trim()),
                };
            }"""
        )

    def test_stage02c_visual_routes_states_payment_and_permissions(self):
        label = os.environ.get("NDT_INVOICE_STAGE02C_LABEL", "before")
        output = (
            Path(settings.BASE_DIR)
            / "luu_tru"
            / "kiem_thu"
            / "uiux_stage_02c_invoice"
            / label
        )
        output.mkdir(parents=True, exist_ok=True)
        screens = (
            ("invoice_list_many", self.user, reverse("hoa_don_cua_toi")),
            ("invoice_list_empty", self.empty_user, reverse("hoa_don_cua_toi")),
            ("invoice_detail_unpaid", self.user, reverse("chi_tiet_hoa_don_cua_toi", args=[self.unpaid.pk])),
            ("invoice_detail_pending", self.user, reverse("chi_tiet_hoa_don_cua_toi", args=[self.pending.pk])),
            ("invoice_detail_paid", self.user, reverse("chi_tiet_hoa_don_cua_toi", args=[self.paid.pk])),
        )
        viewports = (
            ("1920", 1920, 1080),
            ("1440", 1440, 900),
            ("1024", 1024, 768),
            ("768", 768, 900),
            ("390", 390, 844),
        )
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
                    page.on(
                        "console",
                        lambda message: errors.append(f"console:{message.type}:{message.text}")
                        if message.type == "error" else None,
                    )
                    page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                    response = page.goto(self.live_server_url + path, wait_until="networkidle")
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
                        "invoice_count": metrics["invoice_count"],
                        "actions": metrics["actions"],
                        "unlabeled": metrics["unlabeled"],
                        "small_buttons": metrics["small_buttons"],
                        "errors": errors,
                        "focus_visible": focus_visible,
                        "screenshot": screenshot.name,
                    })
                    context.close()

            # Xac minh CTA tren chi tiet mo dung luong VietQR va noi dung backend.
            context = browser.new_context(viewport={"width": 1024, "height": 768})
            context.add_cookies([{
                "name": settings.SESSION_COOKIE_NAME,
                "value": cookies[self.user.pk],
                "url": self.live_server_url,
            }])
            png = bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
                "0000000d49444154789c6360000000020001e221bc330000000049454e44ae426082"
            )
            context.route(
                "https://img.vietqr.io/**",
                lambda route: route.fulfill(status=200, content_type="image/png", body=png),
            )
            page = context.new_page()
            page.goto(
                self.live_server_url
                + reverse("thanh_toan_hoa_don_cua_toi", args=[self.unpaid.pk]),
                wait_until="networkidle",
            )
            page.locator(
                'input[name="phuong_thuc"][value="chuyen_khoan"]'
            ).check(force=True)
            page.get_by_role("button", name="Tiếp tục").click()
            qr = page.locator(".qr-image")
            qr.wait_for(state="visible")
            qr_src = qr.get_attribute("src")
            qr_query = parse_qs(urlsplit(qr_src).query)
            results.append({
                "case": "payment-vietqr",
                "status": 200,
                "qr_loaded": qr.evaluate("image => image.complete && image.naturalWidth > 0"),
                "qr_amount": qr_query.get("amount", [None])[0],
                "qr_content": qr_query.get("addInfo", [None])[0],
                "expected_amount": str(int(self.unpaid.tong_tien)),
                "expected_content": f"NDTMOTEL HD{self.unpaid.pk}",
            })
            context.close()

            protected = (
                ("guest-list", None, reverse("hoa_don_cua_toi"), reverse("dang_nhap")),
                ("admin-list", self.admin, reverse("hoa_don_cua_toi"), reverse("dashboard_admin")),
                ("guest-detail", None, reverse("chi_tiet_hoa_don_cua_toi", args=[self.unpaid.pk]), reverse("dang_nhap")),
                ("admin-detail", self.admin, reverse("chi_tiet_hoa_don_cua_toi", args=[self.unpaid.pk]), reverse("dashboard_admin")),
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

        (output / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for result in results:
            self.assertEqual(result["status"], 200, result)
            if result["case"] == "payment-vietqr":
                self.assertTrue(result["qr_loaded"], result)
                self.assertEqual(result["qr_amount"], result["expected_amount"], result)
                self.assertEqual(result["qr_content"], result["expected_content"], result)
                continue
            if "expected_path" in result:
                self.assertEqual(result["final_path"], result["expected_path"], result)
                continue
            self.assertFalse(result["overflow"], result)
            self.assertEqual(result["broken_images"], 0, result)
            self.assertEqual(result["errors"], [], result)
            self.assertEqual(result["unlabeled"], [], result)
            self.assertTrue(result["focus_visible"], result)

        main = next(result for result in results if result["case"] == "invoice_list_many")
        self.assertEqual(main["invoice_count"], 5, main)
        empty = next(result for result in results if result["case"] == "invoice_list_empty")
        self.assertEqual(empty["invoice_count"], 0, empty)
        client = Client()
        client.force_login(self.user)
        self.assertEqual(
            client.get(
                reverse("chi_tiet_hoa_don_cua_toi", args=[self.foreign_invoice.pk])
            ).status_code,
            404,
        )
