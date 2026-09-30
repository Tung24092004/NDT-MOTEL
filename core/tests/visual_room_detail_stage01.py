"""Visual audit co lap cho chang 0-1 cua trang chi tiet phong."""

import json
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.models import CoSo, DatPhong, HopDong, NguoiThue, Phong


@override_settings(MEDIA_ROOT=Path(settings.BASE_DIR) / "media")
class RoomDetailStage01VisualAudit(StaticLiveServerTestCase):
    """Chup full page va kiem tra quyen hanh dong tren DB test."""

    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.admin = User.objects.create_user("room-audit-admin", is_staff=True)
        self.tenant_user = User.objects.create_user("room-audit-tenant")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="Nguyen Minh Anh",
            cccd="000000001501",
            so_dien_thoai="0900001501",
            email="minh.anh@example.com",
        )
        self.facility = CoSo.objects.create(
            ten_co_so="NDT Motel Hoa Xuan",
            dia_chi="125 Nguyen Phuoc Lan",
            quan="Cam Le",
            so_dien_thoai="0905123456",
            email="hoaxuan@ndtmotel.vn",
            tien_ich_chung=(
                "Bai giu xe co camera, may giat chung, san phoi va khoa cong an ninh."
            ),
            mo_ta=(
                "Co so yen tinh, thong thoang, thuan tien di chuyen den trung tam thanh pho."
            ),
        )
        self.available_room = self._room("A203", "trong")
        self.state_rooms = {
            "da_dat": self._room("S101", "da_dat"),
            "dang_thue": self._room("S201", "dang_thue"),
            "bao_tri": self._room("S301", "bao_tri"),
        }
        today = timezone.localdate()
        booked = DatPhong.objects.create(
            nguoi_thue=self.tenant,
            phong=self.state_rooms["da_dat"],
            ngay_nhan_phong=today + timedelta(days=7),
            so_thang_thue=6,
            ngay_tra_du_kien=today + timedelta(days=187),
            trang_thai="da_duyet",
        )
        rented = DatPhong.objects.create(
            nguoi_thue=self.tenant,
            phong=self.state_rooms["dang_thue"],
            ngay_nhan_phong=today - timedelta(days=30),
            so_thang_thue=6,
            ngay_tra_du_kien=today + timedelta(days=150),
            trang_thai="da_duyet",
        )
        HopDong.objects.create(
            dat_phong=rented,
            so_hop_dong=f"AUDIT-{rented.pk}",
            ngay_bat_dau=today - timedelta(days=30),
            ngay_ket_thuc=today + timedelta(days=150),
            tien_thue_thang=self.state_rooms["dang_thue"].gia_thue,
            trang_thai="dang_hieu_luc",
        )

    def _room(self, number, status):
        return Phong.objects.create(
            co_so=self.facility,
            so_phong=number,
            tang=2,
            loai_phong="phong_cao_cap",
            gia_thue=Decimal("3600000"),
            dien_tich=Decimal("31"),
            tien_ich=(
                "Dieu hoa, nong lanh, tu lanh, giuong, tu quan ao, ban lam viec va wifi."
            ),
            mo_ta=(
                "Phong don anh sang tu nhien, co khu nghi ngoi va khu lam viec tach biet. "
                "Noi that duoc bo tri gon gang de su dung lau dai."
            ),
            so_nguoi_toi_da=3,
            tien_dien_moi_so=Decimal("3500"),
            tien_nuoc_moi_khoi=Decimal("18000"),
            phi_dich_vu=Decimal("120000"),
            tien_coc_mac_dinh=Decimal("600000"),
            trang_thai=status,
        )

    @staticmethod
    def _cookie(user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    @staticmethod
    def _page_metrics(page):
        return page.evaluate(
            """() => {
                const visible = element => {
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden'
                        && rect.width > 0 && rect.height > 0;
                };
                const actions = [...document.querySelectorAll('a[href], button')]
                    .filter(visible)
                    .map(element => ({
                        text: (element.innerText || element.getAttribute('aria-label') || '').trim(),
                        href: element.getAttribute('href'),
                    }));
                return {
                    clientWidth: document.documentElement.clientWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    brokenImages: [...document.images]
                        .filter(image => image.complete && image.naturalWidth === 0).length,
                    galleryImages: document.querySelectorAll('.stay-gallery img').length,
                    thumbnailButtons: document.querySelectorAll('[data-gallery-src]').length,
                    actions,
                    title: document.title,
                };
            }"""
        )

    def test_room_detail_visual_and_permissions(self):
        label = os.environ.get("NDT_ROOM_DETAIL_AUDIT_LABEL", "current")
        output = (
            Path(settings.BASE_DIR)
            / "luu_tru"
            / "kiem_thu"
            / "uiux_stage_01_room_detail"
            / label
        )
        output.mkdir(parents=True, exist_ok=True)
        route = reverse("chi_tiet_phong", args=[self.available_room.pk])
        cookies = {
            "tenant": self._cookie(self.tenant_user),
            "admin": self._cookie(self.admin),
        }
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        results = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)

            # Anh doi chieu chinh: cung mot User, cung du lieu, ba viewport.
            for viewport, width, height in (
                ("1440", 1440, 900),
                ("768", 768, 900),
                ("390", 390, 844),
            ):
                context = browser.new_context(viewport={"width": width, "height": height})
                context.add_cookies(
                    [{
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": cookies["tenant"],
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
                response = page.goto(self.live_server_url + route, wait_until="networkidle")
                page.keyboard.press("Tab")
                focused = page.evaluate(
                    """() => {
                        const active = document.activeElement;
                        const style = active ? getComputedStyle(active) : null;
                        return {
                            tag: active ? active.tagName : null,
                            visible: !!style && (style.outlineStyle !== 'none' || style.boxShadow !== 'none'),
                        };
                    }"""
                )
                metrics = self._page_metrics(page)
                gallery_interaction = page.evaluate(
                    """async () => {
                        const main = document.querySelector('#stay-main-image');
                        const buttons = [...document.querySelectorAll('[data-gallery-src]')];
                        if (!main || buttons.length < 2) return null;
                        const before = main.currentSrc;
                        buttons[1].click();
                        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                        const result = {
                            before,
                            after: main.currentSrc,
                            active_index: buttons.findIndex(button => button.classList.contains('is-active')),
                            pressed: buttons.map(button => button.getAttribute('aria-pressed')),
                        };
                        buttons[0].click();
                        await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
                        return result;
                    }"""
                )
                screenshot = output / f"room_detail_tenant_{viewport}.png"
                page.screenshot(path=str(screenshot), full_page=True)
                results.append(
                    {
                        "case": "tenant-main",
                        "viewport": f"{width}x{height}",
                        "status": response.status if response else None,
                        "overflow": metrics["scrollWidth"] > metrics["clientWidth"],
                        "broken_images": metrics["brokenImages"],
                        "gallery_images": metrics["galleryImages"],
                        "thumbnail_buttons": metrics["thumbnailButtons"],
                        "errors": errors,
                        "focus": focused,
                        "actions": metrics["actions"],
                        "gallery_interaction": gallery_interaction,
                        "screenshot": screenshot.name,
                    }
                )
                context.close()

            # Ma tran quyen: khach, User va Admin tren cung phong trong.
            for role, cookie in (("guest", None), ("tenant", cookies["tenant"]), ("admin", cookies["admin"])):
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                if cookie:
                    context.add_cookies(
                        [{
                            "name": settings.SESSION_COOKIE_NAME,
                            "value": cookie,
                            "url": self.live_server_url,
                        }]
                    )
                page = context.new_page()
                response = page.goto(self.live_server_url + route, wait_until="networkidle")
                metrics = self._page_metrics(page)
                primary_selector = (
                    ".stay-actions .ndt-button--primary"
                    if role == "admin"
                    else ".stay-booking > .ndt-button--primary"
                )
                primary = page.locator(primary_selector).first
                results.append(
                    {
                        "case": f"role-{role}",
                        "status": response.status if response else None,
                        "actions": metrics["actions"],
                        "primary_action": {
                            "text": primary.inner_text().strip(),
                            "href": primary.get_attribute("href"),
                        },
                    }
                )
                context.close()

            # Ma tran trang thai giup phat hien nut dat phong hien sai dieu kien.
            for status, room in self.state_rooms.items():
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                context.add_cookies(
                    [{
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": cookies["tenant"],
                        "url": self.live_server_url,
                    }]
                )
                page = context.new_page()
                state_route = reverse("chi_tiet_phong", args=[room.pk])
                response = page.goto(self.live_server_url + state_route, wait_until="networkidle")
                metrics = self._page_metrics(page)
                results.append(
                    {
                        "case": f"state-{status}",
                        "status": response.status if response else None,
                        "actions": metrics["actions"],
                    }
                )
                context.close()

            # Truy cap truc tiep cac dich GET de xac minh redirect quyen, khong gui POST.
            booking_route = reverse("dat_phong", args=[self.available_room.pk])
            access_cases = [
                ("guest-booking-direct", None, booking_route, reverse("dang_nhap")),
                ("tenant-booking-direct", cookies["tenant"], booking_route, booking_route),
                ("admin-booking-direct", cookies["admin"], booking_route, reverse("dashboard_admin")),
            ]
            access_cases.extend(
                (
                    f"tenant-{status}-booking-direct",
                    cookies["tenant"],
                    reverse("dat_phong", args=[room.pk]),
                    reverse("chi_tiet_phong", args=[room.pk]),
                )
                for status, room in self.state_rooms.items()
            )
            edit_route = reverse("sua_phong", args=[self.available_room.pk])
            access_cases.extend(
                [
                    ("guest-edit-direct", None, edit_route, reverse("dang_nhap")),
                    ("tenant-edit-direct", cookies["tenant"], edit_route, reverse("tai_khoan")),
                    ("admin-edit-direct", cookies["admin"], edit_route, edit_route),
                ]
            )
            for case, cookie, requested_path, expected_final_path in access_cases:
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                if cookie:
                    context.add_cookies(
                        [{
                            "name": settings.SESSION_COOKIE_NAME,
                            "value": cookie,
                            "url": self.live_server_url,
                        }]
                    )
                page = context.new_page()
                response = page.goto(self.live_server_url + requested_path, wait_until="networkidle")
                results.append(
                    {
                        "case": case,
                        "requested_path": requested_path,
                        "final_url": page.url,
                        "final_path": urlsplit(page.url).path,
                        "expected_final_path": expected_final_path,
                        "status": response.status if response else None,
                    }
                )
                context.close()

            browser.close()

        (output / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for result in results:
            self.assertEqual(result["status"], 200, result)
            if result["case"] == "tenant-main":
                self.assertFalse(result["overflow"], result)
                self.assertEqual(result["broken_images"], 0, result)
                self.assertEqual(result["errors"], [], result)
                self.assertGreater(result["gallery_images"], 0, result)
                self.assertGreater(result["thumbnail_buttons"], 0, result)
                interaction = result["gallery_interaction"]
                self.assertIsNotNone(interaction, result)
                self.assertNotEqual(interaction["before"], interaction["after"], result)
                self.assertEqual(interaction["active_index"], 1, result)
                self.assertEqual(interaction["pressed"][1], "true", result)

            if "expected_final_path" in result:
                self.assertEqual(result["final_path"], result["expected_final_path"], result)

        if label == "after":
            actions = {
                result["case"]: result["actions"]
                for result in results
                if "actions" in result
            }
            action_texts = {
                case: [action["text"] for action in items]
                for case, items in actions.items()
            }
            self.assertIn("Đăng nhập để đặt phòng", action_texts["role-guest"])
            self.assertIn("Đặt phòng", action_texts["role-tenant"])
            self.assertIn("Sửa thông tin phòng", action_texts["role-admin"])
            self.assertNotIn("Đặt phòng", action_texts["role-admin"])
            role_results = {
                result["case"]: result
                for result in results
                if result["case"].startswith("role-")
            }
            self.assertEqual(
                role_results["role-guest"]["primary_action"]["href"],
                f'{reverse("dang_nhap")}?next={booking_route}',
            )
            self.assertEqual(
                role_results["role-tenant"]["primary_action"]["href"],
                booking_route,
            )
            self.assertEqual(
                role_results["role-admin"]["primary_action"]["href"],
                reverse("sua_phong", args=[self.available_room.pk]),
            )
            for status in ("da_dat", "dang_thue", "bao_tri"):
                self.assertNotIn("Đặt phòng", action_texts[f"state-{status}"])
