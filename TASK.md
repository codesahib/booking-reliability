# Shared project requirements (applies to all three demos)

## Objective
You are implementing a technical interview case study for a software engineer who joins acquired SaaS companies, learns unfamiliar code, introduces existing AI-assisted engineering workflows, improves engineering productivity and reliability, and leaves maintainable systems behind. This is **not** a request to add a customer-facing chatbot, to build a generic LLM wrapper, or to pretend AI is necessary where deterministic software is better.

Build a self-contained full-stack demo and document **(a) product/process without AI, (b) bottleneck, (c) AI-supported engineering process, (d) improved process/product, (e) measured outcome**.

## Strict scope
- Work inside this repo only. Do not edit sibling repositories or the user's existing portfolio website.
- Use **React + TypeScript + Vite** frontend, **FastAPI + Python** backend, SQLite for local persistence, pytest for backend tests, and Playwright for an essential UI smoke test if feasible. Prefer simple architectures over Docker/microservice overhead.
- Do not require paid APIs, hosted AI services, credentials, or access to Beacon systems. Synthetic data only. No real customer names, emails, payment details, or protected information.
- Use existing AI coding tools (Codex itself) for analysis, feature development, bug investigation, and tests. Do **not** add AI in the runtime product unless it solves a clearly explained, indispensable workflow problem; approval is not needed for routine deterministic automation.
- Use a clean UI that visibly demonstrates the before/after workflow, not just a landing page.
- All commands documented for Ubuntu/WSL. Isolate local ports per task. Include `scripts/reset-demo.sh` and a deterministic seed dataset.
- Keep scope realistic for one repository. Focus on a narrow, fully working vertical slice instead of extensive placeholder features or architecture diagrams without code.

## Mandatory phase gates
1. **Baseline.** Implement a working, intentionally limited (but realistic) existing workflow. Document the limitation in `docs/01-baseline.md`. Commit it with message `baseline: working original workflow` and make Git tag `baseline-demo`. Avoid artificially sabotaging production logic just to manufacture dramatic results.
2. **Diagnosis.** Generate reproducible scenarios that expose the bottleneck. Write `docs/02-diagnosis.md` with observed behavior, suspected causes, and measurable target. Tests should distinguish expected behavior from known shortcomings.
3. **Improvement.** Use Codex-assisted code exploration, implementation and testing to add the smallest effective improvement. Prefer deterministic logic, existing libraries, database constraints, and tests. Commit with `improvement: ...`.
4. **Evaluation.** Run reproducible baseline/after tests or scripts against comparable synthetic data. Report exact metrics in `docs/03-results.md`, including methodology, sample sizes, limitations, and outcomes that did **not** improve. Never invent timings or report suggested targets as measured results.
5. **Handoff.** Produce `README.md`, `docs/04-ai-engineering-process.md`, `docs/05-tradeoffs.md`, `docs/demo-script.md`, and `portfolio/case-study.md`. Include links or paths to code/tests and a quickstart. Document changes and handoff guidance an existing small engineering team could follow.

## What the AI documentation must contain
- What Codex examined (file paths, schemas, logs/tests).
- What decisions it proposed and what was accepted/rejected after engineering review.
- Specific changes to code, tests, and operational workflow.
- Which parts of the final workflow are **ordinary deterministic automation**, which parts benefited from **AI-assisted development**, and which parts still require humans.
- Avoid invented accounts of elapsed human engineering time or fabricated comparisons to a human-only team. If it wasn't measured, say so.

## Quality bar
- Run backend tests and frontend typecheck/build. Run the UI smoke test when tooling permits; document any unavailable browser dependencies.
- Do not leave endpoints as TODOs or dashboards with fake metrics. If a metric is displayed, derive it from live seeded data or mark it clearly as an illustrative scenario.
- Include input validation, meaningful error messages, idempotency where relevant, a deterministic reset path, and at least one negative/edge-case test.
- README must include exact setup, install, test, seed/reset, run, demo, and troubleshooting commands.
- At end, summarize features built, commands actually executed, passing/failing tests, benchmark outputs, relevant Git commits, and known limitations. Never claim to have run a command that was not run.

## Reporting to the hiring manager
Lead with the existing operational/engineering process, not AI. Show why the specific improvement matters, the before/after workflow, and verified evidence. Present the work as **independent, synthetic, portfolio-company-inspired demonstrations**, never as Beacon production changes.

# PROJECT 3 — Campground Booking Incident Reliability Lab

## Story (not a claim about a real company)
Inspired by campground-reservation SaaS: an existing system handles reservations and simulated payment provider events. The point is to demonstrate AI-assisted incident investigation, safe engineering changes, automated regression tests and operational runbooks; no guest-facing chatbot.

## Product WITHOUT AI / baseline workflow
- Guest books a campsite for dates and receives a synthetic reservation confirmation.
- A **fake payment gateway** emits authorization/payment-success/refund webhook events; all monetary movement is simulated locally.
- Admin sees reservation status, payment events and booking history.
- Legacy-like webhook handler processes incoming events but has a realistic lack of idempotency or missing out-of-order event handling. A repeated webhook can cause inconsistent payment/reservation state. Explicitly name it as a simulated reliability weakness, not a proven issue in a real product.

## Concrete problem to demonstrate
1. Payment providers commonly retry webhook delivery; handlers must be idempotent.
2. Production support needs correlated reservation ID, event ID and error context to diagnose state mismatches.
3. Teams may lack adequate failure reproduction and regression test coverage.
4. Engineers need to understand an unfamiliar state machine before they can safely fix it.

## AI-assisted engineering intervention
Use Codex to inspect failing replay cases, structured logs, database updates and test output; propose root causes, implement a safe fix and generate regression tests. If practical, add an optional Sentry-compatible integration controlled by an environment variable; **fully functional local structured logs and incident viewer are mandatory**, without a paid integration. Never send real personal/payment data.

## Improved workflow to implement
- Unique provider-event deduplication, transactional state transitions, sound handling of duplicate and out-of-order events, and explicit error records for invalid transitions.
- Structured logs and an admin incident dashboard that correlates events to reservations and exposes alertable failures.
- Replay harness to reproduce repeated and out-of-order webhook deliveries deterministically.
- Operational runbook: identify incident -> replay -> root cause -> fix -> regression tests -> verify after.
- No real credit-card integrations or external APIs.

## Required demonstration scenario
- Seed a handful of fictional campsites and bookings.
- Trigger a successful simulated charge, then send the same payment-success event twice. Show baseline inconsistency or a duplicated accounting entry.
- Show baseline incident investigation requiring manual log inspection.
- In improved mode, replay the identical events. Only one payment ledger entry exists; incident context is visible in the admin dashboard.
- Add an out-of-order or failed-refund scenario with a documented invariant and a passing regression test.

## Real measurements
Measure on identical replay fixtures:
- Number of duplicate ledger entries in baseline vs improvement.
- Number of invariant violations / failed scenario assertions.
- Time for automated detection (if timed reliably), number of diagnostic steps, and test outcomes. Never equate machine processing duration with human debugging time.

## Tech / local ports
React + TypeScript + Vite frontend `5175`, FastAPI backend `8003`, SQLite local. Use transactions and unique constraints. All payment amounts are fictional and no payment gateways are contacted.

## Deliberately out of scope
Real payment processing, PCI/security claims, production-grade reconciliation for real financial systems, customer notifications, real campground inventory integrations, AI runtime agents handling funds.

## Case-study headline
"AI-Assisted Production Incident Investigation: Hardening a Booking Workflow Against Duplicate Payment Events"
