"""Explicit visual audit for the UI/UX sample screens; excluded from discovery."""

import json
import os
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client
from django.urls import reverse
from playwright.sync_api import sync_playwright

from core.models import CoSo, Phong


class UIUXSampleVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.admin = User.objects.create_user("uiux-admin", is_staff=True)
        self.facility = CoSo.objects.create(
            ten_co_so="NDT Motel UIUX Sample",
            dia_chi="123 Nguyen Van Linh, Da Nang",
            quan="Hai Chau",
            so_dien_thoai="0900000001",
            email="uiux-sample@example.com",
            nguoi_quan_ly="Tran Quan Ly",
            so_tang=6,
            trang_thai="hoat_dong",
        )
        self.rooms = [
            Phong.objects.create(
                co_so=self.facility,
                so_phong=f"UIX-{index:02d}",
                loai_phong=kind,
                tang=(index % 6) + 1,
                gia_thue=Decimal(price),
                dien_tich=Decimal(area),
                so_nguoi_toi_da=capacity,
                tien_coc_mac_dinh=Decimal("500000"),
                trang_thai=status,
                tien_ich="Wifi, may lanh, tu lanh, ban hoc",
                mo_ta="Phong mau phuc vu audit UI/UX.",
            )
            for index, (kind, status, price, area, capacity) in enumerate(
                [
                    ("phong_tieu_chuan", "trong", "3200000", "24", 2),
                    ("phong_cao_cap", "da_dat", "4200000", "32", 3),
                    ("phong_gac_lung", "dang_thue", "3800000", "30", 4),
                    ("can_ho_mini", "bao_tri", "5200000", "40", 4),
                    ("phong_tieu_chuan", "trong", "3000000", "22", 2),
                    ("phong_cao_cap", "trong", "4500000", "34", 3),
                ],
                start=1,
            )
        ]

    def _cookie(self, user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_capture_sample_screens(self):
        label = os.environ.get("NDT_UIUX_AUDIT_LABEL", "current")
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru"
            / "kiem_thu"
            / "uiux_sample"
            / label
        )
        output.mkdir(parents=True, exist_ok=True)

        screens = [
            ("room_list", reverse("quan_ly_phong")),
            ("room_edit", reverse("sua_phong", args=[self.rooms[0].pk])),
            ("facility_detail", reverse("chi_tiet_co_so", args=[self.facility.pk])),
        ]
        viewports = {
            "1440": (1440, 900),
            "1024": (1024, 768),
            "768": (768, 900),
            "390": (390, 844),
        }
        cookie = self._cookie(self.admin)
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        results = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for screen, path in screens:
                for viewport, (width, height) in viewports.items():
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.add_cookies(
                        [{
                            "name": settings.SESSION_COOKIE_NAME,
                            "value": cookie,
                            "url": self.live_server_url,
                        }]
                    )
                    page = context.new_page()
                    errors = []
                    page.on(
                        "console",
                        lambda message: errors.append(f"console:{message.type}:{message.text}")
                        if message.type == "error"
                        else None,
                    )
                    page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                    page.on("dialog", lambda dialog: errors.append(f"native-dialog:{dialog.type}"))
                    response = page.goto(self.live_server_url + path, wait_until="networkidle")
                    page.keyboard.press("Tab")
                    metrics = page.evaluate(
                        """() => {
                            const visible = element => {
                                const style = getComputedStyle(element);
                                const rect = element.getBoundingClientRect();
                                return style.display !== 'none' && style.visibility !== 'hidden'
                                    && rect.width > 0 && rect.height > 0;
                            };
                            const active = document.activeElement;
                            const focusStyle = active ? getComputedStyle(active) : null;
                            return {
                                cw: document.documentElement.clientWidth,
                                sw: document.documentElement.scrollWidth,
                                broken: [...document.images].filter(image => image.complete && image.naturalWidth === 0).length,
                                focusVisible: !!active && active !== document.body && focusStyle
                                    && (focusStyle.outlineStyle !== 'none' || focusStyle.boxShadow !== 'none'),
                                foundation: !!document.querySelector('.ndt-foundation'),
                                buttons: [...document.querySelectorAll('button, a[href]')]
                                    .filter(visible)
                                    .map(element => ({
                                        text: (element.innerText || element.getAttribute('aria-label') || '').trim(),
                                        classes: element.className || '',
                                        href: element.getAttribute('href') || '',
                                    })),
                                containerWidths: [...document.querySelectorAll('main, .room-management, .facility-detail')]
                                    .filter(visible)
                                    .map(element => Math.round(element.getBoundingClientRect().width)),
                            };
                        }"""
                    )
                    screenshot = output / f"{screen}_{viewport}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    interaction = None
                    if viewport == "390" and screen == "room_list":
                        trigger = page.locator("[data-ndt-confirm-form] button[type=submit]").first
                        trigger.focus()
                        trigger.click()
                        dialog = page.locator("[data-ndt-dialog]")
                        interaction = {
                            "delete_dialog_opened": dialog.is_visible(),
                            "delete_dialog_focus_confirm": page.locator("[data-ndt-dialog-confirm]").evaluate(
                                "element => element === document.activeElement"
                            ),
                        }
                        page.keyboard.press("Escape")
                        interaction["delete_dialog_closed"] = dialog.is_hidden()
                        interaction["delete_focus_returned"] = trigger.evaluate(
                            "element => element === document.activeElement"
                        )
                    elif viewport == "390" and screen == "facility_detail":
                        summary = page.locator(".facility-edit-panel summary").first
                        summary.focus()
                        summary.click()
                        form = page.locator(".facility-edit-form")
                        trigger = page.locator("[data-ndt-confirm-form] button[type=submit]").first
                        trigger.focus()
                        trigger.click()
                        dialog = page.locator("[data-ndt-dialog]")
                        interaction = {
                            "edit_panel_opened": form.is_visible(),
                            "status_dialog_opened": dialog.is_visible(),
                            "status_dialog_focus_confirm": page.locator("[data-ndt-dialog-confirm]").evaluate(
                                "element => element === document.activeElement"
                            ),
                        }
                        page.keyboard.press("Escape")
                        interaction["status_dialog_closed"] = dialog.is_hidden()
                        interaction["status_focus_returned"] = trigger.evaluate(
                            "element => element === document.activeElement"
                        )
                    results.append({
                        "screen": screen,
                        "path": path,
                        "viewport": f"{width}x{height}",
                        "status": response.status if response else None,
                        "overflow": metrics["sw"] > metrics["cw"],
                        "broken_images": metrics["broken"],
                        "errors": errors,
                        "focus_visible": metrics["focusVisible"],
                        "foundation_root": metrics["foundation"],
                        "container_widths": metrics["containerWidths"],
                        "buttons": metrics["buttons"],
                        "interaction": interaction,
                        "screenshot": screenshot.name,
                    })
                    context.close()
            browser.close()

        (output / "results.json").write_text(
            json.dumps(
                {
                    "label": label,
                    "case_count": len(results),
                    "cases": results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        self.assertEqual(len(results), len(screens) * len(viewports))
        for result in results:
            self.assertEqual(result["status"], 200, result)
            self.assertFalse(result["overflow"], result)
            self.assertEqual(result["broken_images"], 0, result)
            self.assertEqual(result["errors"], [], result)
            if result["interaction"] is not None:
                self.assertTrue(all(result["interaction"].values()), result)
