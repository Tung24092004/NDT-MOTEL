import re
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase


class DesignFoundationP5Tests(SimpleTestCase):
    def setUp(self):
        self.css_path = Path(settings.BASE_DIR) / "static" / "css" / "foundation" / "p5.css"
        self.js_path = Path(settings.BASE_DIR) / "static" / "js" / "foundation" / "p5-dialog.js"
        self.css = self.css_path.read_text(encoding="utf-8")
        self.js = self.js_path.read_text(encoding="utf-8")
        self.html = render_to_string(
            "core/tests/design_foundation_p5_harness.html",
            {"live_server_url": "http://testserver"},
        )

    def test_foundation_is_opt_in_and_only_loaded_by_approved_screens(self):
        base = (Path(settings.BASE_DIR) / "templates" / "core" / "base.html").read_text(encoding="utf-8")
        tenant_base = (
            Path(settings.BASE_DIR) / "templates" / "core" / "tenant_base.html"
        ).read_text(encoding="utf-8")

        self.assertIn(".ndt-f5", self.css)
        self.assertNotIn("foundation/p5.css", base)
        self.assertNotIn("foundation/p5.css", tenant_base)
        self.assertNotIn("p5-dialog.js", base)
        self.assertNotIn("p5-dialog.js", tenant_base)

        production_templates = Path(settings.BASE_DIR) / "templates" / "core"
        p5_loaders = []
        for template in production_templates.rglob("*.html"):
            if "tests" in template.parts:
                continue
            source = template.read_text(encoding="utf-8")
            if "foundation/p5.css" in source or "p5-dialog.js" in source:
                p5_loaders.append(str(template.relative_to(settings.BASE_DIR)))
        self.assertEqual(
            set(p5_loaders),
            {
                str(Path("templates/core/home.html")),
                str(Path("templates/core/danh_sach_phong.html")),
                str(Path("templates/core/chi_tiet_phong.html")),
                str(Path("templates/core/huong_dan_thue_phong.html")),
                str(Path("templates/core/trung_tam_tro_giup.html")),
                str(Path("templates/core/chinh_sach_ho_tro.html")),
                str(Path("templates/core/quan_ly_phong.html")),
                str(Path("templates/core/sua_phong.html")),
                str(Path("templates/core/tao_phong.html")),
                str(Path("templates/core/quan_ly_dat_phong.html")),
                str(Path("templates/core/chi_tiet_dat_phong.html")),
                str(Path("templates/core/tenant/booking/base.html")),
                str(Path("templates/core/quan_ly_hop_dong.html")),
                str(Path("templates/core/chi_tiet_hop_dong.html")),
                str(Path("templates/core/tao_hop_dong.html")),
                str(Path("templates/core/sua_hop_dong.html")),
                str(Path("templates/core/hop_dong_cua_toi.html")),
                str(Path("templates/core/chi_tiet_hop_dong_cua_toi.html")),
                str(Path("templates/core/quan_ly_hoa_don.html")),
                str(Path("templates/core/tao_hoa_don.html")),
                str(Path("templates/core/chi_tiet_hoa_don.html")),
                str(Path("templates/core/hoa_don_cua_toi.html")),
                str(Path("templates/core/chi_tiet_hoa_don_cua_toi.html")),
                str(Path("templates/core/thanh_toan_hoa_don_cua_toi.html")),
                str(Path("templates/core/quan_ly_sua_chua.html")),
                str(Path("templates/core/chi_tiet_sua_chua.html")),
                str(Path("templates/core/tao_sua_chua.html")),
                str(Path("templates/core/yeu_cau_sua_chua_cua_toi.html")),
                str(Path("templates/core/tao_yeu_cau_sua_chua.html")),
                str(Path("templates/core/chi_tiet_yeu_cau_sua_chua_cua_toi.html")),
                str(Path("templates/core/quan_ly_thong_bao.html")),
                str(Path("templates/core/tao_thong_bao.html")),
                str(Path("templates/core/chi_tiet_thong_bao.html")),
                str(Path("templates/core/thong_bao_admin.html")),
                str(Path("templates/core/chi_tiet_thong_bao_admin.html")),
                str(Path("templates/core/thong_bao_cua_toi.html")),
                str(Path("templates/core/chi_tiet_thong_bao_cua_toi.html")),
                str(Path("templates/core/dashboard_admin.html")),
                str(Path("templates/core/smart_room_dashboard.html")),
                str(Path("templates/core/smart_access_control.html")),
                str(Path("templates/core/xac_thuc_face_id.html")),
                str(Path("templates/core/quan_ly_face_profile.html")),
                str(Path("templates/core/tao_face_profile.html")),
                str(Path("templates/core/chi_tiet_face_profile.html")),
                str(Path("templates/core/face_id_unavailable.html")),
                str(Path("templates/core/quan_ly_quyen_ra_vao.html")),
                str(Path("templates/core/tao_quyen_ra_vao.html")),
                str(Path("templates/core/chi_tiet_quyen_ra_vao.html")),
                str(Path("templates/core/quan_ly_lich_su_ra_vao.html")),
                str(Path("templates/core/tao_lich_su_ra_vao.html")),
                str(Path("templates/core/chi_tiet_lich_su_ra_vao.html")),
                str(Path("templates/core/tai_khoan.html")),
                str(Path("templates/core/cap_nhat_thong_tin.html")),
                str(Path("templates/core/doi_mat_khau.html")),
                str(Path("templates/core/dang_nhap.html")),
                str(Path("templates/core/dang_ky.html")),
                str(Path("templates/core/quan_ly_nguoi_thue.html")),
                str(Path("templates/core/chi_tiet_nguoi_thue.html")),
                str(Path("templates/core/quan_ly_nguoi_o_cung.html")),
                str(Path("templates/core/tao_nguoi_o_cung.html")),
                str(Path("templates/core/chi_tiet_nguoi_o_cung.html")),
                str(Path("templates/core/dang_ky_ghep_phong.html")),
                str(Path("templates/core/yeu_cau_ghep_cua_toi.html")),
                str(Path("templates/core/chi_tiet_yeu_cau_ghep.html")),
                str(Path("templates/core/quan_ly_co_so.html")),
                str(Path("templates/core/tao_co_so.html")),
                str(Path("templates/core/chi_tiet_co_so.html")),
                str(Path("templates/core/quan_ly_chinh_sach.html")),
                str(Path("templates/core/tao_chinh_sach.html")),
                str(Path("templates/core/chi_tiet_chinh_sach.html")),
                str(Path("templates/core/nhat_ky_thao_tac.html")),
                str(Path("templates/core/chi_tiet_nhat_ky_thao_tac.html")),
            },
        )

        url_sources = "\n".join(
            path.read_text(encoding="utf-8")
            for path in Path(settings.BASE_DIR).rglob("urls.py")
        )
        self.assertNotIn("design_foundation_p5_harness", url_sources)

    def test_css_selectors_and_animation_stay_in_the_p5_namespace(self):
        selector_headers = re.findall(r"(?m)^\s*([^@}\n][^{\n]*)\{", self.css)
        selectors = []
        for header in selector_headers:
            depth = 0
            start = 0
            for index, character in enumerate(header):
                if character == "(":
                    depth += 1
                elif character == ")":
                    depth -= 1
                elif character == "," and depth == 0:
                    selectors.append(header[start:index].strip())
                    start = index + 1
            selectors.append(header[start:].strip())

        unscoped = [
            selector
            for selector in selectors
            if selector != "to" and not selector.startswith(".ndt-f5")
        ]
        self.assertEqual(unscoped, [])
        self.assertIn("@keyframes ndt-f5-spin", self.css)
        self.assertNotRegex(self.css, r"@keyframes\s+(?!ndt-f5-)")
        self.assertNotIn("!important", self.css)

    def test_component_contract_is_present(self):
        expected_classes = (
            "ndt-f5-container--full",
            "ndt-f5-container--readable",
            "ndt-f5-container--form",
            "ndt-f5-page-header",
            "ndt-f5-button--primary",
            "ndt-f5-button--secondary",
            "ndt-f5-button--danger",
            "ndt-f5-button--icon",
            "ndt-f5-form-section",
            "ndt-f5-filter",
            "ndt-f5-table",
            "ndt-f5-card",
            "ndt-f5-badge--pending",
            "ndt-f5-badge--info",
            "ndt-f5-alert--danger",
            "ndt-f5-empty",
            "ndt-f5-pagination",
            "ndt-f5-dialog",
        )
        for class_name in expected_classes:
            self.assertIn(class_name, self.css)
            self.assertIn(class_name, self.html)

        self.assertIn('data-label="Người thuê"', self.html)
        self.assertIn('aria-invalid="true"', self.html)
        self.assertIn('aria-current="page"', self.html)
        self.assertIn('aria-label="Mở tùy chọn"', self.html)
        self.assertIn('title="Mở tùy chọn"', self.html)
        self.assertIn('aria-busy="true" aria-disabled="true"', self.html)

        table_body = self.html.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
        self.assertEqual(table_body.count("<td"), table_body.count("data-label="))

    def test_harness_is_isolated_static_fixture_with_accessible_dialog_markup(self):
        self.assertNotIn("{% extends", self.html)
        self.assertIn('data-p5-harness', self.html)
        self.assertIn('role="dialog"', self.html)
        self.assertIn('aria-modal="true"', self.html)
        self.assertIn('aria-labelledby="p5DialogTitle"', self.html)
        self.assertIn('aria-describedby="p5DialogMessage"', self.html)
        self.assertIn('data-dialog-title="Xóa bản ghi này?"', self.html)
        self.assertIn('data-dialog-message=', self.html)

    def test_dialog_contract_includes_keyboard_and_focus_management(self):
        for contract in (
            'event.key === "Escape"',
            'event.key !== "Tab"',
            "restoreFocus",
            "previousFocus",
            "document.body.appendChild(dialog)",
            "data-ndt-f5-dialog-cancel",
            "window.NDTFoundationDialog",
        ):
            self.assertIn(contract, self.js)
        self.assertNotIn("window.confirm", self.js)

    def test_p5_tokens_use_navy_orange_and_semantic_states(self):
        for token in (
            "--ndt-f5-navy: #14243b",
            "--ndt-f5-orange: #b84d16",
            "--ndt-f5-success",
            "--ndt-f5-warning",
            "--ndt-f5-danger",
            "--ndt-f5-pending",
            "--ndt-f5-neutral",
            "--ndt-f5-focus",
        ):
            self.assertIn(token, self.css)
