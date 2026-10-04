from django.core.exceptions import (
    ValidationError as DjangoValidationError,
)
from django.db import transaction
from django.db.models import Q
from django_filters.rest_framework import (
    DjangoFilterBackend,
)
from drf_spectacular.utils import extend_schema
from rest_framework import (
    filters,
    mixins,
    status,
    viewsets,
)
from rest_framework.decorators import action
from rest_framework.permissions import (
    IsAuthenticated,
)
from rest_framework.response import Response

from apps.blood_requests.filters import (
    BloodRequestFilter,
)
from apps.blood_requests.models import (
    BloodRequest,
)
from apps.blood_requests.permissions import (
    IsBloodRequestParticipant,
    manages_request_blood_bank,
)
from apps.accounts.permissions import is_application_admin
from apps.blood_requests.serializers import (
    AssignBloodBankSerializer,
    BloodBankSuggestionSerializer,
    BloodRequestBankAssignmentSerializer,
    BloodRequestCancelSerializer,
    BloodRequestCreateSerializer,
    BloodRequestDetailSerializer,
    BloodRequestListSerializer,
    BloodRequestReservationSerializer,
    BloodRequestStatusHistorySerializer,
    BloodRequestStatusUpdateSerializer,
    FulfilInventorySerializer,
    ReleaseInventorySerializer,
    ReserveInventorySerializer,
    SuggestedBanksQuerySerializer,
)
from apps.blood_requests.services import (
    assign_blood_bank,
    fulfil_inventory_reservation,
    release_inventory_reservation,
    reserve_inventory_for_request,
    suggest_blood_banks,
    transition_blood_request,
)
from apps.notifications.models import Notification
from apps.notifications.services import (
    notify_requester,
)


class BloodRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [
        IsAuthenticated,
        IsBloodRequestParticipant,
    ]

    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
        filters.SearchFilter,
    ]

    filterset_class = BloodRequestFilter

    search_fields = [
        "request_number",
        "patient_name",
        "hospital_name",
        "blood_bank__name",
    ]

    ordering_fields = [
        "created_at",
        "updated_at",
        "required_date",
        "urgency",
        "status",
    ]

    ordering = [
        "-created_at"
    ]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return BloodRequest.objects.none()

        queryset = (
            BloodRequest.objects
            .select_related(
                "requester",
                "blood_bank",
                "blood_group",
                "component",
                "reviewed_by",
                "reservation",
                "reservation__inventory",
                "reservation__inventory__blood_bank",
                "reservation__inventory__blood_group",
                "reservation__inventory__component",
                "reservation__created_by",
                "reservation__released_by",
            )
            .prefetch_related(
                "status_history",
                "status_history__changed_by",
                "assignment_history",
                "assignment_history__previous_blood_bank",
                "assignment_history__new_blood_bank",
                "assignment_history__assigned_by",
            )
        )

        user = self.request.user

        if is_application_admin(user):
            return queryset

        return queryset.filter(
            Q(requester=user)
            | Q(blood_bank__owner=user)
        ).distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return BloodRequestCreateSerializer

        if self.action == "list":
            return BloodRequestListSerializer

        if self.action == "update_status":
            return BloodRequestStatusUpdateSerializer

        if self.action == "cancel":
            return BloodRequestCancelSerializer

        if self.action == "reserve_inventory":
            return ReserveInventorySerializer

        if self.action == "fulfil_inventory":
            return FulfilInventorySerializer

        if self.action == "release_inventory":
            return ReleaseInventorySerializer

        if self.action == "history":
            return BloodRequestStatusHistorySerializer

        if self.action == "suggested_banks":
            return SuggestedBanksQuerySerializer

        if self.action == "assign_bank":
            return AssignBloodBankSerializer

        if self.action == "assignment_history":
            return BloodRequestBankAssignmentSerializer

        return BloodRequestDetailSerializer

    @extend_schema(
        summary="Submit a blood requirement",
        request=BloodRequestCreateSerializer,
        responses={
            status.HTTP_201_CREATED: (
                BloodRequestDetailSerializer
            )
        },
    )
    def create(self, request, *args, **kwargs):
        input_serializer = (
            BloodRequestCreateSerializer(
                data=request.data,
                context=self.get_serializer_context(),
            )
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        blood_request = input_serializer.save()

        output_serializer = (
            BloodRequestDetailSerializer(
                blood_request,
                context=self.get_serializer_context(),
            )
        )

        response_data = {
            "message": (
                "Blood request submitted successfully. "
                "Availability is not guaranteed; please "
                "contact the selected blood bank or "
                "hospital for confirmation."
            ),
            "emergency_notice": (
                "This platform does not replace emergency "
                "medical services."
            ),
            "blood_request": output_serializer.data,
        }

        return Response(
            response_data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Update blood-request status",
        request=BloodRequestStatusUpdateSerializer,
        responses=BloodRequestDetailSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="update-status",
    )
    def update_status(self, request, pk=None):
        blood_request = self.get_object()

        if not manages_request_blood_bank(
            request.user,
            blood_request,
        ):
            return Response(
                {
                    "detail": (
                        "Only the assigned blood-bank "
                        "owner or an administrator can "
                        "update this request."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        input_serializer = (
            BloodRequestStatusUpdateSerializer(
                data=request.data
            )
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        data = input_serializer.validated_data
        new_status = data["new_status"]

        bank_allowed_statuses = {
            BloodRequest.Status.UNDER_REVIEW,
            BloodRequest.Status.ACCEPTED,
            BloodRequest.Status.REJECTED,
            BloodRequest.Status.EXPIRED,
        }

        if new_status not in bank_allowed_statuses:
            return Response(
                {
                    "detail": (
                        "Use fulfil-inventory to record "
                        "partial or completed fulfilment."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                statuses_requiring_release = {
                    BloodRequest.Status.REJECTED,
                    BloodRequest.Status.EXPIRED,
                }

                if (
                    new_status
                    in statuses_requiring_release
                ):
                    release_inventory_reservation(
                        blood_request=blood_request,
                        released_by=request.user,
                        reason=(
                            data.get("note")
                            or "Request closed."
                        ),
                    )

                updated_request = (
                    transition_blood_request(
                        blood_request=blood_request,
                        new_status=new_status,
                        changed_by=request.user,
                        note=data.get("note", ""),
                        units_fulfilled=data.get(
                            "units_fulfilled"
                        ),
                    )
                )

        except DjangoValidationError as error:
            message = (
                error.messages[0]
                if hasattr(error, "messages")
                else str(error)
            )

            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        output_serializer = (
            BloodRequestDetailSerializer(
                updated_request,
                context=self.get_serializer_context(),
            )
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_200_OK,
        )


    @extend_schema(
        summary="Cancel a blood request",
        request=BloodRequestCancelSerializer,
        responses=BloodRequestDetailSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="cancel",
    )
    def cancel(self, request, pk=None):
        blood_request = self.get_object()

        if (
            blood_request.requester_id
            != request.user.id
            and not is_application_admin(request.user)
        ):
            return Response(
                {
                    "detail": (
                        "Only the requester or an "
                        "administrator can cancel "
                        "this request."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        input_serializer = (
            BloodRequestCancelSerializer(
                data=request.data
            )
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        cancellation_reason = (
            input_serializer
            .validated_data["reason"]
        )

        try:
            with transaction.atomic():
                # If inventory is reserved, release it.
                release_inventory_reservation(
                    blood_request=blood_request,
                    released_by=request.user,
                    reason=cancellation_reason,
                )

                # Change the request status to cancelled.
                cancelled_request = (
                    transition_blood_request(
                        blood_request=blood_request,
                        new_status=(
                            BloodRequest.Status.CANCELLED
                        ),
                        changed_by=request.user,
                        note=cancellation_reason,
                    )
                )

        except DjangoValidationError as error:
            message = (
                error.messages[0]
                if hasattr(error, "messages")
                else str(error)
            )

            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # This was missing from the previous method.
        output_serializer = (
            BloodRequestDetailSerializer(
                cancelled_request,
                context=self.get_serializer_context(),
            )
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_200_OK,
        )


    @extend_schema(
        summary="View blood-request status history",
        responses=(
            BloodRequestStatusHistorySerializer(
                many=True
            )
        ),
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="history",
    )
    def history(self, request, pk=None):
        blood_request = self.get_object()

        history_queryset = (
            blood_request.status_history
            .select_related("changed_by")
            .order_by("-created_at")
        )

        page = self.paginate_queryset(
            history_queryset
        )

        if page is not None:
            serializer = (
                BloodRequestStatusHistorySerializer(
                    page,
                    many=True,
                )
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = (
            BloodRequestStatusHistorySerializer(
                history_queryset,
                many=True,
            )
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )


    @extend_schema(
        summary="Reserve inventory for a blood request",
        request=ReserveInventorySerializer,
        responses=BloodRequestReservationSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="reserve-inventory",
    )
    def reserve_inventory(self, request, pk=None):
        blood_request = self.get_object()

        if not manages_request_blood_bank(
            request.user,
            blood_request,
        ):
            return Response(
                {
                    "detail": (
                        "Only the assigned blood-bank "
                        "owner or an administrator can "
                        "reserve inventory."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        input_serializer = ReserveInventorySerializer(
            data=request.data
        )
        input_serializer.is_valid(
            raise_exception=True
        )

        try:
            reservation = reserve_inventory_for_request(
                blood_request=blood_request,
                quantity=(
                    input_serializer
                    .validated_data["quantity"]
                ),
                created_by=request.user,
            )

        except DjangoValidationError as error:
            message = (
                error.messages[0]
                if hasattr(error, "messages")
                else str(error)
            )

            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        output_serializer = (
            BloodRequestReservationSerializer(
                reservation
            )
        )

        return Response(
            {
                "message": (
                    "Inventory reserved successfully."
                ),
                "reservation": output_serializer.data,
            },
            status=status.HTTP_200_OK,
        )


    @extend_schema(
        summary="Fulfil a request using reserved inventory",
        request=FulfilInventorySerializer,
        responses=BloodRequestDetailSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="fulfil-inventory",
    )
    def fulfil_inventory(self, request, pk=None):
        blood_request = self.get_object()

        if not manages_request_blood_bank(
            request.user,
            blood_request,
        ):
            return Response(
                {
                    "detail": (
                        "Only the assigned blood-bank "
                        "owner or an administrator can "
                        "fulfil this request."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        input_serializer = FulfilInventorySerializer(
            data=request.data
        )
        input_serializer.is_valid(
            raise_exception=True
        )

        data = input_serializer.validated_data

        try:
            (
                updated_request,
                reservation,
            ) = fulfil_inventory_reservation(
                blood_request=blood_request,
                quantity=data["quantity"],
                fulfilled_by=request.user,
                note=data["note"],
            )

        except DjangoValidationError as error:
            message = (
                error.messages[0]
                if hasattr(error, "messages")
                else str(error)
            )

            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request_serializer = (
            BloodRequestDetailSerializer(
                updated_request,
                context=self.get_serializer_context(),
            )
        )

        reservation_serializer = (
            BloodRequestReservationSerializer(
                reservation
            )
        )

        return Response(
            {
                "message": (
                    "Reserved inventory fulfilled "
                    "successfully."
                ),
                "blood_request": (
                    request_serializer.data
                ),
                "reservation": (
                    reservation_serializer.data
                ),
            },
            status=status.HTTP_200_OK,
        )


    @extend_schema(
        summary="Release reserved inventory",
        request=ReleaseInventorySerializer,
        responses=BloodRequestReservationSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="release-inventory",
    )
    def release_inventory(self, request, pk=None):
        blood_request = self.get_object()

        if not manages_request_blood_bank(
            request.user,
            blood_request,
        ):
            return Response(
                {
                    "detail": (
                        "Only the assigned blood-bank "
                        "owner or an administrator can "
                        "release inventory."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        input_serializer = ReleaseInventorySerializer(
            data=request.data
        )
        input_serializer.is_valid(
            raise_exception=True
        )

        try:
            reservation = (
                release_inventory_reservation(
                    blood_request=blood_request,
                    released_by=request.user,
                    reason=(
                        input_serializer
                        .validated_data["reason"]
                    ),
                )
            )

        except DjangoValidationError as error:
            message = (
                error.messages[0]
                if hasattr(error, "messages")
                else str(error)
            )

            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if reservation is None:
            return Response(
                {
                    "detail": (
                        "This request does not have an "
                        "inventory reservation."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        notify_requester(
            blood_request=blood_request,
            notification_type=(
                Notification.Type.STATUS_UPDATED
            ),
            title="Reserved inventory released",
            message=(
                f"Reserved units for request "
                f"{blood_request.request_number} "
                f"were released."
            ),
        )

        output_serializer = (
            BloodRequestReservationSerializer(
                reservation
            )
        )

        return Response(
            {
                "message": (
                    "Reserved inventory released "
                    "successfully."
                ),
                "reservation": output_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Suggest nearby blood banks",
        parameters=[SuggestedBanksQuerySerializer],
        responses=BloodBankSuggestionSerializer(
            many=True
        ),
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="suggested-banks",
    )
    def suggested_banks(self, request, pk=None):
        blood_request = self.get_object()

        query_serializer = (
            SuggestedBanksQuerySerializer(
                data=request.query_params
            )
        )

        query_serializer.is_valid(
            raise_exception=True
        )

        data = query_serializer.validated_data

        try:
            suggestions = suggest_blood_banks(
                blood_request=blood_request,
                radius_km=data["radius_km"],
                limit=data["limit"],
            )

        except DjangoValidationError as error:
            message = (
                error.messages[0]
                if hasattr(error, "messages")
                else str(error)
            )

            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        output_serializer = (
            BloodBankSuggestionSerializer(
                suggestions,
                many=True,
            )
        )

        return Response(
            {
                "request_number": (
                    blood_request.request_number
                ),
                "required_units": (
                    blood_request.remaining_units
                ),
                "radius_km": data["radius_km"],
                "count": len(
                    output_serializer.data
                ),
                "results": output_serializer.data,
                "notice": (
                    "Availability may change. Contact the "
                    "blood bank or hospital before visiting."
                ),
                "emergency_notice": (
                    "This platform does not replace "
                    "emergency medical services."
                ),
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="Assign a blood bank to a request",
        request=AssignBloodBankSerializer,
        responses=BloodRequestDetailSerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="assign-bank",
    )
    def assign_bank(self, request, pk=None):
        blood_request = self.get_object()

        allowed = (
            blood_request.requester_id
            == request.user.id
            or is_application_admin(request.user)
        )

        if not allowed:
            return Response(
                {
                    "detail": (
                        "Only the requester or an "
                        "administrator can assign a "
                        "blood bank."
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        input_serializer = AssignBloodBankSerializer(
            data=request.data
        )

        input_serializer.is_valid(
            raise_exception=True
        )

        data = input_serializer.validated_data

        try:
            updated_request = assign_blood_bank(
                blood_request=blood_request,
                blood_bank=data["blood_bank"],
                assigned_by=request.user,
                reason=data.get("reason", ""),
            )

        except DjangoValidationError as error:
            message = (
                error.messages[0]
                if hasattr(error, "messages")
                else str(error)
            )

            return Response(
                {"detail": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        output_serializer = (
            BloodRequestDetailSerializer(
                updated_request,
                context=self.get_serializer_context(),
            )
        )

        return Response(
            {
                "message": (
                    "Blood bank assigned successfully."
                ),
                "blood_request": output_serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary="View blood-bank assignment history",
        responses=(
            BloodRequestBankAssignmentSerializer(
                many=True
            )
        ),
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="assignment-history",
    )
    def assignment_history(
        self,
        request,
        pk=None,
    ):
        blood_request = self.get_object()

        queryset = (
            blood_request.assignment_history
            .select_related(
                "previous_blood_bank",
                "new_blood_bank",
                "assigned_by",
            )
            .order_by("-created_at")
        )

        serializer = (
            BloodRequestBankAssignmentSerializer(
                queryset,
                many=True,
            )
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
