from django.contrib import admin

from apps.donors.models import (
    DonationRecord,
    DonorEligibilityAssessment,
    DonorProfile,
)


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "blood_group",
        "city",
        "state",
        "is_available",
        "last_donation_date",
        "created_at",
    ]

    list_filter = [
        "blood_group",
        "gender",
        "is_available",
        "state",
    ]

    search_fields = [
        "user__email",
        "phone",
        "city",
        "state",
        "pincode",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]


@admin.register(DonorEligibilityAssessment)
class DonorEligibilityAssessmentAdmin(
    admin.ModelAdmin
):
    list_display = [
        "donor",
        "is_eligible",
        "age_at_assessment",
        "weight_at_assessment",
        "assessed_at",
    ]

    list_filter = [
        "is_eligible",
        "assessed_at",
    ]

    search_fields = [
        "donor__user__email",
        "donor__phone",
    ]

    readonly_fields = [
        "assessed_at",
    ]


@admin.register(DonationRecord)
class DonationRecordAdmin(admin.ModelAdmin):
    list_display = [
        "donor",
        "blood_bank",
        "blood_group",
        "donation_date",
        "units_donated",
        "status",
        "recorded_by",
    ]

    list_filter = [
        "status",
        "blood_group",
        "blood_bank",
        "donation_date",
    ]

    search_fields = [
        "donor__user__email",
        "donor__phone",
        "blood_bank__name",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]