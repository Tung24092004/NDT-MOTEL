from datetime import timedelta
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from core.models import NhatKyThaoTac
from core.views_nhat_ky import chi_tiet_nhat_ky_thao_tac, nhat_ky_thao_tac


class AdminAuditLogPostP6Tests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user("audit-staff", is_staff=True)
        self.superuser = User.objects.create_superuser(
            "audit-root", email="root@example.test", password="test"
        )
        self.tenant = User.objects.create_user("audit-tenant")
        self.other = User.objects.create_user("audit-operator")
        self.now = timezone.now()
        self.primary = self._log(
            actor=self.staff,
            action="cap_nhat",
            module="Phòng",
            target="Phong",
            target_id=42,
            title="Cập nhật phòng 42",
            content="Thay đổi giá thuê và trạng thái phòng.",
            old={"gia_thue": "2500000", "trang_thai": "trong"},
            new={"gia_thue": "2700000", "trang_thai": "dang_thue"},
            ip="127.0.0.1",
            happened_at=self.now - timedelta(days=1),
        )
        self.secondary = self._log(
            actor=self.other,
            action="tao",
            module="Hợp đồng",
            target="HopDong",
            target_id=84,
            title="Tạo hợp đồng mới",
            content="Khởi tạo hợp đồng cho khách thuê.",
            happened_at=self.now - timedelta(days=3),
        )
        self.system = self._log(
            actor=None,
            action="khac",
            module="Hệ thống",
            target="",
            target_id=None,
            title="Tác vụ nền",
            content="Đồng bộ dữ liệu định kỳ.",
            happened_at=self.now,
        )

    def test_route_view_template_matrix_is_stable(self):
        cases = (
            (
                "nhat_ky_thao_tac",
                [],
                nhat_ky_thao_tac,
                "core/nhat_ky_thao_tac.html",
            ),
            (
                "chi_tiet_nhat_ky_thao_tac",
                [self.primary.pk],
                chi_tiet_nhat_ky_thao_tac,
                "core/chi_tiet_nhat_ky_thao_tac.html",
            ),
        )
        self.client.force_login(self.staff)
        for name, args, handler, template in cases:
            with self.subTest(name=name):
                path = reverse(name, args=args)
                self.assertIs(resolve(path).func, handler)
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)

    def test_both_render_contexts_keep_admin_permission_contract(self):
        paths = (
            reverse("nhat_ky_thao_tac"),
            reverse("chi_tiet_nhat_ky_thao_tac", args=[self.primary.pk]),
        )
        for path in paths:
            with self.subTest(path=path, role="guest"):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("dang_nhap")))

        self.client.force_login(self.tenant)
        for path in paths:
            with self.subTest(path=path, role="tenant"):
                response = self.client.get(path)
                self.assertEqual((response.status_code, response.url), (302, reverse("home")))
                self.assertIn(
                    "Bạn không có quyền truy cập nhật ký thao tác.",
                    [str(message) for message in get_messages(response.wsgi_request)],
                )

        for user in (self.staff, self.superuser):
            self.client.force_login(user)
            for path in paths:
                with self.subTest(path=path, role=user.username):
                    self.assertEqual(self.client.get(path).status_code, 200)

    def test_list_exposes_the_exact_context_and_read_only_statistics(self):
        self.client.force_login(self.staff)
        before = self._snapshot()
        response = self.client.get(reverse("nhat_ky_thao_tac"))
        self.assertEqual(response.status_code, 200)
        expected = {
            "nhat_ky",
            "page_obj",
            "tong_nhat_ky",
            "nhat_ky_hom_nay",
            "so_nguoi_thao_tac",
            "nhat_ky_moi_nhat",
            "modules",
            "hanh_dongs",
            "nguoi_thuc_hien_ds",
            "q",
            "module",
            "hanh_dong",
            "nguoi_thuc_hien_id",
            "tu_ngay",
            "den_ngay",
            "query_string",
        }
        self.assertTrue(expected.issubset(response.context.keys()))
        self.assertEqual(response.context["tong_nhat_ky"], 3)
        expected_today = NhatKyThaoTac.objects.filter(
            thoi_diem__date=timezone.localdate()
        ).count()
        self.assertEqual(response.context["nhat_ky_hom_nay"], expected_today)
        self.assertEqual(response.context["so_nguoi_thao_tac"], 2)
        self.assertEqual(response.context["nhat_ky_moi_nhat"], self.system)
        self.assertEqual(list(response.context["modules"]), ["Hệ thống", "Hợp đồng", "Phòng"])
        self.assertEqual(list(response.context["hanh_dongs"]), ["cap_nhat", "khac", "tao"])
        self.assertEqual(self._snapshot(), before)

    def test_all_six_filters_keep_current_query_semantics(self):
        self.client.force_login(self.staff)
        path = reverse("nhat_ky_thao_tac")
        cases = (
            ({"q": "giá thuê"}, [self.primary.pk]),
            ({"q": "Phong"}, [self.primary.pk]),
            ({"q": "42"}, [self.primary.pk]),
            ({"module": "Hợp đồng"}, [self.secondary.pk]),
            ({"hanh_dong": "khac"}, [self.system.pk]),
            ({"nguoi_thuc_hien": str(self.other.pk)}, [self.secondary.pk]),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                response = self.client.get(path, query)
                self.assertEqual([item.pk for item in response.context["nhat_ky"]], expected)
                for name, value in query.items():
                    context_name = "nguoi_thuc_hien_id" if name == "nguoi_thuc_hien" else name
                    self.assertEqual(response.context[context_name], value)

        date_cases = (
            ("tu_ngay", timezone.localdate().isoformat(), "thoi_diem__date__gte"),
            (
                "den_ngay",
                (timezone.localdate() - timedelta(days=2)).isoformat(),
                "thoi_diem__date__lte",
            ),
        )
        for parameter, value, lookup in date_cases:
            with self.subTest(parameter=parameter):
                response = self.client.get(path, {parameter: value})
                expected = list(
                    NhatKyThaoTac.objects.filter(**{lookup: value})
                    .order_by("-thoi_diem")
                    .values_list("pk", flat=True)
                )
                self.assertEqual(
                    [item.pk for item in response.context["nhat_ky"]], expected
                )
                self.assertEqual(response.context[parameter], value)

    def test_ordering_pagination_and_query_string_are_preserved(self):
        for index in range(23):
            self._log(
                actor=self.staff,
                action="xem",
                module="Phòng",
                target="Phong",
                target_id=100 + index,
                title=f"Bản ghi phân trang {index:02d}",
                content="Kiểm chứng phân trang.",
                happened_at=self.now - timedelta(minutes=index + 1),
            )
        self.client.force_login(self.staff)
        response = self.client.get(
            reverse("nhat_ky_thao_tac"),
            {"module": "Phòng", "q": "bản ghi", "page": "2"},
        )
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(response.context["page_obj"].paginator.per_page, 20)
        self.assertEqual(len(response.context["nhat_ky"]), 3)
        self.assertEqual(response.context["query_string"], "module=Ph%C3%B2ng&q=b%E1%BA%A3n+ghi")
        timestamps = [item.thoi_diem for item in response.context["nhat_ky"]]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

        invalid = self.client.get(reverse("nhat_ky_thao_tac"), {"page": "not-a-page"})
        self.assertEqual(invalid.context["page_obj"].number, 1)

    def test_detail_supports_json_and_empty_data_and_unknown_id_404(self):
        self.client.force_login(self.staff)
        before = self._snapshot()
        response = self.client.get(
            reverse("chi_tiet_nhat_ky_thao_tac", args=[self.primary.pk])
        )
        self.assertEqual(response.context["log"], self.primary)
        self.assertContains(response, "2500000")
        self.assertContains(response, "2700000")
        empty = self.client.get(
            reverse("chi_tiet_nhat_ky_thao_tac", args=[self.secondary.pk])
        )
        self.assertContains(empty, "Không có dữ liệu cũ.")
        self.assertContains(empty, "Không có dữ liệu mới.")
        self.assertEqual(
            self.client.get(reverse("chi_tiet_nhat_ky_thao_tac", args=[999999])).status_code,
            404,
        )
        self.assertEqual(self._snapshot(), before)

    def test_p5_assets_and_read_only_isolation(self):
        template_dir = Path(settings.BASE_DIR) / "templates" / "core"
        names = ("nhat_ky_thao_tac.html", "chi_tiet_nhat_ky_thao_tac.html")
        for name in names:
            source = (template_dir / name).read_text(encoding="utf-8")
            self.assertIn('class="ndt-f5 ndt-f5-page ndt-admin-audit-log', source)
            self.assertIn("foundation/p5.css", source)
            self.assertIn("admin_audit_log_post_p6.css", source)
            self.assertNotIn("<style", source)
            self.assertNotIn("style=", source)
            self.assertNotIn("<form method=\"post\"", source)
            self.assertNotIn("p5-dialog.js", source)
        self.assertFalse(
            (Path(settings.BASE_DIR) / "static" / "js" / "admin_audit_log_post_p6.js").exists()
        )

    def test_module_css_is_strictly_scoped(self):
        css = (
            Path(settings.BASE_DIR) / "static" / "css" / "admin_audit_log_post_p6.css"
        ).read_text(encoding="utf-8")
        selector_headers = re.findall(r"(?m)^\s*([^@}\n][^{\n]*)\{", css)
        selectors = [selector.strip() for header in selector_headers for selector in header.split(",")]
        self.assertTrue(selectors)
        self.assertEqual(
            [selector for selector in selectors if not selector.startswith(".ndt-f5.ndt-admin-audit-log")],
            [],
        )
        self.assertNotIn("!important", css)

    def _log(
        self,
        *,
        actor,
        action,
        module,
        target,
        target_id,
        title,
        content,
        happened_at,
        old=None,
        new=None,
        ip=None,
    ):
        log = NhatKyThaoTac.objects.create(
            nguoi_thuc_hien=actor,
            hanh_dong=action,
            module=module,
            doi_tuong=target,
            doi_tuong_id=target_id,
            tieu_de=title,
            noi_dung=content,
            du_lieu_cu=old,
            du_lieu_moi=new,
            dia_chi_ip=ip,
            user_agent="Admin Audit Log test agent",
        )
        NhatKyThaoTac.objects.filter(pk=log.pk).update(thoi_diem=happened_at)
        log.refresh_from_db()
        return log

    @staticmethod
    def _snapshot():
        return list(NhatKyThaoTac.objects.order_by("pk").values())
