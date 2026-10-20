from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0025_private_payment_evidence"),
    ]

    operations = [
        migrations.AddField(
            model_name="nguoiocungphong",
            name="da_xac_minh_boi_admin",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Admin da doi chieu thu cong ho so. Gia tri mac dinh False "
                    "de khong coi du lieu cu la da xac minh."
                ),
            ),
        ),
        migrations.AlterField(
            model_name="nguoiocungphong",
            name="trang_thai",
            field=models.CharField(
                choices=[
                    ("cho_bo_sung", "Chờ bổ sung"),
                    ("cho_xac_minh", "Chờ xác minh"),
                    ("da_xac_minh", "Đã xác minh"),
                    ("dang_o", "Đang ở"),
                    ("da_roi", "Đã rời đi"),
                    ("tu_choi", "Từ chối"),
                ],
                default="dang_o",
                max_length=20,
            ),
        ),
    ]
