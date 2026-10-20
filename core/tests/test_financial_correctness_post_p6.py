from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse

from core.dich_vu.hoa_don import calculate_electricity_charge
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import HoaDon


class FinancialCorrectnessInvoiceTests(BusinessFixture):
    def setUp(self):
        self.room.tien_dien_moi_so = Decimal("3500")
        self.room.tien_nuoc_moi_khoi = Decimal("15000")
        self.room.save(update_fields=["tien_dien_moi_so", "tien_nuoc_moi_khoi"])
        self.contract_obj = self.contract()
        self.client.force_login(self.admin)

    def invoice_payload(self, **changes):
        payload = {
            "hop_dong": str(self.contract_obj.pk),
            "thang": "10",
            "nam": "2026",
            "han_thanh_toan": (self.today + timedelta(days=10)).isoformat(),
            "tien_phong": "2500000",
            "chi_so_dien_cu": "100",
            "chi_so_dien_moi": "200",
            "don_gia_dien": "3.500",
            "tien_dien": "1",
            "tien_nuoc": "30000",
            "tien_dich_vu": "0",
            "phi_khac": "0",
        }
        payload.update(changes)
        return payload

    def test_backend_recalculates_electricity_and_persists_snapshot(self):
        response = self.client.post(reverse("tao_hoa_don"), self.invoice_payload())
        self.assertEqual(response.status_code, 302)
        invoice = HoaDon.objects.get(hop_dong=self.contract_obj, thang=10, nam=2026)
        self.assertEqual(invoice.chi_so_dien_cu, Decimal("100"))
        self.assertEqual(invoice.chi_so_dien_moi, Decimal("200"))
        self.assertEqual(invoice.don_gia_dien, Decimal("3500"))
        self.assertEqual(invoice.tien_dien, Decimal("350000"))

    def test_legacy_invoice_keeps_total_with_nullable_snapshot(self):
        invoice = HoaDon.objects.create(
            hop_dong=self.contract_obj,
            thang=9,
            nam=2026,
            tien_phong=Decimal("2500000"),
            tien_dien=Decimal("287500"),
            han_thanh_toan=self.today,
        )

        invoice.refresh_from_db()
        self.assertEqual(invoice.tien_dien, Decimal("287500"))
        self.assertIsNone(invoice.chi_so_dien_cu)
        self.assertIsNone(invoice.chi_so_dien_moi)
        self.assertIsNone(invoice.don_gia_dien)


class ElectricityCalculationTests(SimpleTestCase):
    def test_supported_unit_prices_and_localized_formats(self):
        for raw, expected in (
            ("3250", Decimal("3250")),
            ("3500", Decimal("3500")),
            ("3.500", Decimal("3500")),
            ("3,500", Decimal("3500")),
            ("3600", Decimal("3600")),
            ("4150", Decimal("4150")),
        ):
            with self.subTest(raw=raw):
                old, new, price, amount = calculate_electricity_charge(
                    previous_reading="10",
                    current_reading="20",
                    unit_price=raw,
                )
                self.assertEqual(price, expected)
                self.assertEqual(amount, Decimal("10") * expected)

    def test_invalid_prices_and_descending_readings_are_rejected(self):
        for price in ("0", "-1", "100001"):
            with self.subTest(price=price), self.assertRaises(ValueError):
                calculate_electricity_charge(
                    previous_reading="10",
                    current_reading="20",
                    unit_price=price,
                )
        with self.assertRaises(ValueError):
            calculate_electricity_charge(
                previous_reading="20",
                current_reading="10",
                unit_price="3500",
            )


class FinancialCorrectnessStaticContractTests(BusinessFixture):
    def test_admin_invoice_form_collects_meter_snapshot_not_client_total(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("tao_hoa_don"))
        self.assertContains(response, 'name="chi_so_dien_cu"')
        self.assertContains(response, 'name="chi_so_dien_moi"')
        self.assertContains(response, 'name="don_gia_dien"')
        self.assertContains(response, 'id="tien_dien" type="hidden"')

    def test_water_unit_labels_are_per_person_per_month(self):
        templates = Path(settings.BASE_DIR) / "templates" / "core"
        for name in ("chi_tiet_phong.html", "tao_phong.html", "sua_phong.html"):
            source = (templates / name).read_text(encoding="utf-8")
            self.assertIn("VNĐ/người/tháng", source, name)
            self.assertNotIn("m³", source, name)
