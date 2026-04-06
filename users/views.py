from django.contrib.auth.tokens import default_token_generator
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth import get_user_model
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer
from .permissions import IsAdmin, IsOwnerOrAdmin, IsModeratorOrAdmin
from .google import get_google_auth_url, exchange_code_for_token, get_google_user_info

User = get_user_model()

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({
            "user": UserSerializer(user).data,
            "tokens": get_tokens_for_user(user),
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return Response({
            "user": UserSerializer(user).data,
            "tokens": get_tokens_for_user(user),
        })


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data["refresh"])
            token.blacklist()
            return Response({"detail": "Успешный выход"})
        except TokenError:
            return Response(
                {"detail": "Токен уже недействителен"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except KeyError:
            return Response(
                {"detail": "Передайте refresh токен"},
                status=status.HTTP_400_BAD_REQUEST
            )


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def get_object(self):
        return self.request.user


class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]


class DeactivateUserView(APIView):
    permission_classes = [IsModeratorOrAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
            user.is_active = False
            user.save()
            return Response({"detail": "Пользователь деактивирован"})
        except User.DoesNotExist:
            return Response(
                {"detail": "Не найден"},
                status=status.HTTP_404_NOT_FOUND
            )

class GoogleAuthURLView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        url = get_google_auth_url()
        return Response({"url": url})


class GoogleCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        code = request.query_params.get("code")

        if not code:
            return Response(
                {"detail": "code не передан"},
                status=status.HTTP_400_BAD_REQUEST
            )

        token_data = exchange_code_for_token(code)

        if "error" in token_data:
            return Response(
                {"detail": token_data["error"]},
                status=status.HTTP_400_BAD_REQUEST
            )

        google_access_token = token_data.get("access_token")
        user_info = get_google_user_info(google_access_token)

        email = user_info.get("email")
        if not email:
            return Response(
                {"detail": "Не удалось получить email от Google"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": user_info.get("given_name", ""),
                "last_name": user_info.get("family_name", ""),
                "is_active": True,
            }
        )

        return Response({
            "user": UserSerializer(user).data,
            "tokens": get_tokens_for_user(user),
            "created": created,  
        })