from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import CoSo, Phong


class Command(BaseCommand):
    help = (
        "Bổ sung dữ liệu phòng demo đến đúng số lượng khai báo của từng cơ sở. "
        "Mặc định chỉ DRY-RUN. Dùng --apply để ghi dữ liệu."
    )

    # =========================================================
    # CẤU HÌNH SỐ PHÒNG MỤC TIÊU
    # =========================================================

    ROOM_PLAN = {
        1: {
            1: ["P101", "P102", "P103", "P104", "P105"],
            2: ["P201", "P202", "P203", "P204", "P205"],
            3: ["P301", "P302", "P303", "P304", "P305"],
            4: ["P401", "P402", "P403", "P404", "P405"],
        },
        2: {
            1: ["P101", "P102", "P103", "P104", "P105"],
            2: ["P201", "P202", "P203", "P204", "P205"],
            3: ["P301", "P302", "P303", "P304", "P305"],
            4: ["P401", "P402", "P403", "P404", "P405"],
            5: ["P501", "P502", "P503", "P504", "P505"],
        },
        3: {
            1: ["P101", "P102", "P103", "P104", "P105"],
            2: ["P201", "P202", "P203", "P204", "P205"],
            3: ["P301", "P302", "P303", "P304"],
            4: ["P401", "P402", "P403", "P404"],
        },
        4: {
            1: ["P101", "P102", "P103", "P104", "P105"],
            2: ["P201", "P202", "P203", "P204", "P205"],
            3: ["P301", "P302", "P303", "P304", "P305"],
            4: ["P401", "P402", "P403", "P404"],
            5: ["P501", "P502", "P503", "P504"],
        },
    }

    # =========================================================
    # CẤU HÌNH THEO LOẠI PHÒNG
    # =========================================================

    ROOM_TYPES = {
        "phong_tieu_chuan": {
            "gia_thue": Decimal("2700000"),
            "dien_tich": Decimal("25"),
            "so_nguoi_toi_da": 2,
            "phi_dich_vu": Decimal("100000"),
            "tien_ich": (
                "Giường, Tủ quần áo, Điều hòa, "
                "Nóng lạnh, WiFi"
            ),
            "mo_ta": (
                "Phòng tiêu chuẩn đầy đủ tiện nghi, "
                "không gian thoáng và phù hợp cho 1–2 người ở."
            ),
        },

        "phong_gac_lung": {
            "gia_thue": Decimal("3300000"),
            "dien_tich": Decimal("30"),
            "so_nguoi_toi_da": 3,
            "phi_dich_vu": Decimal("150000"),
            "tien_ich": (
                "Giường, Gác lửng, Tủ quần áo, Điều hòa, "
                "Nóng lạnh, WiFi"
            ),
            "mo_ta": (
                "Phòng gác lửng có không gian sinh hoạt rộng rãi, "
                "phù hợp cho 2–3 người ở."
            ),
        },

        "phong_cao_cap": {
            "gia_thue": Decimal("4200000"),
            "dien_tich": Decimal("32"),
            "so_nguoi_toi_da": 3,
            "phi_dich_vu": Decimal("200000"),
            "tien_ich": (
                "Giường, Tủ quần áo, Điều hòa, TV, "
                "Nóng lạnh, WiFi, Bàn làm việc"
            ),
            "mo_ta": (
                "Phòng cao cấp với không gian hiện đại, "
                "tiện nghi mở rộng và khu vực sinh hoạt thoải mái."
            ),
        },

        "can_ho_mini": {
            "gia_thue": Decimal("4800000"),
            "dien_tich": Decimal("40"),
            "so_nguoi_toi_da": 4,
            "phi_dich_vu": Decimal("250000"),
            "tien_ich": (
                "Giường, Tủ quần áo, Điều hòa, TV, "
                "Nóng lạnh, WiFi, Khu bếp"
            ),
            "mo_ta": (
                "Căn hộ mini có diện tích rộng, khu sinh hoạt riêng "
                "và đầy đủ tiện nghi cho nhu cầu ở lâu dài."
            ),
        },
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Thực sự tạo phòng. Không có --apply chỉ chạy DRY-RUN.",
        )

    # =========================================================
    # CHỌN LOẠI PHÒNG
    # =========================================================

    def get_room_type(self, floor, room_number):
        """
        Phân bổ nhiều loại phòng nhưng vẫn ưu tiên
        phòng tiêu chuẩn để dữ liệu thực tế hơn.
        """

        number = int(room_number[-2:])

        if number == 5:
            return "can_ho_mini"

        if number == 4:
            return "phong_cao_cap"

        if number == 3 and floor >= 2:
            return "phong_gac_lung"

        return "phong_tieu_chuan"

    # =========================================================
    # TẠO THÔNG SỐ PHÒNG
    # =========================================================

    def build_room_data(self, co_so, floor, room_number):
        room_type = self.get_room_type(
            floor,
            room_number,
        )

        config = self.ROOM_TYPES[room_type].copy()

        # Giá nhích nhẹ theo tầng để dữ liệu không quá đồng loạt.
        floor_extra = Decimal(
            str(max(floor - 1, 0) * 100000)
        )

        config["gia_thue"] += floor_extra

        # Cọc mặc định = 1 tháng tiền phòng.
        config["tien_coc_mac_dinh"] = config["gia_thue"]

        # Theo mức đang sử dụng trong dữ liệu hiện tại.
        config["tien_dien_moi_so"] = Decimal("3500")
        config["tien_nuoc_moi_khoi"] = Decimal("15000")

        config["co_so"] = co_so
        config["so_phong"] = room_number
        config["tang"] = floor
        config["loai_phong"] = room_type
        config["trang_thai"] = "trong"

        return config

    # =========================================================
    # HANDLE
    # =========================================================

    def handle(self, *args, **options):
        apply_changes = options["apply"]

        self.stdout.write("")
        self.stdout.write("=" * 78)

        if apply_changes:
            self.stdout.write(
                self.style.WARNING(
                    "CHẾ ĐỘ APPLY — SẼ GHI DỮ LIỆU"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "CHẾ ĐỘ DRY-RUN — KHÔNG GHI DỮ LIỆU"
                )
            )

        self.stdout.write("=" * 78)

        facilities = {
            cs.id: cs
            for cs in CoSo.objects.all()
        }

        missing_facilities = (
            set(self.ROOM_PLAN.keys())
            - set(facilities.keys())
        )

        if missing_facilities:
            raise CommandError(
                "Không tìm thấy cơ sở ID: "
                + ", ".join(
                    str(x)
                    for x in sorted(missing_facilities)
                )
            )

        rooms_to_create = []

        # =====================================================
        # KIỂM TRA PLAN
        # =====================================================

        for co_so_id, floor_plan in self.ROOM_PLAN.items():

            co_so = facilities[co_so_id]

            target_rooms = []

            for floor, room_numbers in floor_plan.items():

                if floor > co_so.so_tang:
                    raise CommandError(
                        f"{co_so.ten_co_so}: "
                        f"tầng {floor} vượt quá "
                        f"{co_so.so_tang} tầng khai báo."
                    )

                for room_number in room_numbers:
                    target_rooms.append(
                        (
                            floor,
                            room_number,
                        )
                    )

            if len(target_rooms) != co_so.so_phong:
                raise CommandError(
                    f"{co_so.ten_co_so}: "
                    f"ROOM_PLAN có {len(target_rooms)} phòng "
                    f"nhưng cơ sở khai báo {co_so.so_phong}."
                )

            existing_rooms = {
                p.so_phong: p
                for p in Phong.objects.filter(
                    co_so=co_so
                )
            }

            self.stdout.write("")
            self.stdout.write(
                self.style.HTTP_INFO(
                    f"[{co_so.id}] {co_so.ten_co_so}"
                )
            )

            self.stdout.write(
                f"  Khai báo : {co_so.so_phong}"
            )

            self.stdout.write(
                f"  Hiện có  : {len(existing_rooms)}"
            )

            facility_new = 0

            for floor, room_number in target_rooms:

                if room_number in existing_rooms:

                    current = existing_rooms[
                        room_number
                    ]

                    self.stdout.write(
                        f"  GIỮ     : {room_number} "
                        f"(ID={current.id}, "
                        f"tầng={current.tang})"
                    )

                    continue

                data = self.build_room_data(
                    co_so,
                    floor,
                    room_number,
                )

                rooms_to_create.append(data)
                facility_new += 1

                self.stdout.write(
                    "  TẠO     : "
                    f"{room_number} | "
                    f"Tầng {floor} | "
                    f"{data['loai_phong']} | "
                    f"{int(data['gia_thue']):,}đ | "
                    f"{data['dien_tich']}m² | "
                    f"Max {data['so_nguoi_toi_da']}"
                )

            expected_missing = (
                co_so.so_phong
                - len(existing_rooms)
            )

            if facility_new != expected_missing:
                raise CommandError(
                    f"{co_so.ten_co_so}: "
                    f"dự kiến thiếu {expected_missing} "
                    f"nhưng plan chuẩn bị tạo "
                    f"{facility_new}."
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  => Tạo thêm: {facility_new}"
                )
            )

        # =====================================================
        # KIỂM TRA TỔNG
        # =====================================================

        current_total = Phong.objects.count()
        new_total = len(rooms_to_create)

        expected_total = sum(
            cs.so_phong
            for cs in facilities.values()
            if cs.id in self.ROOM_PLAN
        )

        self.stdout.write("")
        self.stdout.write("=" * 78)

        self.stdout.write(
            f"Hiện có       : {current_total}"
        )

        self.stdout.write(
            f"Sẽ tạo thêm   : {new_total}"
        )

        self.stdout.write(
            f"Sau khi tạo   : {current_total + new_total}"
        )

        self.stdout.write(
            f"Tổng khai báo : {expected_total}"
        )

        if current_total + new_total != expected_total:
            raise CommandError(
                "Tổng phòng sau khi tạo không khớp "
                "tổng số phòng khai báo."
            )

        if not apply_changes:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN hoàn tất. "
                    "CHƯA có dữ liệu nào được tạo."
                )
            )

            self.stdout.write(
                "Nếu danh sách đúng, chạy:"
            )

            self.stdout.write(
                "python manage.py "
                "tao_du_lieu_phong_demo --apply"
            )

            self.stdout.write("=" * 78)
            return

        # =====================================================
        # APPLY
        # =====================================================

        with transaction.atomic():

            created = 0

            for data in rooms_to_create:

                co_so = data["co_so"]
                room_number = data["so_phong"]

                # Kiểm tra lại ngay trước khi INSERT.
                if Phong.objects.filter(
                    co_so=co_so,
                    so_phong=room_number,
                ).exists():
                    raise CommandError(
                        f"Phát hiện phòng trùng trong lúc APPLY: "
                        f"{co_so.ten_co_so} - {room_number}"
                    )

                Phong.objects.create(**data)
                created += 1

            # ===============================================
            # VERIFY TRONG TRANSACTION
            # ===============================================

            for co_so_id in self.ROOM_PLAN:

                co_so = facilities[co_so_id]

                actual = Phong.objects.filter(
                    co_so=co_so
                ).count()

                if actual != co_so.so_phong:
                    raise CommandError(
                        f"{co_so.ten_co_so}: "
                        f"sau APPLY có {actual}, "
                        f"cần {co_so.so_phong}. "
                        "Transaction sẽ rollback."
                    )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"ĐÃ TẠO THÀNH CÔNG {created} PHÒNG."
            )
        )

        self.stdout.write("")
        self.stdout.write("KIỂM TRA CUỐI:")

        final_total = 0

        for co_so_id in self.ROOM_PLAN:

            co_so = facilities[co_so_id]

            actual = Phong.objects.filter(
                co_so=co_so
            ).count()

            final_total += actual

            self.stdout.write(
                self.style.SUCCESS(
                    f"  {co_so.ten_co_so}: "
                    f"{actual}/{co_so.so_phong}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"  TỔNG: {final_total}/{expected_total}"
            )
        )

        self.stdout.write("=" * 78)