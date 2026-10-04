from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from apps.accounts.permissions import is_application_admin
from apps.accounts.models import Role, UserRole
from apps.locations.serializers import LocationSerializer
from .models import BloodBank, BloodBankVerification


class BloodBankListSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    data_source_label = serializers.CharField(read_only=True)
    information_status = serializers.SerializerMethodField()

    class Meta:
        model = BloodBank
        fields = (
            "id",
            "name",
            "slug",
            "category",
            "location",
            "contact_number",
            "mobile_number",
            "service_time",
            "blood_component_available",
            "apheresis_available",
            "verification_status",
            "is_verified",
            "data_source_label",
            "information_status",
            "information_last_reviewed_at",
        )

    def get_information_status(self, blood_bank) -> str:
        if blood_bank.is_verified:
            return "VERIFIED"

        if (
            blood_bank.source
            == BloodBank.Source.DIRECTORY_IMPORT
        ):
            return "IMPORTED_NOT_VERIFIED"

        if (
            blood_bank.verification_status
            == BloodBank.VerificationStatus.PENDING
        ):
            return "PENDING_VERIFICATION"

        return "NOT_VERIFIED"


class BloodBankDetailSerializer(BloodBankListSerializer):
    owner_email = serializers.EmailField(
        source="owner.email",
        read_only=True,
    )

    class Meta(BloodBankListSerializer.Meta):
        fields = BloodBankListSerializer.Meta.fields + (
            "owner_email",
            "helpline",
            "email",
            "website",
            "license_number",
            "source",
            "source_record_id",
            "is_active",
            "is_public",
            "created_at",
            "updated_at",
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not (
            user
            and user.is_authenticated
            and (
                is_application_admin(user)
                or instance.owner_id == user.id
            )
        ):
            representation.pop("owner_email", None)

        return representation


class BloodBankCreateUpdateSerializer(
    serializers.ModelSerializer
):
    location = LocationSerializer()
    slug = serializers.SlugField(read_only=True)
    verification_status = serializers.CharField(
        read_only=True,
    )
    source = serializers.CharField(read_only=True)

    class Meta:
        model = BloodBank
        fields = (
            "id",
            "name",
            "slug",
            "category",
            "location",
            "contact_number",
            "mobile_number",
            "helpline",
            "email",
            "website",
            "service_time",
            "license_number",
            "blood_component_available",
            "apheresis_available",
            "source",
            "verification_status",
            "is_public",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "slug",
            "source",
            "verification_status",
            "created_at",
            "updated_at",
        )

    def validate_name(self, value):
        cleaned_name = " ".join(value.split())

        if len(cleaned_name) < 3:
            raise serializers.ValidationError(
                "Blood-bank name must contain at least "
                "three characters."
            )

        return cleaned_name

    @transaction.atomic
    def create(self, validated_data):
        location_data = validated_data.pop("location")

        location_serializer = LocationSerializer(
            data=location_data,
        )
        location_serializer.is_valid(raise_exception=True)
        location = location_serializer.save()

        return BloodBank.objects.create(
            location=location,
            **validated_data,
        )

    @transaction.atomic
    def update(self, instance, validated_data):
        location_data = validated_data.pop(
            "location",
            None,
        )

        if location_data is not None:
            location_serializer = LocationSerializer(
                instance.location,
                data=location_data,
                partial=self.partial,
            )
            location_serializer.is_valid(raise_exception=True)
            location_serializer.save()

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        return instance


class BloodBankVerificationSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = BloodBankVerification
        fields = (
            "id",
            "blood_bank",
            "status",
            "license_number",
            "license_expiry_date",
            "license_document",
            "submitted_by",
            "reviewed_by",
            "submitted_at",
            "reviewed_at",
            "remarks",
        )
        read_only_fields = (
            "id",
            "blood_bank",
            "status",
            "submitted_by",
            "reviewed_by",
            "submitted_at",
            "reviewed_at",
        )


class BloodBankVerificationDecisionSerializer(
    serializers.Serializer
):
    status = serializers.ChoiceField(
        choices=(
            BloodBankVerification.Status.APPROVED,
            BloodBankVerification.Status.REJECTED,
        )
    )
    remarks = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
    )

    @transaction.atomic
    def save(self, **kwargs):
        blood_bank = self.context["blood_bank"]
        reviewed_by = self.context["request"].user
        decision = self.validated_data["status"]
        remarks = self.validated_data.get("remarks", "")

        verification = (
            blood_bank.verification_records.filter(
                status=BloodBankVerification.Status.PENDING,
            )
            .order_by("-submitted_at")
            .first()
        )

        if verification is None:
            verification = BloodBankVerification.objects.create(
                blood_bank=blood_bank,
                submitted_by=blood_bank.owner,
                license_number=blood_bank.license_number,
            )

        verification.status = decision
        verification.reviewed_by = reviewed_by
        verification.reviewed_at = timezone.now()
        verification.remarks = remarks

        verification.save(
            update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
                "remarks",
            ]
        )

        if (
            decision
            == BloodBankVerification.Status.APPROVED
        ):
            blood_bank.verification_status = (
                BloodBank.VerificationStatus.VERIFIED
            )
            blood_bank.information_last_reviewed_at = (
                timezone.now()
            )

            self._assign_staff_role(blood_bank)
        else:
            blood_bank.verification_status = (
                BloodBank.VerificationStatus.REJECTED
            )

        blood_bank.save(
            update_fields=[
                "verification_status",
                "information_last_reviewed_at",
                "updated_at",
            ]
        )

        return verification

    @staticmethod
    def _assign_staff_role(blood_bank):
        if blood_bank.owner is None:
            return

        role, _ = Role.objects.get_or_create(
            code=Role.Code.BLOOD_BANK_STAFF,
            defaults={
                "name": Role.Code.BLOOD_BANK_STAFF.label,
                "description": (
                    "Staff member associated with a verified "
                    "blood bank."
                ),
            },
        )

        UserRole.objects.get_or_create(
            user=blood_bank.owner,
            role=role,
            defaults={
                "is_primary": False,
                "is_active": True,
            },
        )


class NearbySearchQuerySerializer(
    serializers.Serializer
):
    latitude = serializers.FloatField(
        min_value=-90,
        max_value=90,
    )
    longitude = serializers.FloatField(
        min_value=-180,
        max_value=180,
    )
    radius_km = serializers.FloatField(
        min_value=1,
        max_value=100,
        default=10,
        required=False,
    )
    category = serializers.ChoiceField(
        choices=BloodBank.Category.choices,
        required=False,
    )
    component_available = serializers.BooleanField(
        required=False,
    )
    apheresis_available = serializers.BooleanField(
        required=False,
    )
    verified_only = serializers.BooleanField(
        default=False,
        required=False,
    )


class NearbyBloodBankSerializer(
    BloodBankListSerializer
):
    distance_km = serializers.FloatField(
        read_only=True,
    )

    class Meta(BloodBankListSerializer.Meta):
        fields = (
            BloodBankListSerializer.Meta.fields
            + ("distance_km",)
        )
