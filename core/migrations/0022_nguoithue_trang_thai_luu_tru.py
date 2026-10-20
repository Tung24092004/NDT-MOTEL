# Generated for Phase 1 residency lifecycle.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0021_booking_deposit_foundation"),
    ]

    operations = [
        migrations.AddField(
            model_name="nguoithue",
            name="trang_thai_luu_tru",
            field=models.CharField(
                choices=[
                    ("dang_o", "Đang ở"),
                    ("tam_vang", "Tạm vắng"),
                    ("da_tra_phong", "Đã trả phòng"),
                ],
                default="dang_o",
                max_length=20,
            ),
        ),
    ]
