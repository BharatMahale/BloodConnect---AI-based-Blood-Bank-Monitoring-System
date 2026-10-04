from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import is_application_admin
from apps.blood_banks.models import BloodBank
from apps.donors.models import (
    DonationRecord,
    DonorEligibilityAssessment,
    DonorProfile,
)
from apps.donors.serializers import (
    DonationRecordCreateSerializer,
    DonationRecordSerializer,
    DonationHistorySerializer,
    DonorEligibilityAssessmentSerializer,
    DonorProfileSerializer,
    EligibilityCheckInputSerializer,
    NearbyDonorSearchQuerySerializer,
    NearbyDonorResultsSerializer,
)
from apps.donors.services.donations import (
    record_donation,
)
from apps.donors.services.eligibility import (
    assess_donor_eligibility,
)
from apps.locations.utils.distance import (
    calculate_haversine_distance,
)


def user_owns_blood_bank(user, blood_bank=None):
    if not user or not user.is_authenticated:
        return False

    queryset = BloodBank.objects.filter(
        owner=user,
        is_active=True,
    )

    if blood_bank is not None:
        queryset = queryset.filter(
            pk=blood_bank.pk,
        )

    return queryset.exists()


class MyDonorProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get_profile(self, request):
        return get_object_or_404(
            DonorProfile.objects.select_related(
                "user",
                "blood_group",
            ),
            user=request.user,
        )

    @extend_schema(
        summary="Get the current user's donor profile",
        responses=DonorProfileSerializer,
    )
    def get(self, request):
        donor = self.get_profile(request)

        serializer = DonorProfileSerializer(
            donor,
            context={"request": request},
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Create the current user's donor profile",
        request=DonorProfileSerializer,
        responses={201: DonorProfileSerializer},
    )
    def post(self, request):
        if DonorProfile.objects.filter(
            user=request.user
        ).exists():
            return Response(
                {
                    "detail": (
                        "A donor profile already exists "
                        "for this account."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DonorProfileSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        donor = serializer.save(
            user=request.user,
        )

        output_serializer = DonorProfileSerializer(
            donor,
            context={"request": request},
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Update the current user's donor profile",
        request=DonorProfileSerializer,
        responses=DonorProfileSerializer,
    )
    def patch(self, request):
        donor = self.get_profile(request)

        serializer = DonorProfileSerializer(
            donor,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        donor = serializer.save()

        return Response(
            DonorProfileSerializer(
                donor,
                context={"request": request},
            ).data,
            status=status.HTTP_200_OK,
        )


class DonorEligibilityCheckView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Run a preliminary donor eligibility assessment",
        request=EligibilityCheckInputSerializer,
        responses={201: DonorEligibilityAssessmentSerializer},
    )
    def post(self, request):
        donor = get_object_or_404(
            DonorProfile,
            user=request.user,
        )

        input_serializer = EligibilityCheckInputSerializer(
            data=request.data,
        )
        input_serializer.is_valid(
            raise_exception=True
        )

        assessment = assess_donor_eligibility(
            donor=donor,
            answers=input_serializer.validated_data,
        )

        output_serializer = (
            DonorEligibilityAssessmentSerializer(
                assessment
            )
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class MyDonationHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="List the current donor's donation history",
        responses=DonationHistorySerializer,
    )
    def get(self, request):
        donor = get_object_or_404(
            DonorProfile,
            user=request.user,
        )

        donations = (
            DonationRecord.objects
            .select_related(
                "donor",
                "donor__user",
                "blood_bank",
                "blood_group",
                "recorded_by",
            )
            .filter(donor=donor)
        )

        serializer = DonationRecordSerializer(
            donations,
            many=True,
        )

        return Response(
            {
                "count": donations.count(),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class DonationRecordCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Record a donation for an owned blood bank",
        request=DonationRecordCreateSerializer,
        responses={201: DonationRecordSerializer},
    )
    def post(self, request):
        input_serializer = (
            DonationRecordCreateSerializer(
                data=request.data,
            )
        )
        input_serializer.is_valid(
            raise_exception=True
        )

        data = input_serializer.validated_data
        blood_bank = data["blood_bank"]

        allowed = (
            is_application_admin(request.user)
            or user_owns_blood_bank(
                request.user,
                blood_bank,
            )
        )

        if not allowed:
            return Response(
                {
                    "detail": (
                        "You do not have permission to "
                        "record donations for this blood bank."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        donation = record_donation(
            donor=data["donor"],
            blood_bank=blood_bank,
            donation_date=data["donation_date"],
            units_donated=data["units_donated"],
            status=data["status"],
            notes=data.get("notes", ""),
            recorded_by=request.user,
        )

        output_serializer = DonationRecordSerializer(
            donation
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
        )


class NearbyDonorSearchView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Search eligible, available nearby donors",
        parameters=[NearbyDonorSearchQuerySerializer],
        responses=NearbyDonorResultsSerializer,
    )
    def get(self, request):
        allowed = (
            is_application_admin(request.user)
            or user_owns_blood_bank(request.user)
        )

        if not allowed:
            return Response(
                {
                    "detail": (
                        "Only authorized blood-bank staff "
                        "can search for donors."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        query_serializer = (
            NearbyDonorSearchQuerySerializer(
                data=request.query_params,
            )
        )
        query_serializer.is_valid(
            raise_exception=True
        )

        search_data = query_serializer.validated_data

        latitude = search_data["latitude"]
        longitude = search_data["longitude"]
        radius_km = search_data["radius_km"]
        blood_group_id = search_data["blood_group"]

        latest_assessment = (
            DonorEligibilityAssessment.objects
            .filter(donor=OuterRef("pk"))
            .order_by("-assessed_at")
        )

        donors = (
            DonorProfile.objects
            .select_related(
                "blood_group",
            )
            .annotate(
                latest_assessment_is_eligible=Subquery(
                    latest_assessment.values(
                        "is_eligible"
                    )[:1]
                ),
                latest_assessed_at=Subquery(
                    latest_assessment.values(
                        "assessed_at"
                    )[:1]
                ),
            )
            .filter(
                blood_group_id=blood_group_id,
                is_available=True,
                medical_declaration_accepted=True,
                latitude__isnull=False,
                longitude__isnull=False,
                latest_assessment_is_eligible=True,
            )
        )

        results = []

        for donor in donors:
            distance = calculate_haversine_distance(
                latitude_1=latitude,
                longitude_1=longitude,
                latitude_2=donor.latitude,
                longitude_2=donor.longitude,
            )

            if float(distance) > float(radius_km):
                continue

            results.append(
                {
                    "id": str(donor.id),
                    "phone": donor.phone,
                    "blood_group": str(
                        donor.blood_group_id
                    ),
                    "blood_group_name": (
                        donor.blood_group.name
                    ),
                    "city": donor.city,
                    "state": donor.state,
                    "distance_km": round(
                        float(distance),
                        2,
                    ),
                    "last_donation_date": (
                        donor.last_donation_date
                    ),
                    "eligibility_assessed_at": (
                        donor.latest_assessed_at
                    ),
                }
            )

        results.sort(
            key=lambda result: result["distance_km"]
        )

        return Response(
            {
                "count": len(results),
                "results": results,
            },
            status=status.HTTP_200_OK,
        )
