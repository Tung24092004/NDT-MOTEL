"""Create approved rent-only invoice drafts for one explicit period."""
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError

from core.dich_vu.hoa_don import billing_period, create_invoice_draft
from core.dich_vu.luu_tru import queryset_hop_dong_luu_tru_hien_tai
from core.models import User


class Command(BaseCommand):
    help = "Tao draft hoa don tien phong cho ky YYYY-MM do Admin chi dinh."

    def add_arguments(self, parser):
        parser.add_argument("period", help="Ky hoa don YYYY-MM.")
        parser.add_argument("--actor", required=True, help="Username Admin thuc hien.")

    def handle(self, *args, **options):
        try:
            year, month = map(int, options["period"].split("-", 1))
            period_start, _ = billing_period(year, month)
        except (ValueError, ValidationError) as error:
            raise CommandError("period phai co dang YYYY-MM hop le.") from error
        actor = User.objects.filter(username=options["actor"], is_active=True).first()
        if not actor or not (actor.is_staff or actor.is_superuser):
            raise CommandError("--actor phai la tai khoan Admin dang hoat dong.")

        created = existing = skipped = errors = 0
        contracts = queryset_hop_dong_luu_tru_hien_tai().order_by("id")
        for contract in contracts:
            if contract.ngay_bat_dau > period_start:
                skipped += 1; continue
            try:
                create_invoice_draft(actor=actor, contract_id=contract.pk, year=year, month=month)
                created += 1
            except ValidationError as error:
                if "da ton tai" in str(error): existing += 1
                else: skipped += 1
            except Exception as error:  # report every independent contract failure
                errors += 1; self.stderr.write(f"contract#{contract.pk}: {error}")
        self.stdout.write(f"period={period_start:%Y-%m} created={created} already_exists={existing} skipped={skipped} error={errors}")
        if errors:
            raise CommandError("Co contract tao draft that bai.")
