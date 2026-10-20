"""P6I contracts for Account & Authentication."""

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection
from django.test import Client, SimpleTestCase, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from core.models import CoSo, DatPhong, HopDong, NguoiThue, Phong, QuyenRaVao


class AccountAuthP6IStaticTests(SimpleTestCase):
    def test_five_templates_are_the_only_p6i_owners(self):
        expected = {
            "tai_khoan.html",
            "cap_nhat_thong_tin.html",
            "doi_mat_khau.html",
            "dang_nhap.html",
            "dang_ky.html",
        }
        root = Path(settings.BASE_DIR) / "templates" / "core"
        owners = {
            path.name
            for path in root.glob("*.html")
            if "ndt-account-auth" in path.read_text(encoding="utf-8")
        }
        self.assertEqual(owners, expected)
        for name in expected:
            source = (root / name).read_text(encoding="utf-8")
            self.assertEqual(source.count("foundation/p5.css"), 1, name)
            self.assertEqual(source.count("ndt-f5 ndt-account-auth"), 1, name)
            self.assertIn("account_auth_p6i.css", source)
            self.assertIn("account_auth_p6i.js", source)
            self.assertNotIn("<script>", source)
            self.assertNotIn("onclick=", source)

    def test_module_assets_are_scoped_and_shared_shell_does_not_load_p5(self):
        base = Path(settings.BASE_DIR)
        css = (base / "static/css/account_auth_p6i.css").read_text(encoding="utf-8")
        js = (base / "static/js/account_auth_p6i.js").read_text(encoding="utf-8")
        self.assertNotIn("!important", css)
        self.assertIn(".ndt-f5.ndt-account-auth", css)
        self.assertIn("event.submitter", js)
        self.assertIn("checkValidity", js)
        self.assertIn("aria-busy", js)
        for shell in ("base.html", "tenant_base.html"):
            source = (base / "templates/core" / shell).read_text(encoding="utf-8")
            self.assertNotIn("foundation/p5.css", source)
            self.assertNotIn("account_auth_p6i", source)

    def test_account_dialog_uses_p5_root_and_api_only(self):
        source = (
            Path(settings.BASE_DIR) / "templates/core/tai_khoan.html"
        ).read_text(encoding="utf-8")
        self.assertIn("p5_dialog_root.html", source)
        self.assertIn("p5-dialog.js", source)
        self.assertNotIn("foundation/dialog.js", source)
        self.assertNotIn("foundation/dialog_root.html", source)


class AccountAuthP6IFunctionalTests(TestCase):
    password = "Current-pass-6201"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        actual_database = connection.settings_dict["NAME"]
        print(f"P6I_FUNCTIONAL_DATABASE={actual_database}")
        if actual_database != "test_ndt_motel":
            raise RuntimeError("P6I functional tests require isolated test_ndt_motel.")

    def setUp(self):
        self.tenant_user = User.objects.create_user(
            "p6i-tenant", password=self.password, email="user-record@example.com"
        )
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="Tên ban đầu",
            cccd="000000006201",
            so_dien_thoai="0900006201",
            email="old@example.com",
            ngay_sinh=date(1995, 3, 12),
            gioi_tinh="nam",
            que_quan="Quê cũ",
            dia_chi_thuong_tru="Địa chỉ cũ",
            nghe_nghiep="Nghề cũ",
            nguoi_lien_he="Liên hệ cũ",
            sdt_nguoi_lien_he="0900006202",
        )
        self.staff = User.objects.create_user(
            "p6i-staff", password=self.password, is_staff=True
        )
        self.superuser = User.objects.create_superuser(
            "p6i-super", "super@example.com", self.password
        )

    def _login(self, user=None):
        self.client.force_login(user or self.tenant_user)

    def test_route_inventory_is_eight_patterns_seven_handlers_five_templates(self):
        names = (
            "dang_ky", "dang_nhap", "dang_xuat", "tai_khoan",
            "doi_mat_khau_user", "cap_nhat_thong_tin", "doi_mat_khau",
            "cap_nhat_thong_tin_legacy",
        )
        handlers = set()
        for name in names:
            match = resolve(reverse(name))
            handlers.add(match.func.view_class if hasattr(match.func, "view_class") else match.func)
        self.assertEqual(len(names), 8)
        self.assertEqual(len(handlers), 7)

    def test_guest_tenant_staff_superuser_access_matrix(self):
        protected = (
            ("tai_khoan", "dang-nhap"),
            ("cap_nhat_thong_tin", "dang-nhap"),
            ("doi_mat_khau_user", "dang-nhap"),
            ("doi_mat_khau", "dang-nhap"),
        )
        for name, redirect_fragment in protected:
            with self.subTest(role="guest", route=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertIn(redirect_fragment, response.url)
        role_expectations = (
            (self.tenant_user, {"tai_khoan": 200, "cap_nhat_thong_tin": 200, "doi_mat_khau_user": 200, "doi_mat_khau": 200}),
            (self.staff, {"tai_khoan": 302, "cap_nhat_thong_tin": 302, "doi_mat_khau_user": 302, "doi_mat_khau": 200}),
            (self.superuser, {"tai_khoan": 302, "cap_nhat_thong_tin": 302, "doi_mat_khau_user": 302, "doi_mat_khau": 200}),
        )
        for user, expectations in role_expectations:
            self.client.force_login(user)
            for name, status in expectations.items():
                with self.subTest(role=user.username, route=name):
                    self.assertEqual(self.client.get(reverse(name)).status_code, status)
            self.client.logout()

    def test_authenticated_user_without_profile_keeps_account_404(self):
        user = User.objects.create_user("profile-missing", password=self.password)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("tai_khoan")).status_code, 404)

    def test_login_validation_success_session_roles_and_next(self):
        response = self.client.post(reverse("dang_nhap"), {"username": "", "password": ""})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vui lòng nhập đầy đủ")
        response = self.client.post(
            reverse("dang_nhap"),
            {"username": "p6i-tenant", "password": "wrong", "next": "/phong/?q=P6I"},
        )
        self.assertContains(response, "Tên đăng nhập hoặc mật khẩu không đúng")
        self.assertContains(response, 'value="/phong/?q=P6I"', html=False)
        self.assertNotContains(response, "wrong")
        disabled_user = User.objects.create_user(
            "p6i-disabled", password=self.password, is_active=False
        )
        for username in ("p6i-missing", disabled_user.username):
            with self.subTest(username=username):
                response = self.client.post(
                    reverse("dang_nhap"),
                    {"username": username, "password": self.password},
                )
                self.assertContains(response, "Tên đăng nhập hoặc mật khẩu không đúng")
        session = self.client.session
        session["pre_login_marker"] = "present"
        session.save()
        old_session_key = session.session_key
        response = self.client.post(
            reverse("dang_nhap"),
            {"username": "p6i-tenant", "password": self.password, "next": "/phong/"},
        )
        self.assertRedirects(response, "/phong/", fetch_redirect_response=False)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.tenant_user.pk)
        self.assertNotEqual(self.client.session.session_key, old_session_key)
        self.assertEqual(self.client.session["pre_login_marker"], "present")
        self.client.logout()
        response = self.client.post(
            reverse("dang_nhap"),
            {"username": "p6i-staff", "password": self.password},
        )
        self.assertRedirects(response, reverse("dashboard_admin"), fetch_redirect_response=False)
        self.client.force_login(self.tenant_user)
        response = self.client.get(reverse("dang_nhap"), {"next": "/phong/"})
        self.assertRedirects(response, "/phong/", fetch_redirect_response=False)
        self.client.force_login(self.staff)
        response = self.client.get(reverse("dang_nhap"), {"next": "/phong/"})
        self.assertRedirects(response, reverse("dashboard_admin"), fetch_redirect_response=False)

    def test_login_and_register_preserve_current_safe_next_contract(self):
        for route in ("dang_nhap", "dang_ky"):
            for unsafe in ("//evil.example/path", "https://evil.example/path"):
                with self.subTest(route=route, target=unsafe):
                    response = self.client.get(reverse(route), {"next": unsafe})
                    if route == "dang_ky":
                        self.assertNotContains(response, f'value="{unsafe}"')
                    else:
                        self.assertNotContains(response, f'value="{unsafe}"')
            safe = "/phong/?q=P6I"
            response = self.client.get(reverse(route), {"next": safe})
            self.assertContains(response, f'value="{safe}"', html=False)
        response = self.client.post(
            reverse("dang_nhap"),
            {"username": self.tenant_user.username, "password": self.password, "next": "//evil.example/path"},
        )
        self.assertRedirects(response, reverse("tai_khoan"), fetch_redirect_response=False)

    def test_register_validation_uniqueness_retention_and_atomic_success(self):
        base = {
            "username": "new-p6i",
            "password": "new-password",
            "password_confirm": "new-password",
            "ho_ten": "Người đăng ký",
            "so_dien_thoai": "0900006299",
            "email": "new@example.com",
            "cccd": "000000006299",
        }
        cases = (
            ({"username": "", "password": "", "password_confirm": ""}, "Vui lòng nhập tên đăng nhập"),
            ({"password": "", "password_confirm": ""}, "Vui lòng nhập mật khẩu"),
            ({"password": "new-password", "password_confirm": "wrong-pass"}, "Xác nhận mật khẩu không khớp"),
            ({"ho_ten": ""}, "Vui lòng nhập họ và tên"),
            ({"so_dien_thoai": ""}, "Vui lòng nhập số điện thoại"),
            ({"so_dien_thoai": "09099"}, "Số điện thoại không đúng định dạng"),
            ({"email": "email-khong-hop-le"}, "Email không đúng định dạng"),
            ({"email": self.tenant_user.email}, "Email đã được đăng ký"),
            ({"username": self.tenant_user.username}, "Tên đăng nhập đã tồn tại"),
            ({"cccd": ""}, "Vui lòng nhập CCCD"),
            ({"cccd": "123"}, "CCCD phải gồm 12 chữ số"),
            ({"cccd": self.tenant.cccd}, "CCCD đã được đăng ký"),
        )
        for changes, message in cases:
            payload = {**base, **changes}
            with self.subTest(message=message):
                response = self.client.post(reverse("dang_ky"), payload)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)
                if payload.get("username"):
                    self.assertContains(response, payload["username"])
        booking_count = DatPhong.objects.count()
        contract_count = HopDong.objects.count()
        room_count = Phong.objects.count()
        access_right_count = QuyenRaVao.objects.count()
        response = self.client.post(reverse("dang_ky"), base)
        self.assertRedirects(response, reverse("dang_nhap"), fetch_redirect_response=False)
        user = User.objects.get(username=base["username"])
        profile = NguoiThue.objects.get(tai_khoan=user)
        self.assertEqual(profile.email, base["email"])
        self.assertTrue(user.check_password(base["password"]))
        self.assertEqual(User.objects.filter(username=base["username"]).count(), 1)
        self.assertEqual(NguoiThue.objects.filter(cccd=base["cccd"]).count(), 1)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(profile.trang_thai_luu_tru, "tam_vang")
        self.assertEqual(DatPhong.objects.count(), booking_count)
        self.assertEqual(HopDong.objects.count(), contract_count)
        self.assertEqual(Phong.objects.count(), room_count)
        self.assertEqual(QuyenRaVao.objects.count(), access_right_count)

    def test_profile_get_has_eight_fields_and_read_only_identity_is_absent(self):
        self._login()
        response = self.client.get(reverse("cap_nhat_thong_tin"))
        for name in (
            "ho_ten", "so_dien_thoai", "email", "que_quan",
            "dia_chi_thuong_tru", "nghe_nghiep", "nguoi_lien_he",
            "sdt_nguoi_lien_he",
        ):
            self.assertContains(response, f'name="{name}"')
        for name in ("cccd", "ngay_sinh", "gioi_tinh"):
            self.assertNotContains(response, f'name="{name}"')

    def test_profile_invalid_post_preserves_all_submitted_values(self):
        self._login()
        payload = {
            "ho_ten": "Tên vừa nhập",
            "so_dien_thoai": "0909999999",
            "email": "email-khong-hop-le",
            "que_quan": "Quê vừa nhập",
            "dia_chi_thuong_tru": "Địa chỉ vừa nhập",
            "nghe_nghiep": "Nghề vừa nhập",
            "nguoi_lien_he": "Liên hệ vừa nhập",
            "sdt_nguoi_lien_he": "0911111111",
        }
        response = self.client.post(reverse("cap_nhat_thong_tin"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Email không đúng định dạng")
        for value in payload.values():
            self.assertContains(response, value)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.ho_ten, "Tên ban đầu")

    def test_profile_valid_updates_exact_eight_fields_not_read_only_identity(self):
        self._login()
        old_cccd, old_birth, old_gender = self.tenant.cccd, self.tenant.ngay_sinh, self.tenant.gioi_tinh
        old_timestamp = self.tenant.ngay_cap_nhat
        payload = {
            "ho_ten": "Tên mới", "so_dien_thoai": "0912345678",
            "email": "new-profile@example.com", "que_quan": "Quê mới",
            "dia_chi_thuong_tru": "Địa chỉ mới", "nghe_nghiep": "Nghề mới",
            "nguoi_lien_he": "Liên hệ mới", "sdt_nguoi_lien_he": "0987654321",
            "cccd": "SHOULD-NOT-CHANGE", "ngay_sinh": "2000-01-01", "gioi_tinh": "nu",
        }
        response = self.client.post(reverse("cap_nhat_thong_tin"), payload)
        self.assertRedirects(response, reverse("tai_khoan"), fetch_redirect_response=False)
        self.tenant.refresh_from_db()
        for field in (
            "ho_ten", "so_dien_thoai", "email", "que_quan",
            "dia_chi_thuong_tru", "nghe_nghiep", "nguoi_lien_he", "sdt_nguoi_lien_he",
        ):
            self.assertEqual(getattr(self.tenant, field), payload[field])
        self.assertEqual((self.tenant.cccd, self.tenant.ngay_sinh, self.tenant.gioi_tinh), (old_cccd, old_birth, old_gender))
        self.assertGreater(self.tenant.ngay_cap_nhat, old_timestamp)
        self.assertEqual(self.tenant_user.email, "user-record@example.com")

    def test_password_five_error_branches_and_success_keep_session(self):
        cases = (
            ({"mat_khau_hien_tai": "wrong", "mat_khau_moi": "New-pass-1", "xac_nhan_mat_khau": "New-pass-1"}, "Mật khẩu hiện tại không chính xác"),
            ({"mat_khau_hien_tai": self.password, "mat_khau_moi": "", "xac_nhan_mat_khau": ""}, "Vui lòng nhập mật khẩu mới"),
            ({"mat_khau_hien_tai": self.password, "mat_khau_moi": "123", "xac_nhan_mat_khau": "123"}, "ít nhất 6 ký tự"),
            ({"mat_khau_hien_tai": self.password, "mat_khau_moi": self.password, "xac_nhan_mat_khau": self.password}, "phải khác mật khẩu hiện tại"),
            ({"mat_khau_hien_tai": self.password, "mat_khau_moi": "New-pass-1", "xac_nhan_mat_khau": "New-pass-2"}, "xác nhận không khớp"),
        )
        for payload, message in cases:
            with self.subTest(message=message):
                client = Client()
                client.force_login(self.tenant_user)
                response = client.post(reverse("doi_mat_khau_user"), payload)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, message)
        self._login()
        response = self.client.post(
            reverse("doi_mat_khau_user"),
            {"mat_khau_hien_tai": self.password, "mat_khau_moi": "New-pass-6201", "xac_nhan_mat_khau": "New-pass-6201"},
        )
        self.assertRedirects(response, reverse("tai_khoan"), fetch_redirect_response=False)
        self.tenant_user.refresh_from_db()
        self.assertTrue(self.tenant_user.check_password("New-pass-6201"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.tenant_user.pk)

    def test_account_hub_owner_filter_order_counts_status_and_no_get_mutation(self):
        facility = CoSo.objects.create(ten_co_so="P6I", dia_chi="Test", quan="Cẩm Lệ")
        room = Phong.objects.create(
            co_so=facility, so_phong="P6I-201", gia_thue=Decimal("3000000"),
            dien_tich=Decimal("25"), so_nguoi_toi_da=2,
            tien_coc_mac_dinh=Decimal("500000"), trang_thai="trong",
        )
        own = DatPhong.objects.create(
            nguoi_thue=self.tenant, phong=room,
            ngay_nhan_phong=timezone.localdate() + timedelta(days=5),
            so_thang_thue=3, trang_thai="cho_duyet",
        )
        foreign_user = User.objects.create_user("foreign-p6i")
        foreign = NguoiThue.objects.create(
            tai_khoan=foreign_user, ho_ten="Foreign", cccd="000000006299", so_dien_thoai="0900006299"
        )
        foreign_booking = DatPhong.objects.create(
            nguoi_thue=foreign, phong=room,
            ngay_nhan_phong=timezone.localdate() + timedelta(days=6),
            so_thang_thue=3, trang_thai="cho_duyet",
        )
        self._login()
        response = self.client.get(reverse("tai_khoan"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["so_dat_phong_cho_duyet"], 1)
        ids = list(response.context["danh_sach_dat_phong"].values_list("pk", flat=True))
        self.assertEqual(ids, [own.pk])
        self.assertNotIn(foreign_booking.pk, ids)
        self.assertEqual(DatPhong.objects.get(pk=own.pk).trang_thai, "cho_duyet")

    def test_legacy_redirect_remains_explicit(self):
        response = self.client.get(reverse("cap_nhat_thong_tin_legacy"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("cap_nhat_thong_tin"))

    def test_logout_requires_csrf_post_and_clears_authenticated_session(self):
        self._login()
        response = self.client.get(reverse("dang_xuat"))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.tenant_user.pk)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.tenant_user)
        response = csrf_client.post(reverse("dang_xuat"))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(int(csrf_client.session["_auth_user_id"]), self.tenant_user.pk)
        response = self.client.post(reverse("dang_xuat"), {"next": "//evil.example/path"})
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)
        response = Client().post(reverse("dang_xuat"))
        self.assertRedirects(response, reverse("home"), fetch_redirect_response=False)

    def test_post_endpoints_reject_missing_csrf(self):
        anonymous = Client(enforce_csrf_checks=True)
        for name in ("dang_nhap", "dang_ky", "dang_xuat"):
            with self.subTest(route=name):
                self.assertEqual(anonymous.post(reverse(name), {}).status_code, 403)

        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.tenant_user)
        for name in ("cap_nhat_thong_tin", "doi_mat_khau_user"):
            with self.subTest(route=name):
                self.assertEqual(protected.post(reverse(name), {}).status_code, 403)
