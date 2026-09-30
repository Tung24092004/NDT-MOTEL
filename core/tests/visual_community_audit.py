"""Explicit isolated browser audit for Module 05; not part of normal discovery."""

import json
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

from core.models import CoSo, DatPhong, HopDong, NguoiOCungPhong, NguoiThue, Phong, YeuCauGhepNguoi


class CommunityVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        today = timezone.localdate()
        self.admin = User.objects.create_user("community-admin", is_staff=True)
        self.owner_user = User.objects.create_user("community-owner")
        self.applicant_user = User.objects.create_user("community-applicant")
        self.visitor_user = User.objects.create_user("community-visitor")
        self.owner = NguoiThue.objects.create(
            tai_khoan=self.owner_user,
            ho_ten="Nguyen Minh Chu",
            cccd="000000000501",
            so_dien_thoai="0900000501",
            email="owner.community@example.com",
        )
        self.applicant = NguoiThue.objects.create(
            tai_khoan=self.applicant_user,
            ho_ten="Tran Gia Han",
            cccd="000000000502",
            so_dien_thoai="0900000502",
            email="applicant.community@example.com",
        )
        NguoiThue.objects.create(
            tai_khoan=self.visitor_user,
            ho_ten="Pham Ngoc Mai",
            cccd="000000000504",
            so_dien_thoai="0900000504",
            email="visitor.community@example.com",
        )
        facility = CoSo.objects.create(ten_co_so="NDT Motel Test", dia_chi="Moi truong test", quan="Cam Le")
        self.room = Phong.objects.create(
            co_so=facility,
            so_phong="M05-501",
            gia_thue=Decimal("3200000"),
            dien_tich=Decimal("28"),
            so_nguoi_toi_da=4,
            tien_coc_mac_dinh=Decimal("500000"),
        )
        booking = DatPhong.objects.create(
            nguoi_thue=self.owner,
            phong=self.room,
            ngay_nhan_phong=today,
            ngay_tra_du_kien=today + timedelta(days=180),
            so_thang_thue=6,
            trang_thai="da_duyet",
        )
        self.contract = HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong="M05-QA-501",
            ngay_bat_dau=today,
            ngay_ket_thuc=today + timedelta(days=180),
            tien_thue_thang=Decimal("3200000"),
            trang_thai="dang_hieu_luc",
            cho_phep_ghep=True,
        )
        self.resident = NguoiOCungPhong.objects.create(
            hop_dong=self.contract,
            ho_ten="Le Hoang Nam",
            cccd="000000000503",
            so_dien_thoai="0900000503",
            quan_he="Ban be",
            ngay_vao=today,
        )
        self.sharing = YeuCauGhepNguoi.objects.create(
            hop_dong=self.contract,
            nguoi_dang_ky=self.applicant,
            ho_ten=self.applicant.ho_ten,
            cccd=self.applicant.cccd,
            so_dien_thoai=self.applicant.so_dien_thoai,
            quan_he="Dong nghiep",
            ngay_du_kien_vao=today + timedelta(days=2),
        )

    def _session_cookie(self, user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_capture_module_05_screens(self):
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru"
            / "kiem_thu"
            / "module_05"
            / "community_qa"
        )
        output.mkdir(parents=True, exist_ok=True)
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        viewports = {"1440": (1440, 900), "1024": (1024, 768), "768": (768, 900), "390": (390, 844)}
        cookies = {
            self.admin.pk: self._session_cookie(self.admin),
            self.owner_user.pk: self._session_cookie(self.owner_user),
            self.applicant_user.pk: self._session_cookie(self.applicant_user),
            self.visitor_user.pk: self._session_cookie(self.visitor_user),
        }
        pages = [
            ("admin_tenants", self.admin, reverse("quan_ly_nguoi_thue")),
            ("admin_tenant_detail", self.admin, reverse("chi_tiet_nguoi_thue", args=[self.owner.pk])),
            ("admin_residents", self.admin, reverse("quan_ly_nguoi_o_cung")),
            ("admin_resident_create", self.admin, reverse("tao_nguoi_o_cung")),
            ("admin_resident_detail", self.admin, reverse("chi_tiet_nguoi_o_cung", args=[self.resident.pk])),
            ("admin_sharing", self.admin, reverse("quan_ly_yeu_cau_ghep")),
            ("admin_sharing_detail", self.admin, reverse("chi_tiet_yeu_cau_ghep", args=[self.sharing.pk])),
            ("tenant_sharing", self.owner_user, reverse("yeu_cau_ghep_cua_toi")),
            ("tenant_sharing_detail", self.applicant_user, reverse("chi_tiet_yeu_cau_ghep", args=[self.sharing.pk])),
            ("tenant_sharing_register", self.visitor_user, reverse("dang_ky_ghep_phong", args=[self.room.pk])),
        ]
        results = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for viewport_name, (width, height) in viewports.items():
                for screen, user, path in pages:
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
                    metrics = page.evaluate("() => ({cw: document.documentElement.clientWidth, sw: document.documentElement.scrollWidth, broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length})")
                    screenshot = output / f"{screen}_{viewport_name}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    results.append({
                        "screen": screen,
                        "width": width,
                        "status": response.status if response else None,
                        "overflow": metrics["sw"] > metrics["cw"],
                        "broken_images": metrics["broken"],
                        "errors": errors,
                        "screenshot": screenshot.name,
                    })
                    context.close()
            browser.close()

        (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        for result in results:
            self.assertEqual(result["status"], 200)
            self.assertFalse(result["overflow"])
            self.assertEqual(result["broken_images"], 0)
            self.assertEqual(result["errors"], [])
