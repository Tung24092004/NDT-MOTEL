from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0028_lichsuravao_structured_result"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hoadon",
            name="trang_thai",
            field=models.CharField(
                choices=[
                    ("draft", "Bản nháp"),
                    ("chua_thanh_toan", "Chưa thanh toán"),
                    ("cho_xac_nhan", "Chờ xác nhận"),
                    ("da_thanh_toan", "Đã thanh toán"),
                    ("qua_han", "Quá hạn"),
                    ("huy", "Đã hủy"),
                ],
                default="chua_thanh_toan",
                max_length=20,
            ),
        ),
    ]
