# BR-002 â€” three targeted reliability follow-ups

Dispatch `F1107-c1d3cf`; runtime source commit `ee4ef7c`. Existing historical evidence, original replay business fixtures, strict baseline failure signatures, and `baseline-demo` are preserved. [Verification metadata](verification.json) records actual command arguments, working directories, UTC execution time, platform and exit codes.

## Red before implementation

```text
.venv/Scripts/python.exe -m pytest -q backend/tests/test_review_fixes.py -o cache_dir=.orchestrator/BR-002/cache --basetemp=.orchestrator/BR-002/red-tmp
exit 1: 11 failed, 1 warning in 3.84s
```

[Full red output](red.txt), [exit code](red-exit.txt). Cases cover BUSY, LOCKED, an extended BUSY code, injected I/O and uncoded storage errors, actual local writer contention, four protocol/incident mutations, and bare-CLI evidence safety. No host disk failure occurred or is claimed. The CLI regression operates on an exact package/fixture copy and a historical sentinel under pytest scratch, so the old unsafe behavior cannot overwrite real evidence.

## Green after implementation

| Check | Result | Output |
|---|---|---|
| Same 11 targeted regressions (`--basetemp=.orchestrator/BR-002/green-tmp`) | Exit 0; 11 passed, one upstream warning | [targeted](green-targeted.txt), [exit](green-targeted-exit.txt) |
| Full current pytest suite with scratch cache/base directory | Exit 0; **46 passed, 6 xfailed**, one upstream warning | [backend](backend-full.txt) |
| TypeScript `--noEmit --incremental false` | Exit 0; no diagnostics | [typecheck](typecheck.txt) |
| Vite build with isolated output/cache | Exit 0; 29 modules, production assets | [build](build.txt) |
| Existing three browser flows, installed Chrome | Exit 0; **3 passed** | [browser](browser.txt) |
| Explicit-output CLI replay | Exit 0; both denominators reported separately | [summary](benchmark.txt), [full report](comparison.json) |

The backend command was `.venv/Scripts/python.exe -m pytest -q -o cache_dir=.orchestrator/BR-002/cache --basetemp=.orchestrator/BR-002/full-tmp`. The full suite retains the prior 35 passes and six exact expected baseline shortcomings and adds 11 passes. The mutation cases alter behavior only in memory and prove that legacy accounting can pass while wrong protocol or incident context fails the added oracle. Injected post-insert storage failures prove rollback and successful same-identity retry; the actual lock test holds a local SQLite writer lock, shortens only its test wait, then releases and retries successfully.

Browser/build isolation: scratch copies of browser tests change only screenshot paths; a scratch server/config uses **18004/15176** and `.orchestrator/BR-002/ui-db`, with refusal to reuse services. Neither standard demo ports nor shared demo databases are used. Build output/cache and screenshots remain scratch artifacts. No global package installation was needed.

## Comparable benchmark and denominators

The actual CLI command in [metadata](verification.json) ran `python -m backend.replay --modes baseline improved --output <repo>/evidence/br-002/comparison.json` from an exact backend/fixture copy under `.orchestrator/BR-002/cli-sandbox`. This keeps its derived replay scratch databases inside the task's own scratch directory. No code or business expectations differ in that copy.

| Mode | Scenarios / deliveries | Legacy failed checks | Duplicate rows | Final invariant violations | Added protocol failed checks |
|---|---|---:|---:|---:|---:|
| Baseline | 7 / 15 | **15 / 31** | **3** | **7** | **17 / 38** |
| Improved | 7 / 15 | **0 / 31** | **0** | **0** | **0 / 38** |

The legacy 31 = four checks per scenario (28) plus the original three basic incident-presence checks. They have not been rewritten. The added 38 = status/outcome for 15 deliveries (30) plus incident correlation/severity for four required records (8). The additional warning record is the early-refund prerequisite warning; the three errors are refund failure, amount mismatch, and conflicting identity. These counts are correlated assertions, not independent trials, productivity measurements, or production incident rates. The CLI fails if **either** improved group fails.

`fixtures/replays.json` retains SHA-256 `60369bc0a3cf08d61e18083217bf7007b30f66c8ca23316d84c025e0b1137042`. A separate `fixtures/protocol-expectations.json` supplies the new acknowledgement/incident contract and its own hash in the report. Historical `evidence/diagnosis.json`, `comparison.json`, `verification.json`, and prior coordination reports were not replaced. Red/targeted output was normalized from PowerShell's UTF-16 capture to UTF-8 with normalized line endings/trailing whitespace for readable diffs; raw captures remain in scratch.

## Handoff and limits

Storage errors now log actual cause with event/reservation/mode correlation to server stderr. Only SQLite BUSY/LOCKED primary codes (including extended forms) return retryable 503; other/unknown storage failures return safe 500 investigation guidance. Client messages omit raw exception text and internal paths. A database incident cannot be promised during storage failure; external log persistence is not implemented.

Bare replay now requires `--output` and exits 2 before evaluating. Normal explicit-output commands remain usable. To reproduce without replacing historical reports:

```bash
source .venv/bin/activate
python -m pytest -q
python -m backend.replay --modes baseline improved --output data/reports/comparison.json
npm run typecheck
npm run build
# With standard task ports free, using an installed browser or Playwright Chromium:
PLAYWRIGHT_CHANNEL=chrome npm run test:ui
```

No transaction/state-machine redesign, payment gateway, partial-payment model, tenancy/authentication, distributed infrastructure, or runtime AI was added. Linux and process-crash durability were not evaluated. Build/test durations are authentic tool output, not a performance claim. No engineering-time, detection-latency, or AI productivity improvement was measured. Prior npm-audit/dependency results remain historical; those checks were not rerun in this targeted follow-up.
