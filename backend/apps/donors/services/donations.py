from datetime import date

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.donors.models import (
    DonationRecord,
    DonorProfile,
)
from apps.inventory.models import (
    BloodComponent,
    BloodInventory,
    InventoryTransaction,
)
from apps.inventory.services.transactions import (
    record_inventory_transaction,
)


@transaction.atomic
def record_donation(
    *,
    donor,
    blood_bank,
    donation_date,
    units_donated,
    status,
    notes,
    recorded_by,
):
    if donation_date > date.today():
        raise ValidationError(
            {
                "donation_date": (
                    "Donation date cannot be in the future."
                )
            }
        )

    if not recorded_by or not recorded_by.is_authenticated:
        raise ValidationError(
            {
                "detail": (
                    "An authenticated staff member "
                    "is required."
                )
            }
        )

    donor = (
        DonorProfile.objects
        .select_for_update()
        .select_related(
            "user",
            "blood_group",
        )
        .get(pk=donor.pk)
    )

    try:
        units_donated = int(units_donated)
    except (TypeError, ValueError) as error:
        raise ValidationError(
            {
                "units_donated": (
                    "Units donated must be a whole number."
                )
            }
        ) from error

    if units_donated <= 0:
        raise ValidationError(
            {
                "units_donated": (
                    "Units donated must be greater than zero."
                )
            }
        )

    try:
        donation = DonationRecord.objects.create(
            donor=donor,
            blood_bank=blood_bank,
            blood_group=donor.blood_group,
            donation_date=donation_date,
            units_donated=units_donated,
            status=status,
            notes=notes,
            recorded_by=recorded_by,
        )
    except IntegrityError as error:
        raise ValidationError(
            {
                "detail": (
                    "A donation record already exists for "
                    "this donor, blood bank and date."
                )
            }
        ) from error

    if status == DonationRecord.Status.COMPLETED:
        whole_blood = BloodComponent.objects.filter(
            name__iexact="Whole Blood",
        ).first()

        if whole_blood is None:
            raise ValidationError(
                {
                    "detail": (
                        "Whole Blood component is missing. "
                        "Run the inventory reference-data "
                        "command first."
                    )
                }
            )

        inventory, _ = BloodInventory.objects.get_or_create(
            blood_bank=blood_bank,
            blood_group=donor.blood_group,
            component=whole_blood,
            defaults={
                "total_units": 0,
                "reserved_units": 0,
                "last_updated_by": recorded_by,
            },
        )

        record_inventory_transaction(
            inventory=inventory,
            transaction_type=(
                InventoryTransaction.Type.DONATION
            ),
            quantity=units_donated,
            reason=(
                "Blood received from completed "
                f"donation {donation.id}."
            ),
            created_by=recorded_by,
            reference_number=(
                f"DONATION-{donation.id}"
            ),
        )

        if (
            donor.last_donation_date is None
            or donation_date > donor.last_donation_date
        ):
            donor.last_donation_date = donation_date

        donor.is_available = False

        donor.save(
            update_fields=[
                "last_donation_date",
                "is_available",
                "updated_at",
            ]
        )

    return donation