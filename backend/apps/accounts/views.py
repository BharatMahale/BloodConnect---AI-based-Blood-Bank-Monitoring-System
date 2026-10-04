from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    LoginResponseSerializer,
    LogoutSerializer,
    MessageSerializer,
    RegistrationResponseSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Register a new user",
        responses={
            status.HTTP_201_CREATED: RegistrationResponseSerializer,
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        response_data = {
            "message": "Registration successful.",
            "user": UserSerializer(user).data,
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
        }

        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
        )


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Log in with email and password",
        request=LoginSerializer,
        responses=LoginResponseSerializer,
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=LogoutSerializer,
        responses={
            status.HTTP_200_OK: MessageSerializer,
        },
    )
    def post(self, request):
        serializer = LogoutSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Logout successful."},
            status=status.HTTP_200_OK,
        )


class CurrentUserView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ChangePasswordSerializer,
        responses={
            status.HTTP_200_OK: MessageSerializer,
        },
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "message": (
                    "Password changed successfully. "
                    "Please log in again."
                )
            },
            status=status.HTTP_200_OK,
        )
