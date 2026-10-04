from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "api/v1/",
        include("apps.core.urls"),
    ),
    path(
        "api/v1/auth/",
        include("apps.accounts.urls"),
    ),
    path(
        "api/v1/",
        include("apps.blood_banks.urls"),
    ),
    path("api/v1/", include("apps.locations.urls")),

    path(
        "api/schema/",
        SpectacularAPIView.as_view(),
        name="api-schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="api-schema",
        ),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(
            url_name="api-schema",
        ),
        name="redoc",
    ),
    path(
        "api/v1/",
        include(
            "apps.inventory.urls",
            namespace="inventory",
        ),
    ),
    path(
        "api/v1/",
        include(
            "apps.blood_requests.urls",
            namespace="blood_requests",
        ),
    ),
    path(
        "api/v1/",
        include(
            "apps.notifications.urls",
            namespace="notifications",
        ),
    ),
    path(
        "api/v1/",
        include(
            "apps.donors.urls",
            namespace="donors",
        ),
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
