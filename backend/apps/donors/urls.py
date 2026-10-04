from django.urls import path

from apps.donors.views import (
    DonationRecordCreateView,
    DonorEligibilityCheckView,
    MyDonationHistoryView,
    MyDonorProfileView,
    NearbyDonorSearchView,
)


app_name = "donors"


urlpatterns = [
    path(
        "donors/me/",
        MyDonorProfileView.as_view(),
        name="my-donor-profile",
    ),
    path(
        "donors/eligibility/check/",
        DonorEligibilityCheckView.as_view(),
        name="donor-eligibility-check",
    ),
    path(
        "donors/history/",
        MyDonationHistoryView.as_view(),
        name="my-donation-history",
    ),
    path(
        "donors/search/",
        NearbyDonorSearchView.as_view(),
        name="nearby-donor-search",
    ),
    path(
        "donations/records/",
        DonationRecordCreateView.as_view(),
        name="donation-record-create",
    ),
]