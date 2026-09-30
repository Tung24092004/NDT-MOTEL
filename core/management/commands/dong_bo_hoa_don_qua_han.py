from django.core.management.base import BaseCommand

from core.quy_tac_nghiep_vu import dong_bo_hoa_don_qua_han


class Command(BaseCommand):
    help = "Dong bo hoa don chua thanh toan da qua han sang trang thai qua_han."

    def handle(self, *args, **options):
        so_luong = dong_bo_hoa_don_qua_han()
        self.stdout.write(
            self.style.SUCCESS(
                f"Da dong bo {so_luong} hoa don qua han."
            )
        )
