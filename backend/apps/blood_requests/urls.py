from rest_framework.routers import DefaultRouter
from apps.blood_requests.views import (
    BloodRequestViewSet,
)


app_name = "blood_requests"

router = DefaultRouter()

router.register(
    "blood-requests",
    BloodRequestViewSet,
    basename="blood-request",
)

urlpatterns = router.urls