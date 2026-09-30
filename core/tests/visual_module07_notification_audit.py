"""Explicit isolated browser audit for Module 07; not part of normal discovery."""

import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.models import NguoiThue, ThongBao


class Module07NotificationVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.admin = User.objects.create_user("module07-admin", is_staff=True)
        self.empty_admin = User.objects.create_user("module07-empty-admin", is_staff=True)
        self.tenant_user = User.objects.create_user("module07-tenant")
        self.empty_tenant_user = User.objects.create_user("module07-empty-tenant")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="Nguyen Minh Thong Bao",
            cccd="000000000701",
            so_dien_thoai="0900000701",
            email="module07.tenant@example.com",
        )
        NguoiThue.objects.create(
            tai_khoan=self.empty_tenant_user,
            ho_ten="Tran An Empty",
            cccd="000000000702",
            so_dien_thoai="0900000702",
            email="module07.empty@example.com",
        )
        self.tenant_unread = ThongBao.objects.create(
            nguoi_thue=self.tenant,
            tieu_de="Lich bao tri dieu hoa dinh ky",
            noi_dung="Ky thuat vien se kiem tra dieu hoa trong khung gio da thong bao.",
            loai="bao_tri",
            muc_do="quan_trong",
            url_lien_ket=reverse("yeu_cau_sua_chua_cua_toi"),
        )
        self.tenant_unread_ids = [self.tenant_unread.pk]
        for index in range(2, 5):
            notice = ThongBao.objects.create(
                nguoi_thue=self.tenant,
                tieu_de=f"Thong bao chua doc cho viewport {index}",
                noi_dung="Du lieu QA rieng de kiem tra trang thai chua doc.",
                loai="he_thong",
            )
            self.tenant_unread_ids.append(notice.pk)
        self.tenant_read = ThongBao.objects.create(
            nguoi_thue=self.tenant,
            tieu_de="Hop dong da duoc cap nhat",
            noi_dung="Thong tin hop dong cua ban da duoc dong bo.",
            loai="hop_dong",
            da_doc=True,
            ngay_doc=timezone.now(),
        )
        self.admin_unread = ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Can doi soat thanh toan moi",
            noi_dung="Nguoi thue da bao chuyen khoan va dang cho quan tri xac nhan.",
            loai="thanh_toan",
            muc_do="quan_trong",
            url_lien_ket=reverse("dashboard_admin"),
        )
        self.admin_read = ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Dat phong da duoc xu ly",
            noi_dung="Yeu cau dat phong truoc do da hoan tat.",
            loai="dat_phong",
            da_doc=True,
            ngay_doc=timezone.now(),
        )

    def _session_cookie(self, user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_capture_module_07_screens(self):
        output = Path(__file__).resolve().parents[2] / "luu_tru" / "kiem_thu" / "module_07" / "notification_qa"
        output.mkdir(parents=True, exist_ok=True)
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        viewports = {
            "1440": (1440, 900),
            "1024": (1024, 768),
            "768": (768, 900),
            "390": (390, 844),
        }
        users = (self.admin, self.empty_admin, self.tenant_user, self.empty_tenant_user)
        cookies = {user.pk: self._session_cookie(user) for user in users}
        pages = [
            ("admin_manage_list_mixed", self.admin, reverse("quan_ly_thong_bao")),
            ("admin_manage_list_empty", self.admin, reverse("quan_ly_thong_bao") + "?q=khong-co-ket-qua"),
            ("admin_create", self.admin, reverse("tao_thong_bao")),
            ("admin_manage_detail_unread", self.admin, reverse("chi_tiet_thong_bao", args=[self.tenant_unread.pk])),
            ("admin_inbox_list_mixed", self.admin, reverse("thong_bao_admin")),
            ("admin_inbox_detail_unread", self.admin, reverse("chi_tiet_thong_bao_admin", args=[self.admin_unread.pk])),
            ("admin_inbox_detail_read", self.admin, reverse("chi_tiet_thong_bao_admin", args=[self.admin_read.pk])),
            ("admin_inbox_empty", self.empty_admin, reverse("thong_bao_admin")),
            ("tenant_list_mixed", self.tenant_user, reverse("thong_bao_cua_toi")),
            ("tenant_detail_marks_read", self.tenant_user, reverse("chi_tiet_thong_bao_cua_toi", args=[self.tenant_unread.pk])),
            ("tenant_list_empty", self.empty_tenant_user, reverse("thong_bao_cua_toi")),
        ]
        results = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for viewport_index, (viewport_name, (width, height)) in enumerate(viewports.items()):
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
                    active_path = path
                    if screen == "tenant_detail_marks_read":
                        active_path = reverse(
                            "chi_tiet_thong_bao_cua_toi",
                            args=[self.tenant_unread_ids[viewport_index]],
                        )
                    response = page.goto(self.live_server_url + active_path, wait_until="networkidle")
                    metrics = page.evaluate("() => ({cw: document.documentElement.clientWidth, sw: document.documentElement.scrollWidth, broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length})")
                    screenshot = output / f"{screen}_{viewport_name}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    results.append({
                        "screen": screen,
                        "width": width,
                        "height": height,
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

        self.tenant_unread.refresh_from_db()
        self.assertTrue(self.tenant_unread.da_doc)
        self.assertIsNotNone(self.tenant_unread.ngay_doc)
