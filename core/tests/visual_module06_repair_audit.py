"""Explicit isolated browser audit for Module 06; not part of normal discovery."""

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

from core.models import (
    CoSo,
    DatPhong,
    HopDong,
    LichSuSuaChua,
    NguoiThue,
    Phong,
    YeuCauGiaHanHopDong,
    YeuCauSuaChua,
)


class Module06RepairVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        today = timezone.localdate()
        self.admin = User.objects.create_user("module06-admin", is_staff=True)
        self.tenant_user = User.objects.create_user("module06-tenant")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="Nguyen Minh Sua",
            cccd="000000000601",
            so_dien_thoai="0900000601",
            email="module06.tenant@example.com",
        )
        facility = CoSo.objects.create(
            ten_co_so="NDT Motel Module 06",
            dia_chi="Moi truong test",
            quan="Cam Le",
        )
        self.room = Phong.objects.create(
            co_so=facility,
            so_phong="M06-601",
            gia_thue=Decimal("3400000"),
            dien_tich=Decimal("29"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("500000"),
        )
        booking = DatPhong.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            ngay_nhan_phong=today - timedelta(days=150),
            ngay_tra_du_kien=today + timedelta(days=20),
            so_thang_thue=6,
            trang_thai="da_duyet",
        )
        self.contract = HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong="M06-QA-601",
            ngay_bat_dau=today - timedelta(days=150),
            ngay_ket_thuc=today + timedelta(days=20),
            tien_thue_thang=Decimal("3400000"),
            tien_coc=Decimal("500000"),
            trang_thai="sap_het_han",
            so_nguoi_o=1,
            cho_phep_ghep=True,
        )
        self.repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            tieu_de="Dieu hoa phong ngu khong lanh",
            noi_dung="Dieu hoa van chay nhung khong lam lanh sau 20 phut.",
            loai_su_co="thiet_bi",
            muc_do="cao",
            trang_thai="dang_xu_ly",
            nguoi_xu_ly="To ky thuat",
            chi_phi=Decimal("150000"),
            chi_tiet_chi_phi="Kiem tra block va ve sinh luoi loc.",
            ghi_chu_admin="Da tiep nhan, hen kiem tra trong ngay.",
            ngay_bat_dau_xu_ly=timezone.now(),
        )
        LichSuSuaChua.objects.create(
            yeu_cau=self.repair,
            hanh_dong="tiep_nhan",
            trang_thai_cu="moi",
            trang_thai_moi="dang_xu_ly",
            noi_dung="Quan ly da tiep nhan yeu cau.",
            nguoi_thuc_hien=self.admin,
        )
        self.renewal = YeuCauGiaHanHopDong.objects.create(
            hop_dong=self.contract,
            nguoi_yeu_cau=self.tenant,
            so_thang_gia_han=3,
            ngay_ket_thuc_cu=self.contract.ngay_ket_thuc,
            ngay_ket_thuc_de_xuat=self.contract.ngay_ket_thuc + timedelta(days=90),
            ly_do="Muon tiep tuc o on dinh trong hoc ky toi.",
            trang_thai="cho_duyet",
        )

    def _session_cookie(self, user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_capture_module_06_screens(self):
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru"
            / "kiem_thu"
            / "module_06"
            / "repair_contract_qa"
        )
        output.mkdir(parents=True, exist_ok=True)
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        viewports = {
            "1440": (1440, 900),
            "1024": (1024, 768),
            "768": (768, 900),
            "390": (390, 844),
        }
        cookies = {
            self.admin.pk: self._session_cookie(self.admin),
            self.tenant_user.pk: self._session_cookie(self.tenant_user),
        }
        pages = [
            ("admin_repair_list", self.admin, reverse("quan_ly_sua_chua")),
            ("admin_repair_detail", self.admin, reverse("chi_tiet_sua_chua", args=[self.repair.pk])),
            ("admin_repair_create", self.admin, reverse("tao_sua_chua")),
            ("tenant_repair_list", self.tenant_user, reverse("yeu_cau_sua_chua_cua_toi")),
            ("tenant_repair_detail", self.tenant_user, reverse("chi_tiet_yeu_cau_sua_chua_cua_toi", args=[self.repair.pk])),
            ("tenant_repair_create", self.tenant_user, reverse("tao_yeu_cau_sua_chua")),
            ("admin_contract_detail_renewal", self.admin, reverse("chi_tiet_hop_dong", args=[self.contract.pk])),
            ("tenant_contract_detail_renewal", self.tenant_user, reverse("chi_tiet_hop_dong_cua_toi", args=[self.contract.pk])),
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
