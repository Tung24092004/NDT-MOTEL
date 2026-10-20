from datetime import date
from decimal import Decimal
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import resolve, reverse

from core.models import ChinhSachHoTro
from core.views_chinh_sach import (
    chi_tiet_chinh_sach,
    quan_ly_chinh_sach,
    tao_chinh_sach,
    xu_ly_chinh_sach,
)


class AdminPoliciesPostP6Tests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("policy-staff", is_staff=True)
        self.superuser = User.objects.create_superuser("policy-root", email="root@example.com", password="test")
        self.tenant = User.objects.create_user("policy-tenant")
        self.policy = ChinhSachHoTro.objects.create(
            ten_chinh_sach="Hỗ trợ sinh viên",
            doi_tuong="sinh_vien",
            loai_ho_tro="phan_tram",
            gia_tri_ho_tro=10,
            ngan_sach=10000000,
            so_luong_nguoi_duoc_ap_dung=25,
            ngay_bat_dau=date(2026, 1, 1),
            ngay_ket_thuc=date(2026, 12, 31),
            dieu_kien="Có thẻ sinh viên",
            mo_ta="Chính sách kiểm chứng",
            trang_thai=True,
        )

    def test_route_view_template_matrix_is_stable(self):
        cases = (
            ("quan_ly_chinh_sach", [], quan_ly_chinh_sach, "core/quan_ly_chinh_sach.html"),
            ("tao_chinh_sach", [], tao_chinh_sach, "core/tao_chinh_sach.html"),
            ("chi_tiet_chinh_sach", [self.policy.pk], chi_tiet_chinh_sach, "core/chi_tiet_chinh_sach.html"),
            ("xu_ly_chinh_sach", [self.policy.pk], xu_ly_chinh_sach, None),
        )
        self.client.force_login(self.staff)
        for name, args, handler, template in cases:
            with self.subTest(name=name):
                path = reverse(name, args=args)
                self.assertIs(resolve(path).func, handler)
                response = self.client.get(path)
                if template:
                    self.assertEqual(response.status_code, 200)
                    self.assertTemplateUsed(response, template)
                else:
                    self.assertRedirects(response, reverse("chi_tiet_chinh_sach", args=[self.policy.pk]))

    def test_render_contexts_are_admin_only_for_staff_and_superuser(self):
        routes = (
            reverse("quan_ly_chinh_sach"),
            reverse("tao_chinh_sach"),
            reverse("chi_tiet_chinh_sach", args=[self.policy.pk]),
        )
        for path in routes:
            with self.subTest(path=path, role="guest"):
                response = self.client.get(path)
                self.assertEqual((response.status_code, response.url), (302, reverse("dang_nhap")))
        self.client.force_login(self.tenant)
        for path in routes:
            with self.subTest(path=path, role="tenant"):
                self.assertRedirects(self.client.get(path), reverse("tai_khoan"), fetch_redirect_response=False)
        for user in (self.staff, self.superuser):
            self.client.force_login(user)
            for path in routes:
                with self.subTest(path=path, role=user.username):
                    self.assertEqual(self.client.get(path).status_code, 200)

    def test_action_endpoint_permission_get_and_missing_object_contract(self):
        action = reverse("xu_ly_chinh_sach", args=[self.policy.pk])
        original = self.policy.trang_thai
        response = self.client.get(action)
        self.assertEqual((response.status_code, response.url), (302, reverse("dang_nhap")))
        self.client.force_login(self.tenant)
        self.assertRedirects(self.client.post(action, {"hanh_dong": "tat"}), reverse("tai_khoan"), fetch_redirect_response=False)
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.trang_thai, original)
        self.client.force_login(self.staff)
        self.assertRedirects(self.client.get(action), reverse("chi_tiet_chinh_sach", args=[self.policy.pk]))
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.trang_thai, original)
        self.assertEqual(self.client.get(reverse("chi_tiet_chinh_sach", args=[999999])).status_code, 404)
        self.assertEqual(self.client.post(reverse("xu_ly_chinh_sach", args=[999999]), {"hanh_dong": "tat"}).status_code, 404)

    def test_list_query_contract_is_preserved(self):
        other = ChinhSachHoTro.objects.create(
            ten_chinh_sach="Hỗ trợ người lao động",
            doi_tuong="nguoi_lao_dong",
            loai_ho_tro="so_tien",
            ngay_bat_dau=date(2026, 1, 1),
            ngay_ket_thuc=date(2026, 12, 31),
        )
        self.client.force_login(self.staff)
        response = self.client.get(reverse("quan_ly_chinh_sach"), {"q": "sinh viên"})
        self.assertContains(response, self.policy.ten_chinh_sach)
        self.assertNotContains(response, other.ten_chinh_sach)
        self.assertEqual(response.context["tu_khoa"], "sinh viên")

    def test_create_preserves_payload_validation_messages_and_redirect(self):
        payload = self._payload("Chính sách mới")
        self.client.force_login(self.staff)
        response = self.client.post(reverse("tao_chinh_sach"), payload)
        self.assertRedirects(response, reverse("quan_ly_chinh_sach"))
        created = ChinhSachHoTro.objects.get(ten_chinh_sach=payload["ten_chinh_sach"])
        expected = {
            "doi_tuong": "khac", "doi_tuong_khac": "Nhóm kiểm chứng", "loai_ho_tro": "so_tien",
            "gia_tri_ho_tro": Decimal("500000"), "ngan_sach": Decimal("25000000"),
            "so_luong_nguoi_duoc_ap_dung": 40, "ngay_bat_dau": date(2026, 2, 1),
            "ngay_ket_thuc": date(2026, 11, 30), "dieu_kien": "Điều kiện kiểm chứng",
            "mo_ta": "Mô tả kiểm chứng", "trang_thai": True,
        }
        for field, value in expected.items():
            self.assertEqual(getattr(created, field), value)

        invalid = payload | {"ten_chinh_sach": "Không được tạo", "ngay_bat_dau": "2026-12-31", "ngay_ket_thuc": "2026-01-01"}
        response = self.client.post(reverse("tao_chinh_sach"), invalid)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ngày kết thúc không được trước ngày bắt đầu.")
        self.assertContains(response, 'value="Không được tạo"')
        self.assertFalse(ChinhSachHoTro.objects.filter(ten_chinh_sach="Không được tạo").exists())

    def test_update_action_preserves_payload_validation_and_side_effect(self):
        self.client.force_login(self.staff)
        payload = self._payload("Chính sách đã cập nhật") | {"hanh_dong": "cap_nhat"}
        response = self.client.post(reverse("xu_ly_chinh_sach", args=[self.policy.pk]), payload)
        self.assertRedirects(response, reverse("chi_tiet_chinh_sach", args=[self.policy.pk]))
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.ten_chinh_sach, "Chính sách đã cập nhật")
        self.assertEqual(self.policy.doi_tuong, "khac")
        self.assertEqual(self.policy.gia_tri_ho_tro, Decimal("500000"))
        self.assertEqual(self.policy.ngay_ket_thuc, date(2026, 11, 30))

        response = self.client.post(reverse("xu_ly_chinh_sach", args=[self.policy.pk]), payload | {"ten_chinh_sach": ""})
        self.assertRedirects(response, reverse("chi_tiet_chinh_sach", args=[self.policy.pk]))
        self.policy.refresh_from_db()
        self.assertEqual(self.policy.ten_chinh_sach, "Chính sách đã cập nhật")

    def test_state_delete_and_unknown_actions_keep_current_side_effects(self):
        self.client.force_login(self.staff)
        action = reverse("xu_ly_chinh_sach", args=[self.policy.pk])
        self.client.post(action, {"hanh_dong": "tat"})
        self.policy.refresh_from_db()
        self.assertFalse(self.policy.trang_thai)
        self.client.post(action, {"hanh_dong": "bat"})
        self.policy.refresh_from_db()
        self.assertTrue(self.policy.trang_thai)
        self.client.post(action, {"hanh_dong": "khong_hop_le"})
        self.assertTrue(ChinhSachHoTro.objects.filter(pk=self.policy.pk).exists())
        response = self.client.post(action, {"hanh_dong": "xoa"})
        self.assertRedirects(response, reverse("quan_ly_chinh_sach"))
        self.assertFalse(ChinhSachHoTro.objects.filter(pk=self.policy.pk).exists())

    def test_action_endpoint_rejects_cross_site_post_without_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        response = client.post(reverse("xu_ly_chinh_sach", args=[self.policy.pk]), {"hanh_dong": "tat"})
        self.assertEqual(response.status_code, 403)
        self.policy.refresh_from_db()
        self.assertTrue(self.policy.trang_thai)

    def test_p5_assets_dialog_and_public_policy_isolation(self):
        template_dir = Path(settings.BASE_DIR) / "templates" / "core"
        names = ("quan_ly_chinh_sach.html", "tao_chinh_sach.html", "chi_tiet_chinh_sach.html")
        for name in names:
            source = (template_dir / name).read_text(encoding="utf-8")
            self.assertIn('class="ndt-f5 ndt-f5-page ndt-admin-policies', source)
            self.assertIn("foundation/p5.css", source)
            self.assertIn("admin_policies_post_p6.css", source)
            self.assertNotIn("style=", source)
            self.assertNotIn("<style", source)
            self.assertNotIn("confirm(", source)
        detail = (template_dir / "chi_tiet_chinh_sach.html").read_text(encoding="utf-8")
        self.assertIn("foundation/p5-dialog.js", detail)
        self.assertIn("admin_policies_post_p6.js", detail)
        self.assertEqual(detail.count("data-policy-confirm"), 2)
        module_js = (Path(settings.BASE_DIR) / "static" / "js" / "admin_policies_post_p6.js").read_text(encoding="utf-8")
        self.assertIn('form.dataset.submitting === "true"', module_js)
        self.assertIn('form.dataset.confirmed = "true"', module_js)
        self.assertIn("form.requestSubmit", module_js)
        for name in names[:2]:
            self.assertNotIn("p5-dialog.js", (template_dir / name).read_text(encoding="utf-8"))
        public = (template_dir / "chinh_sach_ho_tro.html").read_text(encoding="utf-8")
        self.assertNotIn("admin_policies_post_p6", public)
        self.assertNotIn("foundation/p5.css", public)

    def test_module_css_is_strictly_scoped(self):
        css = (Path(settings.BASE_DIR) / "static" / "css" / "admin_policies_post_p6.css").read_text(encoding="utf-8")
        selector_headers = re.findall(r"(?m)^\s*([^@}\n][^{\n]*)\{", css)
        selectors = [selector.strip() for header in selector_headers for selector in header.split(",")]
        self.assertTrue(selectors)
        self.assertEqual([selector for selector in selectors if not selector.startswith(".ndt-f5.ndt-admin-policies")], [])
        self.assertNotIn("!important", css)

    @staticmethod
    def _payload(name):
        return {
            "ten_chinh_sach": name,
            "doi_tuong": "khac",
            "doi_tuong_khac": "Nhóm kiểm chứng",
            "loai_ho_tro": "so_tien",
            "gia_tri_ho_tro": "500000",
            "ngan_sach": "25000000",
            "so_luong_nguoi_duoc_ap_dung": "40",
            "ngay_bat_dau": "2026-02-01",
            "ngay_ket_thuc": "2026-11-30",
            "dieu_kien": "Điều kiện kiểm chứng",
            "trang_thai": "on",
            "mo_ta": "Mô tả kiểm chứng",
        }
