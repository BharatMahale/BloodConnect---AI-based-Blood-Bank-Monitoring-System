import os
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, User, UserRole
from apps.blood_banks.models import BloodBank
from apps.donors.models import DonorProfile
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
    BloodInventory,
    InventoryTransaction,
)
from apps.inventory.services.transactions import (
    record_inventory_transaction,
)
from apps.locations.models import Location


DEMO_BANK_NAME = "BloodConnect Demo Test Bank"
DEMO_BANK_SLUG = "bloodconnect-demo-test-bank"
DEMO_EMAILS = {
    "requester": "requester.demo@bloodconnect.local",
    "staff": "staff.demo@bloodconnect.local",
    "unrelated": "unrelated.demo@bloodconnect.local",
}
PASSWORD_ENVIRONMENTS = {
    "requester": "BC_DEMO_REQUESTER_PASSWORD",
    "staff": "BC_DEMO_STAFF_PASSWORD",
    "unrelated": "BC_DEMO_UNRELATED_PASSWORD",
}


class Command(BaseCommand):
    help = (
        "Create or refresh isolated BloodConnect demo fixtures. "
        "Passwords are read from environment variables and never printed."
    )

    def _passwords(self):
        passwords = {
            name: os.environ.get(environment)
            for name, environment in PASSWORD_ENVIRONMENTS.items()
        }
        missing = [
            environment
            for name, environment in PASSWORD_ENVIRONMENTS.items()
            if not passwords[name]
        ]

        if missing:
            raise CommandError(
                "Set the required password environment variables: "
                + ", ".join(missing)
            )

        return passwords

    @staticmethod
    def _assign_role(user, role_code, *, primary=False):
        role, _ = Role.objects.get_or_create(
            code=role_code,
            defaults={"name": Role.Code(role_code).label},
        )

        if primary:
            UserRole.objects.filter(
                user=user,
                is_primary=True,
            ).update(is_primary=False)

        UserRole.objects.update_or_create(
            user=user,
            role=role,
            defaults={
                "is_active": True,
                "is_primary": primary,
            },
        )

    @transaction.atomic
    def handle(self, *args, **options):
        passwords = self._passwords()
        users = {}

        names = {
            "requester": ("Demo", "Requester"),
            "staff": ("Demo", "Bank Staff"),
            "unrelated": ("Demo", "Unrelated"),
        }

        for kind, email in DEMO_EMAILS.items():
            first_name, last_name = names[kind]
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "phone_number": "9000000000",
                },
            )
            user.first_name = first_name
            user.last_name = last_name
            user.is_active = True
            user.set_password(passwords[kind])
            user.save()
            users[kind] = user

        self._assign_role(
            users["requester"],
            Role.Code.SEEKER,
            primary=True,
        )
        self._assign_role(
            users["requester"],
            Role.Code.DONOR,
        )
        self._assign_role(
            users["staff"],
            Role.Code.BLOOD_BANK_STAFF,
            primary=True,
        )
        self._assign_role(
            users["unrelated"],
            Role.Code.SEEKER,
            primary=True,
        )

        blood_group = BloodGroup.objects.get(code=BloodGroup.Code.O_POSITIVE)
        component = BloodComponent.objects.get(
            code=BloodComponent.Code.WHOLE_BLOOD,
        )

        donor_defaults = {
            "blood_group": blood_group,
            "date_of_birth": date(1995, 6, 15),
            "gender": DonorProfile.Gender.PREFER_NOT_TO_SAY,
            "weight_kg": Decimal("68.00"),
            "phone": "9000000001",
            "address": "BloodConnect demo address",
            "city": "Pune",
            "state": "Maharashtra",
            "pincode": "411001",
            "latitude": Decimal("18.520430"),
            "longitude": Decimal("73.856744"),
            "is_available": True,
            "medical_declaration_accepted": True,
        }
        DonorProfile.objects.update_or_create(
            user=users["requester"],
            defaults=donor_defaults,
        )

        bank = BloodBank.objects.filter(slug=DEMO_BANK_SLUG).first()
        if bank is None:
            location = Location.objects.create(
                address_line="100 BloodConnect Demo Lane",
                locality="Demo Medical District",
                city="Pune",
                district="Pune",
                state="Maharashtra",
                pincode="411001",
                latitude=Decimal("18.520430"),
                longitude=Decimal("73.856744"),
            )
            bank = BloodBank.objects.create(
                owner=users["staff"],
                location=location,
                name=DEMO_BANK_NAME,
                slug=DEMO_BANK_SLUG,
            )

        bank.owner = users["staff"]
        bank.name = DEMO_BANK_NAME
        bank.category = BloodBank.Category.OTHER
        bank.contact_number = "020-00000000"
        bank.email = "demo-bank@bloodconnect.local"
        bank.service_time = "Demo testing only"
        bank.license_number = "BC-DEMO-TEST-ONLY"
        bank.blood_component_available = True
        bank.apheresis_available = False
        bank.source = BloodBank.Source.ADMIN_CREATED
        bank.verification_status = BloodBank.VerificationStatus.VERIFIED
        bank.is_active = True
        bank.is_public = True
        bank.save()

        inventory, _ = BloodInventory.objects.get_or_create(
            blood_bank=bank,
            blood_group=blood_group,
            component=component,
            defaults={
                "total_units": 0,
                "reserved_units": 0,
                "minimum_threshold": 2,
                "last_updated_by": users["staff"],
            },
        )

        available_units = inventory.total_units - inventory.reserved_units
        if available_units < 8:
            record_inventory_transaction(
                inventory=inventory,
                transaction_type=InventoryTransaction.Type.RECEIVED,
                quantity=8 - available_units,
                reason="BloodConnect isolated demo fixture stock",
                created_by=users["staff"],
                reference_number="BC-DEMO-FIXTURE",
            )

        self.stdout.write(self.style.SUCCESS("Demo fixtures are ready."))
        self.stdout.write("Accounts: " + ", ".join(DEMO_EMAILS.values()))
        self.stdout.write(f"Blood bank: {DEMO_BANK_NAME}")
        self.stdout.write("Passwords were read from environment variables and were not printed.")
