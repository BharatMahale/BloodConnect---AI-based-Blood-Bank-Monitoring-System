from rest_framework.routers import DefaultRouter
from .views import (
    BloodComponentViewSet,
    BloodGroupViewSet,
    BloodInventoryViewSet,
)


app_name = "inventory"

router = DefaultRouter()

router.register(
    "blood-groups",
    BloodGroupViewSet,
    basename="blood-group",
)

router.register(
    "blood-components",
    BloodComponentViewSet,
    basename="blood-component",
)

router.register(
    "inventory",
    BloodInventoryViewSet,
    basename="blood-inventory",
)

urlpatterns = router.urls