# Gate 1 — working original workflow

This is an independent synthetic demonstration inspired by campground SaaS. It does not describe a Beacon system or an observed customer incident.

The reservation desk creates local bookings, checks date overlaps, calculates integer-cent prices, and returns a synthetic confirmation. Seed data contains three campsites and three pending bookings. The fake gateway posts authorization, payment-success, refund-success, or refund-failure events. The admin sees reservations, deliveries, ledger entries, and history. No money moves and no provider is contacted.

`backend/baseline.py` is a plausible early handler: it trusts every delivery as a new business event, appends accounting, then sets reservation status from that event. SQLite transactions already protect an individual delivery from partial writes. Booking creation already has idempotency keys and overlap checks. The weakness is specifically missing provider-event identity and event-order checks; it is not a deliberately broken transaction or a random failure generator.

To reproduce: select `res-1001`, send payment success twice. The same event ID appears twice in the ledger, with two fictional $90 charges. Send authorization after success and status regresses to authorized. Support must inspect `data/logs/baseline.jsonl` and compare the event trail with accounting; the original admin has no incident correlation or automatic invariant check.

Baseline tests cover the ordinary authorization/payment path, history, booking idempotency, date validation, overlap rejection, and missing reservations. Retry/order shortcomings are captured separately at the diagnosis gate so passing original-workflow tests are not misrepresented as reliability coverage.

Run (Ubuntu/WSL, repository root):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm ci
bash scripts/reset-demo.sh
python -m pytest -q
npm run build
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8003
# second terminal
npm run dev
```

The `baseline-demo` Git tag preserves this working gate. The final tree retains the same handler for side-by-side experiments. Known baseline limitations must never be used for real payment processing.
