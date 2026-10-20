from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import CoSo, Phong


class Phase03P0FlowTests(TestCase):
    password = "safe-registration-password"

    def setUp(self):
        self.facility = CoSo.objects.create(
            ten_co_so="Phase 03 Facility", dia_chi="1 Test Street", quan="Hai Chau"
        )
        self.room = Phong.objects.create(
            co_so=self.facility,
            so_phong="P03-01",
            loai_phong="phong_tieu_chuan",
            gia_thue=Decimal("2500000"),
            dien_tich=Decimal("24"),
            so_nguoi_toi_da=2,
        )
        self.checkin = timezone.localdate() + timedelta(days=7)
        self.period = {
            "ngay_nhan_phong": self.checkin.isoformat(),
            "so_thang_thue": "3",
        }

    def test_home_exposes_optional_canonical_availability_inputs_and_browse_still_works(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'name="ngay_nhan_phong"')
        self.assertContains(response, 'name="so_thang_thue"')
        self.assertContains(response, reverse("danh_sach_phong"))
        browse = self.client.get(reverse("danh_sach_phong"), {"q": "P03-01"})
        self.assertEqual(browse.status_code, 200)
        self.assertContains(browse, self.room.so_phong)

    def test_period_journey_keeps_room_date_and_months_for_public_detail(self):
        listing = self.client.get(reverse("danh_sach_phong"), self.period)
        self.assertEqual(listing.status_code, 200)
        self.assertIn(self.room.pk, [room.pk for room in listing.context["phong"]])
        detail = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]), self.period)
        booking_url = reverse("dat_phong", args=[self.room.pk])
        self.assertContains(detail, "Tiếp tục đặt phòng")
        self.assertContains(
            detail,
            f"{booking_url}?ngay_nhan_phong={self.checkin.isoformat()}&amp;so_thang_thue=3",
        )
        booking = self.client.get(f"{booking_url}?ngay_nhan_phong={self.checkin.isoformat()}&so_thang_thue=3")
        self.assertRedirects(
            booking,
            f"{reverse('dang_nhap')}?next={booking_url}%3Fngay_nhan_phong%3D{self.checkin.isoformat()}%26so_thang_thue%3D3",
            fetch_redirect_response=False,
        )

    def test_staff_never_sees_tenant_booking_cta_for_selected_period(self):
        staff = User.objects.create_user("phase03-staff", password=self.password, is_staff=True)
        self.client.force_login(staff)
        response = self.client.get(reverse("chi_tiet_phong", args=[self.room.pk]), self.period)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Tiếp tục đặt phòng")
        self.assertNotContains(response, reverse("dat_phong", args=[self.room.pk]))

    def test_registration_preserves_safe_booking_return_and_login_uses_it(self):
        booking_url = f"{reverse('dat_phong', args=[self.room.pk])}?ngay_nhan_phong={self.checkin.isoformat()}&so_thang_thue=3"
        registration = {
            "username": "phase03-new-tenant",
            "password": self.password,
            "password_confirm": self.password,
            "ho_ten": "Phase Three Tenant",
            "so_dien_thoai": "0901234567",
            "email": "phase03@example.com",
            "cccd": "123456789012",
            "next": booking_url,
        }
        response = self.client.get(reverse("dang_ky"), {"next": booking_url})
        self.assertEqual(response.context["next"], booking_url)
        response = self.client.post(reverse("dang_ky"), registration)
        self.assertRedirects(
            response,
            f"{reverse('dang_nhap')}?{urlencode({'next': booking_url})}",
            fetch_redirect_response=False,
        )
        response = self.client.post(reverse("dang_nhap"), {
            "username": registration["username"], "password": self.password, "next": booking_url,
        })
        self.assertRedirects(response, booking_url, fetch_redirect_response=False)

    def test_registration_rejects_unsafe_return_and_keeps_default_login_redirect(self):
        unsafe = "https://evil.example/booking"
        response = self.client.get(reverse("dang_ky"), {"next": unsafe})
        self.assertNotContains(response, unsafe)
        response = self.client.post(reverse("dang_ky"), {
            "username": "phase03-safe-tenant",
            "password": self.password,
            "password_confirm": self.password,
            "ho_ten": "Safe Tenant",
            "so_dien_thoai": "0901234568",
            "email": "phase03-safe@example.com",
            "cccd": "123456789013",
            "next": unsafe,
        })
        self.assertRedirects(response, reverse("dang_nhap"), fetch_redirect_response=False)
