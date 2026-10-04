import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from apps.blood_banks.models import BloodBank


class BloodGroup(models.Model):
    """ABO and Rh blood-group reference data."""

    class Code(models.TextChoices):
        A_POSITIVE = "A+", "A Positive"
        A_NEGATIVE = "A-", "A Negative"
        B_POSITIVE = "B+", "B Positive"
        B_NEGATIVE = "B-", "B Negative"
        AB_POSITIVE = "AB+", "AB Positive"
        AB_NEGATIVE = "AB-", "AB Negative"
        O_POSITIVE = "O+", "O Positive"
        O_NEGATIVE = "O-", "O Negative"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(
        max_length=3,
        choices=Code.choices,
        unique=True,
    )
    name = models.CharField(
        max_length=30,
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(
        default=0,
    )

    class Meta:
        ordering = [
            "display_order",
            "code",
        ]

    def __str__(self):
        return self.code


class BloodComponent(models.Model):
    """Blood component managed by a blood bank."""

    class Code(models.TextChoices):
        WHOLE_BLOOD = "WB", "Whole Blood"
        PACKED_RED_CELLS = "PRBC", "Packed Red Blood Cells"
        PLATELETS = "PLT", "Platelets"
        FRESH_FROZEN_PLASMA = (
            "FFP",
            "Fresh Frozen Plasma",
        )
        CRYOPRECIPITATE = (
            "CRYO",
            "Cryoprecipitate",
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    code = models.CharField(
        max_length=10,
        choices=Code.choices,
        unique=True,
    )
    name = models.CharField(
        max_length=100,
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(
        default=0,
    )

    class Meta:
        ordering = [
            "display_order",
            "name",
        ]

    def __str__(self):
        return self.name


class BloodInventory(models.Model):
    """
    Aggregated stock for one bank, group and component.

    total_units represents all usable units currently held.
    reserved_units represents units temporarily reserved.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    blood_bank = models.ForeignKey(
        BloodBank,
        on_delete=models.CASCADE,
        related_name="inventory_records",
    )
    blood_group = models.ForeignKey(
        BloodGroup,
        on_delete=models.PROTECT,
        related_name="inventory_records",
    )
    component = models.ForeignKey(
        BloodComponent,
        on_delete=models.PROTECT,
        related_name="inventory_records",
    )
    total_units = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
    )
    reserved_units = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
    )
    minimum_threshold = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(0)],
    )
    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="updated_inventory_records",
        null=True,
        blank=True,
    )
    last_updated_at = models.DateTimeField(
        auto_now=True,
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "blood_bank__name",
            "blood_group__display_order",
            "component__display_order",
        ]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "blood_bank",
                    "blood_group",
                    "component",
                ],
                name="unique_bank_group_component",
            ),
            models.CheckConstraint(
                condition=Q(total_units__gte=0),
                name="inventory_total_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(reserved_units__gte=0),
                name="inventory_reserved_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(
                    reserved_units__lte=F("total_units")
                ),
                name="reserved_not_greater_than_total",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "blood_bank",
                    "blood_group",
                    "component",
                ],
                name="inventory_search_idx",
            ),
            models.Index(
                fields=["last_updated_at"],
                name="inventory_updated_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.blood_bank.name} - "
            f"{self.blood_group.code} - "
            f"{self.component.code}"
        )

    @property
    def available_units(self):
        return self.total_units - self.reserved_units

    @property
    def is_low_stock(self):
        return (
            self.available_units
            <= self.minimum_threshold
        )

    @property
    def is_out_of_stock(self):
        return self.available_units == 0


class InventoryTransaction(models.Model):
    """Immutable record of an inventory quantity change."""

    class Type(models.TextChoices):
        DONATION = "DONATION", "Donation"
        RECEIVED = "RECEIVED", "Received"
        ISSUED = "ISSUED", "Issued"
        EXPIRED = "EXPIRED", "Expired"
        TRANSFER_IN = "TRANSFER_IN", "Transfer In"
        TRANSFER_OUT = "TRANSFER_OUT", "Transfer Out"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    inventory = models.ForeignKey(
        BloodInventory,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        db_index=True,
    )
    quantity_change = models.IntegerField()
    quantity_before = models.PositiveIntegerField()
    quantity_after = models.PositiveIntegerField()
    reason = models.TextField()
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="inventory_transactions",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=~Q(quantity_change=0),
                name="inventory_change_not_zero",
            ),
        ]
        indexes = [
            models.Index(
                fields=[
                    "inventory",
                    "created_at",
                ],
                name="inventory_history_idx",
            ),
        ]

    def __str__(self):
        sign = "+" if self.quantity_change > 0 else ""

        return (
            f"{self.inventory} "
            f"{sign}{self.quantity_change}"
        )