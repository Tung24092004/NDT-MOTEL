from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0022_nguoithue_trang_thai_luu_tru"),
    ]

    operations = [
        migrations.AddField(
            model_name="faceprofile",
            name="dong_y_du_lieu_khuon_mat",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="faceprofile",
            name="thoi_diem_dong_y_du_lieu_khuon_mat",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
