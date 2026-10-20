from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve, reverse


class Face05CameraControlsContractTests(SimpleTestCase):
    def setUp(self):
        root = Path(settings.BASE_DIR)
        self.js = (root / "static" / "js" / "smart_room_p6h.js").read_text(encoding="utf-8")
        self.css = (root / "static" / "css" / "smart_room_p6h.css").read_text(encoding="utf-8")
        template_root = root / "templates" / "core"
        self.templates = {
            "enroll": (template_root / "chi_tiet_face_profile.html").read_text(encoding="utf-8"),
            "verify": (template_root / "xac_thuc_face_id.html").read_text(encoding="utf-8"),
        }

    def test_both_camera_consumers_expose_stop_restart_and_live_status(self):
        for name, source in self.templates.items():
            with self.subTest(consumer=name):
                self.assertIn('data-camera-state="idle"', source)
                self.assertIn("data-camera-start", source)
                self.assertIn("data-camera-stop", source)
                self.assertIn('data-restart-label="Mở lại camera"', source)
                self.assertIn('role="status"', source)
                self.assertIn('aria-live="polite"', source)
                self.assertIn("aria-controls=", source)
                self.assertIn("aria-describedby=", source)

    def test_preview_has_an_accessible_name_and_is_the_only_mirrored_surface(self):
        for name, source in self.templates.items():
            with self.subTest(consumer=name):
                self.assertIn('class="smart-camera__preview"', source)
                self.assertIn('aria-label="Bản xem trước camera', source)
        self.assertIn(".smart-camera__preview { transform: scaleX(-1); }", self.css)
        self.assertNotIn("canvas { transform", self.css)

    def test_capture_keeps_source_orientation(self):
        self.assertIn('canvas.getContext("2d").drawImage(video, 0, 0, canvas.width, canvas.height)', self.js)
        self.assertNotIn("context.scale(-1", self.js)
        self.assertNotIn("canvas.style.transform", self.js)

    def test_explicit_camera_state_machine_is_present(self):
        for state in ("idle", "opening", "ready", "stopped", "processing", "denied", "error"):
            self.assertIn(f'"{state}"', self.js)
        self.assertIn("root.dataset.cameraState = state", self.js)

    def test_stop_restart_and_runtime_cleanup_contracts_are_present(self):
        for contract in (
            'stop.addEventListener("click"',
            "activeStream.getTracks().forEach",
            'track.addEventListener("ended", handleRuntimeStop',
            'video.addEventListener("error", handleRuntimeStop)',
            'window.addEventListener("pagehide", teardownCamera',
            "new MutationObserver",
            "if (!root.isConnected) teardownCamera()",
            "video.srcObject = null",
        ):
            self.assertIn(contract, self.js)

    def test_camera_controls_have_visible_keyboard_focus(self):
        self.assertIn(".smart-camera__controls .ndt-f5-button:focus-visible", self.css)
        self.assertIn("outline: 3px solid", self.css)

    def test_existing_camera_routes_and_backend_owners_are_unchanged(self):
        routes = (
            ("chi_tiet_face_profile", (17,), "chi_tiet_face_profile"),
            ("face_id_dang_ky", (17,), "face_id_dang_ky"),
            ("trang_xac_thuc_face_id", (), "trang_xac_thuc_face_id"),
            ("face_id_xac_thuc", (), "face_id_xac_thuc"),
        )
        for route_name, args, expected_view in routes:
            with self.subTest(route=route_name):
                match = resolve(reverse(route_name, args=args))
                self.assertEqual(match.url_name, route_name)
                self.assertEqual(match.func.__name__, expected_view)
