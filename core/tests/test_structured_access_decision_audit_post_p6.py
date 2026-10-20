import importlib
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import LichSuRaVao


class StructuredAccessDecisionContractTests(SimpleTestCase):
    def test_model_exposes_closed_structured_result_vocabulary(self):
        self.assertEqual(
            dict(LichSuRaVao.KET_QUA),
            {"cho_phep": "Cho phép", "tu_choi": "Từ chối", "khong_xac_dinh": "Không xác định"},
        )
        field = LichSuRaVao._meta.get_field("ket_qua")
        self.assertTrue(field.db_index)
        self.assertEqual(field.default, "khong_xac_dinh")

    def test_current_readers_do_not_infer_result_from_note_text(self):
        root = Path(settings.BASE_DIR)
        paths = (
            "templates/core/smart_room_dashboard.html",
            "templates/core/quan_ly_lich_su_ra_vao.html",
            "templates/core/chi_tiet_lich_su_ra_vao.html",
            "templates/core/quyen_va_lich_su_ra_vao_cua_toi.html",
        )
        for relative_path in paths:
            source = (root / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIn(".ket_qua", source)
                self.assertNotIn('"[CHO PHÉP]" in', source)
                self.assertNotIn('"[TỪ CHỐI]" in', source)

    def test_all_production_writers_assign_structured_result(self):
        source = (Path(settings.BASE_DIR) / "core/views_smart_room.py").read_text(encoding="utf-8")
        self.assertIn('ket_qua=("cho_phep" if duoc_phep else "tu_choi")', source)
        self.assertIn("ket_qua=ket_qua", source)
        self.assertIn('ket_qua="cho_phep"', source)
        self.assertNotIn("Model LichSuRaVao hiện chưa có field ket_qua riêng", source)


class StructuredAccessDecisionIntegrationTests(BusinessFixture):
    def make_history(self, *, result, note, source="camera"):
        return LichSuRaVao.objects.create(
            phong=self.room, nguoi_thue=self.tenant, loai_su_kien="vao",
            nguon=source, ket_qua=result, thoi_diem=timezone.now(), ghi_chu=note,
        )

    def test_tenant_render_and_filter_use_field_not_conflicting_note(self):
        denied = self.make_history(result="tu_choi", note="[CHO PHÉP] Chuỗi cố ý mâu thuẫn với field.")
        self.make_history(result="cho_phep", note="Không có prefix legacy.")
        self.client.force_login(self.user)
        response = self.client.get(reverse("quyen_va_lich_su_ra_vao_cua_toi"), {"ket_qua": "tu_choi"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["ket_qua_filter"], "tu_choi")
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertEqual(response.context["lich_su"][0].pk, denied.pk)
        self.assertContains(response, "Từ chối")

    def test_admin_list_filters_by_structured_result(self):
        denied = self.make_history(result="tu_choi", note="Không có prefix.")
        self.make_history(result="cho_phep", note="[TỪ CHỐI] Chuỗi mâu thuẫn.")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("quan_ly_lich_su_ra_vao"), {"ket_qua": "tu_choi"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["ds"]), [denied])
        self.assertContains(response, "Từ chối")

    def test_dashboard_metrics_use_structured_result(self):
        self.make_history(result="cho_phep", note="[TỪ CHỐI] Mâu thuẫn.")
        self.make_history(result="tu_choi", note="[CHO PHÉP] Mâu thuẫn.")
        self.make_history(result="khong_xac_dinh", note="[CHO PHÉP] Legacy giả.")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("smart_room_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["face_id_cho_phep_gan_day"], 1)
        self.assertEqual(response.context["face_id_tu_choi_gan_day"], 1)

    def test_data_migration_backfills_only_known_legacy_signatures(self):
        allowed = self.make_history(result="khong_xac_dinh", note="[CHO PHÉP] Face ID - hợp lệ.")
        denied = self.make_history(result="khong_xac_dinh", note="[TỪ CHỐI] Face ID - không hợp lệ.")
        simulated_allowed = self.make_history(result="khong_xac_dinh", note="Mô phỏng camera: Nhận diện thành công. Đủ điều kiện mở cửa.")
        simulated_denied = self.make_history(result="khong_xac_dinh", note="Mô phỏng camera: Truy cập bị từ chối.")
        ambiguous = self.make_history(result="khong_xac_dinh", note="Ghi chú tự do không đủ bằng chứng.")
        migration = importlib.import_module("core.migrations.0028_lichsuravao_structured_result")

        class CurrentApps:
            @staticmethod
            def get_model(app_label, model_name):
                self.assertEqual((app_label, model_name), ("core", "LichSuRaVao"))
                return LichSuRaVao

        migration.backfill_structured_access_result(CurrentApps(), None)
        results = dict(LichSuRaVao.objects.filter(pk__in=[allowed.pk, denied.pk, simulated_allowed.pk, simulated_denied.pk, ambiguous.pk]).values_list("pk", "ket_qua"))
        self.assertEqual(results[allowed.pk], "cho_phep")
        self.assertEqual(results[denied.pk], "tu_choi")
        self.assertEqual(results[simulated_allowed.pk], "cho_phep")
        self.assertEqual(results[simulated_denied.pk], "tu_choi")
        self.assertEqual(results[ambiguous.pk], "khong_xac_dinh")
