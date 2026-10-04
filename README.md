# BloodConnect

BloodConnect is a web application for discovering blood banks, checking reported inventory, coordinating blood requests, managing donor readiness, and supporting blood-bank inventory operations.

## Problem and objectives

Blood availability information and request coordination are often fragmented. BloodConnect brings public blood-bank discovery, structured requests, inventory reservations, fulfilment history, donor self-service, and notifications into one system. Its objectives are to:

- make verified or imported blood-bank information searchable;
- let authenticated seekers create and track requests;
- match requests with nearby banks reporting suitable stock;
- give blood-bank owners an audited inventory and fulfilment workflow;
- let donors maintain availability, complete preliminary screening, and view donation history;
- preserve role, ownership, privacy, and inventory-integrity boundaries.

Availability is reported data and can change. BloodConnect does not replace hospitals or emergency services.

## Main features

- Public blood-bank directory, filters, address-based nearby search with current-location address detection, detail pages, and inventory display
- Registration, JWT login, rotated refresh tokens, logout, and session restoration
- Blood-request creation, suggestions, bank assignment, status history, cancellation, reservation, release, and fulfilment
- Owner-scoped inventory updates and transaction history
- Donor profile creation/editing, availability, preliminary screening, and donation history
- Recipient-scoped notifications and public/private dashboards
- Accessible DOM dialogs, keyboard focus management, skip link, responsive layouts, and lazy-loaded route content

## User types and authorization

| User type | Current capabilities |
|---|---|
| Anonymous visitor | View the public dashboard and search public blood banks and reported inventory |
| Authenticated seeker | Create, assign, cancel, and monitor their own blood requests |
| Donor | Manage their own donor profile, availability, screening, and history |
| Blood-bank owner | Manage their active bank's inventory and assigned requests |
| Application Admin | Global BloodConnect business authority through the active `ADMIN` role |
| Django superuser | Global authorization bypass and Django administration access |

Django `is_staff` does not independently grant BloodConnect business privileges. The `BLOOD_BANK_STAFF` role currently has no bank-membership scope model, so business authorization is based on bank ownership or Application Admin authority.

## Technology stack

- Backend: Python, Django 5.2, Django REST Framework, Simple JWT, django-filter, django-cors-headers, drf-spectacular
- Database: SQLite for local development; database URLs supported through `django-environ`, with PostgreSQL driver included
- Frontend: React 19, React Router 7, Vite 8, CSS
- Browser testing: Playwright Core with Microsoft Edge
- Production Python packages: Gunicorn and WhiteNoise are declared; no hosting provider or deployment manifest is configured

## Architecture

The browser loads a React/Vite single-page application. Its API client calls the Django REST API under `/api/v1/`. Views enforce authentication and object scope, while service modules perform transactional workflow, matching, reservation, fulfilment, donation, and inventory operations. Django persists state in the configured database.

See [Architecture](docs/ARCHITECTURE.md), [API](docs/API.md), [Workflows](docs/WORKFLOWS.md), [Testing](docs/TESTING.md), and [Deployment](docs/DEPLOYMENT.md).

## Repository structure

```text
BloodConnect/
├── backend/
│   ├── apps/
│   │   ├── accounts/        # Users, roles, authentication, authorization helpers
│   │   ├── blood_banks/     # Bank directory, ownership, verification, import
│   │   ├── blood_requests/  # Request state, matching, assignment, reservations
│   │   ├── core/            # Health checks, dashboards, demo fixtures
│   │   ├── donors/          # Donor profiles, screening, donation records/search
│   │   ├── inventory/       # Reference data, stock, audited transactions
│   │   ├── locations/       # Location data and distance calculation
│   │   └── notifications/   # Recipient-scoped notifications
│   ├── config/              # URLs and development/production settings
│   ├── requirements/        # Base, development, production, and lock files
│   ├── manage.py
│   └── schema.yml           # Generated OpenAPI schema snapshot
├── frontend/
│   ├── src/
│   │   ├── main.jsx         # React entry point and providers
│   │   ├── App.jsx          # Eager application shell, routes, Suspense boundary
│   │   ├── RoutePages.jsx   # Lazy-loaded route implementations
│   │   ├── api.js           # API client, token refresh, session storage
│   │   ├── AuthContext.jsx  # Authentication/session context
│   │   ├── Dialog.jsx       # Accessible modal and focus management
│   │   └── styles.css
│   ├── tests/
│   │   ├── accessibility.mjs
│   │   └── workflow.mjs
│   ├── package.json
│   └── vite.config.js
└── data/
    └── raw/                 # Local source datasets; ignored by Git
```

## Backend setup

The following commands use Windows PowerShell and the project-local virtual environment expected by the repository:

```powershell
Set-Location backend
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r .\requirements\development.txt
Copy-Item .env.example .env
& .\.venv\Scripts\python.exe manage.py migrate
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000
```

Replace the placeholder secret in `.env` before running. Development settings are the default in `manage.py`.

## Frontend setup

In another PowerShell session:

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

Vite serves the frontend at `http://127.0.0.1:5173` and proxies `/api` to `http://127.0.0.1:8000`.

## Environment variables

Backend variables are documented in `backend/.env.example`:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Required Django secret |
| `DEBUG` | Development/debug mode |
| `ALLOWED_HOSTS` | Comma-separated accepted host names |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed frontend origins |
| `DATABASE_URL` | Django database connection URL |
| `SECURE_HSTS_SECONDS` | HSTS duration; production enforces at least 31,536,000 seconds |
| `GEOCODING_BASE_URL` | Configurable geocoding service base URL; defaults to public Nominatim |
| `GEOCODING_USER_AGENT` | Application identifier with a real contact for the geocoding provider |

The frontend optionally reads `VITE_API_BASE_URL`; otherwise it uses `/api/v1`.

For public Nominatim usage, configure a shared Django cache across workers so its one-request-per-second application limit is enforced. Its [usage policy](https://operations.osmfoundation.org/policies/nominatim/) also requires attribution and forbids autocomplete and bulk lookups; see [Architecture](docs/ARCHITECTURE.md) for this project's request behavior.

Browser tests require process-local `BC_DEMO_REQUESTER_PASSWORD`, `BC_DEMO_STAFF_PASSWORD`, `BC_DEMO_UNRELATED_PASSWORD`, and `BC_DEMO_REGISTRATION_PASSWORD`. `BC_FRONTEND_URL` and `BC_BROWSER_PATH` can override their documented defaults. Never commit demo passwords or place them in `.env`.

## Reference data and demo fixtures

After migration, seed blood groups and components:

```powershell
Set-Location backend
& .\.venv\Scripts\python.exe manage.py seed_inventory_reference
```

`create_demo_fixtures` requires the three demo-account password variables in the current process and does not print their values:

```powershell
$env:BC_DEMO_REQUESTER_PASSWORD = '<temporary-strong-password>'
$env:BC_DEMO_STAFF_PASSWORD = '<temporary-strong-password>'
$env:BC_DEMO_UNRELATED_PASSWORD = '<temporary-strong-password>'
& .\.venv\Scripts\python.exe manage.py create_demo_fixtures
```

The repository also provides `import_blood_banks <csv_path> [--dry-run] [--limit N]` for the blood-bank directory dataset and `expire_blood_requests` for scheduled request expiry.

Raw directory and donor CSVs are local source data and are excluded from Git. A fresh clone can run migrations, seed reference data, and create isolated demo fixtures without those CSVs. Provide an authorized dataset separately when using `import_blood_banks`.

## Verification commands

Backend:

```powershell
Set-Location backend
& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\.venv\Scripts\python.exe manage.py test --verbosity 1
```

Frontend:

```powershell
Set-Location frontend
npm.cmd run lint
npm.cmd run build
npm.cmd run test:accessibility
npm.cmd run test:workflow
```

The browser suites require the isolated environment described in [Testing](docs/TESTING.md); do not run their destructive workflows against the normal development database.

## API documentation

When Django is running:

- OpenAPI schema: `/api/schema/`
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- Repository schema snapshot: `backend/schema.yml`

The generated OpenAPI schema is authoritative for detailed request and response shapes. See [API](docs/API.md) for the principal endpoints and authorization rules.

## Recommended demo flow

1. Register or sign in.
2. Search for a blood bank and inspect reported stock.
3. Create a blood request.
4. View suggested banks.
5. Assign a bank.
6. Sign in as the blood-bank owner and open the workspace.
7. Review and accept the request.
8. Reserve stock.
9. Fulfil the reservation.
10. Verify inventory and transaction history.
11. Review the donor profile and complete preliminary screening.
12. Review notifications.
13. Log out.

## Current status

- Backend checks and 164 backend tests: verified passing
- Frontend lint and production build: verified passing
- Focused runtime accessibility suite: 3/3 passing
- Real Microsoft Edge workflow: 17/17 passing
- Route content is lazy-loaded; the eager JavaScript bundle was reduced by approximately 16.7% in the measured audit
- Actual screen-reader testing has not been performed
- Production deployment has not been performed

## Security notes

Implemented protections include JWT authentication, refresh-token rotation and blacklisting, authenticated-by-default API permissions, role and ownership checks, request/notification scoping, transactional inventory audit records, negative-stock prevention, throttling, configured CORS, and production HTTPS/HSTS/secure-cookie settings.

Known limitations are that browser tokens are stored in `localStorage`, direct donor matching has no explicit communication-consent model, and `BLOOD_BANK_STAFF` has no bank-membership scope model. These should be evaluated before production deployment.

## Limitations and future scope

Current UI limitations:

- no general account/profile or password-change screen;
- no self-service bank onboarding, editing, verification, or deactivation UI;
- no nearby-donor matching or donation-recording UI;
- no separate assignment-history screen;
- no explicit donor communication-consent model;
- no bank-staff membership/scope model;
- no completed screen-reader conformance audit;
- no configured or completed production deployment.

These are future enhancements rather than blockers for the verified core seeker, donor, and bank-owner workflows.
