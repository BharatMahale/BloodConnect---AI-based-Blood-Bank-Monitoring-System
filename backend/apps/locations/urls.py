from django.urls import path

from .views import ForwardGeocodeView, ReverseGeocodeView

app_name = "locations"

urlpatterns = [
    path("locations/geocode/", ForwardGeocodeView.as_view(), name="geocode"),
    path("locations/reverse-geocode/", ReverseGeocodeView.as_view(), name="reverse-geocode"),
]
