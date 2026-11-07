# Local incident investigation runbook

All data and monetary movement in this runbook are synthetic. Preserve the event trail while investigating; do not delete duplicate accounting rows as a proposed real-world fix.

## Identify

In the hardened workflow, review **Open incident alerts** or filter the incident panel to open alerts. Search by reservation ID, provider event ID, or incident code, then inspect a record. The context links its reservation, delivery ID, original event outcome, current booking state, and ledger count. Review the ledger/history below it.

Known codes: `refund_failed`, `amount_mismatch`, `event_id_conflict`, `unknown_reservation`, `invalid_transition`, and `refund_deferred`. Informational retry/stale/redundant records are retained without inflating the open-alert count.

In the original workflow, perform four explicit diagnostic actions: (1) find the event in `data/logs/baseline.jsonl`, (2) identify its reservation, (3) compare ledger entries, (4) compare booking status/history. In the improved procedure, (1) find the incident, (2) inspect its correlated context. This is a count of authored procedure steps, not a timed support study.

```bash
grep 'evt-payment' data/logs/baseline.jsonl
curl -sS http://127.0.0.1:8003/api/improved/dashboard
```

SQLite audit records are authoritative. If the file mirror is missing, check server stderr and query the dashboard. A missing log file is not evidence of a missing payment effect.

## Reproduce

Preserve current evidence before reset. The CLI harness does not mutate the ordinary demo databases:

```bash
source .venv/bin/activate
python -m backend.replay --modes baseline improved --output evidence/comparison.json
python -m pytest -q backend/tests/test_reliability.py
```

For manual reproduction, stop both servers, run `bash scripts/reset-demo.sh`, restart them as documented in README, then use the fixture selector. An early refund fixture should leave no temporary negative accounting; after its charge, status is refunded with one charge and one refund.

## Find the cause

Compare the event payload with its original inbox identity and booking total. Check whether the delivery is a retry, a different payload using the same identity, an invalid amount, a valid event waiting for a prerequisite, or an invalid transition. Read the state contract in `docs/05-tradeoffs.md` before changing behavior.

For duplicate accounting in the original mode, the root cause is a new ledger insert per delivery without durable identity. For late authorization, the root cause is arrival-driven status updates. A failed-refund alert is intentionally retained with the charge: a provider failure is not evidence of a completed refund.

## Fix and regress

Add an exact synthetic fixture when a new case is discovered. Implement the smallest deterministic rule consistent with the domain contract. Keep inbox, ledger, status, history, and diagnostic updates in one transaction. Add a regression that checks both accounting and state, including delivery prefixes where ordering matters. Conflicting identities and wrong totals must remain explicit failures.

Human review is required before applying any such model to real payment semantics. The lab cannot determine whether a real external settlement succeeded or whether a guest should receive funds.

## Verify and hand off

```bash
source .venv/bin/activate
bash scripts/verify.sh --ui
```

Confirm zero improved failed assertions and inspect the saved outputs, not just the UI. The baseline's six exact expected shortcomings remain comparison evidence. Escalate unresolved deferred events and failed refunds to a human with domain context; this lab provides no real provider reconciliation or alert delivery. Reset only when preparing another clean synthetic demonstration.
