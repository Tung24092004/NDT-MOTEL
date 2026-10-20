from django.db import migrations, models


def backfill_structured_access_result(apps, schema_editor):
    LichSuRaVao = apps.get_model("core", "LichSuRaVao")

    LichSuRaVao.objects.filter(
        ghi_chu__startswith="[CHO PHÉP]"
    ).update(ket_qua="cho_phep")
    LichSuRaVao.objects.filter(
        ghi_chu__startswith="[TỪ CHỐI]"
    ).update(ket_qua="tu_choi")

    # Writer mô phỏng cũ không dùng prefix nhưng có hai thông điệp cố định.
    LichSuRaVao.objects.filter(
        nguon="camera",
        ghi_chu__startswith="Mô phỏng camera: Nhận diện thành công.",
    ).update(ket_qua="cho_phep")
    LichSuRaVao.objects.filter(
        nguon="camera",
        ghi_chu__startswith="Mô phỏng camera: Truy cập bị từ chối.",
    ).update(ket_qua="tu_choi")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0027_phuluchopdong_banchupnguoiocunghopdong_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="lichsuravao",
            name="ket_qua",
            field=models.CharField(
                choices=[
                    ("cho_phep", "Cho phép"),
                    ("tu_choi", "Từ chối"),
                    ("khong_xac_dinh", "Không xác định"),
                ],
                db_index=True,
                default="khong_xac_dinh",
                help_text=(
                    "Kết quả quyết định truy cập có cấu trúc; "
                    "ghi chú chỉ lưu diễn giải."
                ),
                max_length=20,
            ),
        ),
        migrations.RunPython(
            backfill_structured_access_result,
            migrations.RunPython.noop,
        ),
    ]
