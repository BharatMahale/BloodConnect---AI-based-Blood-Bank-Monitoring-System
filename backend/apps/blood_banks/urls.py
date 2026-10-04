from rest_framework.routers import DefaultRouter
from .views import BloodBankViewSet


app_name = "blood_banks"

router = DefaultRouter()

router.register(
    "blood-banks",
    BloodBankViewSet,
    basename="blood-bank",
)

urlpatterns = router.urls