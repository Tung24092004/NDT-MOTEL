"""Phase 8B-3 admin detail template render regressions."""
from html.parser import HTMLParser

from django.urls import reverse
from django.utils import timezone

from core.models import (
    ChinhSachHoTro,
    FaceProfile,
    HoaDon,
    LichSuRaVao,
    NhatKyThaoTac,
    QuyenRaVao,
    ThongBao,
    YeuCauSuaChua,
)
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture


class Phase8B3AdminDetailRenderTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.invoice = HoaDon.objects.create(
            hop_dong=self.contract_obj,
            thang=9,
            nam=2026,
            tien_phong=2500000,
            han_thanh_toan=self.today,
        )
        self.repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            tieu_de="Phase 8B3 repair",
            noi_dung="Render detail page",
            loai_su_co="dien",
        )
        self.policy = ChinhSachHoTro.objects.create(
            ten_chinh_sach="Phase 8B3 policy",
            loai_ho_tro="so_tien",
            gia_tri_ho_tro=100000,
            ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today,
        )
        self.notice = ThongBao.objects.create(
            nguoi_thue=self.tenant,
            tieu_de="Phase 8B3 notice",
            noi_dung="Render detail page",
        )
        self.resident = self.resident(self.contract_obj)
        self.face_profile = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
        )
        self.permission_obj = QuyenRaVao.objects.create(
            phong=self.room,
            nguoi_thue=self.tenant,
            loai_quyen="chu_phong",
            trang_thai="hoat_dong",
            ngay_bat_dau=self.today,
            ngay_ket_thuc=self.today,
            hop_dong=self.contract_obj,
            nguon_cap="thu_cong",
        )
        self.access_log = LichSuRaVao.objects.create(
            quyen_ra_vao=self.permission_obj,
            phong=self.room,
            nguoi_thue=self.tenant,
            loai_su_kien="vao",
            nguon="thu_cong",
            thoi_diem=timezone.now(),
        )
        self.audit_log = NhatKyThaoTac.objects.create(
            nguoi_thuc_hien=self.admin,
            hanh_dong="xem",
            module="phase_8b3",
            doi_tuong="ui",
            tieu_de="Phase 8B3 audit detail",
        )

    def test_active_admin_detail_pages_render(self):
        self.client.force_login(self.admin)
        cases = [
            ("chi_tiet_dat_phong", [self.contract_obj.dat_phong_id]),
            ("chi_tiet_hop_dong", [self.contract_obj.pk]),
            ("chi_tiet_hoa_don", [self.invoice.pk]),
            ("chi_tiet_sua_chua", [self.repair.pk]),
            ("chi_tiet_chinh_sach", [self.policy.pk]),
            ("chi_tiet_thong_bao", [self.notice.pk]),
            ("chi_tiet_co_so", [self.facility.pk]),
            ("chi_tiet_nguoi_o_cung", [self.resident.pk]),
            ("chi_tiet_face_profile", [self.face_profile.pk]),
            ("chi_tiet_quyen_ra_vao", [self.permission_obj.pk]),
            ("chi_tiet_lich_su_ra_vao", [self.access_log.pk]),
            ("chi_tiet_nhat_ky_thao_tac", [self.audit_log.pk]),
        ]

        for name, args in cases:
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 200)

"""Phase 8B-4 admin create/edit form render regressions."""
from django.urls import reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture


class Phase8B4AdminFormRenderTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.booking_without_contract = self.booking("da_duyet")

    def assert_admin_form_contains(self, name, expected_names, args=None):
        self.client.force_login(self.admin)
        response = self.client.get(reverse(name, args=args or []))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<form", html=False)
        self.assertContains(response, "csrfmiddlewaretoken")
        for field_name in expected_names:
            with self.subTest(route=name, field=field_name):
                self.assertContains(response, f'name="{field_name}"', html=False)

    def test_core_admin_create_edit_forms_render_with_contract_fields(self):
        cases = [
            ("tao_phong", [], ["co_so", "so_phong", "gia_thue", "hinh_anh"]),
            ("sua_phong", [self.room.pk], ["co_so", "so_phong", "gia_thue", "hinh_anh"]),
            (
                "tao_hop_dong",
                [self.booking_without_contract.pk],
                ["so_hop_dong", "tien_thue_thang", "tien_coc", "so_nguoi_o"],
            ),
            (
                "sua_hop_dong",
                [self.contract_obj.pk],
                ["tien_thue_thang", "tien_coc", "so_nguoi_o", "ghi_chu"],
            ),
            ("tao_hoa_don", [], ["hop_dong", "thang", "nam", "tien_phong"]),
            ("tao_sua_chua", [], ["nguoi_thue", "phong", "tieu_de", "noi_dung"]),
            ("tao_chinh_sach", [], ["ten_chinh_sach", "loai_ho_tro", "ngay_bat_dau"]),
            ("tao_thong_bao", [], ["nguoi_thue", "tieu_de", "loai", "noi_dung"]),
            ("tao_co_so", [], ["ten_co_so", "dia_chi", "quan", "trang_thai"]),
        ]

        for name, args, expected_names in cases:
            with self.subTest(route=name):
                self.assert_admin_form_contains(name, expected_names, args)

    def test_smart_room_admin_forms_render_with_contract_fields(self):
        cases = [
            ("tao_nguoi_o_cung", [], ["hop_dong", "ho_ten", "so_dien_thoai"]),
            ("tao_face_profile", [], ["subject_type_ui", "nguoi_thue", "nguoi_o_cung"]),
            ("tao_quyen_ra_vao", [], ["phong", "loai_quyen", "ngay_bat_dau"]),
            ("tao_lich_su_ra_vao", [], ["phong", "loai_su_kien", "thoi_diem"]),
        ]

        for name, args, expected_names in cases:
            with self.subTest(route=name):
                self.assert_admin_form_contains(name, expected_names, args)

    def test_multipart_upload_contracts_remain_present(self):
        self.client.force_login(self.admin)
        for name, args in [
            ("tao_phong", []),
            ("sua_phong", [self.room.pk]),
            ("tao_sua_chua", []),
        ]:
            with self.subTest(route=name):
                response = self.client.get(reverse(name, args=args))
                self.assertContains(response, 'enctype="multipart/form-data"', html=False)

"""Phase 8B-5 tenant self-service render and contract regressions."""
from django.urls import reverse

from core.models import FaceProfile, HoaDon, Phong, ThongBao, YeuCauSuaChua
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture


class Phase8B5TenantUIRegressionTests(BusinessFixture):
    def setUp(self):
        self.client.force_login(self.user)
        self.contract_obj = self.contract()

    def test_profile_update_form_contract_is_preserved(self):
        response = self.client.get(reverse("cap_nhat_thong_tin"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "csrfmiddlewaretoken")
        for field in ["ho_ten", "so_dien_thoai", "email", "nghe_nghiep", "que_quan"]:
            with self.subTest(field=field):
                self.assertContains(response, f'name="{field}"', html=False)

    def test_room_detail_and_booking_form_contract_render_for_tenant(self):
        available_room = Phong.objects.create(
            co_so=self.facility,
            so_phong="BOOK-8B5",
            gia_thue=2500000,
            dien_tich=25,
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=500000,
        )
        detail = self.client.get(reverse("chi_tiet_phong", args=[available_room.pk]))
        self.assertEqual(detail.status_code, 200)

        booking = self.client.get(reverse("dat_phong", args=[available_room.pk]))
        self.assertEqual(booking.status_code, 200)
        self.assertContains(booking, "csrfmiddlewaretoken")
        for field in ["ho_ten", "so_dien_thoai", "cccd", "ngay_nhan_phong", "so_thang_thue"]:
            with self.subTest(field=field):
                self.assertContains(booking, f'name="{field}"', html=False)

    def test_payment_request_page_only_renders_when_invoice_is_eligible(self):
        invoice = HoaDon.objects.create(
            hop_dong=self.contract_obj,
            thang=9,
            nam=2026,
            tien_phong=2500000,
            han_thanh_toan=self.today,
        )
        url = reverse("thanh_toan_hoa_don_cua_toi", args=[invoice.pk])

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, 'name="buoc"', html=False)
        self.assertContains(response, 'name="phuong_thuc"', html=False)

        invoice.trang_thai = "da_thanh_toan"
        invoice.save(update_fields=["trang_thai"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("chi_tiet_hoa_don_cua_toi", args=[invoice.pk]), response.url)

    def test_smart_room_self_service_creates_or_opens_own_face_profile(self):
        response = self.client.get(reverse("nhan_dien_su_dung_phong"))
        self.assertEqual(response.status_code, 302)
        face = FaceProfile.objects.get(nguoi_thue=self.tenant)
        self.assertIn(reverse("chi_tiet_face_profile", args=[face.pk]), response.url)

    def test_other_tenant_cannot_view_private_repair_or_notification(self):
        repair = YeuCauSuaChua.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            tieu_de="Tenant private repair",
            noi_dung="Private repair body",
            loai_su_co="dien",
        )
        notice = ThongBao.objects.create(
            nguoi_thue=self.tenant,
            tieu_de="Tenant private notice",
            noi_dung="Private notice body",
        )

        self.client.force_login(self.other_user)
        private_routes = [
            ("chi_tiet_yeu_cau_sua_chua_cua_toi", repair.pk),
            ("chi_tiet_thong_bao_cua_toi", notice.pk),
        ]
        for name, pk in private_routes:
            with self.subTest(route=name):
                self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 404)

"""Tenant page integration uses isolated test data; never development GET side effects."""
from pathlib import Path
from datetime import timedelta
from django.conf import settings
from django.template.loader import get_template
from django.urls import reverse
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import HoaDon, ThongBao, YeuCauSuaChua, FaceProfile, ChinhSachHoTro


class TenantUITests(BusinessFixture):
    def test_homepage_user_shortcuts_have_personal_labels_and_real_links(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []
                self.current = None

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    self.current = [dict(attrs).get("href", ""), ""]

            def handle_data(self, data):
                if self.current is not None:
                    self.current[1] += data

            def handle_endtag(self, tag):
                if tag == "a" and self.current is not None:
                    self.links.append((self.current[0], " ".join(self.current[1].split())))
                    self.current = None

        self.client.force_login(self.user)
        response = self.client.get(reverse("home"))
        self.assertTemplateUsed(response, "core/home.html")
        links = Links()
        links.feed(response.content.decode())
        for route, label in (
            ("danh_sach_phong", "Tìm phòng"),
            ("dat_phong_cua_toi", "Đặt phòng của tôi"),
            ("hop_dong_cua_toi", "Hợp đồng của tôi"),
            ("hoa_don_cua_toi", "Hóa đơn & thanh toán"),
            ("yeu_cau_sua_chua_cua_toi", "Hỗ trợ của tôi"),
        ):
            self.assertIn((reverse(route), label), links.links)
        self.assertNotContains(response, "Quản lý đặt phòng")
        for href, _ in links.links:
            self.assertFalse(href.startswith("/quan-ly-"), href)
            self.assertFalse(href.startswith("/dashboard-admin/"), href)
            self.assertFalse(href.startswith("/thong-bao-admin/"), href)

    def test_homepage_admin_booking_shortcut_is_unchanged(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("home"))
        self.assertContains(response, "Quản lý đặt phòng")
        self.assertNotContains(response, "Hóa đơn &amp; thanh toán")
        self.assertNotContains(response, "Hỗ trợ của tôi")


    def setUp(self):
        self.client.force_login(self.user)

    def test_public_policy_page_shows_only_current_policies_and_is_read_only(self):
        self.client.logout()
        url = reverse('chinh_sach_ho_tro')
        self.assertContains(self.client.get(url), 'Chưa có chính sách')
        for title, active, start, end in [('Current policy',True,-1,1),('Expired policy',True,-2,-1),('Future policy',True,1,2),('Hidden policy',False,-1,1)]:
            ChinhSachHoTro.objects.create(ten_chinh_sach=title,trang_thai=active,
                ngay_bat_dau=self.today+timedelta(days=start),ngay_ket_thuc=self.today+timedelta(days=end),
                loai_ho_tro='so_tien',gia_tri_ho_tro=150000)
        response = self.client.get(url)
        self.assertContains(response,'Current policy')
        for hidden in ['Expired policy','Future policy','Hidden policy']:
            self.assertNotContains(response,hidden)
        self.assertContains(response,'150.000 VND')
        self.assertEqual(self.client.post(url).status_code,405)

    def test_account_and_core_service_pages_render_shared_shell(self):
        self.contract()
        for name in ['tai_khoan','cap_nhat_thong_tin','doi_mat_khau_user','dat_phong_cua_toi','hop_dong_cua_toi',
                     'hoa_don_cua_toi','yeu_cau_sua_chua_cua_toi','tao_yeu_cau_sua_chua',
                     'yeu_cau_ghep_cua_toi','thong_bao_cua_toi','chinh_sach_ho_tro']:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="tenant-ui"')
                self.assertContains(response, 'css/tenant/components.css')

    def test_account_hub_has_complete_personal_navigation_without_admin_links(self):
        response = self.client.get(reverse('tai_khoan'))
        expected = (
            ('tai_khoan', 'Tài khoản &amp; đặt phòng'),
            ('dat_phong_cua_toi', 'Đặt phòng của tôi'),
            ('hop_dong_cua_toi', 'Hợp đồng của tôi'),
            ('hoa_don_cua_toi', 'Hóa đơn &amp; thanh toán'),
            ('yeu_cau_sua_chua_cua_toi', 'Sửa chữa của tôi'),
            ('yeu_cau_ghep_cua_toi', 'Ở ghép của tôi'),
            ('thong_bao_cua_toi', 'Thông báo của tôi'),
            ('chinh_sach_ho_tro', 'Chính sách hỗ trợ'),
            ('nhan_dien_su_dung_phong', 'Đăng ký Face ID'),
        )
        for route, label in expected:
            with self.subTest(route=route):
                self.assertContains(response, f'href="{reverse(route)}"', html=False)
                self.assertContains(response, label, html=False)
        for admin_path in ('/dashboard-admin/', '/thong-bao-admin/', '/quan-ly-'):
            self.assertNotContains(response, admin_path)

    def test_account_action_urls_are_canonical_and_legacy_urls_redirect(self):
        self.assertEqual(reverse('cap_nhat_thong_tin'), '/tai-khoan/cap-nhat/')
        self.assertEqual(reverse('doi_mat_khau_user'), '/tai-khoan/doi-mat-khau/')
        response = self.client.get(reverse('tai_khoan'))
        self.assertContains(response, 'href="/tai-khoan/cap-nhat/"', html=False)
        self.assertContains(response, 'href="/tai-khoan/doi-mat-khau/"', html=False)
        self.assertRedirects(
            self.client.get('/cap-nhat-thong-tin/'),
            reverse('cap_nhat_thong_tin'),
            fetch_redirect_response=False,
        )
        self.assertEqual(self.client.get('/doi-mat-khau/').status_code, 200)

    def test_password_page_has_valid_template_dom(self):
        response = self.client.get(reverse('doi_mat_khau_user'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h1>Đổi mật khẩu</h1>', html=True)
        self.assertNotContains(response, '```')

    def test_face_id_unavailable_renders_tenant_info_state(self):
        response = self.client.get(reverse('nhan_dien_su_dung_phong'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/face_id_unavailable.html')
        self.assertTemplateUsed(response, 'core/tenant_base.html')
        self.assertContains(response, 'Chưa thể đăng ký Face ID')
        self.assertContains(response, reverse('hop_dong_cua_toi'))
        self.assertNotContains(response, '/quan-ly-face-profile/')

    def test_admin_does_not_render_tenant_account_actions(self):
        self.client.force_login(self.admin)
        for route in ('tai_khoan', 'cap_nhat_thong_tin', 'doi_mat_khau_user'):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertRedirects(
                    response,
                    reverse('dashboard_admin'),
                    fetch_redirect_response=False,
                )

    def test_guest_auth_and_booking_pages(self):
        self.client.logout()
        for name in ['dang_nhap', 'dang_ky']:
            response = self.client.get(reverse(name), {'next': reverse('dat_phong', args=[self.room.pk])})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'class="tenant-ui"')
            self.assertContains(response, 'name="next"')
        self.client.force_login(self.user)
        response = self.client.get(reverse('dat_phong', args=[self.room.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="tenant-ui"')
        response = self.client.post(reverse('dat_phong', args=[self.room.pk]), {
            'ho_ten':self.tenant.ho_ten,'so_dien_thoai':self.tenant.so_dien_thoai,
            'cccd':self.tenant.cccd,'ngay_nhan_phong':str(self.today),'so_thang_thue':'3',
            'tien_coc_du_kien':'1', 'so_nguoi_o':'1', 'da_dong_y_dieu_khoan':'on',
            'companions-TOTAL_FORMS':'0', 'companions-INITIAL_FORMS':'0'})
        self.assertEqual(response.status_code,302)
        response = self.client.get(response.url)
        self.assertTemplateUsed(response,'core/tenant/booking/deposit_payment.html')

    def test_invoice_states_have_correct_cta_and_pending_message(self):
        invoice = HoaDon.objects.create(hop_dong=self.contract(), thang=9, nam=2026,
            tien_phong=2500000, han_thanh_toan=self.today)
        for state in ['chua_thanh_toan','cho_xac_nhan','da_thanh_toan','qua_han','huy']:
            with self.subTest(state=state):
                invoice.trang_thai = state
                invoice.save()
                response = self.client.get(reverse('chi_tiet_hoa_don_cua_toi', args=[invoice.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '2.500.000')
                action = 'href="'+reverse('thanh_toan_hoa_don_cua_toi', args=[invoice.pk])+'"'
                if state in ['chua_thanh_toan','qua_han']:
                    self.assertContains(response, action)
                else:
                    self.assertNotContains(response, action)
                if state == 'cho_xac_nhan':
                    self.assertContains(response, 'Không cần gửi lại')

    def test_contract_notification_and_face_details_render(self):
        hd = self.contract()
        notice = ThongBao.objects.create(nguoi_thue=self.tenant, tieu_de='UI notice', noi_dung='Test')
        face = FaceProfile.objects.create(nguoi_thue=self.tenant, loai_chu_the='nguoi_thue')
        for name, pk in [('chi_tiet_hop_dong_cua_toi', hd.pk),
                         ('chi_tiet_thong_bao_cua_toi', notice.pk), ('chi_tiet_face_profile', face.pk)]:
            response = self.client.get(reverse(name, args=[pk]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'class="tenant-ui"')

    def test_repair_roommate_and_payment_pages_render(self):
        hd = self.contract()
        self.client.force_login(self.other_user)
        response = self.client.get(reverse('dang_ky_ghep_phong',args=[self.room.pk]))
        self.assertEqual(response.status_code,200)
        self.client.force_login(self.user)
        repair = YeuCauSuaChua.objects.create(nguoi_thue=self.tenant, phong=self.room,
            tieu_de='Kiểm tra thiết bị', noi_dung='Mô tả kiểm thử giao diện', loai_su_co='dien')
        sharing = self.sharing_request(hd)
        for name, pk in [('chi_tiet_yeu_cau_sua_chua_cua_toi',repair.pk),
                         ('chi_tiet_yeu_cau_ghep',sharing.pk)]:
            response = self.client.get(reverse(name,args=[pk]))
            self.assertEqual(response.status_code,200)
        invoice = HoaDon.objects.create(hop_dong=hd,thang=9,nam=2026,tien_phong=2500000,han_thanh_toan=self.today)
        url = reverse('thanh_toan_hoa_don_cua_toi',args=[invoice.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code,200)
        for method in ['tien_mat','chuyen_khoan']:
            response = self.client.post(url,{'buoc':'xac_nhan','phuong_thuc':method})
            self.assertEqual(response.status_code,200)

    def test_other_tenant_cannot_view_private_details(self):
        hd = self.contract()
        invoice = HoaDon.objects.create(hop_dong=hd, thang=9, nam=2026, han_thanh_toan=self.today)
        self.client.force_login(self.other_user)
        for name, pk in [('chi_tiet_hop_dong_cua_toi', hd.pk),('chi_tiet_hoa_don_cua_toi',invoice.pk)]:
            self.assertEqual(self.client.get(reverse(name,args=[pk])).status_code,404)

    def test_all_migrated_templates_compile(self):
        for css in (Path(settings.BASE_DIR)/'static/css/tenant').glob('*.css'):
            if css.stem != 'components':
                with self.subTest(template=css.stem):
                    if css.stem == 'booking':
                        for page in ('create', 'list', 'detail', 'deposit_payment', 'success'):
                            get_template('core/tenant/booking/'+page+'.html')
                    else:
                        get_template('core/'+css.stem+'.html')


from core.models import DatPhong, HopDong, NguoiThue


class AdminDashboardUIRegressionTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.pending_booking = self.booking("cho_duyet", tenant=self.other)
        self.rejected_booking = self.booking("tu_choi", tenant=self.other)

    def test_dashboard_renders_live_metrics_statuses_and_real_links(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard_admin"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/dashboard_admin.html")
        self.assertContains(response, 'class="admin-dashboard ndt-foundation"', html=False)
        self.assertContains(response, "css/admin_dashboard.css")
        self.assertNotContains(response, "data-room-count")
        dashboard_source = (
            Path(settings.BASE_DIR) / "templates/core/dashboard_admin.html"
        ).read_text(encoding="utf-8")
        self.assertNotIn("<style", dashboard_source)

        expected_metrics = {
            "tong_phong": Phong.objects.count(),
            "phong_trong": Phong.objects.filter(trang_thai="trong").count(),
            "phong_da_dat": Phong.objects.filter(trang_thai="da_dat").count(),
            "phong_dang_thue": Phong.objects.filter(trang_thai="dang_thue").count(),
            "phong_bao_tri": Phong.objects.filter(trang_thai="bao_tri").count(),
            "tong_nguoi_thue": NguoiThue.objects.count(),
            "tong_dat_phong": DatPhong.objects.count(),
            "dat_phong_cho_duyet": DatPhong.objects.filter(trang_thai="cho_duyet").count(),
            "dat_phong_da_duyet": DatPhong.objects.filter(trang_thai="da_duyet").count(),
            "dat_phong_tu_choi": DatPhong.objects.filter(trang_thai="tu_choi").count(),
            "dat_phong_da_huy": DatPhong.objects.filter(trang_thai="da_huy").count(),
            "tong_hop_dong": HopDong.objects.count(),
            "hop_dong_dang_hieu_luc": HopDong.objects.filter(trang_thai="dang_hieu_luc").count(),
            "hop_dong_sap_het_han": HopDong.objects.filter(trang_thai="sap_het_han").count(),
            "hop_dong_cho_hieu_luc": HopDong.objects.filter(trang_thai="cho_hieu_luc").count(),
            "hop_dong_da_het_han": HopDong.objects.filter(trang_thai="da_het_han").count(),
        }
        for context_name, expected in expected_metrics.items():
            with self.subTest(metric=context_name):
                self.assertEqual(response.context[context_name], expected)

        latest_ids = list(DatPhong.objects.order_by("-id").values_list("id", flat=True)[:5])
        self.assertEqual(
            [booking.id for booking in response.context["danh_sach_dat_phong"]],
            latest_ids,
        )
        self.assertContains(response, self.pending_booking.get_trang_thai_display())
        self.assertContains(response, self.rejected_booking.get_trang_thai_display())

        for route_name in (
            "quan_ly_phong",
            "quan_ly_dat_phong",
            "quan_ly_hop_dong",
            "quan_ly_hoa_don",
            "quan_ly_nguoi_thue",
            "quan_ly_sua_chua",
            "quan_ly_thong_bao",
            "smart_room_dashboard",
        ):
            with self.subTest(route=route_name):
                self.assertContains(response, f'href="{reverse(route_name)}"', html=False)
        for booking_id in latest_ids:
            self.assertContains(
                response,
                f'href="{reverse("chi_tiet_dat_phong", args=[booking_id])}"',
                html=False,
            )
