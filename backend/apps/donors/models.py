import uuid
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class DonorProfile(models.Model):
    class Gender(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"
        OTHER = "OTHER", "Other"
        PREFER_NOT_TO_SAY = (
            "PREFER_NOT_TO_SAY",
            "Prefer not to say",
        )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="donor_profile",
    )

    blood_group = models.ForeignKey(
        "inventory.BloodGroup",
        on_delete=models.PROTECT,
        related_name="donors",
    )

    date_of_birth = models.DateField()

    gender = models.CharField(
        max_length=20,
        choices=Gender.choices,
    )

    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(1)],
    )

    phone = models.CharField(
        max_length=20,
    )

    address = models.TextField()

    city = models.CharField(
        max_length=100,
    )

    state = models.CharField(
        max_length=100,
    )

    pincode = models.CharField(
        max_length=10,
    )

    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )

    last_donation_date = models.DateField(
        null=True,
        blank=True,
    )

    is_available = models.BooleanField(
        default=True,
    )

    medical_declaration_accepted = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["blood_group", "is_available"],
                name="donor_group_available_idx",
            ),
            models.Index(
                fields=["city", "state"],
                name="donor_city_state_idx",
            ),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.blood_group.name}"


class DonorEligibilityAssessment(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    donor = models.ForeignKey(
        DonorProfile,
        on_delete=models.CASCADE,
        related_name="eligibility_assessments",
    )

    is_eligible = models.BooleanField()

    age_at_assessment = models.PositiveSmallIntegerField()

    weight_at_assessment = models.DecimalField(
        max_digits=5,
        decimal_places=2,
    )

    reasons = models.JSONField(
        default=list,
        blank=True,
    )

    answers = models.JSONField(
        default=dict,
        blank=True,
    )

    assessed_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-assessed_at"]

    def __str__(self):
        result = "Eligible" if self.is_eligible else "Not eligible"

        return f"{self.donor.user.email} - {result}"


class DonationRecord(models.Model):
    class Status(models.TextChoices):
        REGISTERED = "REGISTERED", "Registered"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    donor = models.ForeignKey(
        DonorProfile,
        on_delete=models.PROTECT,
        related_name="donation_records",
    )

    blood_bank = models.ForeignKey(
        "blood_banks.BloodBank",
        on_delete=models.PROTECT,
        related_name="donation_records",
    )

    blood_group = models.ForeignKey(
        "inventory.BloodGroup",
        on_delete=models.PROTECT,
        related_name="donation_records",
    )

    donation_date = models.DateField()

    units_donated = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.REGISTERED,
    )

    notes = models.TextField(
        blank=True,
    )

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="recorded_donations",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-donation_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "donor",
                    "blood_bank",
                    "donation_date",
                ],
                name="unique_donor_bank_donation_date",
            ),
        ]
        indexes = [
            models.Index(
                fields=["donor", "status"],
                name="donation_donor_status_idx",
            ),
            models.Index(
                fields=["blood_bank", "donation_date"],
                name="donation_bank_date_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.donor.user.email} - "
            f"{self.donation_date} - {self.status}"
        )