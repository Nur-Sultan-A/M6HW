from django.urls import path

from .views import (
    RegisterView, LoginView, LogoutView,
    MeView, UserListView, UserDetailView,
    DeactivateUserView,
    GoogleAuthURLView, GoogleCallbackView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/google/", GoogleAuthURLView.as_view(), name="google-auth"),
    path("auth/google/callback/", GoogleCallbackView.as_view(), name="google-callback"),
    path("me/", MeView.as_view(), name="me"),
    path("users/", UserListView.as_view(), name="user-list"),
    path("users/<int:pk>/", UserDetailView.as_view(), name="user-detail"),
    path("users/<int:pk>/deactivate/", DeactivateUserView.as_view(), name="deactivate"),
]