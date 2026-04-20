from importlib import invalidate_caches
from typing import Dict, Tuple
from django.core.cache import cache
from django.conf import settings
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .tasks import send_welcome_email, send_deactivation_email

from .serializers import RegisterSerializer, LoginSerializer, UserSerializer
from .permissions import IsAdmin, IsOwnerOrAdmin, IsModeratorOrAdmin
from .google import (
    get_google_auth_url,
    exchange_code_for_token,
    get_google_user_info
)

User = get_user_model()

def generate_tokens(user: User) -> Dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def build_auth_response(user: User, created: bool = False) -> dict:
    return {
        "user": UserSerializer(user).data,
        "tokens": generate_tokens(user),
        "created": created,
    }


def normalize_email(email: str) -> str:
    return email.strip().lower()

def invalidate_user_cache(pk=None):
    cache.delete("users_list")
    if pk:
        cache.delete(f"user_{pk}")

@transaction.atomic
def get_or_create_google_user(user_info: dict) -> Tuple[User, bool]:
    email = normalize_email(user_info.get("email", ""))

    if not email:
        raise ValidationError("Email не получен от Google")

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": user_info.get("given_name", ""),
            "last_name": user_info.get("family_name", ""),
            "is_active": True,
        }
    )

    return user, created

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        self.user = serializer.save()

    def create(self, request, *args, **kwargs):
        super().create(request, *args, **kwargs)
        invalidate_user_cache()

        send_welcome_email.delay(self.user.id)

        return Response(
            build_auth_response(self.user),
            status=status.HTTP_201_CREATED
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response(build_auth_response(user))


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            raise ValidationError("Передайте refresh токен")
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError:
            raise ValidationError("Токен уже недействителен")
        return Response({"detail": "Успешный выход"})


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        response = super().update(request, *args, **kwargs)
        invalidate_user_cache(pk=request.user.id)
        return response

class UserListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        cache_key = "users_list"
        users = cache.get(cache_key)
        if users is None:
            users = User.objects.all()
            cache.set(cache_key, users, timeout=settings.CACHE_TTL)
        return users


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        return User.objects.all()

    def get_object(self):
        cache_key = f"user_{self.kwargs['pk']}"
        user = cache.get(cache_key)
        if user is None:
            user = super().get_object()
            cache.set(cache_key, user, timeout=settings.CACHE_TTL)
        return user

    def perform_update(self, serializer):
        instance = serializer.save()
        invalidate_user_cache(pk=instance.id)

    def perform_destroy(self, instance):
        invalidate_user_cache(pk=instance.id)
        instance.delete()

class DeactivateUserView(APIView):
    permission_classes = [IsModeratorOrAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"detail": "Не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

        user.is_active = False
        user.save(update_fields=["is_active"])

        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)

        invalidate_user_cache(pk=pk)

        send_deactivation_email.delay(user.id)

        return Response({"detail": "Пользователь деактивирован"})

class GoogleAuthURLView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({"url": get_google_auth_url()})


class GoogleCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.query_params.get("code")
        if not code:
            raise ValidationError("code не передан")
        token_data = exchange_code_for_token(code)
        if "error" in token_data:
            raise ValidationError(token_data["error"])
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValidationError("Не удалось получить access_token")
        user_info = get_google_user_info(access_token)
        user, created = get_or_create_google_user(user_info)


        if created:
            invalidate_user_cache()

        return Response(build_auth_response(user, created))
