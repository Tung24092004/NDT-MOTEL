from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_faceprofile_consent"),
    ]

    operations = [
        migrations.AddField(
            model_name="hoadon",
            name="chi_so_dien_cu",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name="hoadon",
            name="chi_so_dien_moi",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True, validators=[MinValueValidator(0)]),
        ),
        migrations.AddField(
            model_name="hoadon",
            name="don_gia_dien",
            field=models.DecimalField(blank=True, decimal_places=0, max_digits=12, null=True, validators=[MinValueValidator(1), MaxValueValidator(100000)]),
        ),
    ]
