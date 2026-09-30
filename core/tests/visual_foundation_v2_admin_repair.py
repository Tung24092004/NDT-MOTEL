"""Isolated visual audit for Foundation V2 Admin repair screens."""

import json
import os
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.models import CoSo, DatPhong, HopDong, LichSuSuaChua, NguoiThue, Phong, YeuCauSuaChua


class FoundationV2AdminRepairVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        today = timezone.localdate()
        now = timezone.now()
        self.admin = User.objects.create_user("repair-v2-admin", is_staff=True)
        self.superuser = User.objects.create_user("repair-v2-super", is_superuser=True)
        self.tenant_user = User.objects.create_user("repair-v2-tenant")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="Nguyễn Minh An",
            cccd="000000009201",
            so_dien_thoai="0900009201",
            email="repair.v2@example.com",
        )
        facility = CoSo.objects.create(
            ten_co_so="NDT Motel Nguyễn Văn Linh",
            dia_chi="125 Nguyễn Văn Linh",
            quan="Hải Châu",
        )
        self.room = Phong.objects.create(
            co_so=facility,
            so_phong="A-302",
            gia_thue=Decimal("3800000"),
            dien_tich=Decimal("28"),
            so_nguoi_toi_da=3,
            tien_coc_mac_dinh=Decimal("1000000"),
        )
        booking = DatPhong.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            ngay_nhan_phong=today - timedelta(days=90),
            ngay_tra_du_kien=today + timedelta(days=90),
            so_thang_thue=6,
            trang_thai="da_duyet",
        )
        HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong="REPAIR-V2-302",
            ngay_bat_dau=today - timedelta(days=90),
            ngay_ket_thuc=today + timedelta(days=90),
            tien_thue_thang=Decimal("3800000"),
            tien_coc=Decimal("1000000"),
            trang_thai="dang_hieu_luc",
            so_nguoi_o=1,
            cho_phep_ghep=True,
        )

        issue_image = SimpleUploadedFile(
            "mat-nuoc.svg",
            (
                '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450">'
                '<rect width="800" height="450" fill="#e9f0f2"/><rect x="100" y="85" width="600" height="280" rx="8" fill="#ffffff" stroke="#84969d" stroke-width="8"/>'
                '<path d="M210 120v150h380V120M400 270v70" fill="none" stroke="#197a89" stroke-width="20"/>'
                '<circle cx="400" cy="355" r="24" fill="#d94941"/><text x="400" y="55" text-anchor="middle" font-family="Arial" font-size="30" fill="#24353b">Ảnh kiểm tra sự cố đường ống</text></svg>'
            ).encode("utf-8"),
            content_type="image/svg+xml",
        )

        self.repairs = {}
        repair_data = [
            ("moi", "Rò rỉ nước dưới bồn rửa", "nuoc", "khan_cap", "", 0),
            ("dang_xu_ly", "Điều hòa phòng ngủ không lạnh", "thiet_bi", "cao", "Tổ kỹ thuật ca sáng", 180000),
            ("cho_thay_the", "Khóa cửa phòng bị kẹt", "phong", "trung_binh", "Anh Phúc", 420000),
            ("hoan_thanh", "Ổ cắm gần bàn học mất điện", "dien", "cao", "Chị Lan", 95000),
            ("tu_choi", "Đề nghị thay rèm theo sở thích", "khac", "thap", "", 0),
        ]
        for index, (state, title, issue_type, severity, handler, cost) in enumerate(repair_data):
            repair = YeuCauSuaChua.objects.create(
                nguoi_thue=self.tenant,
                phong=self.room,
                tieu_de=title,
                noi_dung=(
                    "Sự cố xuất hiện từ tối qua, ảnh hưởng trực tiếp đến sinh hoạt. "
                    "Người thuê đã kiểm tra bước cơ bản nhưng tình trạng chưa cải thiện."
                ),
                loai_su_co=issue_type,
                muc_do=severity,
                hinh_anh=issue_image if state == "moi" else None,
                trang_thai=state,
                nguoi_xu_ly=handler,
                chi_phi=Decimal(str(cost)),
                chi_tiet_chi_phi="Vật tư và công kiểm tra tại phòng." if cost else "",
                ghi_chu_admin=(
                    "Ưu tiên liên hệ người thuê trước khi vào phòng."
                    if state not in ("hoan_thanh", "tu_choi")
                    else "Đã ghi nhận kết quả xử lý."
                ),
                ngay_bat_dau_xu_ly=(now - timedelta(hours=8)) if state in ("dang_xu_ly", "cho_thay_the", "hoan_thanh") else None,
                ngay_hoan_thanh=(now - timedelta(hours=1)) if state == "hoan_thanh" else None,
            )
            YeuCauSuaChua.objects.filter(pk=repair.pk).update(
                ngay_tao=now - timedelta(days=index + 1),
                ngay_cap_nhat=now - timedelta(hours=index + 1),
            )
            repair.refresh_from_db()
            LichSuSuaChua.objects.create(
                yeu_cau=repair,
                hanh_dong="tao",
                trang_thai_cu="",
                trang_thai_moi="moi",
                noi_dung="Người thuê đã gửi yêu cầu sửa chữa.",
                nguoi_thuc_hien=self.tenant_user,
            )
            if state != "moi":
                LichSuSuaChua.objects.create(
                    yeu_cau=repair,
                    hanh_dong="cap_nhat",
                    trang_thai_cu="moi",
                    trang_thai_moi=state,
                    noi_dung=f"Quản lý cập nhật trạng thái thành {repair.get_trang_thai_display()}.",
                    nguoi_thuc_hien=self.admin,
                )
            self.repairs[state] = repair

    def _session_cookie(self, user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_capture_admin_repair_foundation_v2(self):
        phase = os.environ.get("NDT_VISUAL_PHASE", "before")
        output = Path(settings.BASE_DIR, "luu_tru", "kiem_thu", "foundation_v2_admin_repair", phase)
        output.mkdir(parents=True, exist_ok=True)
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        viewports = {
            "1440x900": (1440, 900),
            "1024x768": (1024, 768),
            "768x900": (768, 900),
            "390x844": (390, 844),
        }
        screens = [
            ("list_many", reverse("quan_ly_sua_chua")),
            ("list_empty", reverse("quan_ly_sua_chua") + "?q=khong-co-ket-qua"),
            ("create", reverse("tao_sua_chua")),
            ("detail_new", reverse("chi_tiet_sua_chua", args=[self.repairs["moi"].pk])),
            ("detail_processing", reverse("chi_tiet_sua_chua", args=[self.repairs["dang_xu_ly"].pk])),
            ("detail_waiting", reverse("chi_tiet_sua_chua", args=[self.repairs["cho_thay_the"].pk])),
            ("detail_completed", reverse("chi_tiet_sua_chua", args=[self.repairs["hoan_thanh"].pk])),
            ("detail_rejected", reverse("chi_tiet_sua_chua", args=[self.repairs["tu_choi"].pk])),
        ]
        results = []
        cookie = self._session_cookie(self.admin)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for viewport_name, (width, height) in viewports.items():
                for screen, path in screens:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.add_cookies([{
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": cookie,
                        "url": self.live_server_url,
                    }])
                    page = context.new_page()
                    errors = []
                    page.on("console", lambda message: errors.append(f"console:{message.type}:{message.text}") if message.type == "error" else None)
                    page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                    response = page.goto(self.live_server_url + path, wait_until="networkidle")
                    page.keyboard.press("Tab")
                    metrics = page.evaluate(
                        """() => ({
                            cw: document.documentElement.clientWidth,
                            sw: document.documentElement.scrollWidth,
                            broken: [...document.images].filter(i => i.complete && i.naturalWidth === 0).length,
                            unlabeled: [...document.querySelectorAll('input, select, textarea')].filter(el => {
                                const label = el.id && document.querySelector(`label[for="${el.id}"]`);
                                return !label && !el.getAttribute('aria-label') && el.type !== 'hidden';
                            }).length,
                            focused: document.activeElement ? document.activeElement.tagName : null,
                        })"""
                    )
                    screenshot = output / f"{screen}_{viewport_name}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    results.append({
                        "screen": screen,
                        "viewport": viewport_name,
                        "status": response.status if response else None,
                        "overflow": metrics["sw"] > metrics["cw"],
                        "broken_images": metrics["broken"],
                        "unlabeled_controls": metrics["unlabeled"],
                        "focused_after_tab": metrics["focused"],
                        "errors": errors,
                        "screenshot": screenshot.name,
                    })
                    context.close()
            browser.close()

        role_client = Client()
        role_checks = {}
        protected_paths = [
            reverse("quan_ly_sua_chua"),
            reverse("tao_sua_chua"),
            reverse("chi_tiet_sua_chua", args=[self.repairs["moi"].pk]),
        ]
        for role, user in (("guest", None), ("tenant", self.tenant_user), ("staff", self.admin), ("superuser", self.superuser)):
            role_client.logout()
            if user:
                role_client.force_login(user)
            role_checks[role] = [
                {"status": response.status_code, "location": response.get("Location", "")}
                for response in (role_client.get(path) for path in protected_paths)
            ]

        report = {"phase": phase, "screens": results, "roles": role_checks}
        (output / "results.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        for result in results:
            self.assertEqual(result["status"], 200)
            self.assertFalse(result["overflow"])
            self.assertEqual(result["broken_images"], 0)
            self.assertEqual(result["unlabeled_controls"], 0)
            self.assertEqual(result["errors"], [])

