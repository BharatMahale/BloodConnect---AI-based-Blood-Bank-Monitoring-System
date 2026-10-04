"""Small, provider-independent geocoding adapter for interactive searches."""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache


class GeocodingUnavailable(Exception):
    pass


class GeocodingBusy(Exception):
    pass


def _request(path, params):
    # A shared Django cache is required when the application runs multiple workers.
    if not cache.add("geocoding:provider-slot", True, timeout=1):
        raise GeocodingBusy()
    url = f"{settings.GEOCODING_BASE_URL.rstrip('/')}/{path}?{urlencode(params)}"
    request = Request(url, headers={
        "User-Agent": settings.GEOCODING_USER_AGENT,
        "Accept": "application/json",
    })
    try:
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        raise GeocodingUnavailable() from exc


def _normalize(result, latitude=None, longitude=None):
    if not isinstance(result, dict):
        return None
    address = result.get("display_name")
    try:
        lat = float(result["lat"]) if latitude is None else float(latitude)
        lon = float(result["lon"]) if longitude is None else float(longitude)
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(address, str) or not address.strip():
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return {"address": address.strip(), "latitude": lat, "longitude": lon}


def forward(address):
    key = f"geocoding:forward:{address.casefold()}"
    cached = cache.get(key)
    if cached is not None:
        return cached or None
    results = _request("search", {"q": address, "format": "jsonv2", "limit": 1})
    # Use the provider's top-ranked match and show its canonical address.
    result = _normalize(results[0]) if isinstance(results, list) and results else None
    cache.set(key, result or {}, timeout=86400)
    return result


def reverse(latitude, longitude):
    # Precise browser coordinates are never persisted in a cache or database.
    result = _request("reverse", {
        "lat": latitude, "lon": longitude, "format": "jsonv2", "zoom": 16,
    })
    return _normalize(result, latitude, longitude)
