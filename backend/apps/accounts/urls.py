from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    ChangePasswordView,
    CurrentUserView,
    LoginView,
    LogoutView,
    RegisterView,
)


app_name = "accounts"

urlpatterns = [
    path(
        "register/",
        RegisterView.as_view(),
        name="register",
    ),
    path(
        "login/",
        LoginView.as_view(),
        name="login",
    ),
    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "me/",
        CurrentUserView.as_view(),
        name="current-user",
    ),
    path(
        "change-password/",
        ChangePasswordView.as_view(),
        name="change-password",
    ),
]