"""Stage 02D tenant repair visual audit on the isolated test database."""

import json
import os
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

from core.models import CoSo, DatPhong, HopDong, NguoiThue, Phong, YeuCauSuaChua


class RepairStage02DVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"
    artifact_phase = os.environ.get("NDT_REPAIR_STAGE02D_PHASE", "before")

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        today = timezone.localdate()
        self.admin = User.objects.create_user("repair-02d-admin", is_staff=True)
        self.tenant_user = User.objects.create_user("repair-02d-tenant")
        self.empty_user = User.objects.create_user("repair-02d-empty")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="Nguyen Minh Sua Chua",
            cccd="000000002601",
            so_dien_thoai="0900002601",
            email="repair.02d@example.com",
        )
        NguoiThue.objects.create(
            tai_khoan=self.empty_user,
            ho_ten="Tran Rong",
            cccd="000000002602",
            so_dien_thoai="0900002602",
        )
        facility = CoSo.objects.create(
            ten_co_so="NDT Motel Stage 02D",
            dia_chi="Moi truong test",
            quan="Cam Le",
        )
        self.room = Phong.objects.create(
            co_so=facility,
            so_phong="2D-401",
            gia_thue=Decimal("3600000"),
            dien_tich=Decimal("28"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("500000"),
        )
        booking = DatPhong.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            ngay_nhan_phong=today - timedelta(days=90),
            ngay_tra_du_kien=today + timedelta(days=90),
            so_thang_thue=6,
            trang_thai="da_duyet",
        )
        HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong="S02D-401",
            ngay_bat_dau=today - timedelta(days=90),
            ngay_ket_thuc=today + timedelta(days=90),
            tien_thue_thang=Decimal("3600000"),
            tien_coc=Decimal("500000"),
            trang_thai="dang_hieu_luc",
        )
        now = timezone.now()
        self.repairs = []
        for index, status in enumerate(["moi", "dang_xu_ly", "cho_thay_the", "hoan_thanh", "tu_choi"]):
            repair = YeuCauSuaChua.objects.create(
                nguoi_thue=self.tenant,
                phong=self.room,
                tieu_de=f"Yeu cau {index + 1} - thiet bi phong",
                noi_dung=(
                    "Mo ta hien tuong rat cu the: vi tri gan cua so, tieng on xuat hien "
                    "vao buoi toi va can kiem tra som de tranh anh huong sinh hoat."
                ),
                loai_su_co=["dien", "nuoc", "thiet_bi", "phong", "wifi"][index],
                muc_do=["thap", "trung_binh", "cao", "khan_cap", "trung_binh"][index],
                trang_thai=status,
                nguoi_xu_ly="To ky thuat" if status in {"dang_xu_ly", "cho_thay_the", "hoan_thanh"} else "",
                chi_phi=Decimal("150000") if status == "hoan_thanh" else Decimal("0"),
                chi_tiet_chi_phi="Thay vat tu va ve sinh khu vuc hu hong." if status == "hoan_thanh" else "",
                ghi_chu_admin="Quan ly da tiep nhan va dang sap lich kiem tra." if status != "moi" else "",
                ngay_bat_dau_xu_ly=now if status in {"dang_xu_ly", "cho_thay_the", "hoan_thanh"} else None,
                ngay_hoan_thanh=now if status == "hoan_thanh" else None,
            )
            self.repairs.append(repair)

    def _session_cookie(self, user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_capture_stage_02d_tenant_repair(self):
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru"
            / "kiem_thu"
            / "uiux_stage_02d_repair"
            / self.artifact_phase
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
            "tenant": self._session_cookie(self.tenant_user),
            "empty": self._session_cookie(self.empty_user),
            "admin": self._session_cookie(self.admin),
        }
        pages = [
            ("repair_list_many", "tenant", reverse("yeu_cau_sua_chua_cua_toi")),
            ("repair_list_empty", "empty", reverse("yeu_cau_sua_chua_cua_toi")),
            ("repair_create", "tenant", reverse("tao_yeu_cau_sua_chua")),
            ("repair_detail_new", "tenant", reverse("chi_tiet_yeu_cau_sua_chua_cua_toi", args=[self.repairs[0].pk])),
            ("repair_detail_processing", "tenant", reverse("chi_tiet_yeu_cau_sua_chua_cua_toi", args=[self.repairs[1].pk])),
            ("repair_detail_waiting", "tenant", reverse("chi_tiet_yeu_cau_sua_chua_cua_toi", args=[self.repairs[2].pk])),
            ("repair_detail_done", "tenant", reverse("chi_tiet_yeu_cau_sua_chua_cua_toi", args=[self.repairs[3].pk])),
            ("repair_detail_rejected", "tenant", reverse("chi_tiet_yeu_cau_sua_chua_cua_toi", args=[self.repairs[4].pk])),
            ("guest_list", None, reverse("yeu_cau_sua_chua_cua_toi")),
            ("admin_list", "admin", reverse("yeu_cau_sua_chua_cua_toi")),
        ]
        results = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for viewport_name, (width, height) in viewports.items():
                for screen, actor, path in pages:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    if actor:
                        context.add_cookies([{
                            "name": settings.SESSION_COOKIE_NAME,
                            "value": cookies[actor],
                            "url": self.live_server_url,
                        }])
                    page = context.new_page()
                    errors = []
                    page.on(
                        "console",
                        lambda message: errors.append(f"console:{message.type}:{message.text}")
                        if message.type == "error"
                        else None,
                    )
                    page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                    response = page.goto(self.live_server_url + path, wait_until="networkidle")
                    metrics = page.evaluate(
                        """() => ({
                            cw: document.documentElement.clientWidth,
                            sw: document.documentElement.scrollWidth,
                            broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length,
                            active: document.activeElement && document.activeElement.tagName,
                            buttons: [...document.querySelectorAll('a,button,input[type=submit]')].map(el => ({
                                text: (el.innerText || el.value || el.getAttribute('aria-label') || '').trim(),
                                href: el.getAttribute('href'),
                                type: el.getAttribute('type'),
                                w: Math.round(el.getBoundingClientRect().width),
                                h: Math.round(el.getBoundingClientRect().height)
                            }))
                        })"""
                    )
                    if screen.startswith("repair_"):
                        page.keyboard.press("Tab")
                        focus_visible = page.evaluate(
                            "() => !!document.querySelector(':focus-visible')"
                        )
                        screenshot = output / f"{screen}_{viewport_name}.png"
                        page.screenshot(path=str(screenshot), full_page=True)
                    else:
                        focus_visible = True
                        screenshot = None
                    results.append({
                        "case": screen,
                        "viewport": f"{width}x{height}",
                        "path": path,
                        "status": response.status if response else None,
                        "final_path": page.url.replace(self.live_server_url, ""),
                        "overflow": metrics["sw"] > metrics["cw"],
                        "broken_images": metrics["broken"],
                        "errors": errors,
                        "focus_visible": focus_visible,
                        "small_buttons": [
                            item["text"] or item["href"] or item["type"]
                            for item in metrics["buttons"]
                            if item["w"] and item["h"] and (item["w"] < 44 or item["h"] < 36)
                        ],
                        "screenshot": screenshot.name if screenshot else None,
                    })
                    context.close()
            browser.close()

        (output / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        for result in results:
            self.assertEqual(result["status"], 200)
            self.assertFalse(result["overflow"])
            self.assertEqual(result["broken_images"], 0)
            self.assertEqual(result["errors"], [])
            self.assertTrue(result["focus_visible"])
        guest_results = [r for r in results if r["case"] == "guest_list"]
        admin_results = [r for r in results if r["case"] == "admin_list"]
        self.assertTrue(all(r["final_path"].startswith(reverse("dang_nhap")) for r in guest_results))
        self.assertTrue(all(r["final_path"] == reverse("quan_ly_sua_chua") for r in admin_results))
