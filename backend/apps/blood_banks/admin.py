from django.contrib import admin
from django.utils import timezone
from .models import BloodBank, BloodBankVerification


class BloodBankVerificationInline(admin.TabularInline):
    model = BloodBankVerification
    extra = 0
    fields = (
        "status",
        "license_number",
        "license_expiry_date",
        "submitted_at",
        "reviewed_at",
    )
    readonly_fields = (
        "submitted_at",
        "reviewed_at",
    )


@admin.register(BloodBank)
class BloodBankAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "city",
        "state",
        "category",
        "verification_status",
        "source",
        "is_active",
        "is_public",
    )
    list_filter = (
        "verification_status",
        "source",
        "category",
        "is_active",
        "is_public",
        "location__state",
    )
    search_fields = (
        "name",
        "license_number",
        "location__city",
        "location__district",
        "location__state",
        "location__pincode",
    )
    readonly_fields = (
        "slug",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = (
        "owner",
        "location",
    )
    inlines = (BloodBankVerificationInline,)
    actions = (
        "mark_as_verified",
        "mark_as_suspended",
    )

    @admin.display(
        ordering="location__city",
        description="City",
    )
    def city(self, blood_bank):
        return blood_bank.location.city

    @admin.display(
        ordering="location__state",
        description="State",
    )
    def state(self, blood_bank):
        return blood_bank.location.state

    @admin.action(description="Mark selected banks as verified")
    def mark_as_verified(self, request, queryset):
        queryset.update(
            verification_status=(
                BloodBank.VerificationStatus.VERIFIED
            ),
            information_last_reviewed_at=timezone.now(),
        )

    @admin.action(description="Suspend selected blood banks")
    def mark_as_suspended(self, request, queryset):
        queryset.update(
            verification_status=(
                BloodBank.VerificationStatus.SUSPENDED
            )
        )


@admin.register(BloodBankVerification)
class BloodBankVerificationAdmin(admin.ModelAdmin):
    list_display = (
        "blood_bank",
        "status",
        "license_number",
        "submitted_at",
        "reviewed_at",
        "reviewed_by",
    )
    list_filter = (
        "status",
        "submitted_at",
    )
    search_fields = (
        "blood_bank__name",
        "license_number",
        "submitted_by__email",
        "reviewed_by__email",
    )
    autocomplete_fields = (
        "blood_bank",
        "submitted_by",
        "reviewed_by",
    )
    readonly_fields = ("submitted_at",)