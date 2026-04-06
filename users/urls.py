from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    UserListView,
    UserDetailView,
    DeactivateUserView,
    GoogleAuthURLView,
    GoogleCallbackView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", MeView.as_view(), name="me"),
    path("", UserListView.as_view(), name="user-list"),
    path("<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("<int:pk>/deactivate/", DeactivateUserView.as_view(), name="deactivate"),
    path("auth/google/", GoogleAuthURLView.as_view(), name="google-auth"),
    path("auth/google/callback/", GoogleCallbackView.as_view(), name="google-callback"),
]   