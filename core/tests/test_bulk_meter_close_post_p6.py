from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import (
    DatPhong,
    HoaDon,
    HopDong,
    NguoiThue,
    NhatKyThaoTac,
    Phong,
    ThongBao,
)
from core.views_hoa_don import chot_chi_so_dien_hang_loat


class BulkMeterCloseSourceContractTests(SimpleTestCase):
    def source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def test_route_entry_point_and_assets_are_present(self):
        url = reverse("chot_chi_so_dien_hang_loat")
        self.assertEqual(url, "/quan-ly-hoa-don/chot-chi-so-hang-loat/")
        self.assertIs(resolve(url).func, chot_chi_so_dien_hang_loat)
        invoice_list = self.source("templates/core/quan_ly_hoa_don.html")
        self.assertIn("{% url 'chot_chi_so_dien_hang_loat' %}", invoice_list)

    def test_template_and_css_are_p5_scoped(self):
        template = self.source("templates/core/chot_chi_so_dien_hang_loat.html")
        self.assertIn("ndt-f5 ndt-invoice-management ndt-bulk-meter-close", template)
        self.assertIn("css/foundation/p5.css", template)
        self.assertIn("css/bulk_meter_close_post_p6.css", template)
        self.assertIn("js/bulk_meter_close_post_p6.js", template)
        self.assertIn("{% csrf_token %}", template)
        self.assertNotIn("<style", template.lower())
        css = self.source("static/css/bulk_meter_close_post_p6.css")
        self.assertIn(".ndt-f5.ndt-bulk-meter-close", css)
        self.assertNotIn("!important", css)


class BulkMeterCloseRequestTests(BusinessFixture):
    target_month = 10
    target_year = 2026

    def setUp(self):
        self.room.tien_dien_moi_so = Decimal("3500")
        self.room.tien_nuoc_moi_khoi = Decimal("15000")
        self.room.phi_dich_vu = Decimal("100000")
        self.room.save(update_fields=[
            "tien_dien_moi_so", "tien_nuoc_moi_khoi", "phi_dich_vu"
        ])
        self.contract_one = self.contract(
            start=date(2026, 1, 1),
            end=date(2027, 1, 31),
        )
        self.contract_one.so_nguoi_o = 2
        self.contract_one.save(update_fields=["so_nguoi_o"])
        self.previous = HoaDon.objects.create(
            hop_dong=self.contract_one,
            thang=9,
            nam=2026,
            tien_phong=Decimal("2500000"),
            tien_dien=Decimal("350000"),
            chi_so_dien_cu=Decimal("0"),
            chi_so_dien_moi=Decimal("100"),
            don_gia_dien=Decimal("3500"),
            han_thanh_toan=date(2026, 9, 20),
        )

        self.second_user = User.objects.create_user("bulk-meter-tenant")
        self.second_tenant = NguoiThue.objects.create(
            tai_khoan=self.second_user,
            ho_ten="Bulk Meter Tenant",
            so_dien_thoai="0900005006",
            cccd="000000005006",
        )
        self.second_room = Phong.objects.create(
            co_so=self.facility,
            so_phong="BULK-2",
            gia_thue=Decimal("3000000"),
            dien_tich=Decimal("30"),
            so_nguoi_toi_da=2,
            tien_dien_moi_so=Decimal("4000"),
            tien_nuoc_moi_khoi=Decimal("20000"),
            phi_dich_vu=Decimal("50000"),
            tien_coc_mac_dinh=Decimal("600000"),
        )
        booking = DatPhong.objects.create(
            nguoi_thue=self.second_tenant,
            phong=self.second_room,
            ngay_nhan_phong=date(2026, 1, 1),
            ngay_tra_du_kien=date(2027, 1, 31),
            so_thang_thue=12,
            trang_thai="da_duyet",
        )
        self.contract_two = HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong="HD-BULK-2",
            ngay_bat_dau=date(2026, 1, 1),
            ngay_ket_thuc=date(2027, 1, 31),
            tien_thue_thang=Decimal("3000000"),
            so_nguoi_o=1,
            trang_thai="dang_hieu_luc",
        )

    def url(self):
        return reverse("chot_chi_so_dien_hang_loat")

    def payload(self, **changes):
        payload = {
            "thang": str(self.target_month),
            "nam": str(self.target_year),
            "han_thanh_toan": "2026-10-20",
            "hop_dong_ids": [str(self.contract_one.pk), str(self.contract_two.pk)],
            f"chi_so_cu_{self.contract_one.pk}": "100",
            f"chi_so_moi_{self.contract_one.pk}": "150",
            f"chi_so_cu_{self.contract_two.pk}": "0",
            f"chi_so_moi_{self.contract_two.pk}": "20",
        }
        payload.update(changes)
        return payload

    def login_admin(self):
        self.client.force_login(self.admin)

    def target_invoices(self):
        return HoaDon.objects.filter(thang=self.target_month, nam=self.target_year)

    def test_access_is_admin_only(self):
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url()).status_code, 302)
        self.login_admin()
        self.assertEqual(self.client.get(self.url(), {
            "thang": self.target_month,
            "nam": self.target_year,
        }).status_code, 200)

    def test_get_is_read_only_and_exposes_continuity_hint(self):
        self.login_admin()
        before = list(HoaDon.objects.order_by("pk").values_list(
            "pk", "trang_thai", "ngay_cap_nhat"
        ))
        response = self.client.get(self.url(), {
            "thang": self.target_month,
            "nam": self.target_year,
        })
        self.assertEqual(response.status_code, 200)
        rows = {item.pk: item for item in response.context["hop_dongs"]}
        self.assertEqual(rows[self.contract_one.pk].chi_so_dien_cu_goi_y, Decimal("100"))
        self.assertTrue(rows[self.contract_one.pk].co_the_chot)
        self.assertTrue(rows[self.contract_two.pk].co_the_chot)
        self.assertEqual(
            list(HoaDon.objects.order_by("pk").values_list("pk", "trang_thai", "ngay_cap_nhat")),
            before,
        )

    def test_success_creates_exact_snapshots_notifications_and_audits(self):
        self.login_admin()
        response = self.client.post(self.url(), self.payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.target_invoices().count(), 2)

        first = self.target_invoices().get(hop_dong=self.contract_one)
        self.assertEqual(first.chi_so_dien_cu, Decimal("100"))
        self.assertEqual(first.chi_so_dien_moi, Decimal("150"))
        self.assertEqual(first.don_gia_dien, Decimal("3500"))
        self.assertEqual(first.tien_dien, Decimal("175000"))
        self.assertEqual(first.tien_nuoc, Decimal("30000"))
        self.assertEqual(first.tien_dich_vu, Decimal("100000"))
        self.assertEqual(first.tong_tien, Decimal("2805000"))
        self.assertEqual(first.nguoi_lap, self.admin)

        second = self.target_invoices().get(hop_dong=self.contract_two)
        self.assertEqual(second.tien_dien, Decimal("80000"))
        self.assertEqual(second.tien_nuoc, Decimal("20000"))
        self.assertEqual(second.tien_dich_vu, Decimal("50000"))
        self.assertEqual(second.tong_tien, Decimal("3150000"))
        self.assertEqual(ThongBao.objects.filter(loai="thanh_toan").count(), 2)
        self.assertEqual(
            NhatKyThaoTac.objects.filter(
                module="Hóa đơn", hanh_dong="Tạo hàng loạt"
            ).count(),
            2,
        )

    def test_unselected_contract_is_not_created(self):
        self.login_admin()
        payload = self.payload()
        payload["hop_dong_ids"] = [str(self.contract_one.pk)]
        response = self.client.post(self.url(), payload)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(self.target_invoices().filter(hop_dong=self.contract_one).exists())
        self.assertFalse(self.target_invoices().filter(hop_dong=self.contract_two).exists())

    def test_invalid_second_row_rolls_back_entire_batch(self):
        self.login_admin()
        response = self.client.post(
            self.url(),
            self.payload(**{f"chi_so_moi_{self.contract_two.pk}": "-1"}),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.target_invoices().count(), 0)
        self.assertEqual(ThongBao.objects.filter(loai="thanh_toan").count(), 0)
        self.assertEqual(
            NhatKyThaoTac.objects.filter(hanh_dong="Tạo hàng loạt").count(),
            0,
        )

    def test_stale_duplicate_rolls_back_entire_batch(self):
        HoaDon.objects.create(
            hop_dong=self.contract_two,
            thang=self.target_month,
            nam=self.target_year,
            tien_phong=Decimal("1"),
            han_thanh_toan=date(2026, 10, 20),
        )
        self.login_admin()
        response = self.client.post(self.url(), self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.target_invoices().count(), 1)
        self.assertFalse(self.target_invoices().filter(hop_dong=self.contract_one).exists())

    def test_later_invoice_blocks_backdated_close(self):
        HoaDon.objects.create(
            hop_dong=self.contract_two,
            thang=11,
            nam=2026,
            tien_phong=Decimal("1"),
            han_thanh_toan=date(2026, 11, 20),
        )
        self.login_admin()
        response = self.client.get(self.url(), {"thang": 10, "nam": 2026})
        row = next(item for item in response.context["hop_dongs"] if item.pk == self.contract_two.pk)
        self.assertTrue(row.co_hoa_don_sau)
        self.assertFalse(row.co_the_chot)

        response = self.client.post(self.url(), self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.target_invoices().count(), 0)

    def test_contract_outside_period_cannot_be_submitted(self):
        self.contract_two.ngay_bat_dau = date(2026, 11, 1)
        self.contract_two.save(update_fields=["ngay_bat_dau"])
        self.login_admin()
        response = self.client.post(self.url(), self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.target_invoices().count(), 0)

    def test_invalid_period_fails_closed_without_writes(self):
        self.login_admin()
        before_invoices = HoaDon.objects.count()
        before_notifications = ThongBao.objects.count()
        before_audits = NhatKyThaoTac.objects.count()
        response = self.client.post(self.url(), self.payload(thang="13"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["thang"], "13")
        self.assertEqual(response.context["hop_dongs"], [])
        self.assertEqual(HoaDon.objects.count(), before_invoices)
        self.assertEqual(ThongBao.objects.count(), before_notifications)
        self.assertEqual(NhatKyThaoTac.objects.count(), before_audits)
        self.assertEqual(self.target_invoices().count(), 0)
        self.assertEqual(ThongBao.objects.filter(loai="thanh_toan").count(), 0)
        self.assertEqual(
            NhatKyThaoTac.objects.filter(hanh_dong="Tạo hàng loạt").count(),
            0,
        )
