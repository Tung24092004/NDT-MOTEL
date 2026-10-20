# Generated manually for INVOICE-PAY-01A on 2026-10-16.
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


def backfill_invoice_attempt_numbers(apps, schema_editor):
    Evidence = apps.get_model("core", "ChungTuThanhToan")
    # 0025 guaranteed at most one invoice evidence row.  Keep its primary key,
    # target relation, file metadata and lifecycle fields untouched.
    Evidence.objects.using(schema_editor.connection.alias).filter(
        hoa_don__isnull=False, so_lan__isnull=True
    ).update(so_lan=1)


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0033_phan_hoi_hop_dong"),
    ]

    operations = [
        migrations.AddField(
            model_name="chungtuthanhtoan",
            name="so_lan",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Thứ tự attempt của chứng từ hóa đơn; cọc không dùng trường này.",
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AlterField(
            model_name="chungtuthanhtoan",
            name="hoa_don",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="chung_tu_thanh_toan",
                to="core.hoadon",
            ),
        ),
        # This migration is deliberately irreversible: collapsing multiple
        # attempts back to a one-to-one relation would discard audit evidence.
        migrations.RunPython(backfill_invoice_attempt_numbers, reverse_code=None),
        migrations.AddConstraint(
            model_name="chungtuthanhtoan",
            constraint=models.UniqueConstraint(
                fields=("hoa_don", "so_lan"),
                name="unique_invoice_payment_evidence_attempt",
            ),
        ),
        migrations.AddConstraint(
            model_name="chungtuthanhtoan",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(giao_dich_coc__isnull=False, hoa_don__isnull=True, so_lan__isnull=True)
                    | models.Q(giao_dich_coc__isnull=True, hoa_don__isnull=False, so_lan__gte=1)
                ),
                name="payment_evidence_invoice_attempt_number",
            ),
        ),
    ]
