from django.urls import path
from .views import HealthCheckView
from apps.core.dashboard_views import (
    MyDashboardView,
    PublicDashboardOverviewView,
)


app_name = "core"

urlpatterns = [
    path(
        "health/",
        HealthCheckView.as_view(),
        name="health-check",
    ),
    path(
        "dashboard/overview/",
        PublicDashboardOverviewView.as_view(),
        name="dashboard-overview",
    ),
    path(
        "dashboard/me/",
        MyDashboardView.as_view(),
        name="my-dashboard",
    ),
]