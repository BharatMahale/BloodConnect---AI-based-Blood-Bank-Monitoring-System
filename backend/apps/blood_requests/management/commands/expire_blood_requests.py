from django.core.management.base import (
    BaseCommand,
)
from apps.blood_requests.services import (
    expire_due_requests,
)


class Command(BaseCommand):
    help = (
        "Expire overdue blood requests and release "
        "their reserved inventory."
    )

    def handle(self, *args, **options):
        expired_count = expire_due_requests()

        self.stdout.write(
            self.style.SUCCESS(
                (
                    "Blood-request expiry completed. "
                    f"Expired requests: {expired_count}"
                )
            )
        )