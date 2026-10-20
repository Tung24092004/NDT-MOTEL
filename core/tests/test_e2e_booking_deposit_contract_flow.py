"""One continuous, isolated browser journey from booking to activated contract."""

import shutil
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from PIL import Image
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import close_old_connections, connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.models import (
    ChungTuThanhToan,
    CoSo,
    DatPhong,
    HopDong,
    NguoiThue,
    PhanHoiHopDong,
    Phong,
    ThanhToanCocDatPhong,
)
from core.private_storage import private_payment_evidence_storage


class BookingDepositContractBrowserE2E(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Continuous browser E2E requires isolated test_ndt_motel.")

    def setUp(self):
        self.private_directory = settings.BASE_DIR / ".test-media" / f"booking-contract-e2e-{uuid4().hex}"
        self.private_directory.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.private_directory, ignore_errors=True)
        self.storage_state = dict(private_payment_evidence_storage.__dict__)
        private_payment_evidence_storage._location = str(self.private_directory)
        private_payment_evidence_storage.__dict__.pop("base_location", None)
        private_payment_evidence_storage.__dict__.pop("location", None)

        self.admin = User.objects.create_user("e2e-flow-admin", password="fixture-only", is_staff=True)
        self.user = User.objects.create_user("e2e-flow-tenant", password="fixture-only")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.user,
            ho_ten="Browser E2E Tenant",
            cccd="000000008801",
            so_dien_thoai="0900008801",
            email="browser-e2e@example.test",
        )
        facility = CoSo.objects.create(
            ten_co_so="Browser E2E Facility",
            dia_chi="Test-only",
            quan="QA",
            trang_thai="hoat_dong",
        )
        self.room = Phong.objects.create(
            co_so=facility,
            so_phong="E2E-801",
            gia_thue=Decimal("3000000"),
            dien_tich=Decimal("25"),
            so_nguoi_toi_da=2,
            tien_coc_mac_dinh=Decimal("600000"),
            trang_thai="trong",
        )
        self.receipt = self.private_directory / "e2e-deposit-evidence.png"
        Image.new("RGB", (32, 32), "white").save(self.receipt, format="PNG")

    def tearDown(self):
        private_payment_evidence_storage.__dict__.clear()
        private_payment_evidence_storage.__dict__.update(self.storage_state)
        shutil.rmtree(self.private_directory, ignore_errors=True)
        super().tearDown()

    @staticmethod
    def _cookie(user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    @staticmethod
    def _orm_snapshot(callback):
        """Run synchronous ORM work outside Playwright's event-loop context."""
        def worker():
            close_old_connections()
            try:
                return callback()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(worker).result()

    @staticmethod
    def _booking_state(*, booking_id=None, tenant_id=None, room_id=None):
        query = DatPhong.objects
        if booking_id is not None:
            booking = query.get(pk=booking_id)
        else:
            booking = query.get(nguoi_thue_id=tenant_id, phong_id=room_id)
        deposit = ThanhToanCocDatPhong.objects.get(dat_phong=booking, active_slot=1)
        evidence = ChungTuThanhToan.objects.filter(giao_dich_coc=deposit).first()
        return {
            "booking_id": booking.pk,
            "booking_status": booking.trang_thai,
            "deposit_status": deposit.trang_thai,
            "deposit_amount": str(deposit.so_tien),
            "evidence_status": evidence.trang_thai if evidence else None,
        }

    @staticmethod
    def _contract_state(contract_id):
        contract = HopDong.objects.get(pk=contract_id)
        return {
            "status": contract.trang_thai,
            "current_version_id": contract.phien_ban_hien_tai_id,
            "signed": contract.ngay_ky is not None,
            "accepted": bool(
                contract.phien_ban_hien_tai_id
                and PhanHoiHopDong.objects.filter(
                    phien_ban_id=contract.phien_ban_hien_tai_id,
                    hanh_dong="chap_thuan",
                ).exists()
            ),
        }

    @staticmethod
    def _final_state(booking_id, contract_id, room_id):
        return {
            "contract": BookingDepositContractBrowserE2E._contract_state(contract_id),
            "booking_status": DatPhong.objects.get(pk=booking_id).trang_thai,
            "room_status": Phong.objects.get(pk=room_id).trang_thai,
        }

    def test_tenant_booking_to_activated_contract(self):
        admin_cookie, tenant_cookie = self._cookie(self.admin), self._cookie(self.user)
        tenant_id, room_id = self.tenant.pk, self.room.pk
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        errors, failed_requests = [], []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            contexts = []
            try:
                tenant_context = browser.new_context(viewport={"width": 1440, "height": 900})
                contexts.append(tenant_context)
                tenant_context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": tenant_cookie,
                    "url": self.live_server_url,
                }])
                tenant_page = tenant_context.new_page()
                tenant_page.route(
                    "https://img.vietqr.io/**",
                    lambda route: route.fulfill(status=200, content_type="image/png", body=self.receipt.read_bytes()),
                )

                # Tenant creates the booking through the real multi-step form.
                self.assertEqual(
                    tenant_page.goto(self.live_server_url + reverse("dat_phong", args=[self.room.pk]), wait_until="networkidle").status,
                    200,
                )
                booking_form = tenant_page.locator("#booking-create")
                self.assertEqual(booking_form.count(), 1)
                for _ in range(2):
                    booking_form.locator("#booking-next").click()
                booking_form.locator('input[name="ngay_nhan_phong"]').fill(timezone.localdate().isoformat())
                booking_form.locator('input[name="so_thang_thue"]').fill("3")
                booking_form.locator('input[name="so_nguoi_o"]').fill("1")
                booking_form.locator("#booking-next").click()
                booking_form.locator("#booking-next").click()
                booking_form.locator('input[name="da_dong_y_dieu_khoan"]').check()
                booking_form.locator("#booking-next").click()
                with tenant_page.expect_navigation(wait_until="networkidle"):
                    booking_form.locator("#booking-submit").click()

                booking_state = self._orm_snapshot(
                    lambda: self._booking_state(tenant_id=tenant_id, room_id=room_id)
                )
                booking_id = booking_state["booking_id"]
                self.assertEqual(booking_state["booking_status"], "cho_duyet")
                self.assertEqual(booking_state["deposit_status"], "chua_thanh_toan")

                # Tenant reports the transfer and attaches only a test PNG.
                self.assertEqual(
                    tenant_page.goto(self.live_server_url + reverse("thanh_toan_coc_cua_toi", args=[booking_id]), wait_until="networkidle").status,
                    200,
                )
                deposit_form = tenant_page.locator("form.deposit-report-form")
                self.assertEqual(deposit_form.count(), 1)
                deposit_form.locator("#deposit-evidence").set_input_files(str(self.receipt))
                with tenant_page.expect_navigation(wait_until="networkidle"):
                    deposit_form.locator('button[type="submit"]').click()
                booking_state = self._orm_snapshot(lambda: self._booking_state(booking_id=booking_id))
                self.assertEqual(booking_state["deposit_status"], "cho_xac_nhan")
                self.assertEqual(booking_state["evidence_status"], "cho_doi_soat")

                admin_context = browser.new_context(viewport={"width": 1440, "height": 900})
                contexts.append(admin_context)
                admin_context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": admin_cookie,
                    "url": self.live_server_url,
                }])
                admin_page = admin_context.new_page()
                for page in (tenant_page, admin_page):
                    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.on("requestfailed", lambda request: failed_requests.append(request.url))

                # Admin verifies the private evidence and confirms the received amount.
                self.assertEqual(
                    admin_page.goto(self.live_server_url + reverse("chi_tiet_dat_phong", args=[booking_id]), wait_until="networkidle").status,
                    200,
                )
                evidence_link = admin_page.locator('a[href^="/thanh-toan/chung-tu/"]')
                self.assertEqual(evidence_link.count(), 1)
                self.assertEqual(admin_page.request.get(self.live_server_url + evidence_link.get_attribute("href")).status, 200)
                confirmation_form = admin_page.locator("form.admin-booking-primary-action[data-admin-booking-confirm]")
                self.assertEqual(confirmation_form.count(), 1)
                confirmation_form.locator('input[name="so_tien_thuc_nhan"]').fill(booking_state["deposit_amount"])
                confirmation_form.locator('button[type="submit"]').click()
                dialog_confirm = admin_page.locator("[data-ndt-f5-dialog-confirm]")
                self.assertEqual(dialog_confirm.count(), 1)
                with admin_page.expect_navigation(wait_until="networkidle"):
                    dialog_confirm.click()
                booking_state = self._orm_snapshot(lambda: self._booking_state(booking_id=booking_id))
                self.assertEqual(booking_state["booking_status"], "cho_duyet")
                self.assertEqual(booking_state["deposit_status"], "da_xac_nhan")
                self.assertEqual(booking_state["evidence_status"], "da_chap_nhan")

                # A confirmed deposit permits a draft while the booking remains pending.
                draft_form = admin_page.locator('form[action*="/tao-hop-dong/"]')
                draft_diagnostic = {
                    "url": admin_page.url,
                    "form_actions": admin_page.locator("form").evaluate_all(
                        "forms => forms.map(form => ({action: form.getAttribute('action'), method: form.method}))"
                    ),
                    "feedback": admin_page.locator('[role="alert"], .messages, .admin-booking-feedback--danger').all_inner_texts(),
                    "state": booking_state,
                }
                self.assertEqual(draft_form.count(), 1, f"Draft contract form missing: {draft_diagnostic!r}")
                with admin_page.expect_navigation(wait_until="networkidle"):
                    draft_form.locator('button[type="submit"]').click()
                contract_id = self._orm_snapshot(
                    lambda: HopDong.objects.values_list("pk", flat=True).get(dat_phong_id=booking_id)
                )
                contract_state = self._orm_snapshot(lambda: self._contract_state(contract_id))
                self.assertEqual(contract_state["status"], "nhap")
                booking_state = self._orm_snapshot(lambda: self._booking_state(booking_id=booking_id))
                self.assertEqual(booking_state["booking_status"], "cho_duyet")
                send_form = admin_page.locator('form[action*="/gui-xac-nhan/"]')
                self.assertEqual(send_form.count(), 1)
                with admin_page.expect_navigation(wait_until="networkidle"):
                    send_form.locator('button[type="submit"]').click()
                contract_state = self._orm_snapshot(lambda: self._contract_state(contract_id))
                self.assertEqual(contract_state["status"], "cho_nguoi_thue_xac_nhan")
                self.assertIsNotNone(contract_state["current_version_id"])

                # Tenant accepts the exact current version with their password.
                self.assertEqual(
                    tenant_page.goto(self.live_server_url + reverse("chi_tiet_hop_dong_cua_toi", args=[contract_id]), wait_until="networkidle").status,
                    200,
                )
                acceptance_form = tenant_page.locator('form[action*="/chap-thuan/"]')
                self.assertEqual(acceptance_form.count(), 1)
                acceptance_form.locator('input[name="da_doc_va_chap_thuan"]').check()
                acceptance_form.locator('input[name="mat_khau"]').fill("fixture-only")
                with tenant_page.expect_navigation(wait_until="networkidle"):
                    acceptance_form.locator('button[type="submit"]').click()
                contract_state = self._orm_snapshot(lambda: self._contract_state(contract_id))
                self.assertEqual(contract_state["status"], "cho_kich_hoat")
                self.assertTrue(contract_state["accepted"])

                # Admin activates through the UI confirmation dialog.
                self.assertEqual(
                    admin_page.goto(self.live_server_url + reverse("chi_tiet_hop_dong", args=[contract_id]), wait_until="networkidle").status,
                    200,
                )
                activation_form = admin_page.locator('form[action*="/kich-hoat/"]')
                self.assertEqual(activation_form.count(), 1)
                activation_form.locator('button[type="submit"]').click()
                dialog_confirm = admin_page.locator("[data-ndt-f5-dialog-confirm]")
                self.assertEqual(dialog_confirm.count(), 1)
                with admin_page.expect_navigation(wait_until="networkidle"):
                    dialog_confirm.click()
                final_state = self._orm_snapshot(lambda: self._final_state(booking_id, contract_id, room_id))
                self.assertEqual(final_state["contract"]["status"], "dang_hieu_luc")
                self.assertTrue(final_state["contract"]["signed"])
                self.assertTrue(final_state["contract"]["accepted"])
                self.assertEqual(final_state["booking_status"], "da_duyet")
                self.assertEqual(final_state["room_status"], "dang_thue")
                self.assertEqual(errors, [])
                self.assertEqual(failed_requests, [])
            finally:
                for context in reversed(contexts):
                    context.close()
                browser.close()
