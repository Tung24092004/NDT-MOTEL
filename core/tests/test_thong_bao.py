from unittest.mock import patch

from django.urls import reverse

from core.models import LichSuThongBao, ThongBao
from core.du_lieu_test.du_lieu_test_dat_phong import Phase5BookingFixture
from core.private_storage import private_payment_evidence_storage
from core.tests.test_thanh_toan import evidence_upload


class Phase6NotificationsToastsTests(Phase5BookingFixture):
    def test_invoice_payment_event_reaches_admin_inbox_and_read_action(self):
        from core.models import HoaDon

        invoice = HoaDon.objects.create(
            hop_dong=self.contract(), thang=9, nam=2026,
            tien_phong=2500000, han_thanh_toan=self.today,
        )
        report_url = reverse("thanh_toan_hoa_don_cua_toi", args=[invoice.pk])
        payload = {
            "buoc": "xac_thuc",
            "phuong_thuc": "chuyen_khoan",
            "xac_nhan": "dong_y",
            "anh_chung_tu": evidence_upload(),
        }
        self.client.force_login(self.user)
        with patch.object(
            private_payment_evidence_storage,
            "save",
            side_effect=lambda name, content, max_length=None: name,
        ):
            self.assertEqual(self.client.post(report_url, payload).status_code, 302)
        notice = ThongBao.objects.get(
            nguoi_nhan_user=self.admin,
            ma_tham_chieu=f"INVOICE:{invoice.pk}:PAYMENT_REPORTED:{self.admin.pk}",
        )
        self.client.post(report_url, payload)
        self.assertEqual(ThongBao.objects.filter(nguoi_nhan_user=self.admin).count(), 1)
        self.client.force_login(self.admin)
        inbox = self.client.get(reverse("thong_bao_admin"))
        self.assertContains(inbox, notice.tieu_de)
        detail_url = reverse("chi_tiet_thong_bao_admin", args=[notice.pk])
        self.assertContains(inbox, f'href="{detail_url}"')
        self.assertEqual(inbox.context["so_thong_bao_admin_chua_doc"], 1)
        self.assertEqual(self.client.get(reverse("kiem_tra_thong_bao_admin_moi")).json()["so_chua_doc"], 1)
        object_url = reverse("chi_tiet_hoa_don", args=[invoice.pk])
        detail = self.client.get(detail_url)
        self.assertContains(detail, f'href="{object_url}"')
        notice.refresh_from_db()
        self.assertFalse(notice.da_doc)
        result = self.client.post(reverse("doc_thong_bao_admin", args=[notice.pk]))
        self.assertRedirects(result, object_url)
        notice.refresh_from_db()
        self.assertTrue(notice.da_doc)
        self.assertIsNotNone(notice.ngay_doc)
        self.assertEqual(self.client.get(reverse("thong_bao_admin")).context["so_thong_bao_admin_chua_doc"], 0)
        self.assertEqual(self.client.get(reverse("kiem_tra_thong_bao_admin_moi")).json()["so_chua_doc"], 0)

    def test_user_inbox_only_contains_current_tenant_notifications(self):
        ThongBao.objects.create(nguoi_thue=self.tenant, tieu_de="My tenant notice", noi_dung="Body", loai="dat_phong")
        ThongBao.objects.create(nguoi_thue=self.other, tieu_de="Foreign tenant notice", noi_dung="Body", loai="dat_phong")
        self.client.force_login(self.user)
        response = self.client.get(reverse("thong_bao_cua_toi"))
        self.assertTemplateUsed(response, "core/tenant_base.html")
        self.assertContains(response, "My tenant notice")
        self.assertNotContains(response, "Foreign tenant notice")
        self.assertNotContains(response, 'href="/thong-bao-admin/"')
        self.assertNotContains(response, 'href="/dashboard-admin/"')
        self.assertEqual(self.client.get(reverse("kiem_tra_thong_bao_cua_toi_moi")).json()["so_chua_doc"], 1)

    def test_admin_inbox_badge_and_poll_use_same_recipient(self):
        own = ThongBao.objects.create(nguoi_nhan_user=self.admin, tieu_de="Own inbox", noi_dung="Body", loai="dat_phong")
        other = self.admin.__class__.objects.create_user("inbox-other-admin", is_staff=True)
        ThongBao.objects.create(nguoi_nhan_user=other, tieu_de="Foreign inbox", noi_dung="Body", loai="dat_phong")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("thong_bao_admin"))
        self.assertTemplateUsed(response, "core/base.html")
        self.assertContains(response, "notification-inbox")
        self.assertContains(response, "css/ui-system.css")
        self.assertContains(response, "Own inbox")
        self.assertNotContains(response, "Foreign inbox")
        self.assertEqual(response.context["so_thong_bao_admin_chua_doc"], 1)
        self.assertEqual(list(response.context["thong_bao"]), [own])
        self.assertEqual(self.client.get(reverse("kiem_tra_thong_bao_admin_moi")).json()["so_chua_doc"], 1)
        self.client.post(reverse("doc_tat_ca_thong_bao_admin"))
        response = self.client.get(reverse("thong_bao_admin"))
        self.assertContains(response, 'data-notification-badge hidden')
        self.assertEqual(self.client.get(reverse("kiem_tra_thong_bao_admin_moi")).json()["so_chua_doc"], 0)

    def test_empty_admin_inbox_has_styled_empty_state_and_zero_badge(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("thong_bao_admin"))
        self.assertContains(response, 'class="ndt-f5-empty" role="status"')
        self.assertContains(response, 'data-notification-badge hidden')
        self.assertContains(response, reverse("kiem_tra_thong_bao_admin_moi"))

    def test_admin_bell_points_to_inbox_and_has_single_toast_container(self):
        ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Admin unread",
            noi_dung="Badge source",
            loai="dat_phong",
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("dashboard_admin"))

        self.assertContains(response, 'id="ndtToastRegion"', count=1)
        self.assertContains(response, reverse("thong_bao_admin"))
        self.assertContains(response, "data-notification-badge")

    def test_admin_read_actions_are_post_and_scoped(self):
        own = ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Own",
            noi_dung="Own body",
            loai="dat_phong",
        )
        other_admin = self.admin.__class__.objects.create_user("phase6-other-admin", is_staff=True)
        foreign = ThongBao.objects.create(
            nguoi_nhan_user=other_admin,
            tieu_de="Foreign",
            noi_dung="Foreign body",
            loai="dat_phong",
        )
        self.client.force_login(self.admin)

        get_response = self.client.get(reverse("doc_thong_bao_admin", args=[own.pk]))
        self.assertEqual(get_response.status_code, 405)
        own.refresh_from_db()
        self.assertFalse(own.da_doc)

        post_response = self.client.post(reverse("doc_thong_bao_admin", args=[own.pk]))
        self.assertEqual(post_response.status_code, 302)
        own.refresh_from_db()
        self.assertTrue(own.da_doc)
        self.assertTrue(LichSuThongBao.objects.filter(thong_bao=own, hanh_dong="doc").exists())

        foreign_response = self.client.post(reverse("doc_thong_bao_admin", args=[foreign.pk]))
        self.assertEqual(foreign_response.status_code, 404)
        foreign.refresh_from_db()
        self.assertFalse(foreign.da_doc)

    def test_admin_mark_all_only_updates_current_admin(self):
        own = ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Own",
            noi_dung="Own body",
            loai="dat_phong",
        )
        other_admin = self.admin.__class__.objects.create_user("phase6-mark-all-admin", is_staff=True)
        foreign = ThongBao.objects.create(
            nguoi_nhan_user=other_admin,
            tieu_de="Foreign",
            noi_dung="Foreign body",
            loai="dat_phong",
        )
        self.client.force_login(self.admin)

        self.client.post(reverse("doc_tat_ca_thong_bao_admin"))
        own.refresh_from_db()
        foreign.refresh_from_db()

        self.assertTrue(own.da_doc)
        self.assertFalse(foreign.da_doc)

    def test_polling_does_not_mark_as_read(self):
        notice = ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Poll notice",
            noi_dung="Poll body",
            loai="dat_phong",
        )
        self.client.force_login(self.admin)

        response = self.client.get(reverse("kiem_tra_thong_bao_admin_moi"))
        notice.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(notice.da_doc)
        self.assertContains(response, "Poll notice")

    def test_empty_polling_payload_is_safe(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("kiem_tra_thong_bao_admin_moi"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"so_chua_doc": 0, "items": []})

    def test_notification_forms_use_current_model_choice_values(self):
        self.client.force_login(self.admin)

        create_response = self.client.get(reverse("tao_thong_bao"))
        self.assertContains(create_response, 'value="bao_tri"')
        self.assertContains(create_response, 'value="quan_trong"')
        self.assertContains(create_response, 'value="khancap"')
        self.assertNotContains(create_response, 'value="sua_chua"')
        self.assertNotContains(create_response, 'value="canh_bao"')
        self.assertNotContains(create_response, 'value="khan"')

    def test_notification_screens_render_foundation_contract(self):
        tenant_notice = ThongBao.objects.create(
            nguoi_thue=self.tenant,
            tieu_de="Foundation tenant notice",
            noi_dung="Body",
            loai="bao_tri",
            muc_do="quan_trong",
        )
        admin_notice = ThongBao.objects.create(
            nguoi_nhan_user=self.admin,
            tieu_de="Foundation admin notice",
            noi_dung="Body",
            loai="he_thong",
        )

        self.client.force_login(self.admin)
        for url in (
            reverse("quan_ly_thong_bao"),
            reverse("tao_thong_bao"),
            reverse("chi_tiet_thong_bao", args=[tenant_notice.pk]),
            reverse("thong_bao_admin"),
            reverse("chi_tiet_thong_bao_admin", args=[admin_notice.pk]),
        ):
            response = self.client.get(url)
            self.assertContains(response, "ndt-notification-management")
            self.assertContains(response, "css/foundation/p5.css")
            self.assertContains(response, "css/notification_management_p6f.css")
            self.assertNotContains(response, "css/notification.css")

        self.client.force_login(self.user)
        for url in (
            reverse("thong_bao_cua_toi"),
            reverse("chi_tiet_thong_bao_cua_toi", args=[tenant_notice.pk]),
        ):
            response = self.client.get(url)
            self.assertContains(response, "ndt-notification-management")
            self.assertContains(response, "css/foundation/p5.css")
            self.assertContains(response, "css/notification_management_p6f.css")
            self.assertNotContains(response, "css/notification.css")
