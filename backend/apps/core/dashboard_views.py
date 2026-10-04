from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.blood_banks.models import BloodBank
from apps.blood_requests.models import BloodRequest
from apps.donors.models import (
    DonationRecord,
    DonorProfile,
)
from apps.inventory.models import BloodInventory
from apps.notifications.models import Notification
from apps.core.serializers import (
    MyDashboardSerializer,
    PublicDashboardSerializer,
)


TERMINAL_REQUEST_STATUSES = [
    BloodRequest.Status.COMPLETED,
    BloodRequest.Status.CANCELLED,
    BloodRequest.Status.REJECTED,
    BloodRequest.Status.EXPIRED,
]


def get_inventory_summary(queryset):
    totals = queryset.aggregate(
        total_units_sum=Sum("total_units"),
        reserved_units_sum=Sum("reserved_units"),
    )

    total_units = totals["total_units_sum"] or 0
    reserved_units = totals["reserved_units_sum"] or 0

    return {
        "total_units": total_units,
        "reserved_units": reserved_units,
        "available_units": (
            total_units - reserved_units
        ),
    }


def get_inventory_by_blood_group(queryset):
    rows = (
        queryset
        .values("blood_group__name")
        .annotate(
            total_units_sum=Sum("total_units"),
            reserved_units_sum=Sum(
                "reserved_units"
            ),
        )
        .order_by("blood_group__name")
    )

    results = []

    for row in rows:
        total_units = (
            row["total_units_sum"] or 0
        )
        reserved_units = (
            row["reserved_units_sum"] or 0
        )

        results.append(
            {
                "blood_group": (
                    row["blood_group__name"]
                ),
                "total_units": total_units,
                "reserved_units": reserved_units,
                "available_units": (
                    total_units - reserved_units
                ),
            }
        )

    return results


def get_public_inventory_summary(queryset):
    summary = get_inventory_summary(queryset)

    return {
        "total_units": summary["total_units"],
        "available_units": summary["available_units"],
    }


def get_public_inventory_by_blood_group(queryset):
    return [
        {
            "blood_group": row["blood_group"],
            "total_units": row["total_units"],
            "available_units": row["available_units"],
        }
        for row in get_inventory_by_blood_group(queryset)
    ]

def get_request_status_summary(queryset):
    rows = (
        queryset
        .values("status")
        .annotate(count=Sum(1))
        .order_by("status")
    )

    return {
        row["status"]: row["count"]
        for row in rows
    }


class PublicDashboardOverviewView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Get public BloodConnect dashboard",
        responses=PublicDashboardSerializer,
    )
    def get(self, request):
        visible_banks = BloodBank.objects.filter(
            is_active=True,
            is_public=True,
        )

        inventories = BloodInventory.objects.filter(
            blood_bank__is_active=True,
            blood_bank__is_public=True,
        )

        requests = BloodRequest.objects.all()

        response_data = {
            "blood_banks": {
                "total": visible_banks.count(),
                "verified": visible_banks.filter(
                    verification_status=(
                        BloodBank.VerificationStatus.VERIFIED
                    )
                ).count(),
            },
            "donors": {
                "total": DonorProfile.objects.count(),
                "available": DonorProfile.objects.filter(
                    is_available=True,
                ).count(),
            },
            "requests": {
                "total": requests.count(),
                "active": requests.exclude(
                    status__in=TERMINAL_REQUEST_STATUSES,
                ).count(),
                "completed": requests.filter(
                    status=BloodRequest.Status.COMPLETED,
                ).count(),
                "by_status": (
                    get_request_status_summary(
                        requests
                    )
                ),
            },
            "donations": {
                "total": DonationRecord.objects.count(),
                "completed": DonationRecord.objects.filter(
                    status=(
                        DonationRecord.Status.COMPLETED
                    )
                ).count(),
            },
            "inventory": {
                "summary": get_public_inventory_summary(
                    inventories
                ),
                "by_blood_group": (
                    get_public_inventory_by_blood_group(
                        inventories
                    )
                ),
            },
        }

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )


class MyDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Get dashboard for current user",
        responses=MyDashboardSerializer,
    )
    def get(self, request):
        user = request.user

        my_requests = BloodRequest.objects.filter(
            requester=user,
        )

        owned_banks = BloodBank.objects.filter(
            owner=user,
            is_active=True,
        )

        owned_inventory = BloodInventory.objects.filter(
            blood_bank__in=owned_banks,
        )

        assigned_requests = BloodRequest.objects.filter(
            blood_bank__in=owned_banks,
        )

        donor = (
            DonorProfile.objects
            .select_related(
                "blood_group",
            )
            .filter(user=user)
            .first()
        )

        donor_data = {
            "has_profile": False,
            "is_available": False,
            "is_eligible": None,
            "blood_group": None,
            "donation_count": 0,
            "last_donation_date": None,
        }

        if donor is not None:
            latest_assessment = (
                donor.eligibility_assessments
                .order_by("-assessed_at")
                .first()
            )

            donor_data = {
                "has_profile": True,
                "is_available": donor.is_available,
                "is_eligible": (
                    latest_assessment.is_eligible
                    if latest_assessment
                    else None
                ),
                "blood_group": donor.blood_group.name,
                "donation_count": (
                    donor.donation_records.filter(
                        status=(
                            DonationRecord.Status.COMPLETED
                        )
                    ).count()
                ),
                "last_donation_date": (
                    donor.last_donation_date
                ),
            }

        response_data = {
            "account": {
                "email": user.email,
            },
            "notifications": {
                "unread": Notification.objects.filter(
                    recipient=user,
                    is_read=False,
                ).count(),
            },
            "my_requests": {
                "total": my_requests.count(),
                "active": my_requests.exclude(
                    status__in=TERMINAL_REQUEST_STATUSES,
                ).count(),
                "completed": my_requests.filter(
                    status=(
                        BloodRequest.Status.COMPLETED
                    )
                ).count(),
                "by_status": (
                    get_request_status_summary(
                        my_requests
                    )
                ),
            },
            "donor": donor_data,
            "blood_bank_management": {
                "owned_banks": owned_banks.count(),
                "assigned_requests": (
                    assigned_requests.count()
                ),
                "active_assigned_requests": (
                    assigned_requests.exclude(
                        status__in=(
                            TERMINAL_REQUEST_STATUSES
                        ),
                    ).count()
                ),
                "inventory": get_inventory_summary(
                    owned_inventory
                ),
                "inventory_by_blood_group": (
                    get_inventory_by_blood_group(
                        owned_inventory
                    )
                ),
            },
        }

        return Response(
            response_data,
            status=status.HTTP_200_OK,
        )
