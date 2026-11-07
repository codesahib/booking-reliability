# Gate 4 — measured results

The operational change is payment-event identity plus a safe state machine and usable incident context. AI supported implementation and testing; the measured outcome is deterministic behavior under a fixed replay, not a claim about AI productivity.

## Method and provenance

Latest execution: **2026-11-07 04:55 UTC** (November 6 in America/Toronto), Windows 11, Python 3.13.14, Node 24.22.0, installed Chrome. [Verification metadata](../evidence/verification.json) records source commit `b88c89a`, commands, exit codes, and output files. The original formal execution at 04:12 UTC tested `ca3057d` (33 passes); its [provenance](../evidence/provenance.json) is retained. Linux instructions are supplied but were not run on a Linux host.

`python -m backend.replay --modes baseline improved --output evidence/comparison.json` sends the exact same seven checked-in fixtures to both real FastAPI endpoint implementations using TestClient. Every mode/scenario receives a fresh temporary SQLite database seeded with the same three campsites and pending bookings. There are **15 deliveries and 31 assertions per mode**, not a load test or statistical sample of production traffic. No network gateway, wall-clock sleeps, or random failure generation is involved.

The [baseline handler](../backend/baseline.py) is unchanged from `baseline-demo` (`f3883f3`). [Provenance evidence](../evidence/provenance.json) records its hash and fixture SHA-256 `60369bc0a3cf08d61e18083217bf7007b30f66c8ca23316d84c025e0b1137042`. The final baseline mode has a read-only lab checker and connection-resource fix; neither changes its original webhook accounting or status decisions.

## Counts

| Measure | Baseline | Improved |
|---|---:|---:|
| Scenarios / deliveries | 7 / 15 | 7 / 15 |
| Duplicate-identity ledger entries | 3 | 0 |
| Final named invariant violations | 7 | 0 |
| Failed scenario assertions | 15 / 31 | 0 / 31 |
| Failed scenarios | 6 / 7 | 0 / 7 |

| Scenario | Baseline ledger rows | Improved ledger rows | Baseline failed assertions | Improved failed assertions |
|---|---:|---:|---:|---:|
| Ordinary payment | 1 | 1 | 0 | 0 |
| Success + two identical retries | 3 | 1 | 2 | 0 |
| Late authorization | 1 | 1 | 2 | 0 |
| Refund before charge | 2 | 2 | 2 | 0 |
| Failed refund | 1 | 1 | 1 | 0 |
| Wrong amount | 1 | 0 | 4 | 0 |
| Conflicting event identity | 2 | 1 | 4 | 0 |

Definitions: duplicate rows = excess entries for each event ID within a scenario. Two come from identical success retries, one from conflicting reuse of a payment ID for a refund. Invariant count = failed named checks per reservation in the final snapshot; this is not seven independent root causes. Scenario assertions test status, charge/refund counts, invariants, and, for three cases, required correlated error context. [Full raw traces and checks](../evidence/comparison.json) make the aggregates inspectable.

## Checks actually executed

The latest complete verification used the existing Windows virtualenv with `PLAYWRIGHT_CHANNEL=chrome` and `python scripts/verify.py --ui`; it returned success. Outputs are checked in:

| Check | Observed result |
|---|---|
| `python -m pytest -q` | **35 passed, 6 xfailed**, one upstream deprecation warning |
| `npm run typecheck` | Exit 0 |
| `npm run build` | Exit 0; Vite 7.3.7 production assets generated |
| Comparable HTTP replay | Improved 31/31 assertions pass; baseline failures retained |
| `python -m pip check` | No broken requirements |
| `npm audit --audit-level=high` | 0 vulnerabilities reported at execution |
| `npm run test:ui`, installed Chrome | **3 passed** |

The six strict expected failures apply only to the exact documented baseline mismatch signatures. Unexpected exceptions and changed signatures fail normally. They do not count as improved tests passing. Improved regression coverage includes all six permutations of authorization/charge/refund with retries, prefix invariants, 24 concurrent identical deliveries (one applied, 23 suppressed), concurrent booking overlap, restart persistence, immutable rejected identities, direct constraint enforcement, log-mirror failure, and rollback during deferred-refund reconciliation. Two new cases verify a coherent dashboard read snapshot in each mode while a separate connection commits a payment; [review and red-test evidence](06-independent-review.md) describe the controlled interleaving.

UI evidence verifies original vs improved accounting, correlated failure context, early-refund reconciliation, and mobile booking/idempotent resubmission/overlap rejection. Screenshots come from browser interactions with live seeded data. Repeated smoke runs passed after fixing isolation; the formal saved run also passed.

## Diagnostic procedure and what did not improve

The authored baseline runbook has **four diagnostic actions**: find the log entry, locate the reservation, compare the ledger, check status/history. The improved recipe has **two**: find the incident, open its correlated context. This counts steps in a defined procedure; it is **not** a usability study or a measured reduction in human debugging time. The smoke test exercises filter/inspect navigation and validates the resulting context.

Automated detection latency was **not timed**: application processing duration would not represent support detection or human response. Database commit boundaries make alerts available in the next dashboard response, but no latency percentile, alert delivery SLA, or speedup is claimed.

The ordinary payment case already passed and still does. Failed-refund accounting already stayed paid; the improvement there is diagnostic visibility. Early-refund final ledger row count remains two, while ordering/state correctness improves. No measurement was made of engineering hours saved, customer conversion, throughput, real gateway behavior, or a human-only team's performance. Added audit/inbox writes incur storage and work; no performance improvement is claimed.

## Failures encountered and corrected

Actual development failures were retained in the engineering account rather than treated as successful first attempts:

- Managed Chromium download failed with `ENOSPC`; installed Chrome ran the smoke suite.
- Vite 7.2.2 initially had audit advisories; pinning 7.3.7 removed the reported npm findings.
- Windows replay cleanup exposed unclosed SQLite connections; explicit close fixed it.
- Playwright initially used a Windows-incompatible relative Python command; it now quotes an absolute virtualenv path.
- The mobile test's label-text selector failed on a nested select; using the control's accessible role/name fixed the test.
- A repeated smoke run exposed a reset/serve path mismatch due to module import timing; the server now receives the disposable path explicitly.
- A concurrent lock-file write crashed Vite's Windows watcher; backend/generated artifacts are excluded from its watch list.
- The first all-check runner attempt could not print Vite's Unicode glyphs through a Windows cp1252 pipe; its stdout is now explicitly UTF-8. The complete rerun passed.

Remaining limits: one synthetic provider and currency, one full charge/refund, no authentication or signatures, no multi-process chaos/load tests, no real incident data, and no independent human review. The subsequent independent code audit was another Codex worker, not a human review. See [tradeoffs](05-tradeoffs.md).
