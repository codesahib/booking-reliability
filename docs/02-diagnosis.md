# Gate 2 — reproduce before changing behavior

The working original workflow is commit `f3883f3`, tag `baseline-demo`. No real-company defect is asserted. Fixtures in `fixtures/replays.json` are fixed synthetic provider events, not randomized failures.

## Observed behavior

Executed `python -m backend.replay --modes baseline --output evidence/diagnosis.json` and `python -m pytest -q`. The diagnosis suite produced **3 passes and 6 strict expected failures**. Those expected failures intentionally preserve the known shortcomings; they are not fixed-feature passes.

Seven fresh, identically seeded scenarios contain 15 deliveries and 31 assertions. The original handler fails 6 scenarios / 15 assertions, creates 3 extra ledger rows sharing event IDs, and leaves 7 final-state invariant violations. Full event traces, individual assertions, and HTTP codes are in `evidence/diagnosis.json`.

- Success followed by two identical retries creates **three charge rows**, two excess rows, $270 fictional accounting against a $90 booking.
- Authorization arriving after a charge regresses the reservation to `authorized` while accounting contains a charge.
- Refund success arriving before charge is applied immediately; the later charge overwrites status to `paid` despite an existing refund.
- Refund failure leaves the correct paid state, but no correlated alert record exists. This case is primarily a diagnostic shortcoming, not incorrect accounting.
- A $45 payment against a $90 booking is accepted without an amount check.
- Reusing a payment event ID with a refund payload appends a refund against the same identity. This contributes the third duplicate-identity row in the aggregate measurement.

## Suspected causes and code evidence

`backend/baseline.py` inserts a ledger row for every payment/refund delivery. `backend/db.py` originally has no unique event identity in the ledger and no durable provider-event inbox. Status assignment is driven by arrival order instead of business facts. The log records delivery context but does not classify an error or expose an incident view. Individual writes already use `BEGIN IMMEDIATE`; adding transactions alone will not deduplicate retries.

The first replay run also exposed a genuine Windows file-handle leak: using a SQLite connection as a context manager commits/rolls back but does not close it. Temporary database cleanup raised `PermissionError`. Diagnosis adds explicit `closing(...)` around read/initialization connections and places replay scratch data under `data/`. This resource fix does not change webhook semantics. The successful replay above was run after that fix.

## Proposed smallest fix and targets

1. A durable inbox keyed by provider event ID, plus immutable canonical payload comparison. Accept an identical retry without repeating effects; record conflicting reuse as an error.
2. A single SQLite transaction for inbox, ledger, state, delivery, and incident updates, with ledger uniqueness as a second guard. Model only one full charge and one full refund per reservation.
3. Derive state from ledger facts. Ignore stale authorization; defer an early refund and apply it when its charge arrives. Never create negative exposure before a charge.
4. Reject amount mismatches and unknown reservations explicitly. Surface failed refunds, conflicting IDs, and invalid transitions in a local incident dashboard with reservation/event/delivery correlation.

Targets on the same fixtures: zero duplicate-identity ledger entries, zero final invariant violations, zero failed scenario assertions. Preserve the ordinary payment path and booking functionality. These are targets at this gate, not measured results. Automated detection latency and human debugging time have not been measured.

## Metric definitions

Duplicate ledger entries = sum of `max(count(event_id) - 1, 0)` per scenario. Invariant count = failed named checks per reservation in the **final** snapshot, not a count of unique bugs. Checks include charge/refund cardinality, repeated event identity, amount correctness, refund prerequisite, balance bounds, and status/accounting agreement. Scenario assertions additionally test expected counts/state and required alert context. Transient violations are not counted in this benchmark; improved prefix safety is tested separately.

## Reproduce

```bash
source .venv/bin/activate
python -m backend.replay --modes baseline --output evidence/diagnosis.json
python -m pytest -q backend/tests/test_diagnosis.py
```

No server or external payment provider is required; replay drives the actual FastAPI endpoints using its in-process HTTP client. Baseline manual investigation: locate the JSON log by event ID, locate its reservation, compare event trail to ledger, then compare booking status. This four-action runbook is an authored procedure, not a timed human study.
