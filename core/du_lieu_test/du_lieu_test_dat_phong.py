"""Synthetic UI fixtures reusing the isolated database guard from prior phases."""
from core.du_lieu_test.du_lieu_test_nghiep_vu import BusinessFixture


class Phase5BookingFixture(BusinessFixture):
    def setUp(self):
        self.client.force_login(self.user)

    def payload(self, people=1):
        data = {'ngay_nhan_phong': str(self.today), 'so_thang_thue': '3', 'so_nguoi_o': str(people),
            'da_dong_y_dieu_khoan': 'on', 'companions-TOTAL_FORMS': str(people - 1),
            'companions-INITIAL_FORMS': '0', 'companions-MIN_NUM_FORMS': '0', 'companions-MAX_NUM_FORMS': '100'}
        for index in range(people - 1):
            data.update({f'companions-{index}-ho_ten': f'Companion {index}',
                         f'companions-{index}-cccd': f'{index + 3:012d}'})
        return data

    def submit(self, **changes):
        from django.urls import reverse
        data = self.payload()
        data.update(changes)
        return self.client.post(reverse('dat_phong', args=[self.room.pk]), data)

    def new_booking(self, people=1):
        from core.dich_vu.dat_phong import create_booking
        from core.dich_vu.tien_coc import get_or_create_deposit
        booking = create_booking(actor=self.user, room_id=self.room.pk, checkin=self.today, months=3,
            people=people, companions=[{'ho_ten': f'Companion {i}', 'cccd': f'{i+3:012d}'} for i in range(people-1)], accept_terms=True)
        payment = get_or_create_deposit(actor=self.user, booking_id=booking.pk)
        return booking, payment
