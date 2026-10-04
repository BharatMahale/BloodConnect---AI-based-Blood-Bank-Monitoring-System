from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response
from apps.accounts.permissions import (
    IsAdmin,
    is_application_admin,
)
from .filters import BloodBankFilter
from .models import BloodBank, BloodBankVerification
from .permissions import IsBloodBankOwnerOrAdminOrReadOnly
from .serializers import (
    BloodBankCreateUpdateSerializer,
    BloodBankDetailSerializer,
    BloodBankListSerializer,
    BloodBankVerificationDecisionSerializer,
    BloodBankVerificationSerializer,
    NearbyBloodBankSerializer,
    NearbySearchQuerySerializer,
)
from apps.locations.utils.distance import (
    calculate_haversine_distance,
)


class BloodBankViewSet(viewsets.ModelViewSet):
    lookup_field = "slug"
    filterset_class = BloodBankFilter

    search_fields = (
        "name",
        "location__city",
        "location__district",
        "location__state",
        "location__pincode",
        "license_number",
    )

    ordering_fields = (
        "name",
        "created_at",
        "updated_at",
        "information_last_reviewed_at",
    )

    ordering = ("name",)

    def get_queryset(self):
        queryset = BloodBank.objects.select_related(
            "location",
            "owner",
        )

        user = self.request.user

        if is_application_admin(user):
            return queryset

        public_statuses = (
            BloodBank.VerificationStatus.VERIFIED,
            BloodBank.VerificationStatus.DIRECTORY_IMPORTED,
        )

        visibility_condition = Q(
            is_active=True,
            is_public=True,
            verification_status__in=public_statuses,
        )

        if user.is_authenticated:
            visibility_condition |= Q(owner=user)

        return queryset.filter(
            visibility_condition
        ).distinct()

    def get_serializer_class(self):
        if self.action == "list":
            return BloodBankListSerializer

        if self.action == "retrieve":
            return BloodBankDetailSerializer

        return BloodBankCreateUpdateSerializer

    def get_permissions(self):
        public_actions = [
            "list",
            "retrieve",
            "nearby",
        ]

        if self.action in public_actions:
            permission_classes = [AllowAny]

        elif self.action == "verify":
            permission_classes = [
                IsAuthenticated,
                IsAdmin,
            ]

        else:
            permission_classes = [
                IsAuthenticated,
                IsBloodBankOwnerOrAdminOrReadOnly,
            ]

        return [
            permission_class()
            for permission_class in permission_classes
        ]


    @extend_schema(
        summary="Register a blood bank",
        request=BloodBankCreateUpdateSerializer,
        responses={
            status.HTTP_201_CREATED: (
                BloodBankDetailSerializer
            )
        },
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        blood_bank = serializer.save(
            owner=request.user,
            source=BloodBank.Source.USER_REGISTERED,
            verification_status=(
                BloodBank.VerificationStatus.PENDING
            ),
        )

        BloodBankVerification.objects.create(
            blood_bank=blood_bank,
            submitted_by=request.user,
            license_number=blood_bank.license_number,
        )

        output = BloodBankDetailSerializer(
            blood_bank,
            context=self.get_serializer_context(),
        )

        return Response(
            {
                "message": (
                    "Blood-bank registration submitted for "
                    "verification."
                ),
                "blood_bank": output.data,
            },
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Update a blood bank",
        request=BloodBankCreateUpdateSerializer,
        responses=BloodBankDetailSerializer,
    )
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        blood_bank = serializer.save()

        output = BloodBankDetailSerializer(
            blood_bank,
            context=self.get_serializer_context(),
        )

        return Response(output.data)

    def destroy(self, request, *args, **kwargs):
        blood_bank = self.get_object()

        blood_bank.is_active = False
        blood_bank.is_public = False
        blood_bank.save(
            update_fields=[
                "is_active",
                "is_public",
                "updated_at",
            ]
        )

        return Response(
            {
                "message": (
                    "Blood-bank profile deactivated."
                )
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Approve or reject a blood bank",
        request=BloodBankVerificationDecisionSerializer,
        responses=BloodBankVerificationSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="verify",
    )
    def verify(self, request, slug=None):
        blood_bank = self.get_object()

        serializer = (
            BloodBankVerificationDecisionSerializer(
                data=request.data,
                context={
                    "request": request,
                    "blood_bank": blood_bank,
                },
            )
        )

        serializer.is_valid(raise_exception=True)
        verification = serializer.save()

        return Response(
            {
                "message": (
                    "Blood-bank verification decision "
                    "recorded."
                ),
                "verification": (
                    BloodBankVerificationSerializer(
                        verification
                    ).data
                ),
                "blood_bank_status": (
                    blood_bank.verification_status
                ),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Find nearby blood banks",
        parameters=[NearbySearchQuerySerializer],
        responses=NearbyBloodBankSerializer(many=True),
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="nearby",
    )
    def nearby(self, request):
        query_serializer = NearbySearchQuerySerializer(
            data=request.query_params,
        )
        query_serializer.is_valid(raise_exception=True)

        search_data = query_serializer.validated_data

        user_latitude = search_data["latitude"]
        user_longitude = search_data["longitude"]
        radius_km = search_data["radius_km"]

        public_statuses = [
            BloodBank.VerificationStatus.VERIFIED,
            BloodBank.VerificationStatus.DIRECTORY_IMPORTED,
        ]

        queryset = BloodBank.objects.select_related(
            "location",
            "owner",
        ).filter(
            is_active=True,
            is_public=True,
            verification_status__in=public_statuses,
            location__latitude__isnull=False,
            location__longitude__isnull=False,
        )

        category = search_data.get("category")

        if category:
            queryset = queryset.filter(
                category=category,
            )

        if "component_available" in request.query_params:
            queryset = queryset.filter(
                blood_component_available=(
                    search_data["component_available"]
                )
            )

        if "apheresis_available" in request.query_params:
            queryset = queryset.filter(
                apheresis_available=(
                    search_data["apheresis_available"]
                )
            )

        if search_data["verified_only"]:
            queryset = queryset.filter(
                verification_status=(
                    BloodBank.VerificationStatus.VERIFIED
                )
            )

        nearby_banks = []

        for blood_bank in queryset:
            distance = calculate_haversine_distance(
                latitude_1=user_latitude,
                longitude_1=user_longitude,
                latitude_2=blood_bank.location.latitude,
                longitude_2=blood_bank.location.longitude,
            )

            if float(distance) <= float(radius_km):
                blood_bank.distance_km = round(
                    distance,
                    2,
                )
                nearby_banks.append(blood_bank)

        nearby_banks.sort(
            key=lambda blood_bank: blood_bank.distance_km
        )

        page = self.paginate_queryset(nearby_banks)

        if page is not None:
            output_serializer = NearbyBloodBankSerializer(
                page,
                many=True,
                context=self.get_serializer_context(),
            )

            return self.get_paginated_response(
                output_serializer.data
            )

        output_serializer = NearbyBloodBankSerializer(
            nearby_banks,
            many=True,
            context=self.get_serializer_context(),
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_200_OK,
        )
