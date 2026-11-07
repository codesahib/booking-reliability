# Independent code review: coherent incident snapshots

On 2026-11-06 America/Toronto, a separate Codex worker audited the completed
application from clean commit `ad66463`. This was AI-assisted engineering review,
not independent human review or a production incident. All data is synthetic.

The review covered `backend/improved.py`, `backend/db.py`, `backend/main.py`,
`backend/models.py`, `backend/invariants.py`, backend regressions, replay fixtures
and harness, browser flows, and the benchmark/case-study claims. Within the stated
one-provider, one-charge, one-full-refund model, no new accounting-write defect
was established. The inbox enforces immutable event identity; writer transactions
serialize decisions; ledger uniqueness backstops deduplication. Existing tests
exercise ordering permutations, retries, concurrent duplicate deliveries,
restart persistence, amount rejection, refund reconciliation and rollback.
This review does not establish correctness for workflows outside that model.

## Confirmed defect and smallest correction

The dashboard read reservations, ledger, deliveries and diagnostics with separate
SELECTs and no encompassing read transaction. A payment committed after the
reservation query could produce a response containing a pending reservation and
its newly recorded charge. The resulting invariant violation was a false alert
from an inconsistent read, despite correct transactional payment writes.

Before changing runtime code, two regression cases (baseline and improved mode)
failed on that exact interleaving. [Actual red-test excerpt](../evidence/dashboard-snapshot-red.txt)
records the command and failure. The test commits a real payment on a separate
connection immediately before the dashboard ledger query. Only the disposable
test databases use WAL, allowing a writer to commit while the fixed reader holds
its snapshot. Under the default DELETE journal, the original independent SELECTs
also allow a commit between queries; after the fix a reader instead delays that
commit until closing. Application journal mode is unchanged.

Commit `b88c89a` adds explicit `BEGIN` before the dashboard queries. The existing
connection-closing context ends the read transaction before response rendering.
Both regression cases now pass: the first response contains the coherent old
state, a subsequent request sees the committed paid state, and the reader closes.
An initial test-only assertion attempted to inspect the SQLite connection from
the test thread and hit its thread guard; observing close on the owning thread
corrected that assertion. Payment and refund rules, fixtures and baseline handler
were not changed. Short read transactions can briefly delay writer commits under
the default journal; no performance gain is claimed.

## Verification and evidence limits

The complete existing verifier ran against committed implementation
`b88c89a503463c410ecf89940097cc667f60c7fd` at 2026-11-07 04:55 UTC:

- Backend: 35 passed, six exact expected baseline failures, one known upstream
  deprecation warning.
- TypeScript check and production build: exit 0.
- Identical replay: baseline 3 duplicate-identity ledger rows, 7 final named
  invariant violations, 15/31 failed assertions; improved 0, 0 and 0/31.
- Python dependency compatibility check: passed. npm audit: zero findings at run.
- Installed Chrome browser flows: three passed on isolated ports 8003/5175.

[Execution metadata](../evidence/verification.json) links actual outputs. The
virtualenv's Python initially required sandbox escalation; the approved run used
the existing dependencies. No package installation, ordinary demo reset, tag
movement, push or deployment occurred. Browser tests reset only their isolated
synthetic `data/ui-smoke` directory. Historical provenance remains unchanged; new screenshots
and replay timestamps come from the latest verification.

No required repository check was omitted. Ubuntu/WSL execution, real providers,
signed webhooks, process-crash/chaos testing and load testing were not run. The
benchmark is seven fixed synthetic scenarios, not an estimate of production
failure rates, incident-response speed or AI productivity. A follow-up should
preserve this snapshot boundary if dashboard queries are paginated or extended,
and require separate domain design before adding partial refunds or multiple
payment attempts.
