# Interview demo — five to seven minutes

## Prepare

Install dependencies using README, stop existing demo servers, and reset:

```bash
source .venv/bin/activate
bash scripts/reset-demo.sh
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8003
# second terminal, repository root
npm run dev
```

Open `http://127.0.0.1:5175`. Keep `evidence/comparison.json` and `docs/03-results.md` ready. The baseline commit is `f3883f3`, tagged `baseline-demo`; the original handler is retained unchanged in the final tree.

## 1. Start with the operation

Say: “This independent synthetic demo is inspired by campground-reservation operations. Guests book a site; a fake provider reports payment events; support investigates state mismatches. No real funds or customer data are involved.”

Show three fictional upcoming stays. Select Pine Hollow (`res-1001`, $90). The original admin has a booking history and payment trail, but no correlated incident classification.

## 2. Reproduce a retry failure

In **Original workflow**, leave **Success + two identical retries** selected and click **Replay scenario**. It sends authorization, success, and the same success twice more. Observe:

- Four deliveries, three charge entries, two duplicate-identity ledger rows.
- Three final invariant violations: charge cardinality, repeated ledger event identity, and balance outside booking bounds.
- Paid status alone looks plausible; inspecting accounting reveals the problem.

Show the manual investigation guidance. In a terminal:

```bash
grep 'evt-payment' data/logs/baseline.jsonl
```

Explain that the checker cards are the lab's evaluation overlay. The original workflow at the tag does not have an automated incident detector.

## 3. Show the smallest fix

Switch to **Hardened workflow**, which has the same untouched seed in a separate database. Click **Replay scenario** again. Observe four deliveries, one ledger charge, zero duplicate rows, zero invariant violations, and two suppressed retries.

Inspect a **duplicate event** record. Point out `evt-payment`, `res-1001`, delivery number, original inbox outcome, current paid status, and one ledger entry. Explain that a transaction and unique constraints enforce the rule; Codex does not decide whether to accept a payment at runtime.

## 4. Show an alertable failure

Click **Send refund failure**. The fake provider reports failure; status remains paid and accounting retains its charge. Filter **Open alerts only**, then inspect **refund failed**. There is one open error with the booking/event/delivery context. No refund is fabricated to clear the alert.

## 5. Exercise the ordering edge case

Select Stillwater Point (`res-1002`) and clear the open-only filter if needed. Click **Send refund success** before payment. Its refund is deferred, with no ledger movement. Inspect the warning. Click **Send payment success**: the charge and deferred refund reconcile in one transaction, the reservation becomes refunded, and the prerequisite warning closes automatically. History retains both decisions. The failed-refund error for Pine Hollow remains visible; these are different bookings.

For the guest path, expand **Create a synthetic booking**, choose a campsite and free July dates, and confirm. The page shows a real synthetic reservation ID and pending payment. A payment event can be sent against that new stay. Repeating the same booking submission safely returns the same reservation; a changed overlapping stay is rejected.

## 6. Close with evidence and boundaries

Show `evidence/comparison.json`: seven scenarios, 15 deliveries and 31 assertions per version. Aggregate duplicate-identity ledger rows fall 3 → 0, final invariant violations 7 → 0, failed assertions 15 → 0. The third duplicate row belongs to a separate conflicting-ID scenario, not the three-delivery example.

Show `evidence/verification.json`: 33 backend passes, six exact expected baseline shortcomings, three browser passes, successful typecheck/build. Describe restart, concurrency, all event-order permutations, and injected rollback tests. Ordinary payment behavior already worked and still does.

Say: “Codex supported root-cause analysis, implementation, regression tests, and documentation. The runtime is deterministic. Human engineering time, production latency, and a human-only comparison were not measured. Real provider semantics, partial refunds, authentication, and production rollout need additional work and human review.”

## Offline fallback

If browser dependencies are unavailable during an interview, run the CLI replay and show the committed [before](../evidence/before-duplicate.png), [after](../evidence/after-duplicate.png), [failure context](../evidence/incident-refund-failure.png), and [out-of-order refund](../evidence/out-of-order-refund.png) captures. They were produced by passing browser interactions against the running app, not mock screens.
