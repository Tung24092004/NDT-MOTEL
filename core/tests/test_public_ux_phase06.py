"""Public discovery presentation contracts for Phase 06."""

from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class PublicDiscoveryPresentationTests(SimpleTestCase):
    def test_home_and_room_list_keep_distinct_browse_and_period_paths(self):
        root = Path(settings.BASE_DIR) / "templates/core"
        home = (root / "home.html").read_text(encoding="utf-8")
        rooms = (root / "danh_sach_phong.html").read_text(encoding="utf-8")

        self.assertIn('name="ngay_nhan_phong"', home)
        self.assertIn('name="so_thang_thue"', home)
        self.assertIn("Tìm phòng theo thời gian thuê", home)
        self.assertIn("availability_period", rooms)
        self.assertIn("nhận phòng {{ availability_period.ngay_nhan_phong", rooms)
        self.assertIn("Có thể đặt cho thời gian đã chọn", rooms)
        self.assertIn("Xem phòng phù hợp", rooms)
        self.assertIn("ngay_nhan_phong={{ availability_period.ngay_nhan_phong", rooms)

    def test_room_detail_keeps_actor_safe_period_cta_and_contextual_return(self):
        detail = (Path(settings.BASE_DIR) / "templates/core/chi_tiet_phong.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("Tiếp tục đặt phòng", detail)
        self.assertIn("ndt-contextual-back", detail)
        self.assertIn("{% if availability_query %}?{{ availability_query }}{% endif %}", detail)
        self.assertIn("not user.is_staff and not user.is_superuser", detail)
