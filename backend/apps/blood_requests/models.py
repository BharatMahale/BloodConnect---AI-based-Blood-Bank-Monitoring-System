import uuid
from secrets import token_hex
from django.conf import settings
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.utils import timezone
from apps.blood_banks.models import BloodBank
from apps.inventory.models import (
    BloodComponent,
    BloodGroup,
)


def generate_request_number():
    """
    Generate a readable request number.

    Example:
    BR-20260914-A13F92
    """

    date_part = timezone.now().strftime(
        "%Y%m%d"
    )

    random_part = token_hex(3).upper()

    return f"BR-{date_part}-{random_part}"


phone_validator = RegexValidator(
    regex=r"^\+?[0-9]{10,15}$",
    message=(
        "Enter a valid phone number containing "
        "10 to 15 digits."
    ),
)


class BloodRequest(models.Model):
    class Urgency(models.TextChoices):
        NORMAL = "NORMAL", "Normal"
        URGENT = "URGENT", "Urgent"
        EMERGENCY = "EMERGENCY", "Emergency"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        UNDER_REVIEW = (
            "UNDER_REVIEW",
            "Under Review",
        )
        ACCEPTED = "ACCEPTED", "Accepted"
        PARTIALLY_FULFILLED = (
            "PARTIALLY_FULFILLED",
            "Partially Fulfilled",
        )
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"
        EXPIRED = "EXPIRED", "Expired"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    request_number = models.CharField(
        max_length=30,
        unique=True,
        default=generate_request_number,
        editable=False,
        db_index=True,
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="blood_requests",
    )

    blood_bank = models.ForeignKey(
        BloodBank,
        on_delete=models.PROTECT,
        related_name="blood_requests",
        null=True,
        blank=True,
        help_text=(
            "Selected blood bank. It may be empty "
            "while searching for a suitable bank."
        ),
    )

    blood_group = models.ForeignKey(
        BloodGroup,
        on_delete=models.PROTECT,
        related_name="blood_requests",
    )

    component = models.ForeignKey(
        BloodComponent,
        on_delete=models.PROTECT,
        related_name="blood_requests",
    )

    patient_name = models.CharField(
        max_length=150
    )

    units_required = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1)
        ]
    )

    units_fulfilled = (
        models.PositiveSmallIntegerField(
            default=0
        )
    )

    hospital_name = models.CharField(
        max_length=200
    )

    hospital_address = models.TextField()

    hospital_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
        help_text=(
            "Latitude of the hospital or request location."
        ),
    )

    hospital_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
        help_text=(
            "Longitude of the hospital or request location."
        ),
    )

    contact_phone = models.CharField(
        max_length=16,
        validators=[phone_validator],
    )

    required_date = models.DateField()

    urgency = models.CharField(
        max_length=20,
        choices=Urgency.choices,
        default=Urgency.NORMAL,
        db_index=True,
    )

    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    additional_information = models.TextField(
        blank=True,
        default="",
    )

    blood_bank_response = models.TextField(
        blank=True,
        default="",
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name=(
            "reviewed_blood_requests"
        ),
        null=True,
        blank=True,
    )

    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    expires_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = [
            "-created_at"
        ]

        indexes = [
            models.Index(
                fields=[
                    "requester",
                    "status",
                ],
                name="request_user_status_idx",
            ),
            models.Index(
                fields=[
                    "blood_bank",
                    "status",
                ],
                name="request_bank_status_idx",
            ),
            models.Index(
                fields=[
                    "blood_group",
                    "component",
                ],
                name="request_blood_comp_idx",
            ),
            models.Index(
                fields=[
                    "urgency",
                    "required_date",
                ],
                name="request_urgency_date_idx",
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    units_required__gt=0
                ),
                name=(
                    "blood_request_units_positive"
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(
                    units_fulfilled__gte=0
                ),
                name=(
                    "blood_request_fulfilled_nonnegative"
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(
                    units_fulfilled__lte=models.F(
                        "units_required"
                    )
                ),
                name=(
                    "blood_request_fulfilled_lte_required"
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.request_number} - "
            f"{self.blood_group.name} - "
            f"{self.get_status_display()}"
        )

    @property
    def remaining_units(self):
        return (
            self.units_required
            - self.units_fulfilled
        )

    @property
    def has_coordinates(self):
        return (
            self.hospital_latitude is not None
            and self.hospital_longitude is not None
        )

    @property
    def is_terminal(self):
        return self.status in {
            self.Status.REJECTED,
            self.Status.CANCELLED,
            self.Status.COMPLETED,
            self.Status.EXPIRED,
        }


class BloodRequestStatusHistory(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    blood_request = models.ForeignKey(
        BloodRequest,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    previous_status = models.CharField(
        max_length=25,
        choices=BloodRequest.Status.choices,
        blank=True,
        default="",
    )

    new_status = models.CharField(
        max_length=25,
        choices=BloodRequest.Status.choices,
    )

    note = models.TextField(
        blank=True,
        default="",
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name=(
            "blood_request_status_changes"
        ),
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            "-created_at"
        ]

        indexes = [
            models.Index(
                fields=[
                    "blood_request",
                    "created_at",
                ],
                name="request_history_date_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.blood_request.request_number}: "
            f"{self.previous_status or 'CREATED'} "
            f"→ {self.new_status}"
        )


class BloodRequestReservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PARTIALLY_FULFILLED = (
            "PARTIALLY_FULFILLED",
            "Partially Fulfilled",
        )
        FULFILLED = "FULFILLED", "Fulfilled"
        RELEASED = "RELEASED", "Released"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    blood_request = models.OneToOneField(
        BloodRequest,
        on_delete=models.CASCADE,
        related_name="reservation",
    )

    inventory = models.ForeignKey(
        "inventory.BloodInventory",
        on_delete=models.PROTECT,
        related_name="request_reservations",
    )

    reserved_units = (
        models.PositiveSmallIntegerField(
            default=0,
            help_text=(
                "Units currently held for this request."
            ),
        )
    )

    fulfilled_units = (
        models.PositiveSmallIntegerField(
            default=0,
            help_text=(
                "Total units already supplied "
                "through this reservation."
            ),
        )
    )

    status = models.CharField(
        max_length=25,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name=(
            "created_blood_reservations"
        ),
    )

    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name=(
            "released_blood_reservations"
        ),
        null=True,
        blank=True,
    )

    release_reason = models.TextField(
        blank=True,
        default="",
    )

    released_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    reserved_units__gte=0
                ),
                name=(
                    "request_reserved_units_nonnegative"
                ),
            ),
            models.CheckConstraint(
                condition=models.Q(
                    fulfilled_units__gte=0
                ),
                name=(
                    "request_fulfilled_units_nonnegative"
                ),
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "inventory",
                    "status",
                ],
                name="reservation_inv_status_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.blood_request.request_number} - "
            f"{self.reserved_units} reserved"
        )


class BloodRequestBankAssignment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    blood_request = models.ForeignKey(
        BloodRequest,
        on_delete=models.CASCADE,
        related_name="assignment_history",
    )

    previous_blood_bank = models.ForeignKey(
        BloodBank,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    new_blood_bank = models.ForeignKey(
        BloodBank,
        on_delete=models.PROTECT,
        related_name=(
            "blood_request_assignments"
        ),
    )

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name=(
            "assigned_blood_requests"
        ),
        null=True,
        blank=True,
    )

    reason = models.TextField(
        blank=True,
        default="",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=[
                    "blood_request",
                    "created_at",
                ],
                name="request_assignment_date_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.blood_request.request_number} "
            f"→ {self.new_blood_bank.name}"
        )
