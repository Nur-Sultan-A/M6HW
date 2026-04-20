from celery import shared_task
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta


@shared_task
def send_welcome_email(user_id: int):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        send_mail(
            subject="Добро пожаловать!",
            message=f"Привет {user.full_name or user.email}!\n\nВы успешно зарегистрировались.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return f"Письмо отправлено на {user.email}"
    except User.DoesNotExist:
        return f"Пользователь {user_id} не найден"

@shared_task
def send_deactivation_email(user_id: int):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
        send_mail(
            subject="Ваш аккаунт деактивирован",
            message=f"Здравствуйте, {user.full_name or user.email}.\n\nВаш аккаунт был деактивирован.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return f"Письмо отправлено на {user.email}"
    except User.DoesNotExist:
        return f"Пользователь {user.id} не найден"

@shared_task
def deactivate_inactive_users():
    from django.contrib.auth import get_user_model
    User = get_user_model()

    deadline = timezone.now() - timedelta(days=30)
    users = User.objects.filter(
        last_login__lt=deadline,
        is_active=True,
        role="user"
    )
    count = users.update(is_active=False)
    return f"Деактивировано {count} пользователей"

@shared_task
def cleanup_blacklisted_tokens():
    from rest_framework_simplejwt.token_blacklist.models import (
        OutstandingToken,
        BlacklistedToken
    )
    expired = OutstandingToken.objects.filter(
        expires_at__lt=timezone.now()
    )
    count = expired.count()
    expired.delete()
    return f"Удалено {count} истёкших токенов"

@shared_task
def refresh_users_cache():
    cache.delete("users_list")
    return "Кэш users_list сброшен"