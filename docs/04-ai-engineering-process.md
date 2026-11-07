# Gate 5 — AI-assisted engineering process

The existing process is a small reservation operation: accept a booking, receive a fake gateway event, record accounting, and let an admin investigate discrepancies. The bottleneck is understanding event identity and arrival-order effects across booking state and accounting, then reliably reproducing them. Codex assisted that engineering work. No AI runs inside the product.

## Evidence examined

This repository initially contained only `TASK.md`; there was no acquired production code or company data to analyze. Codex read that task in full, inspected Git state and installed tooling, then built the working limited workflow before diagnosing it. Gate commits are `f3883f3` (`baseline-demo`), `11e96dc` (diagnosis), and `ca3057d` (improvement).

During diagnosis and review it examined:

- `backend/baseline.py`: unconditional ledger insertion and arrival-driven status assignment.
- `backend/db.py`: reservations, ledger, deliveries, and history schema; transaction boundaries; missing unique event identity.
- `backend/main.py`, `backend/models.py`, `backend/seed.py`: API boundaries, integer-cent/date validation, booking idempotency/overlap, and seeded states.
- `fixtures/replays.json`, `backend/replay.py`, and `evidence/diagnosis.json`: exact event order, HTTP outcomes, accounting entries, failed checks, and final invariants.
- `backend/tests/test_diagnosis.py` and pytest output: ordinary behavior distinguished from six exact known failure signatures.
- `data/ui-smoke/logs/{baseline,improved}.jsonl` after actual browser flows; selected records are preserved in `evidence/logs/`.
- `test-results/*/error-context.md` and Playwright traces after failures: label selector behavior, persistent state across runs, and watcher crash output. Transient traces are ignored, not presented as final passing evidence.
- Final files `backend/improved.py`, `backend/invariants.py`, `backend/tests/test_reliability.py`, `src/App.tsx`, and `e2e/smoke.spec.ts`, plus [saved check output](../evidence/verification.json).

Official [FastAPI testing guidance](https://fastapi.tiangolo.com/tutorial/testing/) informed the in-process endpoint harness. SQLite's [transaction documentation](https://www.sqlite.org/lang_transaction.html) informed explicit `BEGIN IMMEDIATE` use; [foreign-key guidance](https://www.sqlite.org/foreignkeys.html) informed connection configuration. These are implementation references, not evidence that this demo is production-certified.

## Decisions reviewed

Engineering review here means Codex self-review against task constraints, code behavior, and test evidence. The user authorized routine implementation decisions. **No independent human code review or production-team approval occurred.** The following accepted/rejected choices describe actual design assessment, not an invented conversation with engineers.

| Proposal | Decision and reason |
|---|---|
| Add only an in-memory seen-ID set | Rejected: lost on restart and unsafe across workers; restart and concurrent-delivery tests require durable identity. |
| Add only transactions | Rejected as insufficient: the baseline already has per-delivery transactions. Two valid transactions can both append the same effect. |
| Durable inbox with unique event IDs and payload comparison | Accepted: distinguish an identical retry from conflicting reuse, including after restart. |
| Unique ledger event ID plus `(reservation_id, kind)` | Accepted: guards both retried identity and a new event ID representing the same full-charge/full-refund business effect. |
| Always reject a refund that arrives before its charge | Rejected for this model: a valid late charge should allow convergence without manual replay. Persist one deferred full refund and reconcile atomically. |
| Order by local timestamps | Rejected: arrival timestamps do not establish provider causality. Use prerequisites and ledger facts. |
| Add queues, microservices, or an ORM | Rejected for this slice: SQLite plus explicit SQL keeps the failure and fix inspectable. |
| Let an LLM decide payment state at runtime | Rejected: unnecessary uncertainty and credentials; transitions have explicit deterministic rules. |
| Optional Sentry-compatible integration | Omitted: local correlated records and JSON logs satisfy diagnosis without an external service or data egress. |

## Specific interventions

`backend/improved.py` stores immutable provider identity, validates reservation/amount, records every delivery, classifies stale/redundant events, defers early refunds, and commits inbox, accounting, state, history, and incident context together. Duplicate accounting effects are prevented by both logic and constraints. The fake provider is singular; there is no claim about a real provider's event schema.

Tests extend the diagnosis cases into improved regressions, exercise all meaningful three-event orders and retries, run concurrent deliveries and competing bookings, restart the app against the same file, and inject failures after a charge insertion during refund reconciliation. A separate test verifies a failed file-log mirror does not produce a misleading retry of committed business effects.

The admin now supports version switching, live lab invariants, a fixture replay control, incident search/filter, and linked reservation/event/delivery context. Operational changes include isolated disposable browser databases, a deterministic offline reset, a source/evidence map, and `scripts/verify.sh` to save real check outputs. Fixes to resource closing, Windows path quoting, file-watch exclusions, and UTF-8 output came from observed failures.

## Responsibility boundaries

| Work | Responsibility |
|---|---|
| Validate payloads, deduplicate, update ledger/status, detect invariants, classify incidents, replay fixtures | Ordinary deterministic application code and database constraints. |
| Explore unfamiliar state transitions, propose hypotheses, implement changes, generate/revise tests, inspect failure artifacts, draft runbooks | Codex-assisted engineering during this session. Proposed changes were accepted only after checks/self-review. |
| Establish real business semantics, evaluate provider contracts, sign off accounting behavior, resolve ambiguous financial incidents, approve migrations and rollout | Humans with domain authority. The lab cannot substitute for them. |

There is no measured elapsed human engineering time, human-only comparator, or attribution study showing how much of the result was caused by AI. Verified claims are limited to the checked-in deterministic fixtures and executed tests. Documentation follows the task's direct technical style; no retrieved personal writing samples were available or claimed.
