from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Phong


class Command(BaseCommand):

    help = (
        "Chuẩn hóa dữ liệu phòng NDT MOTEL. "
        "Dùng --dry-run để xem trước, "
        "--apply để áp dụng vào database."
    )

    # =====================================================
    # THAM SỐ COMMAND
    # =====================================================

    def add_arguments(self, parser):

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Chỉ hiển thị thay đổi dự kiến, "
                "không sửa database."
            ),
        )

        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Thực sự áp dụng các thay đổi "
                "vào database."
            ),
        )

    # =====================================================
    # CHUẨN HÓA LOẠI PHÒNG
    # =====================================================

    def chuan_hoa_loai_phong(self, loai_phong):

        gia_tri = (
            loai_phong or ""
        ).strip()

        # Các giá trị chuẩn hiện tại
        loai_hop_le = {
            "phong_tieu_chuan",
            "phong_cao_cap",
            "phong_gac_lung",
            "can_ho_mini",
        }

        if gia_tri in loai_hop_le:
            return gia_tri

        # Dữ liệu cũ từng nhập tự do
        mapping = {

            # Phòng tiêu chuẩn
            "phòng tiêu chuẩn":
                "phong_tieu_chuan",

            "phong tieu chuan":
                "phong_tieu_chuan",

            "phòng đơn":
                "phong_tieu_chuan",

            "phong don":
                "phong_tieu_chuan",

            "standard":
                "phong_tieu_chuan",

            # Phòng cao cấp
            "vip":
                "phong_cao_cap",

            "phòng vip":
                "phong_cao_cap",

            "phong vip":
                "phong_cao_cap",

            "phòng cao cấp":
                "phong_cao_cap",

            "phong cao cap":
                "phong_cao_cap",

            # Phòng có gác
            "phòng gác lửng":
                "phong_gac_lung",

            "phong gac lung":
                "phong_gac_lung",

            "phòng có gác":
                "phong_gac_lung",

            "phong co gac":
                "phong_gac_lung",

            # Căn hộ mini
            "căn hộ mini":
                "can_ho_mini",

            "can ho mini":
                "can_ho_mini",
        }

        return mapping.get(
            gia_tri.casefold(),
            gia_tri,
        )

    # =====================================================
    # CHUẨN HÓA TIỆN ÍCH
    # =====================================================

    def chuan_hoa_tien_ich(self, tien_ich):

        gia_tri = (
            tien_ich or ""
        ).strip()

        if not gia_tri:
            return ""

        mapping = {

            "wifi":
                "WiFi",

            "wi-fi":
                "WiFi",

            "điều hòa":
                "Điều hòa",

            "điều hoà":
                "Điều hòa",

            # Máy lạnh và điều hòa là cùng nhóm
            "máy lạnh":
                "Điều hòa",

            "nóng lạnh":
                "Nóng lạnh",

            "bình nóng lạnh":
                "Nóng lạnh",

            "giường":
                "Giường",

            "tủ quần áo":
                "Tủ quần áo",

            "tivi":
                "TV",

            "tv":
                "TV",

            "máy giặt":
                "Máy giặt",

            "bàn làm việc":
                "Bàn làm việc",

            "tủ lạnh":
                "Tủ lạnh",
        }

        ket_qua = []
        da_co = set()

        for item in gia_tri.split(","):

            item = item.strip()

            if not item:
                continue

            item_moi = mapping.get(
                item.casefold(),
                item,
            )

            key = item_moi.casefold()

            # Loại bỏ tiện ích trùng
            if key in da_co:
                continue

            da_co.add(key)
            ket_qua.append(item_moi)

        return ", ".join(ket_qua)

    # =====================================================
    # TÊN HIỂN THỊ LOẠI PHÒNG
    # =====================================================

    def ten_loai_phong(self, loai_phong):

        mapping = {

            "phong_tieu_chuan":
                "Phòng tiêu chuẩn",

            "phong_cao_cap":
                "Phòng cao cấp",

            "phong_gac_lung":
                "Phòng có gác",

            "can_ho_mini":
                "Căn hộ mini",
        }

        return mapping.get(
            loai_phong,
            "Phòng",
        )

    # =====================================================
    # KIỂM TRA MÔ TẢ CÓ CẦN LÀM LẠI KHÔNG
    # =====================================================

    def can_chuan_hoa_mo_ta(self, mo_ta):

        gia_tri = (
            mo_ta or ""
        ).strip()

        # Trống
        if not gia_tri:
            return True

        # Các mô tả test / quá sơ sài
        mo_ta_so_sai = {
            "...",
            "phòng vip",
            "phong vip",
            "phòng đầy đủ tiện nghi",
            "phong day du tien nghi",
        }

        return (
            gia_tri.casefold()
            in mo_ta_so_sai
        )

    # =====================================================
    # TẠO MÔ TẢ TỪ DỮ LIỆU THẬT
    # =====================================================

    def tao_mo_ta(
        self,
        phong,
        loai_phong,
        tien_ich,
    ):

        ten_loai = (
            self.ten_loai_phong(
                loai_phong
            )
        )

        # Decimal 30.00 -> 30, 23.50 -> 23.5
        dien_tich = (
            f"{phong.dien_tich:f}"
            .rstrip("0")
            .rstrip(".")
        )

        so_nguoi = (
            phong.so_nguoi_toi_da
        )

        tang = phong.tang

        # ---------------------------------------------
        # PHÒNG TIÊU CHUẨN
        # ---------------------------------------------

        if (
            loai_phong
            == "phong_tieu_chuan"
        ):

            mo_ta = (
                f"{ten_loai} "
                f"{dien_tich}m² "
                f"tại tầng {tang}, "
                f"không gian gọn gàng "
                f"và thuận tiện, "
                f"phù hợp tối đa "
                f"{so_nguoi} người."
            )

        # ---------------------------------------------
        # PHÒNG CAO CẤP
        # ---------------------------------------------

        elif (
            loai_phong
            == "phong_cao_cap"
        ):

            mo_ta = (
                f"{ten_loai} "
                f"{dien_tich}m² "
                f"tại tầng {tang}, "
                f"không gian tiện nghi "
                f"và riêng tư, "
                f"phù hợp tối đa "
                f"{so_nguoi} người."
            )

        # ---------------------------------------------
        # PHÒNG CÓ GÁC
        # ---------------------------------------------

        elif (
            loai_phong
            == "phong_gac_lung"
        ):

            mo_ta = (
                f"{ten_loai} "
                f"{dien_tich}m² "
                f"tại tầng {tang}, "
                f"bố trí không gian "
                f"sinh hoạt linh hoạt, "
                f"phù hợp tối đa "
                f"{so_nguoi} người."
            )

        # ---------------------------------------------
        # CĂN HỘ MINI
        # ---------------------------------------------

        elif (
            loai_phong
            == "can_ho_mini"
        ):

            mo_ta = (
                f"{ten_loai} "
                f"{dien_tich}m² "
                f"tại tầng {tang}, "
                f"không gian rộng rãi "
                f"và riêng tư, "
                f"phù hợp tối đa "
                f"{so_nguoi} người."
            )

        else:

            mo_ta = (
                f"{ten_loai} "
                f"{dien_tich}m² "
                f"tại tầng {tang}, "
                f"phù hợp tối đa "
                f"{so_nguoi} người."
            )

        # Chỉ đưa tiện ích THỰC SỰ có trong DB
        if tien_ich:

            mo_ta += (
                f" Tiện ích gồm "
                f"{tien_ich}."
            )

        return mo_ta

    # =====================================================
    # HANDLE
    # =====================================================

    def handle(
        self,
        *args,
        **options,
    ):

        dry_run = options["dry_run"]
        apply_changes = options["apply"]

        # Không cho chạy cả hai cùng lúc
        if dry_run and apply_changes:

            self.stderr.write(
                self.style.ERROR(
                    "Không dùng đồng thời "
                    "--dry-run và --apply."
                )
            )

            return

        # Nếu không truyền gì -> mặc định dry-run
        if not apply_changes:
            dry_run = True

        # ---------------------------------------------
        # THÔNG BÁO CHẾ ĐỘ
        # ---------------------------------------------

        if dry_run:

            self.stdout.write(
                self.style.WARNING(
                    "\n"
                    "========================================\n"
                    " CHẾ ĐỘ DRY-RUN\n"
                    " DATABASE SẼ KHÔNG BỊ THAY ĐỔI\n"
                    "========================================"
                )
            )

        else:

            self.stdout.write(
                self.style.WARNING(
                    "\n"
                    "========================================\n"
                    " CHẾ ĐỘ APPLY\n"
                    " DATABASE SẼ ĐƯỢC CẬP NHẬT\n"
                    "========================================"
                )
            )

        # ---------------------------------------------
        # DANH SÁCH PHÒNG
        # ---------------------------------------------

        danh_sach_phong = (
            Phong.objects
            .select_related(
                "co_so"
            )
            .order_by(
                "co_so_id",
                "tang",
                "so_phong",
                "id",
            )
        )

        tong_phong = (
            danh_sach_phong.count()
        )

        so_phong_can_sua = 0
        so_phong_bo_qua = 0
        so_phong_giu_nguyen = 0

        loai_hop_le = {
            "phong_tieu_chuan",
            "phong_cao_cap",
            "phong_gac_lung",
            "can_ho_mini",
        }

        # ---------------------------------------------
        # TRANSACTION
        # ---------------------------------------------

        with transaction.atomic():

            for phong in danh_sach_phong:

                # =====================================
                # BỎ QUA TEST02
                # =====================================

                if (
                    (
                        phong.so_phong
                        or ""
                    )
                    .strip()
                    .casefold()
                    == "test02"
                ):

                    so_phong_bo_qua += 1

                    self.stdout.write(
                        self.style.WARNING(
                            "\n[BỎ QUA] "
                            f"ID={phong.id} | "
                            f"{phong.co_so.ten_co_so} | "
                            f"Phòng {phong.so_phong} "
                            "(dữ liệu test)"
                        )
                    )

                    continue

                thay_doi = {}

                # =====================================
                # LOẠI PHÒNG
                # =====================================

                loai_moi = (
                    self.chuan_hoa_loai_phong(
                        phong.loai_phong
                    )
                )

                # Nếu gặp loại không biết -> không đoán
                if loai_moi not in loai_hop_le:

                    so_phong_bo_qua += 1

                    self.stdout.write(
                        self.style.ERROR(
                            "\n[KHÔNG TỰ SỬA] "
                            f"ID={phong.id} | "
                            f"{phong.co_so.ten_co_so} | "
                            f"Phòng {phong.so_phong} | "
                            "Loại phòng lạ: "
                            f"{phong.loai_phong!r}"
                        )
                    )

                    continue

                if (
                    phong.loai_phong
                    != loai_moi
                ):

                    thay_doi[
                        "loai_phong"
                    ] = (
                        phong.loai_phong,
                        loai_moi,
                    )

                # =====================================
                # TIỆN ÍCH
                # =====================================

                tien_ich_cu = (
                    phong.tien_ich
                    or ""
                ).strip()

                tien_ich_moi = (
                    self.chuan_hoa_tien_ich(
                        phong.tien_ich
                    )
                )

                if (
                    tien_ich_cu
                    != tien_ich_moi
                ):

                    thay_doi[
                        "tien_ich"
                    ] = (
                        phong.tien_ich,
                        tien_ich_moi,
                    )

                # =====================================
                # MÔ TẢ
                # =====================================

                if (
                    self.can_chuan_hoa_mo_ta(
                        phong.mo_ta
                    )
                ):

                    mo_ta_moi = (
                        self.tao_mo_ta(
                            phong,
                            loai_moi,
                            tien_ich_moi,
                        )
                    )

                    mo_ta_cu = (
                        phong.mo_ta
                        or ""
                    ).strip()

                    if (
                        mo_ta_cu
                        != mo_ta_moi
                    ):

                        thay_doi[
                            "mo_ta"
                        ] = (
                            phong.mo_ta,
                            mo_ta_moi,
                        )

                # =====================================
                # KHÔNG CÓ GÌ CẦN SỬA
                # =====================================

                if not thay_doi:

                    so_phong_giu_nguyen += 1

                    self.stdout.write(
                        "\n[GIỮ NGUYÊN] "
                        f"ID={phong.id} | "
                        f"{phong.co_so.ten_co_so} | "
                        f"Phòng {phong.so_phong}"
                    )

                    continue

                # =====================================
                # HIỂN THỊ THAY ĐỔI
                # =====================================

                so_phong_can_sua += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        "\n[CẦN CHUẨN HÓA] "
                        f"ID={phong.id} | "
                        f"{phong.co_so.ten_co_so} | "
                        f"Phòng {phong.so_phong}"
                    )
                )

                for (
                    ten_field,
                    (
                        gia_tri_cu,
                        gia_tri_moi,
                    ),
                ) in thay_doi.items():

                    self.stdout.write(
                        f"  {ten_field}:"
                    )

                    self.stdout.write(
                        f"    CŨ  : "
                        f"{gia_tri_cu!r}"
                    )

                    self.stdout.write(
                        f"    MỚI : "
                        f"{gia_tri_moi!r}"
                    )

                # =====================================
                # APPLY
                # =====================================

                if apply_changes:

                    update_fields = []

                    for (
                        ten_field,
                        (
                            _,
                            gia_tri_moi,
                        ),
                    ) in thay_doi.items():

                        setattr(
                            phong,
                            ten_field,
                            gia_tri_moi,
                        )

                        update_fields.append(
                            ten_field
                        )

                    # auto_now không tự chạy khi
                    # update_fields không chứa field này
                    update_fields.append(
                        "ngay_cap_nhat"
                    )

                    phong.save(
                        update_fields=(
                            update_fields
                        )
                    )

            # =========================================
            # DRY-RUN -> ROLLBACK
            # =========================================

            if dry_run:

                transaction.set_rollback(
                    True
                )

        # =================================================
        # TỔNG KẾT
        # =================================================

        self.stdout.write(
            "\n"
            "========================================"
        )

        self.stdout.write(
            "KẾT QUẢ CHUẨN HÓA PHÒNG"
        )

        self.stdout.write(
            "========================================"
        )

        self.stdout.write(
            f"Tổng số phòng       : "
            f"{tong_phong}"
        )

        self.stdout.write(
            f"Cần chuẩn hóa       : "
            f"{so_phong_can_sua}"
        )

        self.stdout.write(
            f"Giữ nguyên          : "
            f"{so_phong_giu_nguyen}"
        )

        self.stdout.write(
            f"Bỏ qua               : "
            f"{so_phong_bo_qua}"
        )

        if dry_run:

            self.stdout.write(
                self.style.WARNING(
                    "\nCHƯA SỬA DATABASE."
                )
            )

            self.stdout.write(
                "Nếu toàn bộ kết quả phía trên "
                "đúng thì mới chạy:"
            )

            self.stdout.write(
                self.style.SUCCESS(
                    "python manage.py "
                    "chuan_hoa_phong --apply"
                )
            )

        else:

            self.stdout.write(
                self.style.SUCCESS(
                    "\nĐÃ CHUẨN HÓA DATABASE."
                )
            )

            self.stdout.write(
                "Command KHÔNG thay đổi:"
            )

            self.stdout.write(
                "- ID phòng"
            )

            self.stdout.write(
                "- Cơ sở"
            )

            self.stdout.write(
                "- Số phòng / tầng"
            )

            self.stdout.write(
                "- Giá thuê"
            )

            self.stdout.write(
                "- Diện tích"
            )

            self.stdout.write(
                "- Sức chứa"
            )

            self.stdout.write(
                "- Trạng thái phòng"
            )

            self.stdout.write(
                "- Đặt phòng / hợp đồng"
            )

            self.stdout.write(
                "- Ảnh phòng"
            )