from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class AdminInvoiceHeaderHotfixContractTests(SimpleTestCase):
    def test_invoice_namespace_owns_readable_p5_header_colors(self):
        css = (Path(settings.BASE_DIR) / "static" / "css" / "invoice_management_p6d.css").read_text(encoding="utf-8")
        expected = (
            ".ndt-f5.ndt-invoice-management .invoice-page-header .ndt-breadcrumb",
            ".ndt-f5.ndt-invoice-management .invoice-page-header .ndt-f5-page-header__title",
            ".ndt-f5.ndt-invoice-management .invoice-page-header .ndt-f5-page-header__description",
        )
        for selector in expected:
            self.assertIn(selector, css)
        self.assertNotIn("!important", css)

    def test_only_admin_invoice_headers_use_the_regressed_hook(self):
        templates = Path(settings.BASE_DIR) / "templates" / "core"
        for name in ("quan_ly_hoa_don.html", "chi_tiet_hoa_don.html"):
            source = (templates / name).read_text(encoding="utf-8")
            self.assertIn('class="ndt-f5-page-header invoice-page-header"', source)
            self.assertIn("css/invoice_management_p6d.css", source)
