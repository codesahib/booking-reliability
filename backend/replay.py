"""Comparable HTTP replay and assertions; baseline failures are data, not hidden."""
import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient

from .main import create_app

FIXTURE_PATH = Path(__file__).resolve().parents[1] / 'fixtures' / 'replays.json'


def fixtures():
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))


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


def scenario_assertions(scenario, data):
    ledger = [row for row in data['ledger'] if row['reservation_id'] == 'res-1001']
    reservation = next(row for row in data['reservations'] if row['id'] == 'res-1001')
    checks = {
        'final_status': reservation['status'] == scenario['expected_status'],
        'charge_count': sum(row['kind'] == 'charge' for row in ledger) == scenario['expected_charges'],
        'refund_count': sum(row['kind'] == 'refund' for row in ledger) == scenario['expected_refunds'],
        'invariants': not invariant_violations(data),
    }
    if scenario.get('expected_incident'):
        checks['alert_context'] = any(row['code'] == scenario['expected_incident'] and
                                      row['reservation_id'] == 'res-1001' and row['event_id']
                                      for row in data.get('incidents', []))
    return checks


def evaluate(modes):
    report = {'fixture_sha256': hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest(),
              'method': 'Fresh seeded SQLite database per mode per scenario; in-process HTTP TestClient; final-state assertions.',
              'modes': {}}
    for mode in modes:
        scenarios = []
        scratch = FIXTURE_PATH.parents[1] / 'data' / 'replay-scratch'
        scratch.mkdir(parents=True, exist_ok=True)
        for scenario in fixtures():
            with tempfile.TemporaryDirectory(prefix='booking-replay-', dir=scratch) as folder:
                with TestClient(create_app(Path(folder))) as client:
                    responses = [client.post(f'/api/{mode}/webhooks', json=event) for event in scenario['events']]
                    data = client.get(f'/api/{mode}/dashboard').json()
                    if 'ledger' not in data:
                        raise RuntimeError(f'Mode unavailable: {mode}: {data}')
                    counts = Counter(row['event_id'] for row in data['ledger'])
                    checks = scenario_assertions(scenario, data)
                    scenarios.append({
                        'id': scenario['id'], 'deliveries': len(responses),
                        'http_statuses': [response.status_code for response in responses],
                        'outcomes': [response.json().get('outcome', 'http_error') for response in responses],
                        'ledger_entries': len(data['ledger']),
                        'duplicate_ledger_entries': sum(max(0, count - 1) for count in counts.values()),
                        'invariant_violations': invariant_violations(data), 'assertions': checks,
                        'failed_assertions': sum(not passed for passed in checks.values()),
                        'incidents': data.get('incidents', []),
                        'delivery_trace': data['deliveries'],
                    })
        report['modes'][mode] = {
            'scenario_count': len(scenarios),
            'delivery_count': sum(s['deliveries'] for s in scenarios),
            'assertion_count': sum(len(s['assertions']) for s in scenarios),
            'failed_scenarios': sum(s['failed_assertions'] > 0 for s in scenarios),
            'failed_assertions': sum(s['failed_assertions'] for s in scenarios),
            'duplicate_ledger_entries': sum(s['duplicate_ledger_entries'] for s in scenarios),
            'invariant_violations': sum(len(s['invariant_violations']) for s in scenarios),
            'scenarios': scenarios,
        }
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--modes', nargs='+', default=['baseline'])
    parser.add_argument('--output', type=Path, default=Path('evidence/diagnosis.json'))
    args = parser.parse_args()
    result = evaluate(args.modes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    for mode, stats in result['modes'].items():
        print(mode, json.dumps({key: value for key, value in stats.items() if key != 'scenarios'}))
    print(f'Full evidence: {args.output}')
