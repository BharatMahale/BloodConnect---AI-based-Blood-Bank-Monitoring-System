from django.contrib import admin
from .models import (
    BloodComponent,
    BloodGroup,
    BloodInventory,
    InventoryTransaction,
)


@admin.register(BloodGroup)
class BloodGroupAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "display_order",
        "is_active",
    )
    list_editable = (
        "display_order",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
    )
    ordering = ("display_order",)


@admin.register(BloodComponent)
class BloodComponentAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "display_order",
        "is_active",
    )
    list_editable = (
        "display_order",
        "is_active",
    )
    search_fields = (
        "code",
        "name",
    )
    ordering = ("display_order",)



class InventoryTransactionInline(admin.TabularInline):
    model = InventoryTransaction
    extra = 0
    can_delete = False
    readonly_fields = (
        "transaction_type",
        "quantity_change",
        "quantity_before",
        "quantity_after",
        "reason",
        "reference_number",
        "created_by",
        "created_at",
    )

    def has_add_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(BloodInventory)
class BloodInventoryAdmin(admin.ModelAdmin):
    list_display = (
        "blood_bank",
        "blood_group",
        "component",
        "total_units",
        "reserved_units",
        "available_units_display",
        "minimum_threshold",
        "low_stock_display",
        "last_updated_at",
    )
    list_filter = (
        "blood_group",
        "component",
        "blood_bank",
    )
    search_fields = (
        "blood_bank__name",
        "blood_group__code",
        "component__name",
    )
    autocomplete_fields = (
        "blood_bank",
        "blood_group",
        "component",
        "last_updated_by",
    )
    readonly_fields = (
        "last_updated_at",
        "created_at",
    )
    inlines = (InventoryTransactionInline,)

    @admin.display(
        description="Available units",
    )
    def available_units_display(self, inventory):
        return inventory.available_units

    @admin.display(
        boolean=True,
        description="Low stock",
    )
    def low_stock_display(self, inventory):
        return inventory.is_low_stock


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "inventory",
        "transaction_type",
        "quantity_change",
        "quantity_before",
        "quantity_after",
        "created_by",
        "created_at",
    )
    list_filter = (
        "transaction_type",
        "created_at",
    )
    search_fields = (
        "inventory__blood_bank__name",
        "reference_number",
        "reason",
        "created_by__email",
    )
    readonly_fields = (
        "inventory",
        "transaction_type",
        "quantity_change",
        "quantity_before",
        "quantity_after",
        "reason",
        "reference_number",
        "created_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False
