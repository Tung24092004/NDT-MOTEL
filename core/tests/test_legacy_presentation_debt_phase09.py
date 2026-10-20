"""Narrow CSS ownership contracts for Phase-09 cleanup."""
from pathlib import Path

from django.test import SimpleTestCase


ROOT = Path(__file__).resolve().parents[2]


class PresentationDebtContracts(SimpleTestCase):
    def test_shared_shell_owns_foundation_and_tenant_shell_keeps_its_own_layer(self):
        shared = (ROOT / "templates/core/base.html").read_text(encoding="utf-8")
        tenant = (ROOT / "templates/core/tenant_base.html").read_text(encoding="utf-8")
        for stylesheet in (
            "css/foundation/tokens.css",
            "css/foundation/typography.css",
            "css/foundation/components.css",
        ):
            self.assertIn(stylesheet, shared)
            self.assertNotIn(stylesheet, tenant)
        self.assertIn("css/tenant/components.css", tenant)

    def test_f5_compatibility_remains_for_active_dialog_and_table_consumers(self):
        p5 = (ROOT / "static/css/foundation/p5.css").read_text(encoding="utf-8")
        dialog = (ROOT / "templates/core/foundation/p5_dialog_root.html").read_text(encoding="utf-8")
        self.assertIn(".ndt-f5-dialog", p5)
        self.assertIn(".ndt-f5-table-wrap", p5)
        self.assertIn("data-ndt-f5-dialog", dialog)
