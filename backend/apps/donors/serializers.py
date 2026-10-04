from datetime import date

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from apps.donors.models import (
    DonationRecord,
    DonorEligibilityAssessment,
    DonorProfile,
)
from apps.blood_banks.models import BloodBank


class DonorEligibilityAssessmentSerializer(
    serializers.ModelSerializer
):
    class Meta:
        model = DonorEligibilityAssessment
        fields = [
            "id",
            "is_eligible",
            "age_at_assessment",
            "weight_at_assessment",
            "reasons",
            "assessed_at",
        ]
        read_only_fields = fields


class DonorProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        source="user.email",
        read_only=True,
    )

    blood_group_name = serializers.CharField(
        source="blood_group.name",
        read_only=True,
    )

    latest_assessment = serializers.SerializerMethodField()

    class Meta:
        model = DonorProfile
        fields = [
            "id",
            "email",
            "blood_group",
            "blood_group_name",
            "date_of_birth",
            "gender",
            "weight_kg",
            "phone",
            "address",
            "city",
            "state",
            "pincode",
            "latitude",
            "longitude",
            "last_donation_date",
            "is_available",
            "medical_declaration_accepted",
            "latest_assessment",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "email",
            "blood_group_name",
            "latest_assessment",
            "created_at",
            "updated_at",
        ]

    @extend_schema_field(
        DonorEligibilityAssessmentSerializer(allow_null=True)
    )
    def get_latest_assessment(self, donor):
        assessment = (
            donor.eligibility_assessments
            .order_by("-assessed_at")
            .first()
        )

        if assessment is None:
            return None

        return DonorEligibilityAssessmentSerializer(
            assessment
        ).data

    def validate_date_of_birth(self, value):
        if value >= date.today():
            raise serializers.ValidationError(
                "Date of birth must be in the past."
            )

        return value

    def validate_last_donation_date(self, value):
        if value and value > date.today():
            raise serializers.ValidationError(
                "Last donation date cannot be in the future."
            )

        return value


class EligibilityCheckInputSerializer(serializers.Serializer):
    feeling_well = serializers.BooleanField()

    has_fever_or_infection = serializers.BooleanField(
        default=False,
    )

    taking_antibiotics = serializers.BooleanField(
        default=False,
    )

    recent_surgery = serializers.BooleanField(
        default=False,
    )

    pregnant_or_breastfeeding = serializers.BooleanField(
        default=False,
    )

    recent_tattoo_or_piercing = serializers.BooleanField(
        default=False,
    )


class DonationRecordCreateSerializer(
    serializers.Serializer
):
    donor = serializers.PrimaryKeyRelatedField(
        queryset=DonorProfile.objects.select_related(
            "user",
            "blood_group",
        ),
    )

    blood_bank = serializers.PrimaryKeyRelatedField(
        queryset=BloodBank.objects.filter(
            is_active=True,
        ),
    )

    donation_date = serializers.DateField()

    units_donated = serializers.IntegerField(
        min_value=1,
        max_value=10,
        default=1,
    )

    status = serializers.ChoiceField(
        choices=DonationRecord.Status.choices,
        default=DonationRecord.Status.COMPLETED,
    )

    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
    )

    def validate_donation_date(self, value):
        if value > date.today():
            raise serializers.ValidationError(
                "Donation date cannot be in the future."
            )

        return value


class DonationRecordSerializer(
    serializers.ModelSerializer
):
    blood_bank_name = serializers.CharField(
        source="blood_bank.name",
        read_only=True,
    )

    blood_group_name = serializers.CharField(
        source="blood_group.name",
        read_only=True,
    )

    donor_email = serializers.EmailField(
        source="donor.user.email",
        read_only=True,
    )

    recorded_by_email = serializers.EmailField(
        source="recorded_by.email",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = DonationRecord
        fields = [
            "id",
            "donor",
            "donor_email",
            "blood_bank",
            "blood_bank_name",
            "blood_group",
            "blood_group_name",
            "donation_date",
            "units_donated",
            "status",
            "notes",
            "recorded_by_email",
            "created_at",
            "updated_at",
        ]

        read_only_fields = fields


class NearbyDonorSearchQuerySerializer(
    serializers.Serializer
):
    blood_group = serializers.UUIDField()

    latitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-90,
        max_value=90,
    )

    longitude = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-180,
        max_value=180,
    )

    radius_km = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=1,
        max_value=100,
        default=25,
    )


class DonationHistorySerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = DonationRecordSerializer(many=True)


class NearbyDonorResultSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    phone = serializers.CharField()
    blood_group = serializers.UUIDField()
    blood_group_name = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    distance_km = serializers.FloatField()
    last_donation_date = serializers.DateField(allow_null=True)
    eligibility_assessed_at = serializers.DateTimeField()


class NearbyDonorResultsSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = NearbyDonorResultSerializer(many=True)
