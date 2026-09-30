"""Small reusable authorization fixtures, confined to test_ndt_motel."""
from datetime import timedelta

from django.apps import apps
from django.contrib.auth.models import AnonymousUser, User
from django.utils import timezone

from core.models import (
    ChinhSachHoTro, CoSo, DatPhong, FaceProfile, HoaDon, HopDong, LichSuHopDong,
    LichSuRaVao, LichSuSuaChua, LichSuThanhToan, LichSuThongBao, LichSuTrangThai,
    NhatKyThaoTac,
    NguoiOCungPhong, NguoiThue, Phong, QuyenRaVao, ThongBao,
    YeuCauGiaHanHopDong, YeuCauGhepNguoi, YeuCauSuaChua,
)
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.dich_vu.ngay_thue import tinh_ngay_ket_thuc_theo_thang


class RoleAccessFixture(BusinessFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.anonymous = AnonymousUser()
        cls.user_a, cls.user_b = cls.user, cls.other_user
        cls.superuser = User.objects.create_user(
            'role-superuser', is_superuser=True, is_staff=False,
        )
        cls.stranger = User.objects.create_user('role-stranger')
        cls.applicant = NguoiThue.objects.create(
            tai_khoan=cls.stranger, ho_ten='Role Applicant',
            so_dien_thoai='0900000003', cccd='000000000003',
        )
        cls.facility_b = CoSo.objects.create(
            ten_co_so='Role Facility B', dia_chi='Test B', quan='Test B',
        )
        cls.room_b = Phong.objects.create(
            co_so=cls.facility_b, so_phong='ROLE-B', gia_thue=2500000,
            dien_tich=25, so_nguoi_toi_da=3, tien_coc_mac_dinh=500000,
        )
        cls.policy = ChinhSachHoTro.objects.create(
            ten_chinh_sach='Role policy', ngay_bat_dau=cls.today,
            ngay_ket_thuc=cls.today + timedelta(days=30),
        )
        cls.audit_log = NhatKyThaoTac.objects.create(
            nguoi_thuc_hien=cls.admin, hanh_dong='xem', tieu_de='Role audit',
        )
        for suffix, tenant, room in [('a', cls.tenant, cls.room),
                                     ('b', cls.other, cls.room_b)]:
            end = tinh_ngay_ket_thuc_theo_thang(cls.today, 3)
            booking = DatPhong.objects.create(
                nguoi_thue=tenant, phong=room, ngay_nhan_phong=cls.today,
                so_thang_thue=3, ngay_tra_du_kien=end, trang_thai='da_duyet',
            )
            contract = HopDong.objects.create(
                dat_phong=booking, so_hop_dong='ROLE-' + suffix.upper(),
                ngay_bat_dau=cls.today, ngay_ket_thuc=end,
                tien_thue_thang=2500000, trang_thai='dang_hieu_luc',
                cho_phep_ghep=True,
            )
            room.dong_bo_trang_thai()
            resident = NguoiOCungPhong.objects.create(
                hop_dong=contract, ho_ten='Resident ' + suffix,
                cccd='00000000000' + ('4' if suffix == 'a' else '5'),
                ngay_vao=cls.today,
            )
            face = FaceProfile.objects.create(
                nguoi_thue=tenant, loai_chu_the='nguoi_thue',
            )
            permission = QuyenRaVao.objects.create(
                hop_dong=contract, nguon_cap='thu_cong', phong=room,
                nguoi_thue=tenant, loai_quyen='chu_phong',
                ngay_bat_dau=cls.today, ngay_ket_thuc=end,
            )
            objects = {
                'booking': booking, 'contract': contract, 'resident': resident,
                'face': face, 'permission': permission,
                'pending_booking': DatPhong.objects.create(
                    nguoi_thue=tenant, phong=room, ngay_nhan_phong=cls.today,
                    so_thang_thue=3, ngay_tra_du_kien=end,
                ),
                'invoice': HoaDon.objects.create(
                    hop_dong=contract, thang=cls.today.month, nam=cls.today.year,
                    tien_phong=2500000, han_thanh_toan=cls.today,
                ),
                'notice': ThongBao.objects.create(
                    nguoi_thue=tenant, tieu_de='Private notice ' + suffix,
                    noi_dung='Private body ' + suffix,
                ),
                'repair': YeuCauSuaChua.objects.create(
                    nguoi_thue=tenant, phong=room, tieu_de='Private repair ' + suffix,
                    noi_dung='Private repair body', loai_su_co='dien',
                ),
                # A is unrelated to B's request; the applicant has a third account.
                'sharing': YeuCauGhepNguoi.objects.create(
                    hop_dong=contract, nguoi_dang_ky=cls.applicant,
                    ho_ten=cls.applicant.ho_ten, cccd=cls.applicant.cccd,
                    ngay_du_kien_vao=cls.today,
                ),
                'renewal': YeuCauGiaHanHopDong.objects.create(
                    hop_dong=contract, nguoi_yeu_cau=tenant, so_thang_gia_han=1,
                    ngay_ket_thuc_cu=end,
                    ngay_ket_thuc_de_xuat=end + timedelta(days=30),
                ),
                'access_log': LichSuRaVao.objects.create(
                    quyen_ra_vao=permission, phong=room, nguoi_thue=tenant,
                    loai_su_kien='vao', nguon='thu_cong', thoi_diem=timezone.now(),
                ),
            }
            for name, obj in objects.items():
                setattr(cls, name + '_' + suffix, obj)
        cls.audit_records = [
            cls.audit_log, cls.access_log_b,
            LichSuThanhToan.objects.create(hoa_don=cls.invoice_b, so_tien=2500000,
                                          phuong_thuc='tien_mat'),
            LichSuHopDong.objects.create(hop_dong=cls.contract_b, hanh_dong='tao'),
            LichSuSuaChua.objects.create(yeu_cau=cls.repair_b, hanh_dong='tao'),
            LichSuThongBao.objects.create(thong_bao=cls.notice_b, hanh_dong='tao'),
            LichSuTrangThai.objects.create(doi_tuong='DatPhong',
                                          doi_tuong_id=cls.booking_b.pk,
                                          trang_thai_moi='da_duyet'),
        ]

    def business_snapshot(self):
        """Compare every business row, not only the endpoint's primary object."""
        return {
            model._meta.label: list(model.objects.order_by('pk').values())
            for model in apps.get_app_config('core').get_models()
        }

    def login_as(self, user):
        self.client.logout()
        if user.is_authenticated:
            self.client.force_login(user)
