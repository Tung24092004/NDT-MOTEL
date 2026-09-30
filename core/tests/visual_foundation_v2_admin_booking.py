"""Isolated visual acceptance audit for Foundation V2 admin booking."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.dich_vu.dat_phong import create_booking
from core.dich_vu.tien_coc import get_or_create_deposit, report_paid
from core.models import CoSo, NguoiThue, Phong


class FoundationV2AdminBookingVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.admin = User.objects.create_user("v2-admin", password="unused", is_staff=True)
        self.tenant_user = User.objects.create_user("v2-tenant", password="unused")
        tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="Nguyễn Minh An",
            cccd="000000000191",
            so_dien_thoai="0900000191",
            email="tenant.v2@example.com",
        )
        facility = CoSo.objects.create(
            ten_co_so="NDT Motel Foundation V2",
            dia_chi="Môi trường test",
            quan="Cẩm Lệ",
        )
        pending_room = Phong.objects.create(
            co_so=facility,
            so_phong="V2-301",
            gia_thue=Decimal("3200000"),
            dien_tich=Decimal("28"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("500000"),
        )
        waiting_room = Phong.objects.create(
            co_so=facility,
            so_phong="V2-302",
            gia_thue=Decimal("2800000"),
            dien_tich=Decimal("24"),
            so_nguoi_toi_da=2,
            tien_coc_mac_dinh=Decimal("400000"),
        )
        self.pending = create_booking(
            actor=self.tenant_user,
            room_id=pending_room.pk,
            checkin=timezone.localdate() + timedelta(days=3),
            months=6,
            people=1,
            companions=[],
            accept_terms=True,
            note="Yêu cầu dùng cho visual audit Foundation V2.",
        )
        payment = get_or_create_deposit(actor=self.tenant_user, booking_id=self.pending.pk)
        report_paid(actor=self.tenant_user, payment_id=payment.pk, bank_transaction="V2-BANK-20260929")
        self.waiting = create_booking(
            actor=self.tenant_user,
            room_id=waiting_room.pk,
            checkin=timezone.localdate() + timedelta(days=8),
            months=3,
            people=1,
            companions=[],
            accept_terms=True,
            note="Yêu cầu chưa có giao dịch cọc.",
        )

    @staticmethod
    def _metrics(page):
        page.keyboard.press("Tab")
        return page.evaluate(
            """() => {
                const active = document.activeElement;
                const style = active ? getComputedStyle(active) : null;
                return {
                    client_width: document.documentElement.clientWidth,
                    scroll_width: document.documentElement.scrollWidth,
                    broken_images: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length,
                    focus_visible: !!active && active.matches(':focus-visible') &&
                        (parseFloat(style.outlineWidth) > 0 || style.boxShadow !== 'none'),
                    unlabeled_controls: [...document.querySelectorAll('input:not([type=hidden]), select, textarea')]
                        .filter(el => !el.labels || el.labels.length === 0)
                        .map(el => el.id || el.name || el.tagName),
                };
            }"""
        )

    def test_capture_foundation_v2_admin_booking(self):
        output = Path(__file__).resolve().parents[2] / "luu_tru" / "kiem_thu" / "foundation_v2_admin_booking" / "after"
        output.mkdir(parents=True, exist_ok=True)

        django_client = Client()
        django_client.force_login(self.admin)
        session_cookie = django_client.cookies["sessionid"].value
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        viewports = {
            "1440": (1440, 900),
            "1024": (1024, 768),
            "768": (768, 900),
            "390": (390, 844),
        }
        cases = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for label, (width, height) in viewports.items():
                context = browser.new_context(viewport={"width": width, "height": height})
                context.add_cookies([{"name": "sessionid", "value": session_cookie, "url": self.live_server_url}])
                page = context.new_page()
                errors = []
                page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
                page.on("pageerror", lambda error: errors.append(f"page:{error}"))

                for screen, path in (
                    ("booking_list", reverse("quan_ly_dat_phong")),
                    ("booking_detail_pending", reverse("chi_tiet_dat_phong", args=[self.pending.pk])),
                ):
                    errors.clear()
                    response = page.goto(self.live_server_url + path, wait_until="networkidle")
                    metrics = self._metrics(page)
                    page.screenshot(path=str(output / f"{screen}_{label}.png"), full_page=True)
                    cases.append({
                        "screen": screen,
                        "viewport": f"{width}x{height}",
                        "status": response.status,
                        "overflow": metrics["scroll_width"] > metrics["client_width"],
                        "broken_images": metrics["broken_images"],
                        "focus_visible": metrics["focus_visible"],
                        "unlabeled_controls": metrics["unlabeled_controls"],
                        "errors": list(errors),
                    })

                context.close()

            context = browser.new_context(viewport={"width": 390, "height": 844})
            context.add_cookies([{"name": "sessionid", "value": session_cookie, "url": self.live_server_url}])
            page = context.new_page()
            errors = []
            page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
            page.on("pageerror", lambda error: errors.append(f"page:{error}"))
            response = page.goto(self.live_server_url + reverse("chi_tiet_dat_phong", args=[self.waiting.pk]), wait_until="networkidle")
            metrics = self._metrics(page)
            page.screenshot(path=str(output / "booking_detail_waiting_390.png"), full_page=True)
            cases.append({"screen": "booking_detail_waiting", "viewport": "390x844", "status": response.status, "overflow": metrics["scroll_width"] > metrics["client_width"], "broken_images": metrics["broken_images"], "focus_visible": metrics["focus_visible"], "unlabeled_controls": metrics["unlabeled_controls"], "errors": errors})

            response = page.goto(self.live_server_url + reverse("quan_ly_dat_phong") + "?q=khong-co-ket-qua", wait_until="networkidle")
            metrics = self._metrics(page)
            page.screenshot(path=str(output / "booking_list_empty_390.png"), full_page=True)
            cases.append({"screen": "booking_list_empty", "viewport": "390x844", "status": response.status, "overflow": metrics["scroll_width"] > metrics["client_width"], "broken_images": metrics["broken_images"], "focus_visible": metrics["focus_visible"], "unlabeled_controls": metrics["unlabeled_controls"], "errors": list(errors)})
            context.close()
            browser.close()

        guest = Client()
        tenant_client = Client()
        tenant_client.force_login(self.tenant_user)
        role_checks = {
            "guest_list": guest.get(reverse("quan_ly_dat_phong")).url,
            "guest_detail": guest.get(reverse("chi_tiet_dat_phong", args=[self.pending.pk])).url,
            "tenant_list": tenant_client.get(reverse("quan_ly_dat_phong")).url,
            "tenant_detail": tenant_client.get(reverse("chi_tiet_dat_phong", args=[self.pending.pk])).url,
        }
        payload = {"viewports": viewports, "cases": cases, "role_checks": role_checks}
        (output / "results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        for result in cases:
            self.assertEqual(result["status"], 200)
            self.assertFalse(result["overflow"])
            self.assertEqual(result["broken_images"], 0)
            self.assertTrue(result["focus_visible"])
            self.assertEqual(result["unlabeled_controls"], [])
            self.assertEqual(result["errors"], [])
        self.assertTrue(role_checks["guest_list"].startswith(reverse("dang_nhap")))
        self.assertTrue(role_checks["guest_detail"].startswith(reverse("dang_nhap")))
        self.assertEqual(role_checks["tenant_list"], reverse("tai_khoan"))
        self.assertEqual(role_checks["tenant_detail"], reverse("tai_khoan"))
