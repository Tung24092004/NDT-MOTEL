import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve, reverse

from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture
from core.models import HoaDon
from core.views_hoa_don import bao_cao_cong_no


class AdminReceivablesAgingSourceContractTests(SimpleTestCase):
    def source(self, relative_path):
        return (Path(settings.BASE_DIR) / relative_path).read_text(encoding="utf-8")

    def test_route_and_admin_invoice_entry_point_are_present(self):
        url = reverse("bao_cao_cong_no")
        self.assertEqual(url, "/quan-ly-hoa-don/bao-cao-cong-no/")
        self.assertIs(resolve(url).func, bao_cao_cong_no)
        invoice_list = self.source("templates/core/quan_ly_hoa_don.html")
        self.assertIn("{% url 'bao_cao_cong_no' %}", invoice_list)

    def test_template_is_scoped_read_only_and_uses_dedicated_asset(self):
        source = self.source("templates/core/bao_cao_cong_no.html")
        self.assertIn("css/foundation/p5.css", source)
        self.assertIn("css/invoice_management_p6d.css", source)
        self.assertIn("css/receivables_report_post_p6.css", source)
        self.assertIn("ndt-f5 ndt-invoice-management ndt-receivables-report", source)
        self.assertIn('method="get"', source)
        self.assertNotIn('method="post"', source.lower())
        self.assertNotIn("{% csrf_token %}", source)

    def test_dedicated_css_is_namespaced(self):
        source = self.source("static/css/receivables_report_post_p6.css")
        self.assertIn(".ndt-f5.ndt-receivables-report", source)
        self.assertNotIn("!important", source)
        self.assertNotIn("url(", source)


class AdminReceivablesAgingRequestTests(BusinessFixture):
    def setUp(self):
        self.contract_obj = self.contract()
        self.amounts = {
            "current": Decimal("1000000"),
            "day_1": Decimal("2000000"),
            "day_7": Decimal("3000000"),
            "day_8": Decimal("4000000"),
            "day_30": Decimal("5000000"),
            "day_31": Decimal("6000000"),
        }
        definitions = (
            (1, "current", 2, "chua_thanh_toan"),
            (2, "day_1", -1, "chua_thanh_toan"),
            (3, "day_7", -7, "cho_xac_nhan"),
            (4, "day_8", -8, "qua_han"),
            (5, "day_30", -30, "qua_han"),
            (6, "day_31", -31, "qua_han"),
        )
        self.invoices = {}
        for month, key, delta, status in definitions:
            self.invoices[key] = HoaDon.objects.create(
                hop_dong=self.contract_obj,
                thang=month,
                nam=2026,
                tien_phong=self.amounts[key],
                han_thanh_toan=self.today + timedelta(days=delta),
                trang_thai=status,
            )
        self.paid = HoaDon.objects.create(
            hop_dong=self.contract_obj,
            thang=7,
            nam=2026,
            tien_phong=Decimal("7000000"),
            han_thanh_toan=self.today - timedelta(days=60),
            trang_thai="da_thanh_toan",
        )
        self.cancelled = HoaDon.objects.create(
            hop_dong=self.contract_obj,
            thang=8,
            nam=2026,
            tien_phong=Decimal("8000000"),
            han_thanh_toan=self.today - timedelta(days=60),
            trang_thai="huy",
        )

    def get_as_admin(self, params=None):
        self.client.force_login(self.admin)
        return self.client.get(reverse("bao_cao_cong_no"), params or {})

    def test_access_is_admin_only_and_endpoint_is_get_only(self):
        url = reverse("bao_cao_cong_no")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 405)

    def test_summary_uses_only_unsettled_invoices_and_exact_amounts(self):
        response = self.get_as_admin()
        self.assertEqual(response.context["thong_ke"]["tong_so"], 6)
        self.assertEqual(
            response.context["thong_ke"]["tong_tien"],
            sum(self.amounts.values()),
        )
        ids = {invoice.pk for invoice in response.context["hoa_don"]}
        self.assertNotIn(self.paid.pk, ids)
        self.assertNotIn(self.cancelled.pk, ids)

    def test_aging_boundaries_are_disjoint_and_inclusive(self):
        expected = {
            "chua_den_han": {self.invoices["current"].pk},
            "qua_han_1_7": {
                self.invoices["day_1"].pk,
                self.invoices["day_7"].pk,
            },
            "qua_han_8_30": {
                self.invoices["day_8"].pk,
                self.invoices["day_30"].pk,
            },
            "qua_han_31_plus": {self.invoices["day_31"].pk},
        }
        for group, invoice_ids in expected.items():
            with self.subTest(group=group):
                response = self.get_as_admin({"nhom_tuoi": group})
                actual = {invoice.pk for invoice in response.context["hoa_don"]}
                self.assertEqual(actual, invoice_ids)
                self.assertEqual(
                    response.context["thong_ke"][group]["so_luong"],
                    len(invoice_ids),
                )

    def test_keyword_status_facility_and_due_date_filters_compose(self):
        target = self.invoices["day_8"]
        response = self.get_as_admin({
            "q": self.tenant.ho_ten,
            "co_so": str(self.facility.pk),
            "trang_thai": "qua_han",
            "tu_han": target.han_thanh_toan.isoformat(),
            "den_han": target.han_thanh_toan.isoformat(),
        })
        self.assertEqual(list(response.context["hoa_don"]), [target])

    def test_invalid_filters_are_ignored_without_expanding_scope(self):
        response = self.get_as_admin({
            "co_so": "not-an-id",
            "trang_thai": "da_thanh_toan",
            "nhom_tuoi": "unknown",
            "tu_han": "invalid",
            "den_han": "invalid",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].paginator.count, 6)
        self.assertEqual(response.context["co_so"], "")
        self.assertEqual(response.context["trang_thai"], "")
        self.assertEqual(response.context["nhom_tuoi"], "")

    def test_pagination_is_twenty_rows(self):
        for month in range(9, 29):
            HoaDon.objects.create(
                hop_dong=self.contract_obj,
                thang=month,
                nam=2027,
                tien_phong=Decimal("1000"),
                han_thanh_toan=self.today,
            )
        response = self.get_as_admin()
        self.assertEqual(len(response.context["hoa_don"]), 20)
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 2)

    def test_csv_matches_filters_has_bom_and_neutralizes_formulas(self):
        self.tenant.ho_ten = "=SUM(1,1)"
        self.tenant.save(update_fields=["ho_ten"])
        response = self.get_as_admin({"nhom_tuoi": "qua_han_31_plus", "xuat": "csv"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment;", response["Content-Disposition"])
        body = response.content.decode("utf-8")
        self.assertTrue(body.startswith("\ufeff"))
        rows = list(csv.reader(StringIO(body.lstrip("\ufeff"))))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], f"HD-{self.invoices['day_31'].pk}")
        self.assertEqual(rows[1][4], "'=SUM(1,1)")

    def test_get_does_not_mutate_invoice_state(self):
        before = list(HoaDon.objects.order_by("pk").values_list(
            "pk", "trang_thai", "ngay_thanh_toan", "ngay_cap_nhat"
        ))
        response = self.get_as_admin({"nhom_tuoi": "qua_han_31_plus"})
        self.assertEqual(response.status_code, 200)
        after = list(HoaDon.objects.order_by("pk").values_list(
            "pk", "trang_thai", "ngay_thanh_toan", "ngay_cap_nhat"
        ))
        self.assertEqual(after, before)
