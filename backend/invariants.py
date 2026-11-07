"""Read-only invariants shared by the dashboard, replay and regression tests."""

def invariant_violations(data):
    issues = []
    for reservation in data['reservations']:
        rid, amount = reservation['id'], reservation['amount_cents']
        ledger = [row for row in data['ledger'] if row['reservation_id'] == rid]
        charges = [row for row in ledger if row['kind'] == 'charge']
        refunds = [row for row in ledger if row['kind'] == 'refund']
        checks = {
            'multiple_charges': len(charges) > 1,
            'multiple_refunds': len(refunds) > 1,
            'repeated_event_in_ledger': len({row['event_id'] for row in ledger}) < len(ledger),
            'incorrect_amount': any(row['amount_cents'] != (amount if row['kind'] == 'charge' else -amount) for row in ledger),
            'refund_without_charge': bool(refunds) and not charges,
            'balance_outside_bounds': not 0 <= sum(row['amount_cents'] for row in ledger) <= amount,
            'status_ledger_mismatch': (
                (bool(refunds) and reservation['status'] != 'refunded') or
                (bool(charges) and not refunds and reservation['status'] != 'paid') or
                (not ledger and reservation['status'] in ('paid', 'refunded'))),
        }
        issues.extend({'reservation_id': rid, 'code': code} for code, failed in checks.items() if failed)
    return issues

