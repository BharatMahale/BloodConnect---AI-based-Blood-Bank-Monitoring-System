# BloodConnect Testing

## Verified baseline

| Area | Verified result |
|---|---|
| Django system check | PASS |
| Migration drift check | PASS; clean |
| Backend tests | 164/164 PASS |
| Frontend ESLint | PASS |
| Frontend production build | PASS |
| Focused runtime accessibility | 3/3 PASS |
| Microsoft Edge end-to-end workflow | 17/17 PASS |

Actual screen-reader testing has not been performed. There is no repository CI workflow; these commands are currently run locally.

## Backend checks and tests

From the repository root in Windows PowerShell:

```powershell
Set-Location backend
& .\.venv\Scripts\python.exe manage.py check
& .\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\.venv\Scripts\python.exe manage.py test --verbosity 1
```

The backend suite covers accounts and authorization, public/private dashboard behavior, blood-bank visibility and nearby search, request workflow/matching/reservations, inventory transactions, donor privacy/eligibility/donation integration, locations, and notifications.

## Frontend static verification

```powershell
Set-Location frontend
npm.cmd run lint
npm.cmd run build
```

The build produces Vite assets under `frontend/dist/`. Route implementations are emitted as a deferred chunk separate from the eager application shell.

## Isolated browser-test environment

The accessibility and workflow suites modify fixture data. Never run them against `backend/db.sqlite3`, a personal database, or production. Use a disposable SQLite database such as `backend/db_e2e.sqlite3`.

The existing test scripts expect:

| Variable | Used by |
|---|---|
| `BC_DEMO_REQUESTER_PASSWORD` | Requester login in both browser suites |
| `BC_DEMO_STAFF_PASSWORD` | Bank-owner login in both browser suites |
| `BC_DEMO_UNRELATED_PASSWORD` | Authorization-denial E2E scenario |
| `BC_DEMO_REGISTRATION_PASSWORD` | Unique registration E2E scenario |
| `BC_FRONTEND_URL` | Optional frontend override; default `http://127.0.0.1:5173` |
| `BC_BROWSER_PATH` | Optional browser override; default Microsoft Edge path on Windows |
| `BC_API_PROXY_TARGET` | Optional Vite API target for an isolated backend on a different port |

Generate strong temporary values in the current process. Avoid values similar to fixture names/emails because Django password similarity validation can reject them. Do not print, save, or commit the values.

Example environment preparation, using placeholders rather than credentials:

```powershell
$projectRoot = (Get-Location).Path # Run this block from the repository root.
$e2eDb = Join-Path $projectRoot 'backend/db_e2e.sqlite3'
$env:DATABASE_URL = 'sqlite:///' + ($e2eDb -replace '\\', '/')
$env:BC_DEMO_REQUESTER_PASSWORD = '<temporary-strong-password>'
$env:BC_DEMO_STAFF_PASSWORD = '<temporary-strong-password>'
$env:BC_DEMO_UNRELATED_PASSWORD = '<temporary-strong-password>'
$env:BC_DEMO_REGISTRATION_PASSWORD = '<temporary-strong-password>'

Set-Location backend
& .\.venv\Scripts\python.exe manage.py migrate --noinput
& .\.venv\Scripts\python.exe manage.py seed_inventory_reference
& .\.venv\Scripts\python.exe manage.py create_demo_fixtures
& .\.venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

Start the frontend in a second process with the same password variables available to the later test process:

```powershell
Set-Location frontend
npm.cmd run dev -- --host 127.0.0.1
```

Verify both the backend and Vite proxy before testing:

```powershell
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/api/v1/health/
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:5173/api/v1/health/
```

Vite's `/api` proxy targets `http://127.0.0.1:8000`.

## Accessibility suite

```powershell
Set-Location frontend
npm.cmd run test:accessibility
```

The suite launches real Microsoft Edge through Playwright Core. Its four focused groups verify:

- skip-link and icon/mobile-menu keyboard behavior;
- Nearby Search address/radius labels and current-location keyboard access;
- focus entry, Tab/Shift+Tab containment, Escape, validation, and restoration for request status, reservation, and cancellation dialogs;
- focus isolation/restoration for fulfilment, release, inventory update, transaction history, and donor screening dialogs.

The suite verifies keyboard behavior and DOM semantics; it does not establish screen-reader conformance.

## Full Edge workflow

```powershell
Set-Location frontend
npm.cmd run test:workflow
```

The 17 scenarios cover:

1. Protected-route redirect
2. Failed login feedback
3. Login and session restoration
4. Rotated single-flight refresh
5. Network-error session preservation
6. Bank search and inventory rendering, plus deterministic address/current-location nearby search, stale-coordinate protection, radius independence, and geolocation/provider failures
7. Request validation, creation, suggestions, assignment, and history
8. Owner workspace scoping
9. Review, acceptance, reservation, fulfilment, and stock integrity
10. Explicit release and cancellation release
11. Donor editing, availability, screening, and history
12. Notification read operations
13. Unrelated-user server denial
14. Empty/offline states
15. Registration
16. Logout/session clearing
17. Mobile/desktop overflow and key-action visibility

The workflow creates and changes isolated requests, inventory transactions, notification state, donor state, and a unique registration account.

## Cleanup

After testing:

1. Stop the frontend and backend processes.
2. Remove only the known disposable `backend/db_e2e.sqlite3` after verifying its path.
3. Remove the four `BC_DEMO_*_PASSWORD` variables and `DATABASE_URL` from the test shell.
4. Leave `backend/db.sqlite3` untouched.

PowerShell environment cleanup:

```powershell
Remove-Item Env:BC_DEMO_REQUESTER_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:BC_DEMO_STAFF_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:BC_DEMO_UNRELATED_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:BC_DEMO_REGISTRATION_PASSWORD -ErrorAction SilentlyContinue
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
```

## Interpreting failures

Classify browser failures before changing application code: fixture/environment issue, harness timing/configuration issue, browser-specific behavior, or real application defect. Do not weaken business, authorization, or accessibility assertions merely to make a test pass.
