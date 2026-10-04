from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Role, User, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    fk_name = "user"
    extra = 0
    autocomplete_fields = ("role", "assigned_by")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)

    list_display = (
        "email",
        "first_name",
        "last_name",
        "display_roles",
        "is_email_verified",
        "is_staff",
        "is_active",
    )

    list_filter = (
        "is_active",
        "is_staff",
        "is_superuser",
        "is_email_verified",
    )

    search_fields = (
        "email",
        "first_name",
        "last_name",
        "phone_number",
    )

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "email",
                    "password",
                )
            },
        ),
        (
            "Personal information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone_number",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": ("is_email_verified",)
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Important dates",
            {
                "fields": (
                    "last_login",
                    "date_joined",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )

    inlines = (UserRoleInline,)

    @admin.display(description="Roles")
    def display_roles(self, user):
        role_codes = user.user_roles.filter(
            is_active=True,
        ).values_list(
            "role__code",
            flat=True,
        )

        return ", ".join(role_codes) or "No role"


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("name",)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "role",
        "is_primary",
        "is_active",
        "assigned_at",
    )
    list_filter = (
        "role",
        "is_primary",
        "is_active",
    )
    search_fields = (
        "user__email",
        "role__code",
        "role__name",
    )
    autocomplete_fields = (
        "user",
        "role",
        "assigned_by",
    )