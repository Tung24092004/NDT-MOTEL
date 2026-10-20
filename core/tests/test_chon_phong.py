from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.models import CoSo, DatPhong, HopDong, NguoiThue, Phong, ThanhToanCocDatPhong


class ChooseRoomTests(TestCase):
    def setUp(self):
        self.facility = CoSo.objects.create(
            ten_co_so="Co so ROOM-03", dia_chi="3 Duong Test", quan="Hai Chau"
        )
        self.room = self.create_room("ROOM-03")
        self.user = User.objects.create_user("room-choice-user", password="Safe-pass-123")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.user,
            ho_ten="Nguoi chon phong",
            cccd="012345678901",
            so_dien_thoai="0900123456",
        )

    def create_room(self, number, **overrides):
        values = {
            "co_so": self.facility,
            "so_phong": number,
            "loai_phong": "phong_tieu_chuan",
            "gia_thue": Decimal("2500000"),
            "dien_tich": Decimal("24"),
            "so_nguoi_toi_da": 2,
        }
        values.update(overrides)
        return Phong.objects.create(**values)

    def create_hold(self, room):
        account = User.objects.create_user("room-hold-tenant")
        tenant = NguoiThue.objects.create(
            tai_khoan=account,
            ho_ten="Nguoi giu cho",
            cccd="012345678902",
            so_dien_thoai="0900123457",
        )
        return DatPhong.objects.create(
            nguoi_thue=tenant,
            phong=room,
            ngay_nhan_phong=timezone.localdate() + timedelta(days=1),
            so_thang_thue=1,
            trang_thai="cho_duyet",
        )

    def test_available_room_shows_choose_action_and_get_reaches_existing_booking_step(self):
        detail = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertContains(detail, "Chọn phòng")
        self.assertContains(detail, "room-actions")
        self.assertContains(detail, "room-primary-action")

        before = DatPhong.objects.count()
        self.client.force_login(self.user)
        response = self.client.get(reverse("dat_phong", args=[self.room.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["phong"].pk, self.room.pk)
        self.assertEqual(DatPhong.objects.count(), before)

    def test_unavailable_or_invalid_price_room_cannot_continue(self):
        self.room.trang_thai = "bao_tri"
        self.room.save(update_fields=["trang_thai"])
        detail = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertNotContains(detail, "room-primary-action")
        self.assertContains(detail, "room-unavailable-reason")

        self.client.force_login(self.user)
        response = self.client.get(reverse("dat_phong", args=[self.room.pk]), follow=True)
        self.assertRedirects(response, reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertIn("Phòng hiện không thể thuê", " ".join(map(str, get_messages(response.wsgi_request))))

        priced_room = self.create_room("ROOM-03-PRICE", gia_thue=Decimal("0"))
        response = self.client.get(reverse("dat_phong", args=[priced_room.pk]))
        self.assertRedirects(response, reverse("chi_tiet_phong", args=[priced_room.pk]))

    def test_guest_login_return_and_live_recheck_do_not_create_business_data(self):
        booking_url = reverse("dat_phong", args=[self.room.pk])
        response = self.client.get(booking_url)
        self.assertRedirects(response, f"{reverse('dang_nhap')}?next={booking_url}")
        response = self.client.post(
            reverse("dang_nhap"),
            {"username": self.user.username, "password": "Safe-pass-123", "next": booking_url},
        )
        self.assertRedirects(response, booking_url)
        self.client.logout()
        response = self.client.get(f"{booking_url}?next=https://outside.example/")
        self.assertRedirects(response, f"{reverse('dang_nhap')}?next={booking_url}%3Fnext%3Dhttps%3A//outside.example/")

        self.client.force_login(self.user)
        detail = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertContains(detail, "Chọn phòng")
        hold = self.create_hold(self.room)
        before = {
            "bookings": DatPhong.objects.count(),
            "contracts": HopDong.objects.count(),
            "room_status": Phong.objects.get(pk=self.room.pk).trang_thai,
        }
        response = self.client.get(booking_url, follow=True)
        self.assertRedirects(response, reverse("chi_tiet_phong", args=[self.room.pk]))
        self.assertIn("Phòng hiện không thể thuê", " ".join(map(str, get_messages(response.wsgi_request))))
        self.assertEqual(DatPhong.objects.count(), before["bookings"])
        self.assertEqual(ThanhToanCocDatPhong.objects.count(), 0)
        self.assertEqual(HopDong.objects.count(), before["contracts"])
        self.assertEqual(Phong.objects.get(pk=self.room.pk).trang_thai, before["room_status"])
        self.assertTrue(hold.pk)

    def test_login_rejects_external_next_after_credentials_are_valid(self):
        for unsafe_next in ("https://outside.example/", "//outside.example/path"):
            with self.subTest(unsafe_next=unsafe_next):
                response = self.client.post(
                    reverse("dang_nhap"),
                    {"username": self.user.username, "password": "Safe-pass-123", "next": unsafe_next},
                )
                self.assertRedirects(response, reverse("tai_khoan"))
                self.client.logout()

    def test_non_public_missing_and_admin_cannot_use_choose_action(self):
        hidden_facility = CoSo.objects.create(
            ten_co_so="Co so an", dia_chi="4 Duong Test", quan="Hai Chau", trang_thai="tam_ngung"
        )
        hidden_room = Phong.objects.create(
            co_so=hidden_facility,
            so_phong="ROOM-03-HIDDEN",
            loai_phong="phong_tieu_chuan",
            gia_thue=Decimal("2500000"),
            dien_tich=Decimal("24"),
        )
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("dat_phong", args=[999999])).status_code, 404)
        self.assertEqual(self.client.get(reverse("dat_phong", args=[hidden_room.pk])).status_code, 404)

        admin = User.objects.create_user("room-choice-admin", password="Safe-pass-123", is_staff=True)
        self.client.force_login(admin)
        response = self.client.get(reverse("dat_phong", args=[self.room.pk]))
        self.assertRedirects(response, reverse("dashboard_admin"))


class ChooseRoomBrowserSmoke(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("ROOM-03 browser smoke requires isolated test_ndt_motel.")

    def setUp(self):
        facility = CoSo.objects.create(ten_co_so="Co so browser ROOM-03", dia_chi="Smoke QA", quan="Hai Chau")
        self.available = Phong.objects.create(
            co_so=facility, so_phong="ROOM-03-BROWSER", loai_phong="phong_tieu_chuan",
            gia_thue=Decimal("2500000"), dien_tich=Decimal("24"), so_nguoi_toi_da=2,
        )
        self.blocked = Phong.objects.create(
            co_so=facility, so_phong="ROOM-03-BLOCKED", loai_phong="phong_tieu_chuan",
            gia_thue=Decimal("2500000"), dien_tich=Decimal("24"), so_nguoi_toi_da=2,
            trang_thai="bao_tri",
        )
        self.user = User.objects.create_user("room-browser-user", password="Safe-pass-123")
        NguoiThue.objects.create(
            tai_khoan=self.user, ho_ten="Nguoi dung browser", cccd="012345678901",
            so_dien_thoai="0900123456",
        )

    @staticmethod
    def _cookie(user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    @staticmethod
    def _assert_clean_page(page, errors, failed):
        metrics = page.evaluate("""() => ({
            width: document.documentElement.clientWidth,
            scroll: document.documentElement.scrollWidth,
        })""")
        assert metrics["scroll"] <= metrics["width"], metrics
        assert not failed, failed
        assert not errors, errors

    def test_guest_user_and_blocked_room_browser_smoke(self):
        available_detail = reverse("chi_tiet_phong", args=[self.available.pk])
        available_booking = reverse("dat_phong", args=[self.available.pk])
        blocked_detail = reverse("chi_tiet_phong", args=[self.blocked.pk])
        blocked_booking = reverse("dat_phong", args=[self.blocked.pk])
        before = (DatPhong.objects.count(), ThanhToanCocDatPhong.objects.count(), HopDong.objects.count())
        user_cookie = self._cookie(self.user)
        errors, failed = [], []
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            guest = browser.new_context(viewport={"width": 1440, "height": 900})
            guest.route("**/favicon.ico", lambda route: route.fulfill(status=204))
            guest_page = guest.new_page()
            for page in (guest_page,):
                page.on("console", lambda msg: errors.append(f"{msg.text} @ {msg.location['url']}") if msg.type == "error" else None)
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.on("requestfailed", lambda req: failed.append(req.url))
                page.on("response", lambda response: failed.append(f"HTTP {response.status}: {response.url}") if response.status >= 400 else None)
            guest_page.goto(self.live_server_url + available_detail, wait_until="networkidle")
            guest_page.get_by_role("link", name="Chọn phòng").click()
            guest_page.wait_for_url("**/dang-nhap/**")
            login_form = guest_page.locator("form.p6i-form")
            login_form.locator('input[name="username"]').fill(self.user.username)
            login_form.locator('input[name="password"]').fill("Safe-pass-123")
            login_form.locator('button[type="submit"]').click()
            guest_page.wait_for_url("**" + available_booking)
            self.assertTrue(guest_page.get_by_text(self.available.so_phong).first.is_visible())
            self._assert_clean_page(guest_page, errors, failed)
            guest.close()

            tenant = browser.new_context(viewport={"width": 390, "height": 844})
            tenant.route("**/favicon.ico", lambda route: route.fulfill(status=204))
            tenant.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": user_cookie, "url": self.live_server_url}])
            tenant_page = tenant.new_page()
            tenant_page.on("console", lambda msg: errors.append(f"{msg.text} @ {msg.location['url']}") if msg.type == "error" else None)
            tenant_page.on("pageerror", lambda err: errors.append(str(err)))
            tenant_page.on("requestfailed", lambda req: failed.append(req.url))
            tenant_page.on("response", lambda response: failed.append(f"HTTP {response.status}: {response.url}") if response.status >= 400 else None)
            tenant_page.goto(self.live_server_url + available_detail, wait_until="networkidle")
            tenant_page.get_by_role("link", name="Chọn phòng").click()
            tenant_page.wait_for_url("**" + available_booking)
            self.assertTrue(tenant_page.get_by_text(self.available.so_phong).first.is_visible())
            self._assert_clean_page(tenant_page, errors, failed)
            tenant_page.goto(self.live_server_url + blocked_detail, wait_until="networkidle")
            self.assertFalse(tenant_page.locator(".room-primary-action").is_visible())
            self.assertTrue(tenant_page.locator(".room-unavailable-reason").is_visible())
            tenant_page.goto(self.live_server_url + blocked_booking, wait_until="networkidle")
            self.assertTrue(tenant_page.url.endswith(blocked_detail))
            self._assert_clean_page(tenant_page, errors, failed)
            tenant.close(); browser.close()

        self.assertEqual((DatPhong.objects.count(), ThanhToanCocDatPhong.objects.count(), HopDong.objects.count()), before)
