# BloodConnect Deployment

## Deployment status

**NOT YET DEPLOYED / REQUIRES HOSTING ENVIRONMENT**

The repository contains Django development and production settings, a Vite production build, Gunicorn and WhiteNoise dependencies, and PostgreSQL driver support. It does not contain a cloud-provider manifest, container definition, reverse-proxy configuration, process manager definition, or automated CI/CD deployment workflow.

## Development

`backend/manage.py` defaults to `config.settings.development`. Development settings enable `DEBUG` and use the console email backend. The default database URL is local SQLite.

```powershell
Set-Location backend
Copy-Item .env.example .env
& .\.venv\Scripts\python.exe manage.py migrate
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

In another shell:

```powershell
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1
```

Vite proxies `/api` to `http://127.0.0.1:8000`.

## Production settings

Production must explicitly select `config.settings.production`, for example through `DJANGO_SETTINGS_MODULE` in the chosen process environment. The repository does not prescribe the hosting command or platform.

The current production settings enforce:

| Setting | Current behavior |
|---|---|
| `DEBUG` | `False` |
| `SECURE_SSL_REDIRECT` | `True` |
| `SESSION_COOKIE_SECURE` | `True` |
| `CSRF_COOKIE_SECURE` | `True` |
| `SECURE_HSTS_SECONDS` | At least `31536000` seconds |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` | `True` |
| `SECURE_HSTS_PRELOAD` | `False` (explicit choice; not enabled automatically) |
| `SECURE_CONTENT_TYPE_NOSNIFF` | `True` |
| `SECURE_PROXY_SSL_HEADER` | Trusts `X-Forwarded-Proto: https` from the configured trusted proxy path |

Before enabling production HSTS for a real domain, confirm HTTPS coverage for the domain and all subdomains. Preload is deliberately disabled.

## Required configuration

| Variable | Production requirement |
|---|---|
| `DJANGO_SECRET_KEY` | Strong, unique secret supplied outside source control |
| `DEBUG` | Optional in the environment; production settings force `False` |
| `ALLOWED_HOSTS` | Actual application host names |
| `CORS_ALLOWED_ORIGINS` | Exact trusted frontend origins |
| `DATABASE_URL` | Required by production settings; use a persistent production database URL. Missing or blank configuration fails closed |
| `SECURE_HSTS_SECONDS` | Optional override, but production enforces a minimum of one year |
| `GEOCODING_BASE_URL` | Choose the geocoding provider endpoint; public Nominatim is intended only for moderate interactive traffic |
| `GEOCODING_USER_AGENT` | Identify this deployment with a working contact URL or email when using Nominatim |

The frontend uses `/api/v1` by default. For a separately hosted API, set `VITE_API_BASE_URL` at frontend build time to the intended API base URL and configure CORS accordingly.

If the public Nominatim endpoint is used, all backend workers must share a Django cache so the one-request-per-second provider slot is application-wide. The default local-memory cache is insufficient for multiple workers. Review the [Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/) before deployment; use another provider or a self-hosted instance for higher traffic.

## Build and static assets

Frontend production assets are generated with:

```powershell
Set-Location frontend
npm.cmd run build
```

Vite writes output to `frontend/dist/`. The repository does not define how a hosting environment serves that directory or handles SPA fallback; the selected host must route client-side URLs to `index.html`.

Django uses:

- `STATIC_URL = "static/"`
- `STATIC_ROOT = backend/staticfiles`
- `MEDIA_URL = "media/"`
- `MEDIA_ROOT = backend/media`

Collect Django static files for a production environment with the standard project command:

```powershell
Set-Location backend
$env:DJANGO_SETTINGS_MODULE = 'config.settings.production'
& .\.venv\Scripts\python.exe manage.py collectstatic --noinput
```

WhiteNoise is declared in production requirements, but it is not currently present in `MIDDLEWARE`; do not assume Django static serving is configured until the hosting integration is completed. Media persistence and serving must also be supplied by the hosting environment.

## Database preparation

Use a persistent production database and run migrations with production settings:

```powershell
Set-Location backend
$env:DJANGO_SETTINGS_MODULE = 'config.settings.production'
& .\.venv\Scripts\python.exe manage.py migrate --noinput
& .\.venv\Scripts\python.exe manage.py seed_inventory_reference
```

Do not run `create_demo_fixtures` in production. The CSV import command is an administrative data operation and should first be validated with `--dry-run` against the intended dataset.

## Pre-deployment checklist

1. Supply secrets and exact host/origin/database values outside source control.
2. Run Django checks and migrations against the target configuration.
3. Seed required blood-group/component reference data.
4. Build the frontend with the correct API base.
5. Configure TLS termination and ensure proxy HTTPS headers are trustworthy.
6. Configure SPA fallback, Django static assets, persistent media, process supervision, and backups.
7. Run the backend, frontend, accessibility, and browser regression suites in a non-production environment.
8. Review localStorage token risk, donor communication consent, and bank-staff scoping before public launch.

No particular cloud provider, DNS setup, TLS provider, backup system, monitoring service, or CI/CD system is implied by this document.
