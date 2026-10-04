from django.contrib import admin
from .models import (
    BloodRequest,
    BloodRequestStatusHistory,
)
from .models import (
    BloodRequest,
    BloodRequestReservation,
    BloodRequestStatusHistory,
    BloodRequestBankAssignment,
)


class BloodRequestStatusHistoryInline(
    admin.TabularInline
):
    model = BloodRequestStatusHistory
    extra = 0
    can_delete = False

    readonly_fields = [
        "previous_status",
        "new_status",
        "note",
        "changed_by",
        "created_at",
    ]

    def has_add_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(BloodRequest)
class BloodRequestAdmin(admin.ModelAdmin):
    list_display = [
        "request_number",
        "patient_name",
        "blood_group",
        "component",
        "units_required",
        "units_fulfilled",
        "urgency",
        "status",
        "blood_bank",
        "required_date",
        "created_at",
    ]

    list_filter = [
        "urgency",
        "status",
        "blood_group",
        "component",
        "required_date",
        "created_at",
    ]

    search_fields = [
        "request_number",
        "patient_name",
        "hospital_name",
        "hospital_latitude",
        "hospital_longitude",
        "contact_phone",
        "requester__email",
        "blood_bank__name",
    ]

    readonly_fields = [
        "id",
        "request_number",
        "remaining_units",
        "created_at",
        "updated_at",
    ]

    autocomplete_fields = [
        "requester",
        "blood_bank",
        "blood_group",
        "component",
        "reviewed_by",
    ]

    date_hierarchy = "created_at"

    inlines = [
        BloodRequestStatusHistoryInline
    ]


@admin.register(BloodRequestStatusHistory)
class BloodRequestStatusHistoryAdmin(
    admin.ModelAdmin
):
    list_display = [
        "blood_request",
        "previous_status",
        "new_status",
        "changed_by",
        "created_at",
    ]

    list_filter = [
        "previous_status",
        "new_status",
        "created_at",
    ]

    search_fields = [
        "blood_request__request_number",
        "changed_by__email",
        "note",
    ]

    readonly_fields = [
        "id",
        "blood_request",
        "previous_status",
        "new_status",
        "note",
        "changed_by",
        "created_at",
    ]

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(BloodRequestReservation)
class BloodRequestReservationAdmin(
    admin.ModelAdmin
):
    list_display = [
        "blood_request",
        "inventory",
        "reserved_units",
        "fulfilled_units",
        "status",
        "created_by",
        "created_at",
    ]

    list_filter = [
        "status",
        "created_at",
        "released_at",
    ]

    search_fields = [
        "blood_request__request_number",
        "blood_request__patient_name",
        "inventory__blood_bank__name",
        "created_by__email",
    ]

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "released_at",
    ]

    autocomplete_fields = [
        "blood_request",
        "inventory",
        "created_by",
        "released_by",
    ]

@admin.register(BloodRequestBankAssignment)
class BloodRequestBankAssignmentAdmin(
    admin.ModelAdmin
):
    list_display = [
        "blood_request",
        "previous_blood_bank",
        "new_blood_bank",
        "assigned_by",
        "created_at",
    ]

    list_filter = [
        "created_at",
        "new_blood_bank",
    ]

    search_fields = [
        "blood_request__request_number",
        "previous_blood_bank__name",
        "new_blood_bank__name",
        "assigned_by__email",
    ]

    readonly_fields = [
        "id",
        "blood_request",
        "previous_blood_bank",
        "new_blood_bank",
        "assigned_by",
        "reason",
        "created_at",
    ]

    def has_add_permission(
        self,
        request,
    ):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False