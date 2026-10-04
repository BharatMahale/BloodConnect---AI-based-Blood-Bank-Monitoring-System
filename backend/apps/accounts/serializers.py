from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (TokenObtainPairSerializer)
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Role, User, UserRole


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = (
            "code",
            "name",
        )


class UserSerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()
    primary_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "is_email_verified",
            "roles",
            "primary_role",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "email",
            "is_email_verified",
            "roles",
            "primary_role",
            "created_at",
            "updated_at",
        )

    def get_roles(self, user) -> list[str]:
        return list(
            user.user_roles.filter(
                is_active=True,
                role__is_active=True,
            ).values_list(
                "role__code",
                flat=True,
            )
        )

    def get_primary_role(self, user) -> str | None:
        assignment = user.user_roles.filter(
            is_primary=True,
            is_active=True,
            role__is_active=True,
        ).select_related("role").first()

        if assignment:
            return assignment.role.code

        return None


class RegisterSerializer(serializers.Serializer):
    PUBLIC_ROLE_CHOICES = (
        Role.Code.SEEKER,
        Role.Code.DONOR,
        Role.Code.CAMP_ORGANIZER,
    )

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    first_name = serializers.CharField(
        max_length=150,
    )
    last_name = serializers.CharField(
        max_length=150,
        required=False,
        allow_blank=True,
    )
    phone_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
    )
    role = serializers.ChoiceField(
        choices=PUBLIC_ROLE_CHOICES,
    )

    def validate_email(self, value):
        normalized_email = value.strip().lower()

        if User.objects.filter(
            email__iexact=normalized_email,
        ).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )

        return normalized_email

    def validate_phone_number(self, value):
        cleaned_number = value.strip()

        if cleaned_number and not cleaned_number.replace(
            "+",
            "",
            1,
        ).isdigit():
            raise serializers.ValidationError(
                "Enter a valid phone number."
            )

        return cleaned_number

    def validate(self, attributes):
        password = attributes.get("password")
        password_confirm = attributes.pop(
            "password_confirm",
            None,
        )

        if password != password_confirm:
            raise serializers.ValidationError(
                {
                    "password_confirm": (
                        "The two passwords do not match."
                    )
                }
            )

        temporary_user = User(
            email=attributes.get("email"),
            first_name=attributes.get("first_name", ""),
            last_name=attributes.get("last_name", ""),
        )

        validate_password(
            password=password,
            user=temporary_user,
        )

        return attributes

    @transaction.atomic
    def create(self, validated_data):
        role_code = validated_data.pop("role")
        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            **validated_data,
        )

        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={
                "name": Role.Code(role_code).label,
            },
        )

        UserRole.objects.create(
            user=user,
            role=role,
            is_primary=True,
        )

        return user


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token["email"] = user.email
        token["roles"] = list(
            user.user_roles.filter(
                is_active=True,
                role__is_active=True,
            ).values_list(
                "role__code",
                flat=True,
            )
        )

        return token

    def validate(self, attributes):
        token_data = super().validate(attributes)

        token_data["user"] = UserSerializer(
            self.user,
        ).data

        return token_data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    default_error_messages = {
        "invalid_token": "The refresh token is invalid or expired."
    }

    def save(self, **kwargs):
        try:
            refresh_token = RefreshToken(
                self.validated_data["refresh"]
            )
            refresh_token.blacklist()
        except Exception:
            self.fail("invalid_token")


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_current_password(self, value):
        user = self.context["request"].user

        if not user.check_password(value):
            raise serializers.ValidationError(
                "The current password is incorrect."
            )

        return value

    def validate(self, attributes):
        new_password = attributes.get("new_password")
        confirmation = attributes.get(
            "new_password_confirm"
        )

        if new_password != confirmation:
            raise serializers.ValidationError(
                {
                    "new_password_confirm": (
                        "The two new passwords do not match."
                    )
                }
            )

        user = self.context["request"].user

        validate_password(
            password=new_password,
            user=user,
        )

        return attributes

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(
            self.validated_data["new_password"]
        )
        user.save(update_fields=["password"])

        return user


class TokenPairSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class RegistrationResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    user = UserSerializer()
    tokens = TokenPairSerializer()


class MessageSerializer(serializers.Serializer):
    message = serializers.CharField()
