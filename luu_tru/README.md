# Luu tru artifact

Thu muc nay chi chua file sinh ra trong qua trinh backup, kiem thu va QA.

- `ban_sao_luu/`: ban sao source, media hoac database; giu nguyen ten goi goc.
- `kiem_thu/`: anh chup, JSON ket qua va snapshot phuc vu doi chieu UI.
- `tam/`: file tam co the tao lai; khong dat source hoac du lieu can bao toan tai day.

Chay Django tren Windows qua `tools/run_django.ps1` de han che cache va file tam trong
cay source. Tao backup moi qua `tools/backup_project.ps1` de output duoc ghi truc tiep
vao `luu_tru/ban_sao_luu/`.
