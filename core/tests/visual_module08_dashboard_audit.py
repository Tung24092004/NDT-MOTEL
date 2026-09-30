"""Explicit isolated browser audit for Module 08; not part of normal discovery."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client
from django.urls import resolve, reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.models import CoSo, DatPhong, HopDong, NguoiThue, Phong


class Module08DashboardVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.admin = User.objects.create_user("module08-admin", is_staff=True)
        self.tenant_user = User.objects.create_user("module08-tenant")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="Nguyen Minh Dashboard",
            cccd="000000000801",
            so_dien_thoai="0900000801",
        )
        self.other_tenant = NguoiThue.objects.create(
            ho_ten="Tran An Dashboard",
            cccd="000000000802",
            so_dien_thoai="0900000802",
        )
        self.facility = CoSo.objects.create(
            ten_co_so="NDT Dashboard QA",
            dia_chi="Du lieu kiem thu co lap",
            quan="Quan QA",
        )
        self.rooms = [
            Phong.objects.create(
                co_so=self.facility,
                so_phong=f"M08-{index}",
                gia_thue=Decimal("2500000"),
                dien_tich=Decimal("24"),
                so_nguoi_toi_da=3,
                trang_thai="bao_tri" if index == 4 else "trong",
            )
            for index in range(1, 7)
        ]
        today = timezone.localdate()
        statuses = ("cho_duyet", "da_duyet", "tu_choi", "da_huy", "da_duyet")
        self.bookings = []
        for index, status in enumerate(statuses):
            self.bookings.append(DatPhong.objects.create(
                nguoi_thue=self.tenant if index % 2 == 0 else self.other_tenant,
                phong=self.rooms[index],
                ngay_nhan_phong=today + timedelta(days=index),
                ngay_tra_du_kien=today + timedelta(days=90 + index),
                so_thang_thue=3,
                tien_coc_du_kien=Decimal("500000"),
                trang_thai=status,
            ))
        HopDong.objects.create(
            dat_phong=self.bookings[1],
            so_hop_dong="M08-ACTIVE",
            ngay_bat_dau=today - timedelta(days=10),
            ngay_ket_thuc=today + timedelta(days=90),
            tien_thue_thang=Decimal("2500000"),
            trang_thai="dang_hieu_luc",
        )
        self.rooms[3].trang_thai = "bao_tri"
        self.rooms[3].save(update_fields=["trang_thai"])

    def _session_cookie(self):
        client = Client()
        client.force_login(self.admin)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def _expected_context(self):
        client = Client()
        client.force_login(self.admin)
        response = client.get(reverse("dashboard_admin"))
        self.assertEqual(response.status_code, 200)
        names = (
            "tong_phong",
            "phong_trong",
            "phong_da_dat",
            "phong_dang_thue",
            "phong_bao_tri",
            "tong_nguoi_thue",
            "tong_dat_phong",
            "dat_phong_cho_duyet",
            "dat_phong_da_duyet",
            "tong_hop_dong",
            "hop_dong_dang_hieu_luc",
        )
        return {name: response.context[name] for name in names}

    def test_capture_module_08_dashboard(self):
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru" / "kiem_thu" / "module_08" / "dashboard_qa"
        )
        output.mkdir(parents=True, exist_ok=True)
        expected = self._expected_context()
        cookie = self._session_cookie()
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        viewports = {
            "1440": (1440, 900),
            "1024": (1024, 768),
            "768": (768, 900),
            "390": (390, 844),
        }
        results = []
        all_hrefs = set()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for viewport_name, (width, height) in viewports.items():
                context = browser.new_context(viewport={"width": width, "height": height})
                context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": cookie,
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
                response = page.goto(
                    self.live_server_url + reverse("dashboard_admin"),
                    wait_until="networkidle",
                )
                browser_data = page.evaluate(
                    """() => ({
                        cw: document.documentElement.clientWidth,
                        sw: document.documentElement.scrollWidth,
                        broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length,
                        metrics: Object.fromEntries([...document.querySelectorAll('[data-dashboard-metric]')]
                            .map(el => [el.dataset.dashboardMetric, el.textContent.trim()])),
                        hrefs: [...document.querySelectorAll('.admin-dashboard a[href]')]
                            .map(el => el.getAttribute('href')),
                        bookingRows: document.querySelectorAll('[data-booking-id]').length,
                        text: document.querySelector('.admin-dashboard').innerText,
                    })"""
                )
                all_hrefs.update(browser_data["hrefs"])
                screenshot = output / f"admin_dashboard_{viewport_name}.png"
                page.screenshot(path=str(screenshot), full_page=True)
                results.append({
                    "screen": "admin_dashboard",
                    "width": width,
                    "height": height,
                    "status": response.status if response else None,
                    "overflow": browser_data["sw"] > browser_data["cw"],
                    "broken_images": browser_data["broken"],
                    "errors": errors,
                    "metrics": browser_data["metrics"],
                    "booking_rows": browser_data["bookingRows"],
                    "screenshot": screenshot.name,
                })
                self.assertNotIn("cho_duyet", browser_data["text"])
                self.assertNotIn("tu_choi", browser_data["text"])
                context.close()
            browser.close()

        for href in all_hrefs:
            self.assertTrue(href and href.startswith("/"), href)
            resolve(urlsplit(href).path)

        (output / "results.json").write_text(
            json.dumps(
                {"expected_backend": expected, "cases": results},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        for result in results:
            self.assertEqual(result["status"], 200)
            self.assertFalse(result["overflow"])
            self.assertEqual(result["broken_images"], 0)
            self.assertEqual(result["errors"], [])
            self.assertEqual(result["booking_rows"], 5)
            for name, value in expected.items():
                if name in result["metrics"]:
                    self.assertEqual(result["metrics"][name], str(value))

