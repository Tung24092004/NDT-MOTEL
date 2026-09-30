"""Explicit isolated browser audit for Module 04; not part of normal discovery."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.dich_vu.dat_phong import create_booking
from core.dich_vu.hop_dong import confirm_deposit_and_create_contract
from core.dich_vu.tien_coc import get_or_create_deposit, report_paid
from core.models import CoSo, NguoiThue, Phong


class ContractManagementVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.admin = User.objects.create_user("contract-admin", password="unused", is_staff=True)
        self.user = User.objects.create_user("contract-tenant", password="unused")
        tenant = NguoiThue.objects.create(
            tai_khoan=self.user,
            ho_ten="Nguyen Minh An",
            cccd="000000000191",
            so_dien_thoai="0900000191",
            email="contract.tenant@example.com",
        )
        facility = CoSo.objects.create(ten_co_so="NDT Motel Test", dia_chi="Moi truong test", quan="Cam Le")
        room = Phong.objects.create(
            co_so=facility,
            so_phong="CQA-401",
            gia_thue=Decimal("3300000"),
            dien_tich=Decimal("28"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("500000"),
        )
        booking = create_booking(
            actor=self.user,
            room_id=room.pk,
            checkin=timezone.localdate() + timedelta(days=1),
            months=6,
            people=1,
            companions=[],
            accept_terms=True,
            note="Contract visual QA isolated booking.",
        )
        payment = get_or_create_deposit(actor=self.user, booking_id=booking.pk)
        report_paid(actor=self.user, payment_id=payment.pk, bank_transaction="CONTRACT-QA-20260927")
        self.contract = confirm_deposit_and_create_contract(actor=self.admin, booking_id=booking.pk)

    def _session_cookie(self, user):
        client = Client()
        client.force_login(user)
        return client.cookies["sessionid"].value

    def test_capture_contract_screens(self):
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru"
            / "kiem_thu"
            / "module_04"
            / "ui_contract_management_qa"
        )
        output.mkdir(parents=True, exist_ok=True)
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        results = []
        viewports = {"1440": (1440, 900), "1024": (1024, 768), "768": (768, 900), "390": (390, 844)}
        cookies = {
            self.admin.pk: self._session_cookie(self.admin),
            self.user.pk: self._session_cookie(self.user),
        }
        pages = [
            ("admin_list", self.admin, "/quan-ly-hop-dong/"),
            ("admin_detail", self.admin, f"/quan-ly-hop-dong/{self.contract.pk}/"),
            ("tenant_list", self.user, "/hop-dong-cua-toi/"),
            ("tenant_detail", self.user, f"/hop-dong-cua-toi/{self.contract.pk}/"),
        ]

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for label, (width, height) in viewports.items():
                for screen, user, path in pages:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.add_cookies([{"name": "sessionid", "value": cookies[user.pk], "url": self.live_server_url}])
                    page = context.new_page()
                    errors = []
                    page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
                    page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                    response = page.goto(self.live_server_url + path, wait_until="networkidle")
                    metrics = page.evaluate("() => ({cw: document.documentElement.clientWidth, sw: document.documentElement.scrollWidth, broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length})")
                    page.screenshot(path=str(output / f"{screen}_{label}.png"), full_page=True)
                    results.append({"screen": screen, "width": width, "status": response.status, "overflow": metrics["sw"] > metrics["cw"], "broken_images": metrics["broken"], "errors": errors})
                    context.close()
            browser.close()

        (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        for result in results:
            self.assertEqual(result["status"], 200)
            self.assertFalse(result["overflow"])
            self.assertEqual(result["broken_images"], 0)
            self.assertEqual(result["errors"], [])
