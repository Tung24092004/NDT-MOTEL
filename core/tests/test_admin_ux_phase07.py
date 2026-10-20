"""Focused contracts for the Phase-07 admin information architecture."""
from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse


ROOT = Path(__file__).resolve().parents[2]


class AdminNavigationContracts(SimpleTestCase):
    def test_canonical_admin_domains_keep_their_existing_routes(self):
        expected = {
            "dashboard_admin": "/dashboard-admin/",
            "quan_ly_phong": "/quan-ly-phong/",
            "quan_ly_dat_phong": "/quan-ly-dat-phong/",
            "quan_ly_hop_dong": "/quan-ly-hop-dong/",
            "quan_ly_hoa_don": "/quan-ly-hoa-don/",
            "quan_ly_nguoi_thue": "/quan-ly-nguoi-thue/",
            "quan_ly_sua_chua": "/quan-ly-sua-chua/",
            "smart_room_dashboard": "/smart-room/",
            "quan_ly_thong_bao": "/quan-ly-thong-bao/",
            "nhat_ky_thao_tac": "/nhat-ky-thao-tac/",
        }
        for name, path in expected.items():
            self.assertEqual(reverse(name), path)

    def test_admin_shell_and_dashboard_use_the_phase07_terms(self):
        shell = (ROOT / "templates/core/base.html").read_text(encoding="utf-8")
        dashboard = (ROOT / "templates/core/dashboard_admin.html").read_text(encoding="utf-8")
        admin_smart_panel = shell.split('data-panel-id="admin-smart"', 1)[1].split(
            'data-panel-id="admin-system"', 1
        )[0]
        for label in (
            "Tổng quan vận hành",
            "Phòng &amp; cơ sở",
            "Đặt phòng &amp; cọc",
            "Hợp đồng",
            "Tài chính",
            "Người thuê &amp; lưu trú",
            "Sửa chữa &amp; bảo trì",
            "Ra vào &amp; Face ID",
            "Thông báo",
            "Nhật ký thao tác",
        ):
            self.assertIn(label, shell)
        self.assertNotIn("Smart Room", admin_smart_panel)
        self.assertIn("Tổng quan vận hành", dashboard)
        self.assertIn("Nhận diện và quyền ra vào", dashboard)


class CanonicalAdminActionContracts(SimpleTestCase):
    def test_deposit_settlement_stays_in_django_admin_service_action(self):
        source = (ROOT / "core/admin.py").read_text(encoding="utf-8")
        self.assertIn("core_thanhtoancocdatphong_settle", source)
        self.assertIn("self.admin_site.admin_view(self.settle_view)", source)
        self.assertIn("settle_confirmed_deposit(actor=request.user", source)

    def test_legacy_invoice_review_stays_in_django_admin_service_action(self):
        source = (ROOT / "core/admin.py").read_text(encoding="utf-8")
        self.assertIn("core_hoadon_legacy_review", source)
        self.assertIn("self.admin_site.admin_view(self.legacy_review_view)", source)
        self.assertIn("reconcile_legacy_paid_invoice(actor=request.user", source)
