from django.core.management.base import BaseCommand
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
)


class Command(BaseCommand):
    help = "Create blood groups and blood components."

    BLOOD_GROUPS = [
        ("A+", "A Positive"),
        ("A-", "A Negative"),
        ("B+", "B Positive"),
        ("B-", "B Negative"),
        ("AB+", "AB Positive"),
        ("AB-", "AB Negative"),
        ("O+", "O Positive"),
        ("O-", "O Negative"),
    ]

    COMPONENTS = [
        ("WB", "Whole Blood"),
        ("PRBC", "Packed Red Blood Cells"),
        ("PLT", "Platelets"),
        ("FFP", "Fresh Frozen Plasma"),
        ("CRYO", "Cryoprecipitate"),
    ]

    def handle(self, *args, **options):
        groups_created = 0
        components_created = 0

        for order, (code, name) in enumerate(
            self.BLOOD_GROUPS,
            start=1,
        ):
            _, created = BloodGroup.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "display_order": order,
                    "is_active": True,
                },
            )

            if created:
                groups_created += 1

        for order, (code, name) in enumerate(
            self.COMPONENTS,
            start=1,
        ):
            _, created = (
                BloodComponent.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": name,
                        "display_order": order,
                        "is_active": True,
                    },
                )
            )

            if created:
                components_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                "Inventory reference data ready.\n"
                f"Blood groups created: {groups_created}\n"
                "Blood groups available: "
                f"{BloodGroup.objects.count()}\n"
                "Components created: "
                f"{components_created}\n"
                "Components available: "
                f"{BloodComponent.objects.count()}"
            )
        )