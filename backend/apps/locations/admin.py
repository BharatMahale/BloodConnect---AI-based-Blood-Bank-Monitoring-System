from django.contrib import admin
from .models import Location


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = (
        "city",
        "district",
        "state",
        "pincode",
        "has_coordinates_display",
    )
    list_filter = ("state",)
    search_fields = (
        "address_line",
        "locality",
        "city",
        "district",
        "state",
        "pincode",
    )
    ordering = (
        "state",
        "district",
        "city",
    )

    @admin.display(
        boolean=True,
        description="Coordinates",
    )
    def has_coordinates_display(self, location):
        return location.has_coordinates