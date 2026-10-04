from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response

from apps.accounts.permissions import is_application_admin
from .filters import BloodInventoryFilter
from .models import (
    BloodComponent,
    BloodGroup,
    BloodInventory,
    InventoryTransaction,
)
from .permissions import IsBloodBankOwnerOrAdmin
from .serializers import (
    BloodComponentSerializer,
    BloodGroupSerializer,
    BloodInventorySerializer,
    InventoryTransactionSerializer,
    StockUpdateSerializer,
)
from .services.transactions import (
    adjust_inventory,
    record_inventory_transaction,
)
from django.db.models import Q
from apps.blood_banks.models import BloodBank


class BloodGroupViewSet(
    viewsets.ReadOnlyModelViewSet
):
    permission_classes = [AllowAny]
    serializer_class = BloodGroupSerializer
    pagination_class = None

    queryset = BloodGroup.objects.all().order_by(
        "name"
    )


class BloodComponentViewSet(
    viewsets.ReadOnlyModelViewSet
):
    permission_classes = [AllowAny]
    serializer_class = BloodComponentSerializer
    pagination_class = None

    queryset = BloodComponent.objects.all().order_by(
        "name"
    )


class BloodInventoryViewSet(
    viewsets.ModelViewSet
):
    serializer_class = BloodInventorySerializer
    permission_classes = [
        IsBloodBankOwnerOrAdmin
    ]

    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]

    filterset_class = BloodInventoryFilter

    ordering_fields = [
        "total_units",
        "reserved_units",
        "last_updated_at",
        "blood_group__name",
        "component__name",
    ]

    ordering = [
        "blood_bank__name",
        "blood_group__name",
        "component__name",
    ]

    http_method_names = [
        "get",
        "post",
        "head",
        "options",
    ]

    def user_is_application_admin(self):
        if not hasattr(self, "_user_is_application_admin"):
            self._user_is_application_admin = (
                is_application_admin(self.request.user)
            )

        return self._user_is_application_admin

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["can_view_all_reserved_units"] = (
            self.user_is_application_admin()
        )
        return context

    def get_queryset(self):
        queryset = (
            BloodInventory.objects
            .select_related(
                "blood_bank",
                "blood_group",
                "component",
                "last_updated_by",
            )
        )

        user = self.request.user

        if self.user_is_application_admin():
            return queryset

        public_statuses = [
            BloodBank.VerificationStatus.VERIFIED,
            BloodBank.VerificationStatus
            .DIRECTORY_IMPORTED,
        ]

        visibility_condition = Q(
            blood_bank__is_active=True,
            blood_bank__is_public=True,
            blood_bank__verification_status__in=(
                public_statuses
            ),
        )

        if user.is_authenticated:
            visibility_condition |= Q(
                blood_bank__owner=user
            )

        return queryset.filter(
            visibility_condition
        ).distinct()

    def get_permissions(self):
        if self.action in [
            "list",
            "retrieve",
        ]:
            return [AllowAny()]

        return [
            IsAuthenticated(),
            IsBloodBankOwnerOrAdmin(),
        ]

    @extend_schema(
        summary=(
            "Create an audited inventory transaction"
        ),
        request=StockUpdateSerializer,
        responses=BloodInventorySerializer,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="update-stock",
    )
    def update_stock(self, request, pk=None):
        inventory = self.get_object()

        self.check_object_permissions(
            request,
            inventory,
        )

        input_serializer = StockUpdateSerializer(
            data=request.data
        )
        input_serializer.is_valid(
            raise_exception=True
        )

        data = input_serializer.validated_data
        transaction_type = data[
            "transaction_type"
        ]

        try:
            if transaction_type == (
                InventoryTransaction.Type.ADJUSTMENT
            ):
                adjust_inventory(
                    inventory=inventory,
                    new_total_units=data["quantity"],
                    reason=data["reason"],
                    created_by=request.user,
                    reference_number=data.get(
                        "reference_number",
                        "",
                    ),
                )

            else:
                record_inventory_transaction(
                    inventory=inventory,
                    transaction_type=(
                        transaction_type
                    ),
                    quantity=data["quantity"],
                    reason=data["reason"],
                    created_by=request.user,
                    reference_number=data.get(
                        "reference_number",
                        "",
                    ),
                )

        except ValidationError as error:
            if hasattr(error, "messages"):
                message = error.messages[0]
            else:
                message = str(error)

            return Response(
                {"detail": message},
                status=(
                    status.HTTP_400_BAD_REQUEST
                ),
            )

        inventory.refresh_from_db()

        output_serializer = (
            BloodInventorySerializer(
                inventory,
                context=(
                    self.get_serializer_context()
                ),
            )
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        summary=(
            "View inventory transaction history"
        ),
        responses=(
            InventoryTransactionSerializer(
                many=True
            )
        ),
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="transactions",
    )
    def transactions(self, request, pk=None):
        inventory = self.get_object()

        self.check_object_permissions(
            request,
            inventory,
        )

        queryset = (
            InventoryTransaction.objects
            .filter(inventory=inventory)
            .select_related("created_by")
            .order_by("-created_at")
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = (
                InventoryTransactionSerializer(
                    page,
                    many=True,
                )
            )

            return self.get_paginated_response(
                serializer.data
            )

        serializer = (
            InventoryTransactionSerializer(
                queryset,
                many=True,
            )
        )

        return Response(
            serializer.data,
            status=status.HTTP_200_OK,
        )
