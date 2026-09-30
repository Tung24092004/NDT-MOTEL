"""Visual audit co lap cho Chang 2A: danh sach va chi tiet dat phong cua User."""

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
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.dich_vu.dat_phong import create_booking
from core.dich_vu.tien_coc import get_or_create_deposit, report_paid
from core.models import CoSo, DatPhong, NguoiThue, Phong


class BookingStage02AVisualAudit(StaticLiveServerTestCase):
    """Chup hai route that va xac minh quyen/hien thi ma khong gui POST."""

    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        self.today = timezone.localdate()
        self.admin = User.objects.create_user("stage02a-admin", is_staff=True)
        self.user = User.objects.create_user("stage02a-tenant")
        self.empty_user = User.objects.create_user("stage02a-empty")
        self.other_user = User.objects.create_user("stage02a-other")
        self.tenant = self._tenant(self.user, "Nguyen Minh Anh", "000000002001")
        self._tenant(self.empty_user, "Le An Nhien", "000000002002")
        self.other_tenant = self._tenant(self.other_user, "Tran Gia Han", "000000002003")
        self.facility = CoSo.objects.create(
            ten_co_so="NDT Motel Hoa Xuan",
            dia_chi="125 Nguyen Phuoc Lan",
            quan="Cam Le",
            so_dien_thoai="0905123456",
            email="hoaxuan@ndtmotel.vn",
        )
        rooms = [self._room(f"B20{index}", Decimal("3200000") + index * 150000) for index in range(1, 7)]

        self.unpaid = self._new_booking(rooms[0], people=2, note="Can phong yen tinh de lam viec tai nha.")
        self.unpaid_payment = get_or_create_deposit(actor=self.user, booking_id=self.unpaid.pk)

        self.pending = self._new_booking(rooms[1], people=1, note="Du kien nhan phong vao buoi sang.")
        pending_payment = get_or_create_deposit(actor=self.user, booking_id=self.pending.pk)
        report_paid(actor=self.user, payment_id=pending_payment.pk, bank_transaction="STAGE02A-BANK-001")

        self.rejected = self._new_booking(rooms[2], people=1)
        rejected_payment = get_or_create_deposit(actor=self.user, booking_id=self.rejected.pk)
        DatPhong.objects.filter(pk=self.rejected.pk).update(
            trang_thai="tu_choi",
            ly_do_tu_choi="Phong khong con kha dung tai thoi diem xet duyet.",
        )
        type(rejected_payment).objects.filter(pk=rejected_payment.pk).update(
            trang_thai="tu_choi",
            ly_do_tu_choi="Giao dich chua tim thay tren sao ke.",
            active_slot=None,
        )

        self.cancelled = self._new_booking(rooms[3], people=1)
        cancelled_payment = get_or_create_deposit(actor=self.user, booking_id=self.cancelled.pk)
        DatPhong.objects.filter(pk=self.cancelled.pk).update(trang_thai="da_huy")
        type(cancelled_payment).objects.filter(pk=cancelled_payment.pk).update(
            trang_thai="da_huy",
            active_slot=None,
        )

        self.other_booking = DatPhong.objects.create(
            nguoi_thue=self.other_tenant,
            phong=rooms[4],
            ngay_nhan_phong=self.today + timedelta(days=20),
            so_thang_thue=3,
            ngay_tra_du_kien=self.today + timedelta(days=110),
            trang_thai="cho_duyet",
        )

    @staticmethod
    def _tenant(user, name, cccd):
        return NguoiThue.objects.create(
            tai_khoan=user,
            ho_ten=name,
            cccd=cccd,
            so_dien_thoai="09" + cccd[-8:],
            email=f"{user.username}@example.com",
        )

    def _room(self, number, rent):
        return Phong.objects.create(
            co_so=self.facility,
            so_phong=number,
            tang=2,
            loai_phong="phong_cao_cap",
            gia_thue=rent,
            dien_tich=Decimal("30"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("600000"),
            trang_thai="trong",
        )

    def _new_booking(self, room, people=1, note=""):
        companions = []
        if people > 1:
            companions.append({
                "ho_ten": "Tran Bao Chau",
                "cccd": "000000002099",
                "so_dien_thoai": "0900002099",
                "quan_he": "Ban be",
            })
        return create_booking(
            actor=self.user,
            room_id=room.pk,
            checkin=self.today + timedelta(days=14),
            months=6,
            people=people,
            companions=companions,
            accept_terms=True,
            allow_sharing=False,
            note=note,
        )

    @staticmethod
    def _cookie(user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    @staticmethod
    def _metrics(page):
        return page.evaluate(
            """() => {
                const visible = element => {
                    const style = getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    return style.display !== 'none' && style.visibility !== 'hidden'
                        && rect.width > 0 && rect.height > 0;
                };
                const actions = [...document.querySelectorAll('.booking-page a[href], .booking-page button')]
                    .filter(visible)
                    .map(element => ({
                        text: (element.innerText || element.getAttribute('aria-label') || '').trim(),
                        href: element.getAttribute('href'),
                        type: element.getAttribute('type'),
                    }));
                const controls = [...document.querySelectorAll('.booking-page input, .booking-page select, .booking-page textarea')]
                    .filter(element => element.type !== 'hidden' && visible(element));
                const buttons = [...document.querySelectorAll('.booking-page button, .booking-page .ndt-button')]
                    .filter(visible);
                const unlabeled = controls.filter(element => {
                    if (element.getAttribute('aria-label') || element.getAttribute('aria-labelledby')) return false;
                    if (element.closest('label')) return false;
                    return !element.id || !document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
                }).map(element => element.name || element.id);
                return {
                    client_width: document.documentElement.clientWidth,
                    scroll_width: document.documentElement.scrollWidth,
                    broken_images: [...document.images].filter(image => image.complete && image.naturalWidth === 0).length,
                    record_count: document.querySelectorAll('.booking-record').length,
                    actions,
                    unlabeled,
                    small_buttons: buttons.filter(element => {
                        const rect = element.getBoundingClientRect();
                        return rect.width < 44 || rect.height < 44;
                    }).map(element => (element.innerText || element.getAttribute('aria-label') || '').trim()),
                };
            }"""
        )

    def test_stage02a_visual_routes_states_and_permissions(self):
        label = os.environ.get("NDT_BOOKING_STAGE02A_LABEL", "current")
        output = Path(settings.BASE_DIR) / "luu_tru" / "kiem_thu" / "uiux_stage_02a_booking" / label
        output.mkdir(parents=True, exist_ok=True)
        screens = (
            ("booking_list_many", self.user, reverse("dat_phong_cua_toi")),
            ("booking_list_empty", self.empty_user, reverse("dat_phong_cua_toi")),
            ("booking_detail_unpaid", self.user, reverse("chi_tiet_dat_phong_cua_toi", args=[self.unpaid.pk])),
            ("booking_detail_pending", self.user, reverse("chi_tiet_dat_phong_cua_toi", args=[self.pending.pk])),
        )
        viewports = (("1440", 1440, 900), ("1024", 1024, 768), ("768", 768, 900), ("390", 390, 844))
        cookies = {user.pk: self._cookie(user) for _, user, _ in screens}
        admin_cookie = self._cookie(self.admin)
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        results = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for screen, user, path in screens:
                for viewport, width, height in viewports:
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
                    dialog_check = None
                    if screen == "booking_detail_unpaid" and viewport == "390":
                        page.locator("#cancel-reason").fill("Kiem tra dialog tren database test")
                        trigger = page.locator("[data-cancel-booking-form] button[type=submit]")
                        trigger.focus()
                        trigger.click()
                        dialog = page.locator("[data-ndt-dialog]")
                        dialog.wait_for(state="visible")
                        dialog_check = {
                            "opened": dialog.is_visible(),
                            "confirm_focused": page.locator("[data-ndt-dialog-confirm]").evaluate("el => el === document.activeElement"),
                        }
                        page.keyboard.press("Escape")
                        dialog.wait_for(state="hidden")
                        dialog_check["closed"] = dialog.is_hidden()
                        dialog_check["focus_returned"] = trigger.evaluate("el => el === document.activeElement")
                        page.locator("#cancel-reason").fill("")
                    page.keyboard.press("Tab")
                    focus_visible = page.evaluate(
                        """() => {
                            const style = getComputedStyle(document.activeElement);
                            return document.activeElement !== document.body
                                && (style.outlineStyle !== 'none' || style.boxShadow !== 'none');
                        }"""
                    )
                    page.evaluate("window.scrollTo(0, 0)")
                    metrics = self._metrics(page)
                    screenshot = output / f"{screen}_{viewport}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    results.append({
                        "case": screen,
                        "viewport": f"{width}x{height}",
                        "path": path,
                        "status": response.status if response else None,
                        "overflow": metrics["scroll_width"] > metrics["client_width"],
                        "broken_images": metrics["broken_images"],
                        "record_count": metrics["record_count"],
                        "actions": metrics["actions"],
                        "unlabeled": metrics["unlabeled"],
                        "small_buttons": metrics["small_buttons"],
                        "errors": errors,
                        "focus_visible": focus_visible,
                        "dialog": dialog_check,
                        "screenshot": screenshot.name,
                    })
                    context.close()

            protected = (
                ("guest-list", None, reverse("dat_phong_cua_toi"), reverse("dang_nhap")),
                ("admin-list", self.admin, reverse("dat_phong_cua_toi"), reverse("dashboard_admin")),
                ("guest-detail", None, reverse("chi_tiet_dat_phong_cua_toi", args=[self.unpaid.pk]), reverse("dang_nhap")),
                ("admin-detail", self.admin, reverse("chi_tiet_dat_phong_cua_toi", args=[self.unpaid.pk]), reverse("dashboard_admin")),
            )
            for case, user, path, expected in protected:
                context = browser.new_context()
                if user:
                    context.add_cookies([{
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": admin_cookie,
                        "url": self.live_server_url,
                    }])
                page = context.new_page()
                response = page.goto(self.live_server_url + path, wait_until="networkidle")
                results.append({
                    "case": case,
                    "status": response.status if response else None,
                    "path": path,
                    "final_path": urlsplit(page.url).path,
                    "expected_path": expected,
                })
                context.close()
            browser.close()

        (output / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

        for result in results:
            self.assertEqual(result["status"], 200, result)
            if "expected_path" in result:
                self.assertEqual(result["final_path"], result["expected_path"], result)
                continue
            self.assertFalse(result["overflow"], result)
            self.assertEqual(result["broken_images"], 0, result)
            self.assertEqual(result["errors"], [], result)
            self.assertEqual(result["unlabeled"], [], result)
            self.assertEqual(result["small_buttons"], [], result)
            self.assertTrue(result["focus_visible"], result)
            if result["dialog"]:
                self.assertEqual(
                    result["dialog"],
                    {"opened": True, "confirm_focused": True, "closed": True, "focus_returned": True},
                    result,
                )

        main = next(result for result in results if result["case"] == "booking_list_many")
        self.assertGreaterEqual(main["record_count"], 4, main)
        main_actions = [action["text"] for action in main["actions"]]
        self.assertIn("Xem chi tiết", main_actions)
        self.assertIn("Chuyển khoản cọc", main_actions)
        unpaid = next(result for result in results if result["case"] == "booking_detail_unpaid")
        self.assertIn("Hủy yêu cầu", [action["text"] for action in unpaid["actions"]])
        pending = next(result for result in results if result["case"] == "booking_detail_pending")
        pending_actions = [action["text"] for action in pending["actions"]]
        self.assertNotIn("Hủy yêu cầu", pending_actions)
        self.assertIn("Gửi yêu cầu xử lý hủy", pending_actions)

        client = Client()
        client.force_login(self.user)
        self.assertEqual(
            client.get(reverse("chi_tiet_dat_phong_cua_toi", args=[self.other_booking.pk])).status_code,
            404,
        )
