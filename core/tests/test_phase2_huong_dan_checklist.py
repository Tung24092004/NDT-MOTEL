"""Kiem thu Phase 2 tren co so du lieu test tach biet."""
from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import FaceProfile, HoaDon, ThanhToanCocDatPhong


class HuongDanThuePhongTests(BusinessFixture):
    def test_khach_xem_duoc_huong_dan_khong_lo_du_lieu_nguoi_thue(self):
        response = self.client.get(reverse("huong_dan_thue_phong"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Hướng dẫn thuê phòng")
        self.assertContains(response, "Xem phòng")
        self.assertContains(response, "Đăng ký")
        self.assertContains(response, "Đăng nhập")
        self.assertNotContains(response, self.tenant.ho_ten)
        self.assertNotContains(response, self.tenant.cccd)


class ViecTiepTheoTaiKhoanTests(BusinessFixture):
    def setUp(self):
        self.client.force_login(self.user)

    def _context(self):
        response = self.client.get(reverse("tai_khoan"))
        self.assertEqual(response.status_code, 200)
        return response, response.context["viec_tiep_theo"]

    def _booking_cho_coc(self, tenant=None):
        booking = self.booking(status="cho_duyet", tenant=tenant)
        type(booking).objects.filter(pk=booking.pk).update(
            gia_thue_thang_tai_thoi_diem_dat=Decimal("2500000"),
            tien_coc_du_kien=Decimal("500000"),
            da_dong_y_dieu_khoan=True,
            thoi_diem_dong_y_dieu_khoan=timezone.now(),
            noi_dung_dieu_khoan_snapshot="Điều khoản kiểm thử",
            ty_le_hoan_coc_snapshot=Decimal("50"),
            han_thanh_toan_coc=timezone.now() + timedelta(hours=24),
        )
        booking.refresh_from_db()
        return booking

    def test_uu_tien_hoan_thien_ho_so(self):
        self.tenant.so_dien_thoai = ""
        self.tenant.save(update_fields=["so_dien_thoai"])

        response, item = self._context()

        self.assertEqual(item["ma"], "ho_so")
        self.assertContains(response, 'data-next-step="ho_so"')
        self.assertEqual(item["duong_dan"], reverse("cap_nhat_thong_tin"))

    def test_uu_tien_thanh_toan_coc(self):
        booking = self._booking_cho_coc()
        ThanhToanCocDatPhong.objects.create(
            dat_phong=booking,
            so_tien=booking.tien_coc_du_kien,
        )

        _, item = self._context()

        self.assertEqual(item["ma"], "thanh_toan_coc")
        self.assertEqual(
            item["duong_dan"],
            reverse("thanh_toan_coc_cua_toi", args=[booking.pk]),
        )

    def test_da_bao_coc_chi_cho_xac_nhan_khong_moi_thanh_toan_lai(self):
        booking = self._booking_cho_coc()
        ThanhToanCocDatPhong.objects.create(
            dat_phong=booking,
            so_tien=booking.tien_coc_du_kien,
            trang_thai="cho_xac_nhan",
            thoi_diem_user_bao_da_thanh_toan=timezone.now(),
        )

        response, item = self._context()

        self.assertEqual(item["ma"], "cho_xac_nhan_coc")
        self.assertEqual(item["nhan_nut"], "Xem yêu cầu")
        self.assertContains(response, "Không cần thanh toán lại")
        self.assertNotEqual(
            item["duong_dan"],
            reverse("thanh_toan_coc_cua_toi", args=[booking.pk]),
        )

    def test_hop_dong_hieu_luc_chua_co_face_id(self):
        self.contract()

        _, item = self._context()

        self.assertEqual(item["ma"], "face_id")
        self.assertEqual(item["duong_dan"], reverse("nhan_dien_su_dung_phong"))

    def test_face_id_hop_le_thi_uu_tien_hoa_don(self):
        contract = self.contract()
        FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            face_encoding="phase-2-vector",
            dong_y_du_lieu_khuon_mat=True,
        )
        invoice = HoaDon.objects.create(
            hop_dong=contract,
            thang=9,
            nam=2026,
            tien_phong=Decimal("2500000"),
            han_thanh_toan=self.today,
            trang_thai="qua_han",
        )

        _, item = self._context()

        self.assertEqual(item["ma"], "hoa_don")
        self.assertEqual(
            item["duong_dan"],
            reverse("chi_tiet_hoa_don_cua_toi", args=[invoice.pk]),
        )

    def test_face_id_thieu_consent_van_can_dang_ky_lai(self):
        self.contract()
        FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
            face_encoding="legacy-vector",
        )

        _, item = self._context()

        self.assertEqual(item["ma"], "face_id")
        self.assertEqual(item["duong_dan"], reverse("nhan_dien_su_dung_phong"))

    def test_khong_co_viec_khan_chi_hien_xem_phong(self):
        _, item = self._context()

        self.assertEqual(item["ma"], "on_dinh")
        self.assertEqual(item["nhan_nut"], "Xem phòng")

    def test_checklist_khong_dung_du_lieu_tenant_khac(self):
        booking = self._booking_cho_coc(tenant=self.other)
        ThanhToanCocDatPhong.objects.create(
            dat_phong=booking,
            so_tien=booking.tien_coc_du_kien,
        )

        response, item = self._context()

        self.assertEqual(item["ma"], "on_dinh")
        self.assertNotContains(response, booking.ma_yeu_cau)

    def test_da_tra_phong_khong_duoc_dan_sang_face_id(self):
        self.contract()
        self.tenant.trang_thai_luu_tru = "da_tra_phong"
        self.tenant.save(update_fields=["trang_thai_luu_tru"])

        response, item = self._context()

        self.assertEqual(item["ma"], "on_dinh")
        self.assertIsNone(response.context["hop_dong_hien_tai"])
        self.assertNotContains(response, reverse("nhan_dien_su_dung_phong"))
