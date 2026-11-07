# Tradeoffs and handoff boundaries

The improvement keeps the original payment story small: one reservation, one provider, one full charge, and at most one full refund. The benefit is a state machine that can be inspected and replayed end to end. The tradeoff is that several real payment workflows do not fit this model.

## State contract

| Incoming event | Prerequisite / current fact | Effect |
|---|---|---|
| Authorization | Pending or authorized | Authorized; no ledger entry |
| Late authorization | Charge or refund already recorded | Ignore, retain diagnostic record; never regress state |
| Payment success | Matching reservation/amount, no charge | Append one charge; paid |
| Payment success with deferred refund | Same prerequisites | Append charge and deferred refund in the same transaction; refunded |
| Payment success with another event ID | Charge already exists | Ignore as redundant under the one-charge contract |
| Refund success | Charge exists, no refund | Append one negative full refund; refunded |
| Refund success before charge | No charge or deferred refund | Retain as deferred; create an open warning; no ledger movement |
| Another refund identity | Already deferred/refunded | Ignore as redundant under the one-refund contract |
| Refund failure | Paid, not refunded | Preserve paid state and charge; record open error |
| Refund failure outside paid state | No valid paid prerequisite | Reject with `invalid_transition` |
| Identical delivery retry | Same event ID + canonical payload | Record duplicate delivery; repeat no effects |
| Same event ID, changed payload | Any state | Reject; retain original identity and record conflict |
| Wrong amount / unknown reservation | Any state | Reject; retain explicit error context |

Rejected IDs remain rejected on identical retry. A missing reservation is treated as a permanent domain error in this local model; an identity is not automatically resurrected if data appears later. A corrected business event must use a new synthetic event identity, after investigation. This is a lab contract, not guidance for altering a real provider's event IDs.

Events are not sorted by timestamp. An early refund waits indefinitely if its charge never arrives; there is no expiry job or fabricated automatic success. It remains visible as an open warning. A failed-refund error is not automatically dismissed by a later event; humans must review the original failure. The demo has no incident acknowledgement/edit endpoint.

## Persistence and failure semantics

`BEGIN IMMEDIATE` serializes writers before read/modify/write decisions. The inbox primary key and ledger unique indexes backstop application logic. All improved domain/audit writes share that transaction. Unexpected transaction failure rolls back the delivery and effects, allowing retry; such an error cannot promise a durable incident in an unavailable database. Operational failures go to server error output. A busy webhook database produces a retryable `503` after the configured SQLite wait.

SQLite is sufficient for this local slice and real concurrent threads are tested. This is not proof of throughput, high availability, multiple-writer scaling, network partition handling, process-crash durability, or gateway reconciliation. WAL tuning, background jobs, and distributed queues were not needed to demonstrate the invariant and were not added.

JSON file logging is a best-effort mirror after commit. A crash between commit and file append can leave that mirror incomplete. SQLite delivery and incident records are authoritative; query/export them for reliable diagnosis. A transactional outbox would be appropriate if external log delivery became a requirement.

Booking creation uses a caller idempotency key and an overlap check under the same writer lock. Date ranges are half-open; adjacent stays are allowed. Pending/paid stays reserve inventory; refunded stays release it in this simplified model. This does not model cancellations, holds expiring, partial stays, taxes, authorization expiry, or guest accounts. Seed business data is fixed; new booking IDs and audit timestamps are intentionally real runtime values.

## Operational scope

The API binds to localhost and has no authentication, authorization, CSRF protection, webhook signatures, provider secret, rate limits, or external notification channel. It must not be exposed as a public payment service. These were explicitly outside the vertical slice, and no PCI/security or production-readiness claim is made. No real card processing or personal data is present. Optional Sentry integration is omitted; no external monitoring account is needed.

The full dashboard returns unpaginated synthetic records and refreshes after actions/version changes. It does not stream remote updates. Large-volume dashboards, pagination, retention policy, provider namespaces, partial refunds, multiple attempts, and manual incident workflow would require additional domain design and tests.

## Maintainable handoff

Start with `backend/improved.py`, `backend/db.py`, `fixtures/replays.json`, and `backend/tests/test_reliability.py`. Keep the baseline handler unchanged as a comparison artifact. Add a fixture and a regression before broadening state semantics. Run the [verification script](../scripts/verify.sh) and review [the runbook](runbook.md).

The two-mode setup is an experiment, not an in-place data migration. A real rollout would require human review of existing duplicate ledger entries, backup/reconciliation, a migration strategy for event identity, provider-specific retry/ordering semantics, and a staged rollout with monitoring. Never apply unique constraints blindly to unreconciled real accounting data. The lab's reset replaces only its synthetic files and is not a production repair strategy.

Locked Python package versions and the npm lockfile preserve the evaluated dependency set. `pip check` validates compatibility, not security. npm audit reported zero findings at execution; neither check is a broad security certification. The pinned Starlette/AnyIO combination emits one known deprecation warning in TestClient. Browser evidence used installed Chrome because managed Chromium download hit host disk limits.
