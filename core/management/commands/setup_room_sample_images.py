from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import HinhAnhPhong, Phong


ROOM_SAMPLES = (
    {
        "id": 1,
        "so_phong": "P101",
        "loai_phong": "phong_tieu_chuan",
        "directory": "phong_tieu_chuan",
        "images": (
            ("01_toan_canh.png", "Toan canh phong tieu chuan"),
            ("02_khu_ngu.jpg", "Khu ngu phong tieu chuan"),
            ("03_tien_nghi.jpg", "Ban lam viec va tu tien nghi"),
            ("04_wc.jpg", "Khu ve sinh phong tieu chuan"),
            ("05_cua_so.jpg", "Khu ngu gan cua so va ban cong"),
        ),
    },
    {
        "id": 14,
        "so_phong": "P104",
        "loai_phong": "phong_cao_cap",
        "directory": "phong_cao_cap",
        "images": (
            ("01_toan_canh.jpg", "Toan canh phong cao cap"),
            ("02_khu_ngu.jpg", "Khu ngu phong cao cap"),
            ("03_tiep_khach.jpg", "Khu tiep khach va lam viec"),
            ("04_wc.jpg", "Khu ve sinh phong cao cap"),
            ("05_tien_nghi.jpg", "Tu va tien nghi phong cao cap"),
        ),
    },
    {
        "id": 3,
        "so_phong": "P201",
        "loai_phong": "phong_gac_lung",
        "directory": "phong_gac_lung",
        "images": (
            ("01_toan_canh.jpg", "Toan canh phong co gac lung"),
            ("02_tang_duoi.jpg", "Khong gian sinh hoat tang duoi"),
            ("03_khu_ngu_gac.jpg", "Khu ngu tren gac"),
            ("04_wc.jpg", "Khu ve sinh phong gac lung"),
            ("05_cau_thang.jpg", "Cau thang va khu vuc luu tru"),
        ),
    },
    {
        "id": 5,
        "so_phong": "P301",
        "loai_phong": "can_ho_mini",
        "directory": "can_ho_mini",
        "images": (
            ("01_toan_canh.jpg", "Toan canh can ho mini"),
            ("02_khu_ngu.jpg", "Khu ngu can ho mini"),
            ("03_bep.jpg", "Khu bep can ho mini"),
            ("04_wc.jpg", "Khu ve sinh can ho mini"),
            ("05_ban_an.jpg", "Ban an va cua so can ho mini"),
        ),
    },
)


class Command(BaseCommand):
    help = "Gan anh mau theo loai phong cho dung bon phong mau da cau hinh."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Chi kiem tra va liet ke thay doi, khong ghi database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        media_root = Path(settings.MEDIA_ROOT)
        plans = []

        for sample in ROOM_SAMPLES:
            try:
                room = Phong.objects.select_related("co_so").get(pk=sample["id"])
            except Phong.DoesNotExist as exc:
                raise CommandError(f"Khong tim thay phong mau id={sample['id']}.") from exc

            if room.so_phong != sample["so_phong"] or room.loai_phong != sample["loai_phong"]:
                raise CommandError(
                    "Phong mau khong khop: "
                    f"id={room.id}, so_phong={room.so_phong}, loai_phong={room.loai_phong}; "
                    f"yeu cau so_phong={sample['so_phong']}, loai_phong={sample['loai_phong']}."
                )

            existing = {
                str(image.anh): image
                for image in room.hinh_anh.order_by("thu_tu", "id")
            }
            if len(existing) > 5:
                raise CommandError(
                    f"Phong id={room.id} dang co {len(existing)} anh; command khong tu xoa de dua ve toi da 5."
                )

            room_plans = []
            for order, (filename, description) in enumerate(sample["images"], start=1):
                relative_path = f"phong_mau/{sample['directory']}/{filename}"
                absolute_path = media_root / Path(relative_path)
                if not absolute_path.is_file():
                    raise CommandError(f"Thieu file anh: {absolute_path}")

                if relative_path in existing:
                    status = "DA CO"
                elif len(existing) + sum(p[0] == "TAO" for p in room_plans) < 5:
                    status = "TAO"
                else:
                    status = "BO QUA - PHONG DA DU 5 ANH"

                room_plans.append(
                    (status, relative_path, description, order, order == 1)
                )

            plans.append((room, room_plans))

        create_count = sum(
            status == "TAO"
            for _, room_plans in plans
            for status, *_ in room_plans
        )
        mode = "DRY-RUN" if dry_run else "THUC HIEN"
        self.stdout.write(f"[{mode}] Se tao {create_count} HinhAnhPhong.")
        for room, room_plans in plans:
            self.stdout.write(
                f"Phong id={room.id} {room.so_phong} | co_so_id={room.co_so_id} | {room.loai_phong}"
            )
            for status, relative_path, description, order, representative in room_plans:
                self.stdout.write(
                    f"  {status}: {relative_path} | thu_tu={order} | "
                    f"dai_dien={'co' if representative else 'khong'} | {description}"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run: khong co thay doi database."))
            return

        with transaction.atomic():
            for room, room_plans in plans:
                for status, relative_path, description, order, representative in room_plans:
                    if status != "TAO":
                        continue
                    HinhAnhPhong.objects.create(
                        phong=room,
                        anh=relative_path,
                        mo_ta=description,
                        la_anh_dai_dien=representative,
                        thu_tu=order,
                    )

        self.stdout.write(self.style.SUCCESS(f"Da tao {create_count} HinhAnhPhong."))
