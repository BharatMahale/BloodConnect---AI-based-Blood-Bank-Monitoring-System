# BloodConnect API

The API is mounted at `/api/v1/`. Except for endpoints explicitly marked public, Django REST Framework requires JWT authentication by default. Send access tokens as `Authorization: Bearer <token>`.

For exhaustive schemas, validation constraints, pagination, and response definitions, use the generated OpenAPI documentation:

- Schema: `/api/schema/`
- Swagger UI: `/api/docs/`
- ReDoc: `/api/redoc/`
- Repository snapshot: `backend/schema.yml`

## Authentication and accounts

| Method | Path | Authentication | Purpose and important data |
|---|---|---|---|
| POST | `/api/v1/auth/register/` | Public | Register with email, password/confirmation, name, optional phone, and a public role (`SEEKER`, `DONOR`, or `CAMP_ORGANIZER`). Returns user and token pair. |
| POST | `/api/v1/auth/login/` | Public | Authenticate with email/password. Returns access, refresh, and user data. |
| POST | `/api/v1/auth/token/refresh/` | Refresh token | Rotate a refresh token and obtain a new access token. Rotation and blacklisting are enabled. |
| POST | `/api/v1/auth/logout/` | Authenticated | Blacklist the supplied refresh token. |
| GET | `/api/v1/auth/me/` | Authenticated | Return the current user, active roles, and primary role. |
| PATCH/PUT | `/api/v1/auth/me/` | Authenticated | Update supported current-user fields such as first name, last name, and phone. Email and role fields are read-only. |
| POST | `/api/v1/auth/change-password/` | Authenticated | Change password using current password, new password, and confirmation. |

## Blood banks and locations

Locations are nested within blood-bank resources; there is no standalone public location endpoint.

| Method | Path | Authentication | Purpose and scoping |
|---|---|---|---|
| GET | `/api/v1/blood-banks/` | Public | Paginated search/filter/order of public active verified or directory-imported banks. Owners also see their bank; Application Admins see all. |
| POST | `/api/v1/blood-banks/` | Authenticated | Register a user-owned bank in pending verification state. Body includes bank details and nested location. |
| GET | `/api/v1/blood-banks/{slug}/` | Public/scoped | Retrieve a visible bank. Owner email is returned only to the owner or Application Admin. |
| PUT/PATCH | `/api/v1/blood-banks/{slug}/` | Owner/Application Admin | Update supported bank and nested location fields. |
| DELETE | `/api/v1/blood-banks/{slug}/` | Owner/Application Admin | Soft-deactivate the bank by making it inactive and non-public. |
| POST | `/api/v1/blood-banks/{slug}/verify/` | Application Admin | Approve or reject with `status` and optional `remarks`. Uses the application `ADMIN` role, not `is_staff`. |
| GET | `/api/v1/blood-banks/nearby/` | Public | Find visible banks by required `latitude`/`longitude`; optional radius, category, component/apheresis flags, and verified-only filter. |
| POST | `/api/v1/locations/geocode/` | Public | Resolve a trimmed `address` (1–250 characters) into `{address, latitude, longitude}`. Returns 404 if no match, 429 when the provider slot is busy, or 503 when unavailable. |
| POST | `/api/v1/locations/reverse-geocode/` | Public | Resolve geographic `latitude`/`longitude` into `{address, latitude, longitude}`. Coordinates must be within ±90/±180. The returned coordinates are the submitted browser position. |

Important bank response fields include ID, name, slug, category, location, contact/service information, component/apheresis flags, verification/information status, and optional distance.

## Inventory and reference data

| Method | Path | Authentication | Purpose and scoping |
|---|---|---|---|
| GET | `/api/v1/blood-groups/` | Public | List active blood-group reference data. |
| GET | `/api/v1/blood-components/` | Public | List active component reference data. |
| GET | `/api/v1/inventory/` | Public/scoped | List inventory. Public access is constrained to visible banks; `owned=true` scopes owner workspaces. Supports bank/group/component filters. |
| GET | `/api/v1/inventory/{id}/` | Public/scoped | Retrieve one visible inventory row. |
| POST | `/api/v1/inventory/{id}/update-stock/` | Bank owner/Application Admin | Audited stock movement. Body uses transaction type, quantity, reason, and optional reference number. `ADJUSTMENT` treats quantity as the corrected total. |
| GET | `/api/v1/inventory/{id}/transactions/` | Bank owner/Application Admin | List the inventory row's transaction audit history. |

Inventory responses distinguish `total_units`, `reserved_units`, and computed available units. Services reject negative inventory and corrected totals below reserved units.

## Blood requests

| Method | Path | Authentication | Purpose and scoping |
|---|---|---|---|
| GET | `/api/v1/blood-requests/` | Authenticated | List requests visible to the requester, assigned bank owner, or Application Admin. Filters include status and assigned-owned-bank scope. |
| POST | `/api/v1/blood-requests/` | Authenticated | Create a request using bank (optional), blood group, component, patient/hospital/contact data, units, urgency, required date, and optional hospital coordinates/information. |
| GET | `/api/v1/blood-requests/{id}/` | Authorized viewer | Retrieve request detail, reservation, status history, and scoped contact information. |
| POST | `/api/v1/blood-requests/{id}/update-status/` | Assigned bank owner/Application Admin | Move through review decisions. Body includes `new_status` and optional/required note. Fulfilment states must use the fulfil endpoint. |
| POST | `/api/v1/blood-requests/{id}/cancel/` | Requester/Application Admin | Cancel with required `reason`; releases an existing reservation atomically. |
| GET | `/api/v1/blood-requests/{id}/history/` | Authorized viewer | Return status-history records. |
| POST | `/api/v1/blood-requests/{id}/reserve-inventory/` | Assigned bank owner/Application Admin | Reserve a positive whole-unit `quantity` against matching inventory. |
| POST | `/api/v1/blood-requests/{id}/fulfil-inventory/` | Assigned bank owner/Application Admin | Fulfil reserved units with `quantity` and `note`; creates an issued transaction and updates request state. |
| POST | `/api/v1/blood-requests/{id}/release-inventory/` | Assigned bank owner/Application Admin | Release remaining reservation with required `reason` without changing physical total stock. |
| GET | `/api/v1/blood-requests/{id}/suggested-banks/` | Authorized viewer | Return distance/stock-ranked suggestions; optional radius and limit parameters. |
| POST | `/api/v1/blood-requests/{id}/assign-bank/` | Requester/Application Admin | Assign `blood_bank` with optional reason and record assignment history. |
| GET | `/api/v1/blood-requests/{id}/assignment-history/` | Authorized viewer | Return the request's bank-assignment audit history. |

`PARTIALLY_FULFILLED` and `COMPLETED` are produced by fulfilment, not by ordinary status updates.

## Donors and donations

| Method | Path | Authentication | Purpose and scoping |
|---|---|---|---|
| GET | `/api/v1/donors/me/` | Authenticated | Retrieve the caller's donor profile. |
| POST | `/api/v1/donors/me/` | Authenticated | Create the caller's sole donor profile. |
| PATCH | `/api/v1/donors/me/` | Authenticated | Update the caller's donor profile, availability, location, and declarations. |
| POST | `/api/v1/donors/eligibility/check/` | Authenticated donor | Store a preliminary assessment from the supported health-questionnaire booleans. Not clinical approval. |
| GET | `/api/v1/donors/history/` | Authenticated donor | Return the caller's donation records. |
| GET | `/api/v1/donors/search/` | Bank owner/Application Admin | Search eligible, available nearby donors by blood-group UUID, latitude, longitude, and radius. |
| POST | `/api/v1/donations/records/` | Bank owner/Application Admin | Record a donation using donor, owned bank, date, units, status, and notes. Completed donation handling integrates with inventory. |

Nearby donor results intentionally expose only donor ID, phone, blood group identifiers/name, city, state, distance, last donation date, and eligibility-assessment timestamp. Email is not included.

## Notifications

All notification endpoints require authentication and are scoped to the current recipient.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/notifications/` | List current user's notifications. |
| POST | `/api/v1/notifications/{id}/mark-read/` | Mark one owned notification read. |
| POST | `/api/v1/notifications/mark-all-read/` | Mark all current-user notifications read. |
| GET | `/api/v1/notifications/unread-count/` | Return current-user unread count. |

## Core and dashboards

| Method | Path | Authentication | Purpose |
|---|---|---|---|
| GET | `/api/v1/health/` | Public | Report API/database health without implementation details. |
| GET | `/api/v1/dashboard/overview/` | Public | Privacy-safe aggregate totals. |
| GET | `/api/v1/dashboard/me/` | Authenticated | Current account, request, donor, notification, and owned-bank summary. |

## Common behavior

- List endpoints may use page-number pagination with a default page size of 20.
- Search, filtering, and ordering are provided where configured by each viewset.
- Validation errors use HTTP 400 with field or detail messages.
- Authentication failures use 401; authorization failures generally use 403, while scoped querysets may intentionally produce 404.
- Conflicting workflow state is rejected rather than silently altered.
- Anonymous and authenticated request rates default to 100/hour and 1,000/hour respectively.
