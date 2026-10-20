from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from core import views_smart_room


class SmartRoomP6HUiContractTests(SimpleTestCase):
    templates = (
        "smart_room_dashboard.html",
        "smart_access_control.html",
        "xac_thuc_face_id.html",
        "quan_ly_face_profile.html",
        "tao_face_profile.html",
        "chi_tiet_face_profile.html",
        "face_id_unavailable.html",
        "quan_ly_quyen_ra_vao.html",
        "tao_quyen_ra_vao.html",
        "chi_tiet_quyen_ra_vao.html",
        "quan_ly_lich_su_ra_vao.html",
        "tao_lich_su_ra_vao.html",
        "chi_tiet_lich_su_ra_vao.html",
    )

    def setUp(self):
        self.template_root = Path(settings.BASE_DIR) / "templates" / "core"
        self.css = (Path(settings.BASE_DIR) / "static" / "css" / "smart_room_p6h.css").read_text(encoding="utf-8")
        self.js = (Path(settings.BASE_DIR) / "static" / "js" / "smart_room_p6h.js").read_text(encoding="utf-8")

    def test_all_thirteen_templates_use_scoped_p5_contract(self):
        self.assertEqual(len(self.templates), 13)
        for name in self.templates:
            source = (self.template_root / name).read_text(encoding="utf-8")
            self.assertIn("css/foundation/p5.css", source, name)
            self.assertIn("css/smart_room_p6h.css", source, name)
            self.assertIn("ndt-smart-room-management", source, name)
            self.assertNotIn("css/smart_room.css", source, name)
            self.assertNotIn("bill_smart_full_refresh.css", source, name)
            self.assertNotIn("<style", source, name)
            self.assertNotIn("<script>", source, name)

    def test_module_assets_are_scoped_and_do_not_use_important(self):
        self.assertIn(".ndt-f5.ndt-smart-room-management", self.css)
        self.assertNotIn("!important", self.css)
        self.assertNotIn("window.confirm", self.js)
        self.assertIn("window.NDTFoundationDialog.confirm", self.js)
        self.assertIn("trigger: submitter", self.js)
        self.assertIn("if (event.defaultPrevented) return;", self.js)

    def test_camera_and_form_safety_contracts_are_externalized(self):
        for contract in (
            "navigator.mediaDevices.getUserMedia",
            'canvas.toDataURL("image/jpeg", 0.9)',
            "new AbortController()",
            "form.requestSubmit(submitter || undefined)",
            'button.setAttribute("aria-busy", "true")',
            'window.addEventListener("pagehide", teardownCamera',
        ):
            self.assertIn(contract, self.js)

    def test_dangerous_workflows_use_accessible_p5_dialog(self):
        for name in ("chi_tiet_face_profile.html", "chi_tiet_quyen_ra_vao.html", "chi_tiet_lich_su_ra_vao.html"):
            source = (self.template_root / name).read_text(encoding="utf-8")
            self.assertIn("data-smart-confirm", source)
            self.assertIn("core/foundation/p5_dialog_root.html", source)
            self.assertIn("js/foundation/p5-dialog.js", source)

    def test_roommate_management_is_not_pulled_into_p6h(self):
        for name in self.templates:
            source = (self.template_root / name).read_text(encoding="utf-8")
            self.assertNotIn("bill_smart_full_refresh.css", source)
        roommate = (self.template_root / "quan_ly_nguoi_o_cung.html").read_text(encoding="utf-8")
        self.assertNotIn("smart_room_p6h.css", roommate)

    def test_all_twenty_routes_resolve_to_the_locked_views(self):
        routes = (
            ("smart_room_dashboard", (), "smart_room_dashboard"),
            ("smart_access_control", (), "smart_access_control"),
            ("nhan_dien_su_dung_phong", (), "nhan_dien_su_dung_phong"),
            ("quan_ly_face_profile", (), "quan_ly_face_profile"),
            ("tao_face_profile", (), "tao_face_profile"),
            ("chi_tiet_face_profile", (17,), "chi_tiet_face_profile"),
            ("face_profile_image", (17,), "face_profile_image"),
            ("face_profile_media", ("blocked.jpg",), "face_profile_media"),
            ("face_id_dang_ky", (17,), "face_id_dang_ky"),
            ("xu_ly_face_profile", (17,), "xu_ly_face_profile"),
            ("trang_xac_thuc_face_id", (), "trang_xac_thuc_face_id"),
            ("face_id_xac_thuc", (), "face_id_xac_thuc"),
            ("quan_ly_quyen_ra_vao", (), "quan_ly_quyen_ra_vao"),
            ("tao_quyen_ra_vao", (), "tao_quyen_ra_vao"),
            ("chi_tiet_quyen_ra_vao", (17,), "chi_tiet_quyen_ra_vao"),
            ("xu_ly_quyen_ra_vao", (17,), "xu_ly_quyen_ra_vao"),
            ("quan_ly_lich_su_ra_vao", (), "quan_ly_lich_su_ra_vao"),
            ("tao_lich_su_ra_vao", (), "tao_lich_su_ra_vao"),
            ("chi_tiet_lich_su_ra_vao", (17,), "chi_tiet_lich_su_ra_vao"),
            ("xu_ly_lich_su_ra_vao", (17,), "xu_ly_lich_su_ra_vao"),
        )
        self.assertEqual(len(routes), 20)
        for route_name, args, view_name in routes:
            with self.subTest(route=route_name):
                match = resolve(reverse(route_name, args=args))
                self.assertEqual(match.url_name, route_name)
                self.assertEqual(match.func.__name__, view_name)


class SmartRoomP6HJson404Tests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.admin = SimpleNamespace(is_authenticated=True, is_staff=True, is_superuser=False)

    @patch("core.views_smart_room.transaction.atomic", return_value=nullcontext())
    @patch("core.views_smart_room.get_object_or_404", side_effect=Http404("missing profile"))
    def test_enrollment_missing_profile_is_json_404(self, _missing, _atomic):
        request = self.factory.post("/smart-room/face/999/enroll/", {"image": "data:image/jpeg;base64,AA=="})
        request.user = self.admin
        response = views_smart_room.face_id_dang_ky(request, 999)
        self.assertEqual(response.status_code, 404)
        payload = json.loads(response.content)
        self.assertEqual(
            payload,
            {"success": False, "message": "Không tìm thấy hồ sơ Face ID."},
        )

    @patch("core.views_smart_room.get_object_or_404", side_effect=Http404("missing room"))
    def test_verification_missing_room_is_json_404(self, _missing):
        request = self.factory.post("/smart-room/face/verify/", {"image": "data:image/jpeg;base64,AA==", "phong": "999", "loai_su_kien": "vao"})
        request.user = self.admin
        response = views_smart_room.face_id_xac_thuc(request)
        self.assertEqual(response.status_code, 404)
        payload = json.loads(response.content)
        self.assertEqual(
            payload,
            {
                "success": False,
                "message": "Không tìm thấy phòng cần xác thực.",
                "access": "error",
            },
        )
