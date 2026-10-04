# BloodConnect Workflows

## Authorization reference

| Authority | Scope |
|---|---|
| Django superuser | Global bypass |
| Application Admin (`ADMIN`) | Global BloodConnect administrative authority |
| Blood-bank owner | Their own active bank, inventory, and assigned requests |
| Normal user/donor | Their own account, requests, donor profile, and notifications |

`is_staff` alone is not application authority. `BLOOD_BANK_STAFF` currently has no bank-membership scope model and is therefore not independently used to authorize bank operations.

## A. Registration and login

- **Actor:** Anonymous visitor
- **Preconditions:** Unique email; valid password and supported public role for registration
- **Steps:** Submit registration or login; receive access/refresh tokens and serialized user; frontend stores the session and opens the authenticated dashboard.
- **Result:** Authenticated session. Expired access tokens are refreshed once through the rotated-token flow.
- **Authorization:** Registration/login are public. Authenticated endpoints require a valid Bearer access token.

## B. Blood-bank discovery

- **Actor:** Anyone
- **Preconditions:** None
- **Steps:** Search/filter directory records, or enter an address and radius for nearby search. The address resolves through the locations API before the existing nearby bank API receives coordinates. The current-location action resolves browser coordinates to a readable address first. Open bank detail and filter reported inventory as before.
- **Result:** Active/public verified or directory-imported banks and their reported stock are shown.
- **Authorization:** Public users cannot see private, inactive, pending, or rejected banks. Owners can see their own bank; Application Admins can see all.

## C. Blood-request creation

- **Actor:** Authenticated user
- **Preconditions:** Valid group, component, units, required date, patient/hospital/contact data; coordinates must be supplied together when used.
- **Steps:** Complete the request form and submit it. The service creates the request in `PENDING`, adds initial history, and generates notifications.
- **Result:** A trackable request and status history.
- **Authorization:** Request ownership is assigned to the authenticated user.

## D. Suggested-bank matching

- **Actor:** Authorized request viewer, normally the requester
- **Preconditions:** Request location and required inventory data
- **Steps:** Request suggestions using radius/limit parameters. The matching service evaluates distance and reported available stock.
- **Result:** Ranked nearby banks with a safety notice that availability can change.
- **Authorization:** The request queryset must expose the request to the caller.

## E. Bank assignment

- **Actor:** Requester or Application Admin
- **Preconditions:** Non-terminal request and valid bank
- **Steps:** Select a suggestion and submit assignment. The assignment service records previous/new bank and actor.
- **Result:** Request is assigned and the bank is notified.
- **Authorization:** Unrelated users and unassigned bank owners cannot assign.

## F. Review

- **Actor:** Assigned blood-bank owner or Application Admin
- **Preconditions:** `PENDING` request assigned to the managed bank
- **Steps:** Use the status action to move the request to `UNDER_REVIEW`, optionally recording a note.
- **Result:** Review metadata/history and requester notification are recorded.
- **Authorization:** Ownership is checked against the assigned bank.

## G. Acceptance or rejection

- **Actor:** Assigned blood-bank owner or Application Admin
- **Preconditions:** `UNDER_REVIEW`
- **Steps:** Move to `ACCEPTED`, or to `REJECTED` with a required reason. Rejection releases an existing reservation if applicable.
- **Result:** Accepted requests can reserve inventory; rejected requests are terminal.
- **Authorization:** Assigned-bank ownership or Application Admin authority.

## H. Inventory reservation

- **Actor:** Assigned blood-bank owner or Application Admin
- **Preconditions:** Accepted/eligible request, matching owned inventory, sufficient available units
- **Steps:** Submit a positive whole-unit quantity. The service locks inventory and creates or updates the reservation.
- **Result:** Units become reserved rather than physically removed.
- **Authorization:** Only the assigned bank's owner or Application Admin.

## I. Fulfilment

- **Actor:** Assigned blood-bank owner or Application Admin
- **Preconditions:** Active reservation with sufficient reserved units
- **Steps:** Submit a fulfilment quantity and note. The service locks the relevant records, records an `ISSUED` inventory transaction, reduces physical and reserved stock, and updates request/reservation state.
- **Result:** Request becomes `PARTIALLY_FULFILLED` or `COMPLETED`; histories and notifications are updated.
- **Authorization:** Assigned-bank ownership or Application Admin authority.

`PARTIALLY_FULFILLED` and `COMPLETED` are reached through this fulfilment workflow, not through generic status updates.

## J. Partial fulfilment

- **Actor:** Assigned blood-bank owner or Application Admin
- **Preconditions:** Fulfilled total remains below required units and reservation remains available
- **Steps:** Fulfil part of the reservation; repeat later when additional reserved units are available.
- **Result:** Cumulative fulfilled units increase and the request remains `PARTIALLY_FULFILLED` until complete.
- **Authorization:** Same as fulfilment.

## K. Cancellation

- **Actor:** Requester or Application Admin
- **Preconditions:** Non-terminal request; cancellation reason
- **Steps:** Open the cancellation dialog and confirm. The service releases any reservation and transitions to `CANCELLED` atomically.
- **Result:** Terminal cancelled request, released reservation, unchanged physical stock, notifications/history.
- **Authorization:** Requester or Application Admin only.

## L. Explicit reservation release

- **Actor:** Assigned blood-bank owner or Application Admin
- **Preconditions:** Active or partially fulfilled reservation; release reason
- **Steps:** Submit release. Reserved units are returned to availability without changing physical total stock.
- **Result:** Reservation becomes `RELEASED`; request remains otherwise unchanged.
- **Authorization:** Assigned-bank ownership or Application Admin authority.

## M. Donor profile

- **Actor:** Authenticated user
- **Preconditions:** Reference blood groups available
- **Steps:** Create or patch personal, location, consent, and availability data.
- **Result:** One self-scoped donor profile used for screening/history and eligible matching.
- **Authorization:** A user can access only their own donor profile.

## N. Donor screening

- **Actor:** Donor with a profile
- **Preconditions:** Existing donor profile
- **Steps:** Complete the preliminary health questionnaire in the accessible dialog.
- **Result:** Eligibility assessment and timestamp are stored and displayed. This is not clinical approval.
- **Authorization:** Self-scoped authenticated action.

## O. Notifications

- **Actor:** Authenticated recipient
- **Preconditions:** Authenticated session
- **Steps:** List notifications, mark one read, or mark all read; dashboard reads the aggregate count.
- **Result:** Recipient-specific read state.
- **Authorization:** Querysets and actions are scoped to the notification recipient.

## P. Bank-owner workspace

- **Actor:** User owning an active blood bank, or Application Admin where allowed by the API
- **Preconditions:** Managed bank
- **Steps:** Load owned inventory and assigned requests; update stock with a reason/reference; inspect transaction history; open an assigned request for status, reservation, release, or fulfilment actions.
- **Result:** Current dashboard totals and audited operational state.
- **Authorization:** Inventory and request actions enforce bank ownership on the backend.

## Q. Public dashboard

- **Actor:** Anyone
- **Preconditions:** None
- **Steps:** Load `/`; frontend requests `/api/v1/dashboard/overview/`.
- **Result:** Privacy-safe aggregate counts for public banks, available donors, active requests, and completed donations.
- **Authorization:** Public endpoint; individual donor/request data is not returned.

## State-transition summary

| Current | Allowed next states |
|---|---|
| `PENDING` | `UNDER_REVIEW`, `CANCELLED`, `EXPIRED` |
| `UNDER_REVIEW` | `ACCEPTED`, `REJECTED`, `CANCELLED`, `EXPIRED` |
| `ACCEPTED` | `PARTIALLY_FULFILLED`, `COMPLETED`, `CANCELLED`, `EXPIRED` |
| `PARTIALLY_FULFILLED` | further partial fulfilment, `COMPLETED`, `CANCELLED`, `EXPIRED` |
| `REJECTED`, `CANCELLED`, `COMPLETED`, `EXPIRED` | Terminal |

The generic status endpoint intentionally permits bank-review decisions rather than direct fulfilment statuses. System operations may transition only to `EXPIRED`.
