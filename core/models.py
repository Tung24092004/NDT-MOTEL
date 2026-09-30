from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from .booking_identifiers import booking_reference, deposit_reference, normalize_cccd


# =========================================================
# 1. CƠ SỞ
# =========================================================

class CoSo(models.Model):

    TRANG_THAI = [
        ("hoat_dong", "Đang hoạt động"),
        ("tam_ngung", "Tạm ngưng"),
        ("dong_cua", "Đã đóng"),
    ]

    ten_co_so = models.CharField(max_length=200)

    dia_chi = models.CharField(max_length=255)

    quan = models.CharField(max_length=100)

    so_dien_thoai = models.CharField(
        max_length=20,
        blank=True
    )

    email = models.EmailField(blank=True)

    nguoi_quan_ly = models.CharField(
        max_length=150,
        blank=True
    )

    sdt_quan_ly = models.CharField(
        max_length=20,
        blank=True
    )

    so_tang = models.PositiveIntegerField(default=1)

    so_phong = models.PositiveIntegerField(default=0)

    tien_ich_chung = models.TextField(
        blank=True,
        help_text="Ví dụ: Wifi, camera, bãi giữ xe, máy giặt..."
    )

    mo_ta = models.TextField(blank=True)

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="hoat_dong"
    )

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cơ sở"
        verbose_name_plural = "Các cơ sở"
        ordering = ["ten_co_so"]

    def __str__(self):
        return self.ten_co_so


# =========================================================
# 2. PHÒNG
# =========================================================

class Phong(models.Model):

    TRANG_THAI = [
        ("trong", "Phòng trống"),
        ("da_dat", "Đã đặt"),
        ("dang_thue", "Đang thuê"),
        ("bao_tri", "Bảo trì"),
    ]

    LOAI_PHONG = [
        ("phong_tieu_chuan", "Phòng tiêu chuẩn"),
        ("phong_cao_cap", "Phòng cao cấp"),
        ("phong_gac_lung", "Phòng có gác"),
        ("can_ho_mini", "Căn hộ mini"),
    ]

    co_so = models.ForeignKey(
        CoSo,
        on_delete=models.CASCADE,
        related_name="phong"
    )

    so_phong = models.CharField(
        max_length=20
    )

    tang = models.PositiveIntegerField(
        default=1
    )

    loai_phong = models.CharField(
        max_length=30,
        choices=LOAI_PHONG,
        default="phong_tieu_chuan"
    )

    gia_thue = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[
            MinValueValidator(0)
        ]
    )

    dien_tich = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[
            MinValueValidator(0)
        ]
    )

    tien_ich = models.TextField(
        blank=True,
        help_text=(
            "Ví dụ: Điều hòa, nóng lạnh, "
            "tủ lạnh, giường..."
        )
    )

    so_nguoi_toi_da = models.PositiveIntegerField(
        default=2
    )

    tien_dien_moi_so = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[
            MinValueValidator(0)
        ]
    )

    tien_nuoc_moi_khoi = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[
            MinValueValidator(0)
        ]
    )

    phi_dich_vu = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[
            MinValueValidator(0)
        ]
    )

    tien_coc_mac_dinh = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[
            MinValueValidator(0)
        ]
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="trong"
    )

    mo_ta = models.TextField(
        blank=True
    )

    ngay_tao = models.DateTimeField(
        auto_now_add=True
    )

    ngay_cap_nhat = models.DateTimeField(
        auto_now=True
    )

    # =====================================================
    # SỐ NGƯỜI ĐANG Ở
    # =====================================================

    @property
    def so_nguoi_dang_o(self):
        """
        Số người hiện đang ở trong phòng.

        Bao gồm:
        - Người thuê chính
        - Người ở cùng có trạng thái đang ở
        """

        hop_dong = (
            self.hop_dong_dang_hieu_luc()
        )

        if not hop_dong:
            return 0

        so_nguoi = 1

        so_nguoi += (
            hop_dong.nguoi_o_cung
            .filter(
                trang_thai="dang_o"
            )
            .count()
        )

        return so_nguoi

    # =====================================================
    # SỐ CHỖ CÒN LẠI
    # =====================================================

    @property
    def so_cho_con_lai(self):

        return max(
            (
                self.so_nguoi_toi_da
                - self.so_nguoi_dang_o
            ),
            0
        )

    # =====================================================
    # HỢP ĐỒNG ĐANG HIỆU LỰC
    # =====================================================

    def hop_dong_dang_hieu_luc(self):

        dat_phong = (
            self.dat_phong
            .filter(
                trang_thai="da_duyet",
                hop_dong__trang_thai__in=[
                    "dang_hieu_luc",
                    "sap_het_han",
                ],
            )
            .select_related(
                "hop_dong"
            )
            .first()
        )

        if dat_phong:
            return dat_phong.hop_dong

        return None

    # =====================================================
    # XÁC ĐỊNH TRẠNG THÁI NGHIỆP VỤ
    # =====================================================

    def trang_thai_nghiep_vu(self):
        """
        Xác định trạng thái phòng dựa trên dữ liệu nghiệp vụ.

        1. Có hợp đồng đang hiệu lực / sắp hết hạn
           -> đang thuê

        2. Có đơn đã duyệt nhưng chưa có hợp đồng
           hoặc hợp đồng đang chờ hiệu lực
           -> đã đặt

        3. Không còn dữ liệu giữ phòng
           -> phòng trống

        Trạng thái bảo trì được xử lý riêng.
        """

        # -------------------------------------------------
        # 1. ĐANG THUÊ
        # -------------------------------------------------

        co_hop_dong_dang_thue = (
            self.dat_phong
            .filter(
                trang_thai="da_duyet",
                hop_dong__trang_thai__in=[
                    "dang_hieu_luc",
                    "sap_het_han",
                ],
            )
            .exists()
        )

        if co_hop_dong_dang_thue:
            return "dang_thue"

        # -------------------------------------------------
        # 2. ĐÃ DUYỆT NHƯNG CHƯA CÓ HỢP ĐỒNG
        # -------------------------------------------------

        co_dat_phong_chua_hop_dong = (
            self.dat_phong
            .filter(
                trang_thai="da_duyet",
                hop_dong__isnull=True,
            )
            .exists()
        )

        if co_dat_phong_chua_hop_dong:
            return "da_dat"

        # -------------------------------------------------
        # 3. HỢP ĐỒNG CHỜ HIỆU LỰC
        # -------------------------------------------------

        co_hop_dong_cho_hieu_luc = (
            self.dat_phong
            .filter(
                trang_thai="da_duyet",
                hop_dong__trang_thai=
                    "cho_hieu_luc",
            )
            .exists()
        )

        if co_hop_dong_cho_hieu_luc:
            return "da_dat"

        # -------------------------------------------------
        # 4. PHÒNG TRỐNG
        # -------------------------------------------------

        return "trong"

    # =====================================================
    # ĐỒNG BỘ TRẠNG THÁI PHÒNG
    # =====================================================

    def dong_bo_trang_thai(
        self,
        giu_bao_tri=True
    ):
        """
        Đồng bộ trường trang_thai
        với dữ liệu nghiệp vụ.

        Bảo trì chỉ được giữ lại khi:
        - không có hợp đồng đang thuê
        - không có đặt phòng đang giữ chỗ
        """

        trang_thai_dung = (
            self.trang_thai_nghiep_vu()
        )

        # -------------------------------------------------
        # GIỮ BẢO TRÌ NẾU PHÒNG THỰC SỰ TRỐNG
        # -------------------------------------------------

        if (
            giu_bao_tri
            and self.trang_thai == "bao_tri"
            and trang_thai_dung == "trong"
        ):
            return self.trang_thai

        # -------------------------------------------------
        # ĐỒNG BỘ
        # -------------------------------------------------

        if (
            self.trang_thai
            != trang_thai_dung
        ):

            self.trang_thai = (
                trang_thai_dung
            )

            self.save(
                update_fields=[
                    "trang_thai",
                    "ngay_cap_nhat",
                ]
            )

        return self.trang_thai

    # =====================================================
    # ẢNH PHÒNG
    # =====================================================

    @property
    def anh_dai_dien(self):
        """
        Trả về ảnh đại diện của phòng.

        Quy tắc:
        - Ưu tiên ảnh được đánh dấu là ảnh đại diện.
        - Nếu chưa chọn ảnh đại diện, dùng ảnh đầu tiên theo thứ tự.
        - Nếu phòng chưa có ảnh, trả về None.
        """

        anh = (
            self.hinh_anh
            .filter(la_anh_dai_dien=True)
            .order_by("thu_tu", "id")
            .first()
        )

        if anh:
            return anh

        return (
            self.hinh_anh
            .order_by("thu_tu", "id")
            .first()
        )

    @property
    def co_hinh_anh(self):
        """Cho template kiểm tra nhanh phòng đã có ảnh hay chưa."""

        return self.hinh_anh.exists()

    @property
    def gallery_hien_thi(self):
        """Gallery rieng, gallery phong mau cung loai, hoac danh sach rong."""
        from core.dich_vu.gallery_phong import gallery_hien_thi

        return gallery_hien_thi(self)

    @property
    def anh_dai_dien_hien_thi(self):
        """Anh dai dien thuc te sau khi ap dung gallery dung chung."""
        from core.dich_vu.gallery_phong import anh_dai_dien_hien_thi

        return anh_dai_dien_hien_thi(self)

    # =====================================================
    # META
    # =====================================================

    class Meta:

        verbose_name = "Phòng"
        verbose_name_plural = "Các phòng"

        ordering = [
            "co_so",
            "tang",
            "so_phong",
        ]

        # Chỉ cấm trùng số phòng
        # TRONG CÙNG MỘT CƠ SỞ.
        #
        # Ví dụ:
        # Cơ sở A - 102
        # Cơ sở B - 102
        # => HỢP LỆ.
        #
        # Cơ sở A - 102
        # Cơ sở A - 102
        # => KHÔNG HỢP LỆ.

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "co_so",
                    "so_phong",
                ],
                name=(
                    "unique_so_phong_"
                    "trong_co_so"
                )
            )
        ]

    def __str__(self):

        return (
            f"{self.co_so.ten_co_so} "
            f"- Phòng {self.so_phong}"
        )
# =========================================================
# 3. HÌNH ẢNH PHÒNG
# =========================================================

class HinhAnhPhong(models.Model):
    """
    Thư viện ảnh của một phòng.

    Một phòng có thể có nhiều ảnh. Ảnh đại diện được dùng thống nhất
    tại Trang chủ, Tìm phòng và các vị trí cần thumbnail. Toàn bộ ảnh
    được dùng làm gallery tại trang Chi tiết phòng.
    """

    phong = models.ForeignKey(
        Phong,
        on_delete=models.CASCADE,
        related_name="hinh_anh"
    )

    anh = models.ImageField(
        upload_to="phong/%Y/%m/",
    )

    mo_ta = models.CharField(
        max_length=255,
        blank=True
    )

    la_anh_dai_dien = models.BooleanField(
        default=False
    )

    thu_tu = models.PositiveIntegerField(
        default=0
    )

    ngay_tao = models.DateTimeField(
        auto_now_add=True
    )

    ngay_cap_nhat = models.DateTimeField(
        auto_now=True
    )

    def save(self, *args, **kwargs):
        """
        Bảo đảm mỗi phòng chỉ có một ảnh được đánh dấu đại diện.

        Nếu đây là ảnh đầu tiên của phòng thì tự động đặt làm đại diện.
        Khi chọn một ảnh mới làm đại diện, các ảnh còn lại tự bỏ cờ.
        """

        if not self.pk and not self.phong.hinh_anh.exists():
            self.la_anh_dai_dien = True

        super().save(*args, **kwargs)

        if self.la_anh_dai_dien:
            (
                HinhAnhPhong.objects
                .filter(phong=self.phong)
                .exclude(pk=self.pk)
                .update(la_anh_dai_dien=False)
            )

    def delete(self, *args, **kwargs):
        """
        Nếu xóa ảnh đại diện, tự chọn ảnh còn lại đầu tiên làm đại diện.
        """

        phong = self.phong
        dang_la_dai_dien = self.la_anh_dai_dien

        super().delete(*args, **kwargs)

        if dang_la_dai_dien:
            anh_thay_the = (
                phong.hinh_anh
                .order_by("thu_tu", "id")
                .first()
            )

            if anh_thay_the:
                anh_thay_the.la_anh_dai_dien = True
                anh_thay_the.save(
                    update_fields=[
                        "la_anh_dai_dien",
                        "ngay_cap_nhat",
                    ]
                )

    class Meta:
        verbose_name = "Hình ảnh phòng"
        verbose_name_plural = "Hình ảnh phòng"
        ordering = [
            "phong",
            "thu_tu",
            "id",
        ]

    def __str__(self):
        return (
            f"{self.phong.co_so.ten_co_so} - "
            f"Phòng {self.phong.so_phong} - Ảnh {self.id}"
        )


# =========================================================
# 4. NGƯỜI THUÊ / TÀI KHOẢN
# =========================================================

class NguoiThue(models.Model):

    GIOI_TINH = [
        ("nam", "Nam"),
        ("nu", "Nữ"),
        ("khac", "Khác"),
    ]

    tai_khoan = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="nguoi_thue"
    )

    ho_ten = models.CharField(max_length=150)

    ngay_sinh = models.DateField(
        null=True,
        blank=True
    )

    gioi_tinh = models.CharField(
        max_length=10,
        choices=GIOI_TINH,
        blank=True
    )

    so_dien_thoai = models.CharField(max_length=20)

    email = models.EmailField(blank=True)

    # CCCD là định danh duy nhất.
    # Họ tên KHÔNG unique.
    cccd = models.CharField(
        max_length=20,
        unique=True
    )

    ngay_cap_cccd = models.DateField(
        null=True,
        blank=True
    )

    noi_cap_cccd = models.CharField(
        max_length=200,
        blank=True
    )

    que_quan = models.CharField(
        max_length=200,
        blank=True
    )

    dia_chi_thuong_tru = models.CharField(
        max_length=255,
        blank=True
    )

    nghe_nghiep = models.CharField(
        max_length=100,
        blank=True
    )

    nguoi_lien_he = models.CharField(
        max_length=150,
        blank=True
    )

    sdt_nguoi_lien_he = models.CharField(
        max_length=20,
        blank=True
    )

    ghi_chu = models.TextField(blank=True)

    dang_hoat_dong = models.BooleanField(default=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Người thuê"
        verbose_name_plural = "Người thuê"
        ordering = ["-ngay_tao"]

    def __str__(self):
        return self.ho_ten


# =========================================================
# 4. ĐẶT PHÒNG
# =========================================================

class DatPhong(models.Model):

    so_nguoi_o = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    dong_y_nhan_yeu_cau_ghep = models.BooleanField(default=False)
    gia_thue_thang_tai_thoi_diem_dat = models.DecimalField(
        max_digits=12, decimal_places=0, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    snapshot_gia_la_backfill = models.BooleanField(default=False)
    da_dong_y_dieu_khoan = models.BooleanField(default=False)
    thoi_diem_dong_y_dieu_khoan = models.DateTimeField(null=True, blank=True)
    noi_dung_dieu_khoan_snapshot = models.TextField(blank=True)
    ty_le_hoan_coc_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    han_thanh_toan_coc = models.DateTimeField(null=True, blank=True, db_index=True)
    ma_yeu_cau = models.CharField(max_length=34, unique=True, default=booking_reference, editable=False)

    def clean(self):
        super().clean()
        if self.so_nguoi_o < 1 or self.so_nguoi_o > self.phong.so_nguoi_toi_da:
            raise ValidationError({'so_nguoi_o': 'So nguoi khong phu hop suc chua phong.'})
        if self.so_thang_thue is not None and not 1 <= self.so_thang_thue <= 36:
            raise ValidationError({'so_thang_thue': 'Thoi han thue phai tu 1 den 36 thang.'})
        if self.da_dong_y_dieu_khoan and (
            not self.noi_dung_dieu_khoan_snapshot.strip()
            or not self.thoi_diem_dong_y_dieu_khoan
            or self.ty_le_hoan_coc_snapshot is None
        ):
            raise ValidationError('Dong y dieu khoan can noi dung, thoi diem va ty le hoan coc.')

    TRANG_THAI = [
        ("cho_duyet", "Chờ duyệt"),
        ("da_duyet", "Đã duyệt"),
        ("tu_choi", "Từ chối"),
        ("da_huy", "Đã hủy"),
    ]

    nguoi_thue = models.ForeignKey(
        NguoiThue,
        on_delete=models.CASCADE,
        related_name="dat_phong"
    )

    phong = models.ForeignKey(
        Phong,
        on_delete=models.CASCADE,
        related_name="dat_phong"
    )

    ngay_dat = models.DateTimeField(
        auto_now_add=True
    )

    ngay_nhan_phong = models.DateField()
    so_thang_thue = models.PositiveSmallIntegerField(
    null=True,
    blank=True,
    verbose_name="Thời hạn thuê",
    help_text="Số tháng thuê do người thuê lựa chọn khi đặt phòng"
)

    ngay_tra_du_kien = models.DateField(
        null=True,
        blank=True
    )

    tien_coc_du_kien = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[
            MinValueValidator(0)
        ]
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="cho_duyet"
    )

    ly_do_tu_choi = models.TextField(
        blank=True
    )

    ghi_chu = models.TextField(
        blank=True
    )

    ngay_cap_nhat = models.DateTimeField(
        auto_now=True
    )

    ngay_duyet = models.DateTimeField(
        null=True,
        blank=True
    )

    ngay_tu_choi = models.DateTimeField(
        null=True,
        blank=True
    )

    ngay_huy = models.DateTimeField(
        null=True,
        blank=True
    )

    nguoi_xu_ly = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dat_phong_da_xu_ly"
    )

    # =====================================================
    # META
    # =====================================================

    class Meta:
        verbose_name = "Đặt phòng"
        verbose_name_plural = "Đặt phòng"
        constraints = [
            models.CheckConstraint(check=models.Q(so_nguoi_o__gte=1), name='booking_people_positive'),
            models.CheckConstraint(check=models.Q(gia_thue_thang_tai_thoi_diem_dat__gte=0) | models.Q(gia_thue_thang_tai_thoi_diem_dat__isnull=True), name='booking_rent_nonnegative'),
            models.CheckConstraint(check=models.Q(tien_coc_du_kien__gte=0), name='booking_deposit_nonnegative'),
            models.CheckConstraint(check=models.Q(ty_le_hoan_coc_snapshot__range=(0, 100)) | models.Q(ty_le_hoan_coc_snapshot__isnull=True), name='booking_refund_percentage'),
            models.CheckConstraint(check=models.Q(da_dong_y_dieu_khoan=False) | (models.Q(thoi_diem_dong_y_dieu_khoan__isnull=False, ty_le_hoan_coc_snapshot__isnull=False) & ~models.Q(noi_dung_dieu_khoan_snapshot='')), name='booking_terms_evidence'),
        ]
        ordering = [
            "-ngay_dat"
        ]

    # =====================================================
    # HIỂN THỊ
    # =====================================================

    def __str__(self):

        return (
            f"{self.nguoi_thue.ho_ten} "
            f"- {self.phong.so_phong}"
        )

    # =====================================================
    # SAVE
    # =====================================================

    def save(self, *args, **kwargs):
        """
        Lưu yêu cầu đặt phòng.

        Chức năng:
        - Tự ghi thời gian duyệt / từ chối / hủy.
        - Bảo đảm các timestamp được lưu khi view sử dụng
          update_fields.
        - Sau khi DatPhong thay đổi, trạng thái phòng được
          đồng bộ tập trung bằng Phong.dong_bo_trang_thai().

        DatPhong KHÔNG tự gán trực tiếp:
            phong.trang_thai = "da_dat"
            phong.trang_thai = "trong"

        vì trạng thái phòng còn phụ thuộc vào hợp đồng.
        """

        # -------------------------------------------------
        # UPDATE_FIELDS
        # -------------------------------------------------

        update_fields = kwargs.get(
            "update_fields"
        )

        if update_fields is not None:

            update_fields = set(
                update_fields
            )

            # auto_now sẽ chỉ được cập nhật nếu field
            # nằm trong update_fields
            update_fields.add(
                "ngay_cap_nhat"
            )

        # -------------------------------------------------
        # NGÀY DUYỆT
        # -------------------------------------------------

        if (
            self.trang_thai == "da_duyet"
            and self.ngay_duyet is None
        ):

            self.ngay_duyet = timezone.now()

            if update_fields is not None:
                update_fields.add(
                    "ngay_duyet"
                )

        # -------------------------------------------------
        # NGÀY TỪ CHỐI
        # -------------------------------------------------

        if (
            self.trang_thai == "tu_choi"
            and self.ngay_tu_choi is None
        ):

            self.ngay_tu_choi = timezone.now()

            if update_fields is not None:
                update_fields.add(
                    "ngay_tu_choi"
                )

        # -------------------------------------------------
        # NGÀY HỦY
        # -------------------------------------------------

        if (
            self.trang_thai == "da_huy"
            and self.ngay_huy is None
        ):

            self.ngay_huy = timezone.now()

            if update_fields is not None:
                update_fields.add(
                    "ngay_huy"
                )

        # -------------------------------------------------
        # CẬP NHẬT LẠI UPDATE_FIELDS
        # -------------------------------------------------

        if update_fields is not None:

            kwargs["update_fields"] = list(
                update_fields
            )

        # -------------------------------------------------
        # LƯU DATPHONG
        # -------------------------------------------------

        super().save(
            *args,
            **kwargs
        )

        # -------------------------------------------------
        # ĐỒNG BỘ TRẠNG THÁI PHÒNG
        # -------------------------------------------------
        #
        # Không tự quyết định phòng là:
        #   - trống
        #   - đã đặt
        #   - đang thuê
        #
        # Phong sẽ kiểm tra cả:
        #   DatPhong
        #   HopDong
        #   trạng thái bảo trì
        #
        # rồi mới quyết định.
        # -------------------------------------------------

        self.phong.dong_bo_trang_thai()


class KhaiBaoNguoiOCungDatPhong(models.Model):
    TRANG_THAI = [(value, value) for value in ('cho_xac_minh', 'da_xac_minh', 'tu_choi', 'da_huy')]
    dat_phong = models.ForeignKey(DatPhong, on_delete=models.PROTECT, related_name='nguoi_di_cung_khai_bao')
    ho_ten = models.CharField(max_length=150)
    ngay_sinh = models.DateField(null=True, blank=True)
    gioi_tinh = models.CharField(max_length=10, choices=NguoiThue.GIOI_TINH, blank=True)
    cccd = models.CharField(max_length=12)
    so_dien_thoai = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    quan_he = models.CharField(max_length=50, blank=True)
    ghi_chu = models.TextField(blank=True)
    trang_thai_xac_minh = models.CharField(max_length=20, choices=TRANG_THAI, default='cho_xac_minh')
    ly_do_tu_choi = models.TextField(blank=True)
    ngay_tao = models.DateTimeField(auto_now_add=True)
    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        self.cccd = normalize_cccd(self.cccd)
        if len(self.cccd) != 12 or not self.cccd.isascii() or not self.cccd.isdigit():
            raise ValidationError({'cccd': 'CCCD phai gom 12 chu so.'})
        if self.cccd == normalize_cccd(self.dat_phong.nguoi_thue.cccd):
            raise ValidationError({'cccd': 'Khong khai bao lai nguoi thue chinh.'})
        if self.ngay_sinh and self.ngay_sinh > timezone.localdate():
            raise ValidationError({'ngay_sinh': 'Ngay sinh khong o tuong lai.'})
        if self.trang_thai_xac_minh in ('cho_xac_minh', 'da_xac_minh'):
            count = type(self).objects.filter(dat_phong_id=self.dat_phong_id,
                trang_thai_xac_minh__in=('cho_xac_minh', 'da_xac_minh')).exclude(pk=self.pk).count()
            limit = min(self.dat_phong.so_nguoi_o, self.dat_phong.phong.so_nguoi_toi_da)
            if count + 2 > limit:
                raise ValidationError('So nguoi khai bao vuot so nguoi da chon/suc chua.')

    def save(self, *args, **kwargs):
        self.cccd = normalize_cccd(self.cccd)
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('dat_phong', 'cccd'), name='booking_companion_identity')]
        indexes = [models.Index(fields=('dat_phong', 'trang_thai_xac_minh'), name='booking_companion_status')]

    def __str__(self):
        return f'{self.ho_ten} - {self.dat_phong.ma_yeu_cau}'


class ThanhToanCocDatPhong(models.Model):
    ACTIVE_STATES = ('chua_thanh_toan', 'cho_xac_nhan', 'da_xac_nhan')
    TRANG_THAI = [(value, value) for value in (*ACTIVE_STATES, 'tu_choi', 'da_huy', 'da_hoan_tien')]
    dat_phong = models.ForeignKey(DatPhong, on_delete=models.PROTECT, related_name='giao_dich_coc')
    so_tien = models.DecimalField(max_digits=12, decimal_places=0, validators=[MinValueValidator(0)])
    phuong_thuc = models.CharField(max_length=20, choices=[('chuyen_khoan', 'Chuyen khoan'), ('tien_mat', 'Tien mat')], default='chuyen_khoan')
    ma_tham_chieu = models.CharField(max_length=35, unique=True, default=deposit_reference, editable=False)
    noi_dung_chuyen_khoan = models.CharField(max_length=80, unique=True, editable=False)
    ma_giao_dich = models.CharField(max_length=100, blank=True)
    trang_thai = models.CharField(max_length=20, choices=TRANG_THAI, default='chua_thanh_toan')
    # NULL permits historical attempts; slot 1 is reserved for the active attempt.
    active_slot = models.PositiveSmallIntegerField(null=True, blank=True, default=1, editable=False)
    thoi_diem_user_bao_da_thanh_toan = models.DateTimeField(null=True, blank=True)
    thoi_diem_admin_xac_nhan = models.DateTimeField(null=True, blank=True)
    nguoi_xac_nhan = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='giao_dich_coc_da_xac_nhan')
    ly_do_tu_choi = models.TextField(blank=True)
    ghi_chu = models.TextField(blank=True)
    ngay_tao = models.DateTimeField(auto_now_add=True)
    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if not self.ma_tham_chieu.strip():
            raise ValidationError('Giao dich can ma tham chieu.')
        if self.so_tien != self.dat_phong.tien_coc_du_kien:
            raise ValidationError({'so_tien': 'Tien coc phai lay tu snapshot dat phong.'})
        if self.trang_thai == 'cho_xac_nhan' and not self.thoi_diem_user_bao_da_thanh_toan:
            raise ValidationError('Can thoi diem User bao thanh toan.')
        if self.trang_thai == 'da_xac_nhan' and not self.thoi_diem_admin_xac_nhan:
            raise ValidationError('Can thoi diem Admin xac nhan.')

    def save(self, *args, **kwargs):
        self.active_slot = 1 if self.trang_thai in self.ACTIVE_STATES else None
        if not self.noi_dung_chuyen_khoan:
            self.noi_dung_chuyen_khoan = f'NDTMOTEL COC {self.dat_phong.ma_yeu_cau} {self.ma_tham_chieu[-8:]}'
        self.full_clean()
        return super().save(*args, **kwargs)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=('dat_phong', 'active_slot'), name='booking_one_active_deposit'),
            models.CheckConstraint(check=models.Q(so_tien__gte=0), name='deposit_amount_nonnegative'),
            models.CheckConstraint(check=~models.Q(ma_tham_chieu=''), name='deposit_reference_present'),
            models.CheckConstraint(check=(models.Q(trang_thai__in=('chua_thanh_toan', 'cho_xac_nhan', 'da_xac_nhan'), active_slot=1) & models.Q(active_slot__isnull=False)) | models.Q(trang_thai__in=('tu_choi', 'da_huy', 'da_hoan_tien'), active_slot__isnull=True), name='deposit_active_slot_consistent'),
            models.CheckConstraint(check=~models.Q(trang_thai='cho_xac_nhan') | models.Q(thoi_diem_user_bao_da_thanh_toan__isnull=False), name='deposit_report_time_required'),
            models.CheckConstraint(check=~models.Q(trang_thai='da_xac_nhan') | models.Q(thoi_diem_admin_xac_nhan__isnull=False), name='deposit_confirmation_time'),
        ]
        indexes = [models.Index(fields=('dat_phong', 'trang_thai'), name='booking_deposit_status')]

    def __str__(self):
        return self.ma_tham_chieu

# =========================================================
# 5. HỢP ĐỒNG
# =========================================================

class HopDong(models.Model):

    TRANG_THAI = [
        ("cho_hieu_luc", "Chờ hiệu lực"),
        ("dang_hieu_luc", "Đang hiệu lực"),
        ("sap_het_han", "Sắp hết hạn"),
        ("da_het_han", "Đã hết hạn"),
        ("da_huy", "Đã hủy"),
    ]

    dat_phong = models.OneToOneField(
        DatPhong,
        on_delete=models.CASCADE,
        related_name="hop_dong"
    )

    so_hop_dong = models.CharField(
        max_length=50,
        unique=True
    )

    ngay_bat_dau = models.DateField()

    ngay_ket_thuc = models.DateField()

    tien_coc = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    tien_thue_thang = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(0)]
    )

    ngay_thanh_toan_hang_thang = models.PositiveIntegerField(
        default=5,
        help_text="Ngày thanh toán tiền phòng hàng tháng"
    )

    phuong_thuc_thanh_toan = models.CharField(
        max_length=50,
        choices=[
            ("tien_mat", "Tiền mặt"),
            ("chuyen_khoan", "Chuyển khoản"),
        ],
        default="chuyen_khoan"
    )

    so_nguoi_o = models.PositiveIntegerField(default=1)

    cho_phep_ghep = models.BooleanField(
        default=False,
        verbose_name="Cho phép ở ghép",
        help_text="Cho phép người khác đăng ký vào ở cùng phòng"
    )

    tien_phat_tre_han = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    dieu_khoan = models.TextField(blank=True)

    ghi_chu = models.TextField(blank=True)

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="cho_hieu_luc"
    )

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    ngay_ky = models.DateTimeField(
        null=True,
        blank=True
    )

    ngay_huy = models.DateTimeField(
        null=True,
        blank=True
    )

    ly_do_huy = models.TextField(blank=True)

    nguoi_tao = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hop_dong_da_tao"
    )

    nguoi_cap_nhat = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hop_dong_da_cap_nhat"
    )

    class Meta:
        verbose_name = "Hợp đồng"
        verbose_name_plural = "Hợp đồng"
        ordering = ["-ngay_tao"]

    def __str__(self):
        return (
            f"{self.so_hop_dong} - "
            f"{self.dat_phong.nguoi_thue.ho_ten}"
        )

    @property
    def so_ngay_con_lai(self):
        if not self.ngay_ket_thuc:
            return None

        return (self.ngay_ket_thuc - timezone.localdate()).days

    @property
    def da_het_han(self):
        return (
            self.ngay_ket_thuc
            and self.ngay_ket_thuc < timezone.localdate()
        )


# =========================================================
# 5A. LỊCH SỬ HỢP ĐỒNG
# =========================================================

class LichSuHopDong(models.Model):

    HANH_DONG = [
        ("tao", "Tạo hợp đồng"),
        ("cap_nhat", "Cập nhật"),
        ("ky", "Xác nhận ký"),
        ("kich_hoat", "Kích hoạt"),
        ("sap_het_han", "Chuyển sang sắp hết hạn"),
        ("het_han", "Hết hạn"),
        ("gia_han", "Gia hạn"),
        ("huy", "Hủy hợp đồng"),
        ("khoi_phuc", "Khôi phục"),
    ]

    hop_dong = models.ForeignKey(
        HopDong,
        on_delete=models.CASCADE,
        related_name="lich_su"
    )

    hanh_dong = models.CharField(
        max_length=30,
        choices=HANH_DONG
    )

    trang_thai_cu = models.CharField(
        max_length=30,
        blank=True
    )

    trang_thai_moi = models.CharField(
        max_length=30,
        blank=True
    )

    noi_dung = models.TextField(blank=True)

    nguoi_thuc_hien = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_hop_dong"
    )

    thoi_diem = models.DateTimeField(
        auto_now_add=True
    )

    dia_chi_ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Lịch sử hợp đồng"
        verbose_name_plural = "Lịch sử hợp đồng"
        ordering = ["-thoi_diem"]

    def __str__(self):
        return (
            f"{self.hop_dong.so_hop_dong} - "
            f"{self.get_hanh_dong_display()} - "
            f"{self.thoi_diem.strftime('%d/%m/%Y %H:%M:%S')}"
        )


# =========================================================
# 5B. YÊU CẦU GHÉP NGƯỜI
# =========================================================

class YeuCauGhepNguoi(models.Model):

    TRANG_THAI = [
        ("cho_duyet", "Chờ duyệt"),
        ("da_duyet", "Đã duyệt"),
        ("tu_choi", "Từ chối"),
        ("da_huy", "Đã hủy"),
    ]

    GIOI_TINH = [
        ("nam", "Nam"),
        ("nu", "Nữ"),
        ("khac", "Khác"),
    ]

    hop_dong = models.ForeignKey(
        HopDong,
        on_delete=models.CASCADE,
        related_name="yeu_cau_ghep"
    )

    nguoi_dang_ky = models.ForeignKey(
        NguoiThue,
        on_delete=models.CASCADE,
        related_name="yeu_cau_ghep"
    )

    ho_ten = models.CharField(max_length=150)

    ngay_sinh = models.DateField(
        null=True,
        blank=True
    )

    gioi_tinh = models.CharField(
        max_length=10,
        choices=GIOI_TINH,
        blank=True
    )

    cccd = models.CharField(
        max_length=20,
        blank=True
    )

    so_dien_thoai = models.CharField(
        max_length=20,
        blank=True
    )

    quan_he = models.CharField(
        max_length=50,
        blank=True,
        help_text="Ví dụ: bạn, anh/chị/em, đồng nghiệp..."
    )

    ngay_du_kien_vao = models.DateField()

    ly_do = models.TextField(blank=True)

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="cho_duyet"
    )

    ly_do_tu_choi = models.TextField(blank=True)

    ghi_chu_admin = models.TextField(blank=True)

    ngay_xu_ly = models.DateTimeField(
        null=True,
        blank=True
    )

    nguoi_xu_ly = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="yeu_cau_ghep_da_xu_ly"
    )

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Yêu cầu ghép người"
        verbose_name_plural = "Yêu cầu ghép người"
        ordering = ["-ngay_tao"]

    def __str__(self):
        phong = self.hop_dong.dat_phong.phong.so_phong

        return (
            f"{self.ho_ten} - "
            f"Phòng {phong} - "
            f"{self.get_trang_thai_display()}"
        )

    @property
    def phong(self):
        return self.hop_dong.dat_phong.phong

# =========================================================
# 5C. YÊU CẦU GIA HẠN HỢP ĐỒNG
# =========================================================

class YeuCauGiaHanHopDong(models.Model):

    TRANG_THAI = [
        ("cho_duyet", "Chờ duyệt"),
        ("da_duyet", "Đã duyệt"),
        ("tu_choi", "Từ chối"),
        ("da_huy", "Đã hủy"),
    ]

    hop_dong = models.ForeignKey(
        HopDong,
        on_delete=models.CASCADE,
        related_name="yeu_cau_gia_han"
    )

    nguoi_yeu_cau = models.ForeignKey(
        NguoiThue,
        on_delete=models.CASCADE,
        related_name="yeu_cau_gia_han_hop_dong"
    )

    so_thang_gia_han = models.PositiveIntegerField(
        help_text="Số tháng người thuê đề nghị gia hạn"
    )

    ngay_ket_thuc_cu = models.DateField(
        help_text="Ngày kết thúc hợp đồng trước khi gia hạn"
    )

    ngay_ket_thuc_de_xuat = models.DateField(
        help_text="Ngày kết thúc dự kiến nếu yêu cầu được duyệt"
    )

    ly_do = models.TextField(
        blank=True,
        help_text="Lý do hoặc ghi chú của người thuê"
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="cho_duyet"
    )

    ly_do_tu_choi = models.TextField(
        blank=True
    )

    ghi_chu_admin = models.TextField(
        blank=True
    )

    ngay_xu_ly = models.DateTimeField(
        null=True,
        blank=True
    )

    nguoi_xu_ly = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="yeu_cau_gia_han_da_xu_ly"
    )

    ngay_tao = models.DateTimeField(
        auto_now_add=True
    )

    ngay_cap_nhat = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        verbose_name = "Yêu cầu gia hạn hợp đồng"
        verbose_name_plural = "Yêu cầu gia hạn hợp đồng"
        ordering = ["-ngay_tao"]

    def __str__(self):
        return (
            f"{self.hop_dong.so_hop_dong} - "
            f"{self.nguoi_yeu_cau.ho_ten} - "
            f"{self.get_trang_thai_display()}"
        )
# =========================================================
# 6. HÓA ĐƠN / THANH TOÁN
# =========================================================

class HoaDon(models.Model):

    TRANG_THAI = [
        ("chua_thanh_toan", "Chưa thanh toán"),
        ("cho_xac_nhan", "Chờ xác nhận"),
        ("da_thanh_toan", "Đã thanh toán"),
        ("qua_han", "Quá hạn"),
        ("huy", "Đã hủy"),
    ]

    hop_dong = models.ForeignKey(
        HopDong,
        on_delete=models.CASCADE,
        related_name="hoa_don"
    )

    thang = models.PositiveIntegerField()

    nam = models.PositiveIntegerField()

    tien_phong = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    tien_dien = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    tien_nuoc = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    tien_dich_vu = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    phi_khac = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    chi_tiet_phi = models.TextField(
        blank=True,
        help_text="Mô tả các khoản phí phát sinh"
    )

    han_thanh_toan = models.DateField()

    ngay_thanh_toan = models.DateTimeField(
        null=True,
        blank=True
    )

    phuong_thuc = models.CharField(
        max_length=50,
        choices=[
            ("tien_mat", "Tiền mặt"),
            ("chuyen_khoan", "Chuyển khoản"),
        ],
        blank=True
    )

    ma_giao_dich = models.CharField(
        max_length=100,
        blank=True,
        help_text="Mã giao dịch nếu thanh toán chuyển khoản"
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="chua_thanh_toan"
    )

    ghi_chu = models.TextField(blank=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    nguoi_lap = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hoa_don_da_lap"
    )

    nguoi_xac_nhan = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hoa_don_da_xac_nhan"
    )

    class Meta:
        verbose_name = "Hóa đơn"
        verbose_name_plural = "Hóa đơn"
        ordering = ["-nam", "-thang", "-ngay_tao"]

        constraints = [
            models.UniqueConstraint(
                fields=["hop_dong", "thang", "nam"],
                name="unique_hoa_don_theo_hop_dong_thang_nam"
            )
        ]

    def __str__(self):
        return (
            f"Hóa đơn {self.thang}/{self.nam} - "
            f"{self.hop_dong.so_hop_dong}"
        )

    @property
    def tong_tien(self):
        return (
            self.tien_phong
            + self.tien_dien
            + self.tien_nuoc
            + self.tien_dich_vu
            + self.phi_khac
        )

    @property
    def con_no(self):
        if self.trang_thai == "da_thanh_toan":
            return 0

        return self.tong_tien


# =========================================================
# 6B. LỊCH SỬ THANH TOÁN
# =========================================================

class LichSuThanhToan(models.Model):

    hoa_don = models.ForeignKey(
        HoaDon,
        on_delete=models.CASCADE,
        related_name="lich_su_thanh_toan"
    )

    so_tien = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        validators=[MinValueValidator(0)]
    )

    phuong_thuc = models.CharField(
        max_length=50,
        choices=[
            ("tien_mat", "Tiền mặt"),
            ("chuyen_khoan", "Chuyển khoản"),
        ]
    )

    ma_giao_dich = models.CharField(
        max_length=100,
        blank=True
    )

    noi_dung = models.TextField(blank=True)

    nguoi_thuc_hien = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_thanh_toan"
    )

    thoi_diem = models.DateTimeField(
        auto_now_add=True
    )

    dia_chi_ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Lịch sử thanh toán"
        verbose_name_plural = "Lịch sử thanh toán"
        ordering = ["-thoi_diem"]

    def __str__(self):
        return (
            f"{self.hoa_don} - "
            f"{self.so_tien:,.0f}đ - "
            f"{self.thoi_diem.strftime('%d/%m/%Y %H:%M:%S')}"
        )


# =========================================================
# 7. YÊU CẦU SỬA CHỮA
# =========================================================

class YeuCauSuaChua(models.Model):

    LOAI_SU_CO = [
        ("dien", "Điện"),
        ("nuoc", "Nước"),
        ("thiet_bi", "Thiết bị"),
        ("phong", "Cơ sở vật chất"),
        ("wifi", "Wifi / Internet"),
        ("ve_sinh", "Vệ sinh"),
        ("khac", "Khác"),
    ]

    MUC_DO = [
        ("thap", "Thấp"),
        ("trung_binh", "Trung bình"),
        ("cao", "Cao"),
        ("khan_cap", "Khẩn cấp"),
    ]

    TRANG_THAI = [
        ("moi", "Mới"),
        ("dang_xu_ly", "Đang xử lý"),
        ("cho_thay_the", "Chờ thay thế"),
        ("hoan_thanh", "Hoàn thành"),
        ("tu_choi", "Từ chối"),
    ]

    nguoi_thue = models.ForeignKey(
        NguoiThue,
        on_delete=models.CASCADE,
        related_name="yeu_cau_sua_chua"
    )

    phong = models.ForeignKey(
        Phong,
        on_delete=models.CASCADE,
        related_name="yeu_cau_sua_chua"
    )

    tieu_de = models.CharField(max_length=200)

    noi_dung = models.TextField()

    loai_su_co = models.CharField(
        max_length=20,
        choices=LOAI_SU_CO,
        default="khac"
    )

    muc_do = models.CharField(
        max_length=20,
        choices=MUC_DO,
        default="trung_binh"
    )

    hinh_anh = models.ImageField(
        upload_to="yeu_cau_sua_chua/",
        blank=True,
        null=True
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="moi"
    )

    nguoi_xu_ly = models.CharField(
        max_length=150,
        blank=True
    )

    chi_phi = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    chi_tiet_chi_phi = models.TextField(blank=True)

    ghi_chu_admin = models.TextField(blank=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_bat_dau_xu_ly = models.DateTimeField(
        null=True,
        blank=True
    )

    ngay_hoan_thanh = models.DateTimeField(
        null=True,
        blank=True
    )

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    nguoi_xu_ly_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sua_chua_da_xu_ly"
    )

    class Meta:
        verbose_name = "Yêu cầu sửa chữa"
        verbose_name_plural = "Yêu cầu sửa chữa"
        ordering = ["-ngay_tao"]

    def __str__(self):
        return (
            f"{self.tieu_de} - "
            f"{self.phong.so_phong}"
        )


# =========================================================
# 7B. LỊCH SỬ SỬA CHỮA
# =========================================================

class LichSuSuaChua(models.Model):

    HANH_DONG = [
        ("tao", "Tạo yêu cầu"),
        ("tiep_nhan", "Tiếp nhận"),
        ("xu_ly", "Bắt đầu xử lý"),
        ("cho_thay_the", "Chờ thay thế"),
        ("hoan_thanh", "Hoàn thành"),
        ("tu_choi", "Từ chối"),
        ("cap_nhat", "Cập nhật"),
    ]

    yeu_cau = models.ForeignKey(
        YeuCauSuaChua,
        on_delete=models.CASCADE,
        related_name="lich_su"
    )

    hanh_dong = models.CharField(
        max_length=30,
        choices=HANH_DONG
    )

    trang_thai_cu = models.CharField(
        max_length=30,
        blank=True
    )

    trang_thai_moi = models.CharField(
        max_length=30,
        blank=True
    )

    noi_dung = models.TextField(blank=True)

    nguoi_thuc_hien = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_sua_chua"
    )

    thoi_diem = models.DateTimeField(auto_now_add=True)

    dia_chi_ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Lịch sử sửa chữa"
        verbose_name_plural = "Lịch sử sửa chữa"
        ordering = ["-thoi_diem"]


# =========================================================
# 8. CHÍNH SÁCH HỖ TRỢ
# =========================================================

class ChinhSachHoTro(models.Model):

    DOI_TUONG = [
        ("sinh_vien", "Sinh viên"),
        ("nguoi_lao_dong", "Người lao động"),
        ("ho_gia_dinh", "Hộ gia đình"),
        ("nguoi_cao_tuoi", "Người cao tuổi"),
        ("khach_thue_moi", "Khách thuê mới"),
        ("khach_thue_lau_dai", "Khách thuê lâu dài"),
        ("khac", "Khác"),
    ]

    LOAI_HO_TRO = [
        ("phan_tram", "Theo phần trăm"),
        ("so_tien", "Theo số tiền"),
        ("mien_phi", "Miễn phí"),
    ]

    ten_chinh_sach = models.CharField(max_length=200)

    doi_tuong = models.CharField(
        max_length=30,
        choices=DOI_TUONG,
        default="sinh_vien"
    )

    doi_tuong_khac = models.CharField(
        max_length=200,
        blank=True
    )

    loai_ho_tro = models.CharField(
        max_length=20,
        choices=LOAI_HO_TRO,
        default="phan_tram"
    )

    gia_tri_ho_tro = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    ngan_sach = models.DecimalField(
        max_digits=12,
        decimal_places=0,
        default=0,
        validators=[MinValueValidator(0)]
    )

    so_luong_nguoi_duoc_ap_dung = models.PositiveIntegerField(
        default=0
    )

    ngay_bat_dau = models.DateField()

    ngay_ket_thuc = models.DateField()

    dieu_kien = models.TextField(blank=True)

    trang_thai = models.BooleanField(default=True)

    mo_ta = models.TextField(blank=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    nguoi_tao = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chinh_sach_da_tao"
    )

    class Meta:
        verbose_name = "Chính sách hỗ trợ"
        verbose_name_plural = "Chính sách hỗ trợ"
        ordering = ["-ngay_tao"]

    def __str__(self):
        return self.ten_chinh_sach


# =========================================================
# 9. THÔNG BÁO
# =========================================================

class ThongBao(models.Model):

    LOAI_THONG_BAO = [
        ("thanh_toan", "Thanh toán"),
        ("hop_dong", "Hợp đồng"),
        ("bao_tri", "Bảo trì"),
        ("dat_phong", "Đặt phòng"),
        ("chinh_sach", "Chính sách hỗ trợ"),
        ("smart_room", "Smart Room"),
        ("he_thong", "Hệ thống"),
    ]

    MUC_DO = [
        ("binh_thuong", "Bình thường"),
        ("quan_trong", "Quan trọng"),
        ("khancap", "Khẩn cấp"),
    ]

    nguoi_thue = models.ForeignKey(
        NguoiThue,
        on_delete=models.CASCADE,
        related_name="thong_bao",
        null=True,
        blank=True
    )

    nguoi_nhan_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="thong_bao_he_thong",
        null=True,
        blank=True
    )

    tieu_de = models.CharField(max_length=200)

    noi_dung = models.TextField()

    loai = models.CharField(
        max_length=20,
        choices=LOAI_THONG_BAO,
        default="he_thong"
    )

    muc_do = models.CharField(
        max_length=20,
        choices=MUC_DO,
        default="binh_thuong"
    )

    da_doc = models.BooleanField(default=False)

    ngay_doc = models.DateTimeField(
        null=True,
        blank=True
    )

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    url_lien_ket = models.CharField(
        max_length=500,
        blank=True
    )

    ma_tham_chieu = models.CharField(
        max_length=100,
        blank=True
    )

    class Meta:
        verbose_name = "Thông báo"
        verbose_name_plural = "Thông báo"
        ordering = ["-ngay_tao"]

    def __str__(self):
        if self.nguoi_thue:
            nguoi = self.nguoi_thue.ho_ten
        elif self.nguoi_nhan_user:
            nguoi = self.nguoi_nhan_user.username
        else:
            nguoi = "Hệ thống"

        return f"{self.tieu_de} - {nguoi}"


# =========================================================
# 9B. LỊCH SỬ THÔNG BÁO
# =========================================================

class LichSuThongBao(models.Model):

    thong_bao = models.ForeignKey(
        ThongBao,
        on_delete=models.CASCADE,
        related_name="lich_su"
    )

    hanh_dong = models.CharField(
        max_length=50,
        choices=[
            ("tao", "Tạo thông báo"),
            ("doc", "Đã đọc"),
            ("xem", "Đã xem"),
            ("cap_nhat", "Cập nhật"),
        ]
    )

    nguoi_thuc_hien = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_thong_bao"
    )

    thoi_diem = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lịch sử thông báo"
        verbose_name_plural = "Lịch sử thông báo"
        ordering = ["-thoi_diem"]


# =========================================================
# SMART ROOM — PHASE 1
# =========================================================


# =========================================================
# 10. NGƯỜI Ở CÙNG PHÒNG
# =========================================================

class NguoiOCungPhong(models.Model):

    TRANG_THAI = [
        ("dang_o", "Đang ở"),
        ("da_roi", "Đã rời đi"),
    ]

    GIOI_TINH = [
        ("nam", "Nam"),
        ("nu", "Nữ"),
        ("khac", "Khác"),
    ]

    hop_dong = models.ForeignKey(
        HopDong,
        on_delete=models.CASCADE,
        related_name="nguoi_o_cung"
    )

    ho_ten = models.CharField(max_length=150)

    ngay_sinh = models.DateField(
        null=True,
        blank=True
    )

    gioi_tinh = models.CharField(
        max_length=10,
        choices=GIOI_TINH,
        blank=True
    )

    cccd = models.CharField(
        max_length=20,
        blank=True
    )

    so_dien_thoai = models.CharField(
        max_length=20,
        blank=True
    )

    quan_he = models.CharField(
        max_length=50,
        blank=True
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="dang_o"
    )

    ngay_vao = models.DateField()

    ngay_ra = models.DateField(
        null=True,
        blank=True
    )

    ghi_chu = models.TextField(blank=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Người ở cùng phòng"
        verbose_name_plural = "Người ở cùng phòng"
        ordering = ["-ngay_tao"]

    def __str__(self):
        phong = self.hop_dong.dat_phong.phong.so_phong
        return f"{self.ho_ten} - Phòng {phong}"


# =========================================================
# 11. HỒ SƠ KHUÔN MẶT
# =========================================================

class FaceProfile(models.Model):

    LOAI_CHU_THE = [
        ("nguoi_thue", "Người thuê chính"),
        ("nguoi_o_cung", "Người ở cùng"),
    ]

    TRANG_THAI = [
        ("chua_co_anh", "Chưa có ảnh"),
        ("co_anh", "Đã có ảnh"),
        ("da_xac_thuc", "Đã xác thực"),
        ("bi_vo_hieu", "Bị vô hiệu"),
    ]

    nguoi_thue = models.OneToOneField(
        NguoiThue,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="face_profile"
    )

    nguoi_o_cung = models.OneToOneField(
        NguoiOCungPhong,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="face_profile"
    )

    loai_chu_the = models.CharField(
        max_length=20,
        choices=LOAI_CHU_THE
    )

    anh_dai_dien = models.ImageField(
        upload_to="face_profiles/",
        blank=True,
        null=True
    )

    face_encoding = models.TextField(
        blank=True,
        null=True,
        help_text="Vector đặc trưng khuôn mặt được mã hóa từ SFace."
    )
    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="chua_co_anh"
    )

    ghi_chu = models.TextField(blank=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    def clean(self):

        co_nguoi_thue = bool(self.nguoi_thue_id)

        co_nguoi_o_cung = bool(self.nguoi_o_cung_id)

        if co_nguoi_thue and co_nguoi_o_cung:
            raise ValidationError(
                "FaceProfile chỉ được liên kết với một người "
                "(người thuê chính HOẶC người ở cùng)."
            )

        if not co_nguoi_thue and not co_nguoi_o_cung:
            raise ValidationError(
                "FaceProfile phải liên kết với ít nhất một người."
            )

    class Meta:
        verbose_name = "Hồ sơ khuôn mặt"
        verbose_name_plural = "Hồ sơ khuôn mặt"
        ordering = ["-ngay_tao"]

    def __str__(self):

        if self.nguoi_thue:
            return f"FaceProfile - {self.nguoi_thue.ho_ten}"

        if self.nguoi_o_cung:
            return f"FaceProfile - {self.nguoi_o_cung.ho_ten}"

        return f"FaceProfile #{self.pk}"


# =========================================================
# 12. QUYỀN RA VÀO
# =========================================================

class QuyenRaVao(models.Model):

    NGUON_CAP = [
        ("legacy_unknown", "Chưa xác định nguồn cấp"),
        ("thu_cong", "Cấp thủ công"),
        ("face_id", "Đăng ký Face ID"),
        ("duyet_ghep", "Duyệt ở ghép"),
    ]
    hop_dong = models.ForeignKey(
        HopDong, on_delete=models.PROTECT, null=True, blank=True,
        related_name="quyen_ra_vao_theo_hop_dong",
    )
    nguon_cap = models.CharField(
        max_length=20, choices=NGUON_CAP, default="legacy_unknown",
    )

    LOAI_QUYEN = [
        ("chu_phong", "Chủ phòng (người thuê chính)"),
        ("nguoi_o_cung", "Người ở cùng"),
        ("khach_tam_thoi", "Khách tạm thời"),
    ]

    TRANG_THAI = [
        ("hoat_dong", "Đang hoạt động"),
        ("tam_khoa", "Tạm khóa"),
        ("het_han", "Hết hạn"),
        ("bi_thu_hoi", "Bị thu hồi"),
    ]

    phong = models.ForeignKey(
        Phong,
        on_delete=models.CASCADE,
        related_name="quyen_ra_vao"
    )

    nguoi_thue = models.ForeignKey(
        NguoiThue,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="quyen_ra_vao"
    )

    nguoi_o_cung = models.ForeignKey(
        NguoiOCungPhong,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="quyen_ra_vao"
    )

    loai_quyen = models.CharField(
        max_length=20,
        choices=LOAI_QUYEN
    )

    trang_thai = models.CharField(
        max_length=20,
        choices=TRANG_THAI,
        default="hoat_dong"
    )

    ngay_bat_dau = models.DateField()

    ngay_ket_thuc = models.DateField(
        null=True,
        blank=True
    )

    ma_the = models.CharField(
        max_length=50,
        blank=True,
        help_text="Mã thẻ từ / mã PIN"
    )

    ghi_chu = models.TextField(blank=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)

    ngay_cap_nhat = models.DateTimeField(auto_now=True)

    nguoi_tao = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quyen_ra_vao_da_tao"
    )

    def clean(self):

        co_nguoi_thue = bool(self.nguoi_thue_id)

        co_nguoi_o_cung = bool(self.nguoi_o_cung_id)

        if co_nguoi_thue and co_nguoi_o_cung:
            raise ValidationError(
                "QuyenRaVao chỉ được liên kết với một người."
            )

        if not co_nguoi_thue and not co_nguoi_o_cung:
            raise ValidationError(
                "QuyenRaVao phải liên kết với ít nhất một người."
            )

        if self.nguon_cap != "legacy_unknown":
            from .quy_tac_nghiep_vu import permission_binding_is_valid
            if not permission_binding_is_valid(self):
                raise ValidationError("Quyền không khớp hợp đồng, phòng hoặc chủ thể.")

    class Meta:
        verbose_name = "Quyền ra vào"
        verbose_name_plural = "Quyền ra vào"
        ordering = ["-ngay_tao"]

    def __str__(self):

        if self.nguoi_thue:
            ten = self.nguoi_thue.ho_ten
        elif self.nguoi_o_cung:
            ten = self.nguoi_o_cung.ho_ten
        else:
            ten = "Không rõ"

        return f"Quyền - {ten} - P{self.phong.so_phong}"


# =========================================================
# 13. LỊCH SỬ RA VÀO
# =========================================================

class LichSuRaVao(models.Model):

    LOAI_SU_KIEN = [
        ("vao", "Vào phòng"),
        ("ra", "Ra khỏi phòng"),
    ]

    NGUON_DU_LIEU = [
        ("thu_cong", "Nhập tay"),
        ("the_tu", "Thẻ từ"),
        ("camera", "Nhận diện camera"),
        ("ma_pin", "Mã PIN"),
    ]

    quyen_ra_vao = models.ForeignKey(
        QuyenRaVao,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su"
    )

    phong = models.ForeignKey(
        Phong,
        on_delete=models.CASCADE,
        related_name="lich_su_ra_vao"
    )

    nguoi_thue = models.ForeignKey(
        NguoiThue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_ra_vao"
    )

    nguoi_o_cung = models.ForeignKey(
        NguoiOCungPhong,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_ra_vao"
    )

    ten_nguoi = models.CharField(
        max_length=150,
        blank=True
    )

    loai_su_kien = models.CharField(
        max_length=10,
        choices=LOAI_SU_KIEN
    )

    nguon = models.CharField(
        max_length=20,
        choices=NGUON_DU_LIEU,
        default="thu_cong"
    )

    thoi_diem = models.DateTimeField(
        help_text="Thời điểm thực tế ra/vào"
    )

    ghi_chu = models.TextField(blank=True)

    ngay_tao = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):

        if not self.ten_nguoi:

            if self.nguoi_thue_id and self.nguoi_thue:
                self.ten_nguoi = self.nguoi_thue.ho_ten

            elif self.nguoi_o_cung_id and self.nguoi_o_cung:
                self.ten_nguoi = self.nguoi_o_cung.ho_ten

        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Lịch sử ra vào"
        verbose_name_plural = "Lịch sử ra vào"
        ordering = ["-thoi_diem"]

    def __str__(self):

        label = (
            "Vào"
            if self.loai_su_kien == "vao"
            else "Ra"
        )

        return (
            f"{label} - {self.ten_nguoi} - "
            f"P{self.phong.so_phong} - "
            f"{self.thoi_diem.strftime('%d/%m/%Y %H:%M:%S')}"
        )


# =========================================================
# 14. NHẬT KÝ THAO TÁC HỆ THỐNG — AUDIT LOG
# =========================================================

class NhatKyThaoTac(models.Model):

    HANH_DONG = [
        ("dang_nhap", "Đăng nhập"),
        ("dang_xuat", "Đăng xuất"),

        ("tao", "Tạo mới"),
        ("xem", "Xem"),
        ("cap_nhat", "Cập nhật"),
        ("xoa", "Xóa"),

        ("duyet", "Duyệt"),
        ("tu_choi", "Từ chối"),
        ("huy", "Hủy"),

        ("thanh_toan", "Thanh toán"),
        ("xuat_pdf", "Xuất PDF"),
        ("xuat_excel", "Xuất Excel"),

        ("kich_hoat", "Kích hoạt"),
        ("vo_hieu", "Vô hiệu hóa"),
        ("gia_han", "Gia hạn"),

        ("khac", "Khác"),
    ]

    nguoi_thuc_hien = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="nhat_ky_thao_tac"
    )

    hanh_dong = models.CharField(
        max_length=30,
        choices=HANH_DONG
    )

    module = models.CharField(
        max_length=100,
        blank=True
    )

    doi_tuong = models.CharField(
        max_length=100,
        blank=True
    )

    doi_tuong_id = models.PositiveBigIntegerField(
        null=True,
        blank=True
    )

    tieu_de = models.CharField(
        max_length=255
    )

    noi_dung = models.TextField(
        blank=True
    )

    du_lieu_cu = models.JSONField(
        null=True,
        blank=True
    )

    du_lieu_moi = models.JSONField(
        null=True,
        blank=True
    )

    dia_chi_ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    user_agent = models.TextField(
        blank=True
    )

    thoi_diem = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Nhật ký thao tác"
        verbose_name_plural = "Nhật ký thao tác"
        ordering = ["-thoi_diem"]

    def __str__(self):

        nguoi = (
            self.nguoi_thuc_hien.username
            if self.nguoi_thuc_hien
            else "Hệ thống"
        )

        return (
            f"{self.thoi_diem.strftime('%d/%m/%Y %H:%M:%S')} - "
            f"{nguoi} - "
            f"{self.tieu_de}"
        )


# =========================================================
# 15. LỊCH SỬ TRẠNG THÁI DÙNG CHUNG
# =========================================================

class LichSuTrangThai(models.Model):

    doi_tuong = models.CharField(
        max_length=100,
        help_text="Ví dụ: DatPhong, HopDong, HoaDon..."
    )

    doi_tuong_id = models.PositiveBigIntegerField()

    trang_thai_cu = models.CharField(
        max_length=50,
        blank=True
    )

    trang_thai_moi = models.CharField(
        max_length=50
    )

    ly_do = models.TextField(
        blank=True
    )

    nguoi_thuc_hien = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lich_su_trang_thai"
    )

    thoi_diem = models.DateTimeField(
        auto_now_add=True
    )

    dia_chi_ip = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = "Lịch sử trạng thái"
        verbose_name_plural = "Lịch sử trạng thái"
        ordering = ["-thoi_diem"]

    def __str__(self):

        return (
            f"{self.doi_tuong} #{self.doi_tuong_id}: "
            f"{self.trang_thai_cu or '---'} → "
            f"{self.trang_thai_moi}"
        )
