"""Explicit isolated browser audit for Module 03; not part of normal discovery."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.db import connection
from django.test import Client
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.dich_vu.dat_phong import create_booking
from core.dich_vu.tien_coc import get_or_create_deposit, report_paid
from core.models import CoSo, NguoiThue, Phong


class AdminBookingVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.admin = User.objects.create_user("visual-admin", password="unused", is_staff=True)
        self.user = User.objects.create_user("visual-tenant", password="unused")
        tenant = NguoiThue.objects.create(
            tai_khoan=self.user, ho_ten="Nguyễn Minh An", cccd="000000000091",
            so_dien_thoai="0900000091", email="tenant.test@example.com",
        )
        facility = CoSo.objects.create(ten_co_so="NDT Motel Test", dia_chi="Môi trường test", quan="Cẩm Lệ")
        room = Phong.objects.create(
            co_so=facility, so_phong="TEST-301", gia_thue=Decimal("3200000"),
            dien_tich=Decimal("28"), so_nguoi_toi_da=3, tien_coc_mac_dinh=Decimal("500000"),
        )
        booking = create_booking(
            actor=self.user, room_id=room.pk, checkin=timezone.localdate() + timedelta(days=2),
            months=6, people=1, companions=[], accept_terms=True, note="Booking phục vụ visual QA cô lập.",
        )
        payment = get_or_create_deposit(actor=self.user, booking_id=booking.pk)
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="TEST-BANK-20260927")
        self.booking = booking

    def test_capture_admin_booking_screens(self):
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru"
            / "kiem_thu"
            / "module_03"
            / "ui_admin_booking_payment_qa"
        )
        output.mkdir(parents=True, exist_ok=True)
        client = Client()
        client.force_login(self.admin)
        session_cookie = client.cookies["sessionid"].value
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        results = []
        viewports = {"1440": (1440, 1000), "1024": (1024, 900), "768": (768, 900), "390": (390, 844)}

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for label, (width, height) in viewports.items():
                context = browser.new_context(viewport={"width": width, "height": height})
                context.add_cookies([{"name": "sessionid", "value": session_cookie, "url": self.live_server_url}])
                page = context.new_page()
                errors = []
                page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
                page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                response = page.goto(self.live_server_url + "/quan-ly-dat-phong/", wait_until="networkidle")
                metrics = page.evaluate("() => ({cw: document.documentElement.clientWidth, sw: document.documentElement.scrollWidth, broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length})")
                page.screenshot(path=str(output / f"booking_list_{label}.png"), full_page=True)
                results.append({"screen": "list", "width": width, "status": response.status, "overflow": metrics["sw"] > metrics["cw"], "broken_images": metrics["broken"], "errors": errors})

                if label in ("1440", "390"):
                    errors.clear()
                    response = page.goto(self.live_server_url + f"/quan-ly-dat-phong/{self.booking.pk}/", wait_until="networkidle")
                    metrics = page.evaluate("() => ({cw: document.documentElement.clientWidth, sw: document.documentElement.scrollWidth, broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length})")
                    page.screenshot(path=str(output / f"booking_detail_{label}.png"), full_page=True)
                    page.locator("#payment-review").screenshot(path=str(output / f"payment_review_{label}.png"))
                    results.append({"screen": "detail", "width": width, "status": response.status, "overflow": metrics["sw"] > metrics["cw"], "broken_images": metrics["broken"], "errors": list(errors)})
                    if label == "390":
                        page.locator("[data-admin-booking-confirm]").first.locator("button[type=submit]").click()
                        page.locator("[data-ndt-dialog]").screenshot(path=str(output / "dialog_390.png"))
                context.close()
            browser.close()

        (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        for result in results:
            self.assertEqual(result["status"], 200)
            self.assertFalse(result["overflow"])
            self.assertEqual(result["broken_images"], 0)
            self.assertEqual(result["errors"], [])
