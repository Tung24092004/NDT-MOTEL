"""Explicit isolated browser and camera-contract audit for Module 09."""

import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import sync_playwright

from core.models import (
    CoSo,
    DatPhong,
    FaceProfile,
    HopDong,
    LichSuRaVao,
    NguoiThue,
    Phong,
    QuyenRaVao,
)


class Module09SmartRoomVisualAudit(StaticLiveServerTestCase):
    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.settings_dict["NAME"] != "test_ndt_motel":
            raise RuntimeError("Visual audit requires isolated test_ndt_motel.")

    def setUp(self):
        today = timezone.localdate()
        self.admin = User.objects.create_user("module09-admin", is_staff=True)
        self.tenant_user = User.objects.create_user("module09-tenant")
        self.ineligible_user = User.objects.create_user("module09-ineligible")
        self.tenant = NguoiThue.objects.create(
            tai_khoan=self.tenant_user,
            ho_ten="Nguyen Minh Smart Room",
            cccd="000000000901",
            so_dien_thoai="0900000901",
        )
        NguoiThue.objects.create(
            tai_khoan=self.ineligible_user,
            ho_ten="Tran An Chua Du Dieu Kien",
            cccd="000000000902",
            so_dien_thoai="0900000902",
        )
        facility = CoSo.objects.create(
            ten_co_so="NDT Smart Room QA",
            dia_chi="Du lieu kiem thu co lap",
            quan="Quan QA",
        )
        self.room = Phong.objects.create(
            co_so=facility,
            so_phong="M09-01",
            gia_thue=Decimal("2500000"),
            dien_tich=Decimal("24"),
            so_nguoi_toi_da=3,
        )
        booking = DatPhong.objects.create(
            nguoi_thue=self.tenant,
            phong=self.room,
            ngay_nhan_phong=today,
            ngay_tra_du_kien=today + timedelta(days=90),
            so_thang_thue=3,
            trang_thai="da_duyet",
        )
        self.contract = HopDong.objects.create(
            dat_phong=booking,
            so_hop_dong="M09-ACTIVE",
            ngay_bat_dau=today,
            ngay_ket_thuc=today + timedelta(days=90),
            tien_thue_thang=Decimal("2500000"),
            trang_thai="dang_hieu_luc",
        )
        self.face = FaceProfile.objects.create(
            nguoi_thue=self.tenant,
            loai_chu_the="nguoi_thue",
            trang_thai="da_xac_thuc",
        )
        self.permission = QuyenRaVao.objects.create(
            phong=self.room,
            nguoi_thue=self.tenant,
            loai_quyen="chu_phong",
            trang_thai="hoat_dong",
            ngay_bat_dau=today,
            ngay_ket_thuc=today + timedelta(days=90),
            hop_dong=self.contract,
            nguon_cap="thu_cong",
            nguoi_tao=self.admin,
        )
        self.access_log = LichSuRaVao.objects.create(
            quyen_ra_vao=self.permission,
            phong=self.room,
            nguoi_thue=self.tenant,
            ten_nguoi=self.tenant.ho_ten,
            loai_su_kien="vao",
            nguon="camera",
            thoi_diem=timezone.now(),
        )

    def _cookie(self, user):
        client = Client()
        client.force_login(user)
        return client.cookies[settings.SESSION_COOKIE_NAME].value

    def _install_camera_mock(self, page, *, timeout_ms=None):
        page.add_init_script(
            f"window.__module09TimeoutMs = {json.dumps(timeout_ms)};"
        )
        page.add_init_script(
            """
            (() => {
                const timeoutMs = window.__module09TimeoutMs;
                window.__cameraStops = 0;
                window.__authRequests = [];
                const listeners = {};
                const track = {
                    readyState: "live",
                    stop() { this.readyState = "ended"; window.__cameraStops += 1; },
                    addEventListener(name, callback) { listeners[name] = callback; }
                };
                const stream = {
                    getVideoTracks: () => [track],
                    getTracks: () => [track]
                };
                Object.defineProperty(navigator, "mediaDevices", {
                    configurable: true,
                    value: { getUserMedia: async () => stream }
                });
                Object.defineProperty(HTMLMediaElement.prototype, "srcObject", {
                    configurable: true,
                    get() { return this.__srcObject || null; },
                    set(value) { this.__srcObject = value; }
                });
                Object.defineProperty(HTMLMediaElement.prototype, "readyState", {
                    configurable: true,
                    get() { return this.srcObject ? 4 : 0; }
                });
                Object.defineProperty(HTMLVideoElement.prototype, "videoWidth", {
                    configurable: true,
                    get() { return this.srcObject ? 640 : 0; }
                });
                Object.defineProperty(HTMLVideoElement.prototype, "videoHeight", {
                    configurable: true,
                    get() { return this.srcObject ? 480 : 0; }
                });
                HTMLMediaElement.prototype.play = async function () {
                    this.dispatchEvent(new Event("loadeddata"));
                    this.dispatchEvent(new Event("playing"));
                };
                HTMLCanvasElement.prototype.getContext = () => ({ drawImage() {} });
                HTMLCanvasElement.prototype.toDataURL = () => "data:image/jpeg;base64,module09mock";
                if (timeoutMs !== null) {
                    const nativeSetTimeout = window.setTimeout.bind(window);
                    window.setTimeout = (callback, delay, ...args) =>
                        nativeSetTimeout(callback, delay === 30000 ? timeoutMs : delay, ...args);
                }
            })();
            """
        )

    def test_capture_all_module_09_screens(self):
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru" / "kiem_thu" / "module_09" / "visual_qa"
        )
        output.mkdir(parents=True, exist_ok=True)
        viewports = {
            "1920": (1920, 1080),
            "1440": (1440, 900),
            "1024": (1024, 768),
            "768": (768, 900),
            "390": (390, 844),
        }
        screens = [
            ("smart_dashboard", "admin", reverse("smart_room_dashboard")),
            ("smart_access", "admin", reverse("smart_access_control")),
            ("face_terminal", "admin", reverse("trang_xac_thuc_face_id")),
            ("face_list", "admin", reverse("quan_ly_face_profile")),
            ("face_create", "admin", reverse("tao_face_profile")),
            ("face_detail", "admin", reverse("chi_tiet_face_profile", args=[self.face.pk])),
            ("permission_list", "admin", reverse("quan_ly_quyen_ra_vao")),
            ("permission_create", "admin", reverse("tao_quyen_ra_vao")),
            ("permission_detail", "admin", reverse("chi_tiet_quyen_ra_vao", args=[self.permission.pk])),
            ("history_list", "admin", reverse("quan_ly_lich_su_ra_vao")),
            ("history_create", "admin", reverse("tao_lich_su_ra_vao")),
            ("history_detail", "admin", reverse("chi_tiet_lich_su_ra_vao", args=[self.access_log.pk])),
            ("face_unavailable", "tenant", reverse("nhan_dien_su_dung_phong")),
        ]
        cookies = {
            "admin": self._cookie(self.admin),
            "tenant": self._cookie(self.ineligible_user),
        }
        results = []
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            for name, role, path in screens:
                for viewport_name, (width, height) in viewports.items():
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.add_cookies([{
                        "name": settings.SESSION_COOKIE_NAME,
                        "value": cookies[role],
                        "url": self.live_server_url,
                    }])
                    page = context.new_page()
                    errors = []
                    page.on(
                        "console",
                        lambda message: errors.append(f"console:{message.type}:{message.text}")
                        if message.type == "error" else None,
                    )
                    page.on("pageerror", lambda error: errors.append(f"page:{error}"))
                    response = page.goto(self.live_server_url + path, wait_until="networkidle")
                    metrics = page.evaluate(
                        """() => ({
                            cw: document.documentElement.clientWidth,
                            sw: document.documentElement.scrollWidth,
                            broken: [...document.images].filter(
                                image => image.complete && image.naturalWidth === 0
                            ).length,
                            textLength: document.body.innerText.trim().length,
                            stylesheet: [...document.styleSheets].some(
                                sheet => sheet.href && sheet.href.includes('/static/css/smart_room.css')
                            )
                        })"""
                    )
                    screenshot = output / f"{name}_{viewport_name}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    result = {
                        "screen": name,
                        "role": role,
                        "width": width,
                        "height": height,
                        "status": response.status if response else None,
                        "overflow": metrics["sw"] > metrics["cw"],
                        "broken_images": metrics["broken"],
                        "errors": errors,
                        "text_length": metrics["textLength"],
                        "smart_room_stylesheet": metrics["stylesheet"],
                        "screenshot": screenshot.name,
                    }
                    results.append(result)
                    context.close()
            browser.close()

        (output / "results.json").write_text(
            json.dumps({"cases": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.assertEqual(len(results), len(screens) * len(viewports))
        for result in results:
            with self.subTest(screen=result["screen"], width=result["width"]):
                self.assertEqual(result["status"], 200)
                self.assertFalse(result["overflow"])
                self.assertEqual(result["broken_images"], 0)
                self.assertEqual(result["errors"], [])
                self.assertGreater(result["text_length"], 40)
                self.assertTrue(result["smart_room_stylesheet"])

    def test_camera_contracts_with_mocked_media(self):
        output = (
            Path(__file__).resolve().parents[2]
            / "luu_tru" / "kiem_thu" / "module_09" / "camera_mock"
        )
        output.mkdir(parents=True, exist_ok=True)
        chrome = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        admin_cookie = self._cookie(self.admin)
        cases = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=chrome, headless=True)
            context = browser.new_context(viewport={"width": 1024, "height": 768})
            context.add_cookies([
                {
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": admin_cookie,
                    "url": self.live_server_url,
                },
                {"name": "csrftoken", "value": "module09-csrf", "url": self.live_server_url},
            ])
            page = context.new_page()
            self._install_camera_mock(page)
            page.goto(
                self.live_server_url + reverse("smart_access_control"),
                wait_until="networkidle",
            )
            initial = page.evaluate("document.getElementById('scanBtn').disabled")
            page.select_option("#phong", str(self.room.pk))
            room_only = page.evaluate("document.getElementById('scanBtn').disabled")
            page.evaluate(
                """() => {
                    window.fetch = (url, options) => {
                        window.__authRequests.push({
                            url,
                            method: options.method,
                            csrf: options.headers['X-CSRFToken'],
                            body: options.body.toString()
                        });
                        return new Promise(resolve => { window.__resolveAuth = resolve; });
                    };
                }"""
            )
            page.click("#startCameraBtn")
            page.wait_for_function("!document.getElementById('scanBtn').disabled")
            page.click("#scanBtn")
            page.evaluate("document.getElementById('scanBtn').click()")
            processing = page.evaluate(
                """() => ({
                    count: window.__authRequests.length,
                    scan: document.getElementById('scanBtn').disabled,
                    room: document.getElementById('phong').disabled,
                    event: document.getElementById('loaiSuKien').disabled,
                    request: window.__authRequests[0]
                })"""
            )
            page.evaluate(
                """() => window.__resolveAuth({
                    ok: true,
                    status: 200,
                    json: async () => ({
                        duoc_phep: true,
                        ten_nguoi: 'Nguoi kiem thu',
                        phong: 'M09-01',
                        loai_su_kien: 'vao'
                    })
                })"""
            )
            page.wait_for_function("!document.getElementById('phong').disabled")
            restored = page.evaluate(
                """() => ({
                    scan: document.getElementById('scanBtn').disabled,
                    room: document.getElementById('phong').disabled,
                    event: document.getElementById('loaiSuKien').disabled
                })"""
            )
            page.evaluate("window.dispatchEvent(new Event('beforeunload'))")
            cleanup = page.evaluate("window.__cameraStops")
            params = dict(
                pair.split("=", 1) for pair in processing["request"]["body"].split("&")
            )
            cases.append({
                "flow": "smart_access_control",
                "initial_disabled": initial,
                "room_only_disabled": room_only,
                "processing": processing,
                "restored": restored,
                "cleanup_stops": cleanup,
            })
            self.assertTrue(initial)
            self.assertTrue(room_only)
            self.assertEqual(processing["count"], 1)
            self.assertTrue(processing["scan"] and processing["room"] and processing["event"])
            self.assertEqual(processing["request"]["method"], "POST")
            self.assertTrue(processing["request"]["csrf"])
            self.assertEqual(params["phong"], str(self.room.pk))
            self.assertEqual(params["loai_su_kien"], "vao")
            self.assertTrue(params["image"].startswith("data%3Aimage%2Fjpeg"))
            self.assertFalse(restored["scan"] or restored["room"] or restored["event"])
            self.assertGreaterEqual(cleanup, 1)
            context.close()

            context = browser.new_context(viewport={"width": 1024, "height": 768})
            context.add_cookies([{
                "name": settings.SESSION_COOKIE_NAME,
                "value": admin_cookie,
                "url": self.live_server_url,
            }])
            page = context.new_page()
            self._install_camera_mock(page, timeout_ms=25)
            page.goto(
                self.live_server_url + reverse("trang_xac_thuc_face_id"),
                wait_until="networkidle",
            )
            page.select_option("#phong", str(self.room.pk))
            page.evaluate(
                """() => {
                    window.fetch = (url, options) => {
                        window.__authRequests.push({
                            url,
                            method: options.method,
                            csrf: options.headers['X-CSRFToken'],
                            fields: Object.fromEntries(options.body.entries())
                        });
                        return new Promise((resolve, reject) => {
                            options.signal.addEventListener('abort', () => reject(
                                new DOMException('Aborted', 'AbortError')
                            ));
                        });
                    };
                }"""
            )
            page.click("#btnStart")
            page.wait_for_function("!document.getElementById('btnAuth').disabled")
            page.click("#btnAuth")
            page.wait_for_function(
                "document.getElementById('terminalStatus').textContent.includes('30 giây')"
            )
            timeout_state = page.evaluate(
                """() => ({
                    count: window.__authRequests.length,
                    request: window.__authRequests[0],
                    roomDisabled: document.getElementById('phong').disabled,
                    authDisabled: document.getElementById('btnAuth').disabled,
                    status: document.getElementById('terminalStatus').textContent
                })"""
            )
            page.evaluate("window.dispatchEvent(new Event('beforeunload'))")
            timeout_cleanup = page.evaluate("window.__cameraStops")
            cases.append({
                "flow": "face_terminal_timeout",
                "state": timeout_state,
                "cleanup_stops": timeout_cleanup,
            })
            fields = timeout_state["request"]["fields"]
            self.assertEqual(timeout_state["count"], 1)
            self.assertEqual(timeout_state["request"]["method"], "POST")
            self.assertTrue(timeout_state["request"]["csrf"])
            self.assertEqual(fields["phong"], str(self.room.pk))
            self.assertEqual(fields["loai_su_kien"], "vao")
            self.assertTrue(fields["image"].startswith("data:image/jpeg"))
            self.assertFalse(timeout_state["roomDisabled"])
            self.assertFalse(timeout_state["authDisabled"])
            self.assertIn("30 giây", timeout_state["status"])
            self.assertGreaterEqual(timeout_cleanup, 1)
            context.close()
            browser.close()

        (output / "results.json").write_text(
            json.dumps(
                {"camera_mode": "mocked_media_and_network", "cases": cases},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
