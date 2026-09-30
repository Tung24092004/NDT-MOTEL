"""Regression tests for deterministic multi-gallery room images."""

from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch

from django.conf import settings
from django.db import connection
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

from core.dich_vu.gallery_phong import (
    _gallery_tren_dia,
    chuan_bi_gallery_hien_thi,
    ma_gallery_hien_thi,
)
from core.dich_vu.room_gallery_mapping import ma_gallery_cua_phong
from core.models import CoSo, HinhAnhPhong, Phong


@override_settings(MEDIA_ROOT=Path(settings.BASE_DIR) / "media")
class GalleryPhongTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("These tests require the isolated test_ndt_motel database.")
        cls.co_so = CoSo.objects.create(
            ten_co_so="Gallery Test",
            dia_chi="Test",
            quan="Test",
        )

    def tearDown(self):
        _gallery_tren_dia.cache_clear()

    def tao_phong(self, so_phong, loai_phong="phong_tieu_chuan"):
        return Phong.objects.create(
            co_so=self.co_so,
            so_phong=so_phong,
            loai_phong=loai_phong,
            gia_thue=Decimal("2500000"),
            dien_tich=Decimal("25"),
            so_nguoi_toi_da=2,
        )

    def tao_anh(self, phong, ten, thu_tu=0, dai_dien=False, legacy=False):
        prefix = "phong_mau/legacy" if legacy else "phong/test"
        return HinhAnhPhong.objects.create(
            phong=phong,
            anh=f"{prefix}/{ten}.jpg",
            thu_tu=thu_tu,
            la_anh_dai_dien=dai_dien,
        )

    def test_01_phong_co_anh_rieng_dung_toan_bo_gallery_rieng(self):
        phong = self.tao_phong("R-01")
        anh_2 = self.tao_anh(phong, "rieng-2", thu_tu=2)
        anh_1 = self.tao_anh(phong, "rieng-1", thu_tu=1, dai_dien=True)

        self.assertEqual(phong.gallery_hien_thi, [anh_1, anh_2])
        self.assertEqual(phong.anh_dai_dien_hien_thi, anh_1)
        self.assertIsNone(ma_gallery_hien_thi(phong))

    def test_02_phong_khong_anh_dung_style_mapping(self):
        phong = self.tao_phong("P102")

        self.assertEqual(ma_gallery_hien_thi(phong), ma_gallery_cua_phong(phong))
        self.assertEqual(len(phong.gallery_hien_thi), 5)

    def test_03_cung_phong_luon_cung_style_sau_khi_tai_lai(self):
        phong = self.tao_phong("P103")
        expected = ma_gallery_cua_phong(phong)

        phong = Phong.objects.get(pk=phong.pk)
        self.assertEqual(ma_gallery_cua_phong(phong), expected)

    def test_04_hai_phong_lien_tiep_nhan_style_khac_nhau(self):
        phong_1 = self.tao_phong("P104")
        phong_2 = self.tao_phong("P105")

        self.assertNotEqual(ma_gallery_cua_phong(phong_1), ma_gallery_cua_phong(phong_2))

    def test_05_gallery_chi_tiet_chi_chua_mot_style(self):
        phong = self.tao_phong("P106")
        codes = {anh.gallery_code for anh in phong.gallery_hien_thi}

        self.assertEqual(codes, {ma_gallery_cua_phong(phong)})
        self.assertEqual(len({anh.anh.name for anh in phong.gallery_hien_thi}), 5)

    def test_06_anh_dai_dien_thuoc_gallery_do(self):
        phong = self.tao_phong("P107")

        self.assertIn(phong.anh_dai_dien_hien_thi, phong.gallery_hien_thi)
        self.assertEqual(phong.anh_dai_dien_hien_thi.gallery_code, ma_gallery_cua_phong(phong))

    def test_07_cac_surface_dung_cung_anh_dai_dien(self):
        phong = self.tao_phong("P108")
        image_url = phong.anh_dai_dien_hien_thi.anh.url

        home = self.client.get(reverse("home"))
        room_list = self.client.get(reverse("danh_sach_phong"))
        detail = self.client.get(reverse("chi_tiet_phong", args=[phong.pk]))
        booking = render_to_string(
            "core/tenant/booking/components/room_summary.html",
            {"phong": phong},
        )
        self.assertContains(home, image_url)
        self.assertContains(room_list, image_url)
        self.assertContains(detail, image_url)
        self.assertIn(image_url, booking)

    def test_08_thieu_style_fallback_ve_gallery_mac_dinh_cua_loai(self):
        phong = self.tao_phong("P109")
        default_image = Mock(la_anh_dai_dien=True, gallery_code="TC01")

        with patch(
            "core.dich_vu.gallery_phong._gallery_tren_dia",
            side_effect=[(), (default_image,)],
        ) as mocked:
            chuan_bi_gallery_hien_thi([phong])

        self.assertEqual(phong.gallery_hien_thi, [default_image])
        self.assertEqual(mocked.call_count, 2)

    def test_09_thieu_toan_bo_gallery_template_dung_placeholder(self):
        phong = self.tao_phong("P110", "can_ho_mini")
        with patch("core.dich_vu.gallery_phong._gallery_tren_dia", return_value=()):
            self.assertEqual(phong.gallery_hien_thi, [])
            response = self.client.get(reverse("chi_tiet_phong", args=[phong.pk]))

        self.assertContains(response, "images/room-placeholder.svg")

    def test_10_chuan_bi_danh_sach_khong_query_fallback(self):
        for index in range(111, 121):
            self.tao_phong(f"P{index}")
        ds_phong = list(Phong.objects.prefetch_related("hinh_anh").order_by("id"))

        with self.assertNumQueries(0):
            chuan_bi_gallery_hien_thi(ds_phong)

        self.assertTrue(all(phong.anh_dai_dien_hien_thi for phong in ds_phong))

    def test_11_anh_mau_legacy_khong_override_mapping(self):
        phong = self.tao_phong("P121")
        self.tao_anh(phong, "cu", legacy=True)

        self.assertEqual(ma_gallery_hien_thi(phong), ma_gallery_cua_phong(phong))

    def test_12_trang_admin_giu_nguyen_phan_quyen(self):
        phong = self.tao_phong("P122")

        response = self.client.get(reverse("sua_phong", args=[phong.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("dang_nhap"), response.url)

    def test_13_anh_rieng_dong_bo_list_detail_booking(self):
        phong = self.tao_phong("P123")
        anh_rieng = self.tao_anh(phong, "private-cover", dai_dien=True)
        image_url = anh_rieng.anh.url

        room_list = self.client.get(reverse("danh_sach_phong"))
        detail = self.client.get(reverse("chi_tiet_phong", args=[phong.pk]))
        booking = render_to_string(
            "core/tenant/booking/components/room_summary.html",
            {"phong": phong},
        )

        self.assertContains(room_list, image_url)
        self.assertContains(detail, image_url)
        self.assertIn(image_url, booking)
