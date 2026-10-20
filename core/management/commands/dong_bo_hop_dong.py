from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import HopDong, ThongBao
from core.views_hop_dong import cap_nhat_trang_thai_hop_dong


class Command(BaseCommand):
    help = (
        "Đồng bộ trạng thái hợp đồng và tạo thông báo "
        "nhắc sắp hết hạn/hết hạn cho người thuê."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Chỉ kiểm tra và hiển thị kết quả dự kiến, "
                "không thay đổi dữ liệu."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        hom_nay = timezone.localdate()

        tong_hop_dong = 0
        tong_cap_nhat = 0
        tong_thong_bao = 0
        tong_bo_qua = 0
        tong_loi = 0

        hop_dong_ids = list(
            HopDong.objects
            .exclude(trang_thai="da_huy")
            .values_list("id", flat=True)
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Bắt đầu đồng bộ hợp đồng ngày "
                f"{hom_nay.strftime('%d/%m/%Y')}..."
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN: Không có dữ liệu nào được thay đổi."
                )
            )

        for hop_dong_id in hop_dong_ids:
            tong_hop_dong += 1

            try:
                if dry_run:
                    hop_dong = (
                        HopDong.objects
                        .select_related(
                            "dat_phong",
                            "dat_phong__nguoi_thue",
                            "dat_phong__phong",
                        )
                        .get(pk=hop_dong_id)
                    )

                    trang_thai_cu = hop_dong.trang_thai

                    trang_thai_du_kien = (
                        self._xac_dinh_trang_thai_du_kien(
                            hop_dong,
                            hom_nay,
                        )
                    )

                    if trang_thai_du_kien != trang_thai_cu:
                        tong_cap_nhat += 1

                        self.stdout.write(
                            f"[DRY-RUN] {hop_dong.so_hop_dong}: "
                            f"{trang_thai_cu} -> "
                            f"{trang_thai_du_kien}"
                        )

                    thong_bao = self._xac_dinh_thong_bao(
                        hop_dong,
                        hom_nay,
                    )

                    if thong_bao:
                        ma_tham_chieu = thong_bao["ma_tham_chieu"]

                        da_ton_tai = ThongBao.objects.filter(
                            ma_tham_chieu=ma_tham_chieu
                        ).exists()

                        if not da_ton_tai:
                            tong_thong_bao += 1

                            self.stdout.write(
                                f"[DRY-RUN] Sẽ tạo thông báo "
                                f"{ma_tham_chieu} cho "
                                f"{hop_dong.so_hop_dong}"
                            )

                    continue

                with transaction.atomic():
                    hop_dong = (
                        HopDong.objects
                        .select_for_update()
                        .select_related(
                            "dat_phong",
                            "dat_phong__nguoi_thue",
                            "dat_phong__phong",
                        )
                        .get(pk=hop_dong_id)
                    )

                    trang_thai_cu = hop_dong.trang_thai

                    hop_dong = (
                        cap_nhat_trang_thai_hop_dong(
                            hop_dong
                        )
                    )

                    hop_dong.refresh_from_db()

                    if hop_dong.trang_thai != trang_thai_cu:
                        tong_cap_nhat += 1

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"[CẬP NHẬT] "
                                f"{hop_dong.so_hop_dong}: "
                                f"{trang_thai_cu} -> "
                                f"{hop_dong.trang_thai}"
                            )
                        )

                    thong_bao = self._xac_dinh_thong_bao(
                        hop_dong,
                        hom_nay,
                    )

                    if thong_bao is None:
                        continue

                    nguoi_thue = (
                        hop_dong
                        .dat_phong
                        .nguoi_thue
                    )

                    if nguoi_thue is None:
                        tong_bo_qua += 1

                        self.stdout.write(
                            self.style.WARNING(
                                f"[BỎ QUA] "
                                f"{hop_dong.so_hop_dong} "
                                f"không xác định được người thuê."
                            )
                        )

                        continue

                    ma_tham_chieu = (
                        thong_bao["ma_tham_chieu"]
                    )

                    da_ton_tai = (
                        ThongBao.objects
                        .filter(
                            ma_tham_chieu=ma_tham_chieu
                        )
                        .exists()
                    )

                    if da_ton_tai:
                        continue

                    ThongBao.objects.create(
                        nguoi_thue=nguoi_thue,
                        tieu_de=thong_bao["tieu_de"],
                        noi_dung=thong_bao["noi_dung"],
                        loai="hop_dong",
                        muc_do=thong_bao["muc_do"],
                        ma_tham_chieu=ma_tham_chieu,
                    )

                    tong_thong_bao += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"[THÔNG BÁO] "
                            f"{hop_dong.so_hop_dong}: "
                            f"{thong_bao['tieu_de']}"
                        )
                    )

            except HopDong.DoesNotExist:
                tong_bo_qua += 1

            except Exception as exc:
                tong_loi += 1

                self.stderr.write(
                    self.style.ERROR(
                        f"[LỖI] Hợp đồng ID "
                        f"{hop_dong_id}: {exc}"
                    )
                )

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "===== KẾT QUẢ ĐỒNG BỘ HỢP ĐỒNG ====="
            )
        )

        self.stdout.write(
            f"Tổng hợp đồng kiểm tra: {tong_hop_dong}"
        )
        self.stdout.write(
            f"Hợp đồng đổi trạng thái: {tong_cap_nhat}"
        )
        self.stdout.write(
            f"Thông báo mới: {tong_thong_bao}"
        )
        self.stdout.write(
            f"Bỏ qua: {tong_bo_qua}"
        )
        self.stdout.write(
            f"Lỗi: {tong_loi}"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN hoàn tất. "
                    "Không có dữ liệu nào được lưu."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Đồng bộ hợp đồng hoàn tất."
                )
            )

        if tong_loi:
            raise CommandError(
                f"Đồng bộ hợp đồng hoàn tất với {tong_loi} lỗi; xem stderr để biết chi tiết."
            )

    def _xac_dinh_trang_thai_du_kien(
        self,
        hop_dong,
        hom_nay,
    ):
        """
        Chỉ dùng cho --dry-run.

        Mô phỏng cùng quy tắc thời gian với
        cap_nhat_trang_thai_hop_dong().
        """

        if hop_dong.trang_thai == "da_huy":
            return "da_huy"

        if hom_nay < hop_dong.ngay_bat_dau:
            return "cho_hieu_luc"

        if hom_nay > hop_dong.ngay_ket_thuc:
            return "da_het_han"

        so_ngay_con_lai = (
            hop_dong.ngay_ket_thuc - hom_nay
        ).days

        if 0 <= so_ngay_con_lai <= 30:
            return "sap_het_han"

        return "dang_hieu_luc"

    def _xac_dinh_thong_bao(
        self,
        hop_dong,
        hom_nay,
    ):
        """
        Chỉ trả về một thông báo phù hợp nhất cho ngày hiện tại.

        Các khoảng:
        - 16 -> 30 ngày: mốc 30 ngày
        - 8  -> 15 ngày: mốc 15 ngày
        - 1  -> 7 ngày : mốc 7 ngày
        - 0 ngày       : ngày cuối hợp đồng
        - < 0 ngày     : hợp đồng đã hết hạn

        Cách chia khoảng giúp:
        - Không spam nhiều mốc cũ cùng lúc.
        - Nếu tác vụ chạy trễ vài ngày vẫn có nhắc nhở phù hợp.
        """

        if hop_dong.trang_thai == "da_huy":
            return None

        if not hop_dong.ngay_ket_thuc:
            return None

        so_ngay_con_lai = (
            hop_dong.ngay_ket_thuc - hom_nay
        ).days

        so_hop_dong = hop_dong.so_hop_dong
        ngay_ket_thuc = (
            hop_dong.ngay_ket_thuc.strftime(
                "%d/%m/%Y"
            )
        )

        if so_ngay_con_lai < 0:
            return {
                "ma_tham_chieu": (
                    f"HD_{hop_dong.id}_{hop_dong.ngay_ket_thuc.strftime('%Y%m%d')}_EXPIRED"
                ),
                "tieu_de": (
                    "Hợp đồng thuê phòng đã hết hạn"
                ),
                "noi_dung": (
                    f"Hợp đồng {so_hop_dong} "
                    f"đã hết hạn vào ngày "
                    f"{ngay_ket_thuc}. "
                    f"Vui lòng liên hệ quản lý nếu "
                    f"bạn cần hỗ trợ hoặc muốn "
                    f"tiếp tục thuê phòng."
                ),
                "muc_do": "quan_trong",
            }

        if so_ngay_con_lai == 0:
            return {
                "ma_tham_chieu": (
                    f"HD_{hop_dong.id}_{hop_dong.ngay_ket_thuc.strftime('%Y%m%d')}_REMIND_0"
                ),
                "tieu_de": (
                    "Hợp đồng kết thúc hôm nay"
                ),
                "noi_dung": (
                    f"Hợp đồng {so_hop_dong} "
                    f"kết thúc vào hôm nay "
                    f"({ngay_ket_thuc}). "
                    f"Vui lòng liên hệ quản lý "
                    f"nếu bạn có nhu cầu gia hạn."
                ),
                "muc_do": "quan_trong",
            }

        if 1 <= so_ngay_con_lai <= 7:
            return {
                "ma_tham_chieu": (
                    f"HD_{hop_dong.id}_{hop_dong.ngay_ket_thuc.strftime('%Y%m%d')}_REMIND_7"
                ),
                "tieu_de": (
                    "Hợp đồng sắp hết hạn"
                ),
                "noi_dung": (
                    f"Hợp đồng {so_hop_dong} "
                    f"còn {so_ngay_con_lai} ngày "
                    f"và sẽ kết thúc vào "
                    f"{ngay_ket_thuc}. "
                    f"Vui lòng liên hệ quản lý "
                    f"nếu bạn muốn gia hạn."
                ),
                "muc_do": "quan_trong",
            }

        if 8 <= so_ngay_con_lai <= 15:
            return {
                "ma_tham_chieu": (
                    f"HD_{hop_dong.id}_{hop_dong.ngay_ket_thuc.strftime('%Y%m%d')}_REMIND_15"
                ),
                "tieu_de": (
                    "Nhắc nhở hợp đồng sắp hết hạn"
                ),
                "noi_dung": (
                    f"Hợp đồng {so_hop_dong} "
                    f"còn {so_ngay_con_lai} ngày "
                    f"và sẽ kết thúc vào "
                    f"{ngay_ket_thuc}. "
                    f"Bạn có thể chuẩn bị kế hoạch "
                    f"gia hạn nếu tiếp tục thuê."
                ),
                "muc_do": "binh_thuong",
            }

        if 16 <= so_ngay_con_lai <= 30:
            return {
                "ma_tham_chieu": (
                    f"HD_{hop_dong.id}_{hop_dong.ngay_ket_thuc.strftime('%Y%m%d')}_REMIND_30"
                ),
                "tieu_de": (
                    "Hợp đồng còn dưới 30 ngày"
                ),
                "noi_dung": (
                    f"Hợp đồng {so_hop_dong} "
                    f"còn {so_ngay_con_lai} ngày "
                    f"và dự kiến kết thúc vào "
                    f"{ngay_ket_thuc}. "
                    f"Vui lòng theo dõi thời hạn "
                    f"hợp đồng và chuẩn bị gia hạn "
                    f"nếu cần."
                ),
                "muc_do": "binh_thuong",
            }

        return None
