"""Thu hồi quyền ra vào không còn thỏa điều kiện lưu trú."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.dich_vu.luu_tru import danh_gia_quyen_ra_vao
from core.models import QuyenRaVao


class Command(BaseCommand):
    help = "Thu hồi idempotent các quyền ra vào đã hết điều kiện lưu trú."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Chỉ thống kê, không ghi dữ liệu.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        today = timezone.localdate()
        queryset = (
            QuyenRaVao.objects.filter(trang_thai="hoat_dong")
            .select_related(
                "hop_dong__dat_phong__phong",
                "hop_dong__dat_phong__nguoi_thue",
                "nguoi_thue",
                "nguoi_o_cung__hop_dong",
            )
            .order_by("id")
        )
        if not dry_run:
            queryset = queryset.select_for_update()
        rights = list(queryset)

        invalid = []
        for right in rights:
            evaluation = danh_gia_quyen_ra_vao(right, today)
            if not evaluation.du_dieu_kien:
                invalid.append((right, evaluation))
        if dry_run:
            for right, evaluation in invalid:
                subject = (
                    f"tenant#{right.nguoi_thue_id}"
                    if right.nguoi_thue_id
                    else f"companion#{right.nguoi_o_cung_id}"
                )
                self.stdout.write(
                    f"- permission#{right.id} {subject} room#{right.phong_id}: "
                    f"reasons={evaluation.ma_trang_thai}"
                )
            self.stdout.write(f"DRY-RUN: {len(invalid)} access rights need revocation; no writes.")
            return

        marker = "[RESIDENCY_ELIGIBILITY:He thong]"
        for right, evaluation in invalid:
            contract_expired = bool(
                right.hop_dong_id and right.hop_dong.ngay_ket_thuc < today
            )
            permission_expired = bool(
                right.ngay_ket_thuc and right.ngay_ket_thuc < today
            )
            right.trang_thai = "het_han" if contract_expired or permission_expired else "bi_thu_hoi"
            cutoff = right.hop_dong.ngay_ket_thuc if contract_expired else today
            if not right.ngay_ket_thuc or right.ngay_ket_thuc > cutoff:
                right.ngay_ket_thuc = cutoff
            if marker not in (right.ghi_chu or ""):
                right.ghi_chu = f"{right.ghi_chu or ''}\n{marker}".strip()
            right.save(
                update_fields=["trang_thai", "ngay_ket_thuc", "ghi_chu", "ngay_cap_nhat"]
            )
            self.stdout.write(
                f"- revoked permission#{right.id} -> {right.trang_thai}: "
                f"reasons={evaluation.ma_trang_thai}"
            )

        self.stdout.write(self.style.SUCCESS(f"Revoked {len(invalid)} access rights."))
