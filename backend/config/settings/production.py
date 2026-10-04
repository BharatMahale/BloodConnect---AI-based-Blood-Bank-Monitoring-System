from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import env


DEBUG = False

database_url = env("DATABASE_URL")
if not database_url.strip():
    raise ImproperlyConfigured(
        "DATABASE_URL must be set for production."
    )

DATABASES = {"default": env.db_url_config(database_url)}

SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = max(
    env.int(
        "SECURE_HSTS_SECONDS",
        default=31536000,
    ),
    31536000,
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True

SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)
