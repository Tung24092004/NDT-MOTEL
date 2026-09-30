"""Nghiep vu dich vu/phan quyen."""



def la_admin(request):
    return (
        request.user.is_authenticated
        and (
            request.user.is_staff
            or request.user.is_superuser
        )
    )
