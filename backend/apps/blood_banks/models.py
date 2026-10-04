import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.text import slugify
from apps.locations.models import Location


class BloodBank(models.Model):
    """Blood-bank directory and profile record."""

    class Category(models.TextChoices):
        GOVERNMENT = "GOVERNMENT", "Government"
        PRIVATE = "PRIVATE", "Private"
        CHARITY = "CHARITY", "Charity"
        OTHER = "OTHER", "Other"

    class Source(models.TextChoices):
        USER_REGISTERED = (
            "USER_REGISTERED",
            "User Registered",
        )
        DIRECTORY_IMPORT = (
            "DIRECTORY_IMPORT",
            "Directory Import",
        )
        ADMIN_CREATED = (
            "ADMIN_CREATED",
            "Admin Created",
        )

    class VerificationStatus(models.TextChoices):
        DIRECTORY_IMPORTED = (
            "DIRECTORY_IMPORTED",
            "Directory Imported",
        )
        PENDING = "PENDING", "Pending Verification"
        VERIFIED = "VERIFIED", "Verified"
        REJECTED = "REJECTED", "Rejected"
        SUSPENDED = "SUSPENDED", "Suspended"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="owned_blood_banks",
        null=True,
        blank=True,
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="blood_banks",
    )
    name = models.CharField(
        max_length=255,
        db_index=True,
    )
    slug = models.SlugField(
        max_length=280,
        unique=True,
        blank=True,
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.OTHER,
        db_index=True,
    )
    contact_number = models.CharField(
        max_length=100,
        blank=True,
    )
    mobile_number = models.CharField(
        max_length=100,
        blank=True,
    )
    helpline = models.CharField(
        max_length=100,
        blank=True,
    )
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    service_time = models.CharField(
        max_length=100,
        blank=True,
    )
    license_number = models.CharField(
        max_length=150,
        blank=True,
    )
    blood_component_available = models.BooleanField(
        null=True,
        blank=True,
    )
    apheresis_available = models.BooleanField(
        null=True,
        blank=True,
    )
    source = models.CharField(
        max_length=30,
        choices=Source.choices,
        default=Source.USER_REGISTERED,
        db_index=True,
    )
    source_record_id = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
    )

    source_metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    verification_status = models.CharField(
        max_length=30,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )
    information_last_reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
    )
    is_public = models.BooleanField(
        default=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(
                fields=[
                    "verification_status",
                    "is_active",
                    "is_public",
                ],
                name="bank_visibility_idx",
            ),
            models.Index(
                fields=["category", "name"],
                name="bank_category_name_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_record_id"],
                condition=~Q(source_record_id=""),
                name="unique_bank_source_record",
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "blood-bank"
            slug = base_slug

            if BloodBank.objects.filter(
                slug=slug,
            ).exclude(pk=self.pk).exists():
                slug = (
                    f"{base_slug}-"
                    f"{str(self.id)[:8]}"
                )

            self.slug = slug

        super().save(*args, **kwargs)

    @property
    def is_verified(self):
        return (
            self.verification_status
            == self.VerificationStatus.VERIFIED
        )

    @property
    def data_source_label(self):
        if self.source == self.Source.DIRECTORY_IMPORT:
            return "Imported directory information"

        if self.source == self.Source.ADMIN_CREATED:
            return "Administrator-created information"

        return "Blood-bank submitted information"


class BloodBankVerification(models.Model):
    """History of blood-bank verification submissions."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    blood_bank = models.ForeignKey(
        BloodBank,
        on_delete=models.CASCADE,
        related_name="verification_records",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    license_number = models.CharField(
        max_length=150,
        blank=True,
    )
    license_expiry_date = models.DateField(
        null=True,
        blank=True,
    )
    license_document = models.FileField(
        upload_to="blood_banks/verification/",
        null=True,
        blank=True,
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="submitted_bank_verifications",
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_bank_verifications",
        null=True,
        blank=True,
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self):
        return (
            f"{self.blood_bank.name} - "
            f"{self.get_status_display()}"
        )