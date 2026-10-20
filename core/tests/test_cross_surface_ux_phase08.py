"""Structural contracts for Phase-08 shared responsive presentation."""
from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


def template(name):
    return (ROOT / "templates/core" / name).read_text(encoding="utf-8")


class CrossSurfaceFoundationContracts(SimpleTestCase):
    def test_shared_shell_loads_the_canonical_foundation(self):
        shell = template("base.html")
        self.assertIn("css/foundation/tokens.css", shell)
        self.assertIn("css/foundation/typography.css", shell)
        self.assertIn("css/foundation/components.css", shell)
        self.assertIn("ndt-foundation", shell)

    def test_public_room_discovery_keeps_period_controls_and_foundation_structure(self):
        listing = template("danh_sach_phong.html")
        detail = template("chi_tiet_phong.html")
        self.assertIn("availability_form.ngay_nhan_phong", listing)
        self.assertIn("availability_form.so_thang_thue", listing)
        self.assertIn("ndt-filter-bar__form", listing)
        self.assertIn("ndt-f5-page-header__title", detail)

    def test_tenant_finance_and_account_keep_headers_and_empty_states(self):
        account = template("tai_khoan.html")
        billing = template("hoa_don_cua_toi.html")
        self.assertIn("ndt-page-header", account)
        self.assertIn("ndt-f5-page-header__actions", account)
        self.assertIn("ndt-page-header", billing)
        self.assertIn("ndt-empty-state", billing)

    def test_admin_navigation_and_dense_table_keep_responsive_structure(self):
        shell = template("base.html")
        bookings = template("quan_ly_dat_phong.html")
        dashboard = template("dashboard_admin.html")
        self.assertIn("Ra vào &amp; Face ID", shell)
        self.assertIn("ndt-f5-table-wrap", bookings)
        self.assertIn("ndt-f5-filter__actions", bookings)
        self.assertIn("Tổng quan vận hành", dashboard)
