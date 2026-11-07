"""Comparable HTTP replay and assertions; baseline failures are data, not hidden."""
import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path

from fastapi.testclient import TestClient

from .main import create_app
from .invariants import invariant_violations

FIXTURE_PATH = Path(__file__).resolve().parents[1] / 'fixtures' / 'replays.json'
PROTOCOL_PATH = Path(__file__).resolve().parents[1] / 'fixtures' / 'protocol-expectations.json'


def fixtures():
    return json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))


def protocol_assertions(scenario, responses, data):
    """Additional protocol checks; never merged into the legacy 31 checks."""
    expected = json.loads(PROTOCOL_PATH.read_text(encoding='utf-8'))[scenario['id']]
    if len(expected) != len(scenario['events']) or len(responses) != len(expected):
        raise ValueError('Protocol expectations must cover every fixture delivery')
    checks = {}
    for index, (event, response, contract) in enumerate(zip(scenario['events'], responses, expected), 1):
        prefix = f'delivery_{index}'
        checks[f'{prefix}_status'] = response.status_code == contract['status']
        checks[f'{prefix}_outcome'] = response.json().get('outcome') == contract['outcome']
        if 'incident' in contract:
            incident = contract['incident']
            delivery_id = response.json().get('delivery_id')
            delivery = next((row for row in data['deliveries'] if row['id'] == delivery_id and
                             row['event_id'] == event['event_id'] and row['reservation_id'] == event['reservation_id'] and
                             row['event_type'] == event['type']), None)
            linked = [row for row in data.get('incidents', []) if delivery is not None and
                      row['code'] == incident['code'] and row['delivery_id'] == delivery_id and
                      row['event_id'] == event['event_id'] and row['reservation_id'] == event['reservation_id']]
            checks[f'{prefix}_incident_correlation'] = bool(linked)
            checks[f'{prefix}_incident_severity'] = any(row['severity'] == incident['severity'] for row in linked)
    return checks


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
              'protocol_expectations_sha256': hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest(),
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
                    protocol = protocol_assertions(scenario, responses, data)
                    scenarios.append({
                        'id': scenario['id'], 'deliveries': len(responses),
                        'http_statuses': [response.status_code for response in responses],
                        'outcomes': [response.json().get('outcome', 'http_error') for response in responses],
                        'ledger_entries': len(data['ledger']),
                        'duplicate_ledger_entries': sum(max(0, count - 1) for count in counts.values()),
                        'invariant_violations': invariant_violations(data), 'assertions': checks,
                        'failed_assertions': sum(not passed for passed in checks.values()),
                        'protocol_assertions': protocol,
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
            'protocol': {
                'assertion_count': sum(len(s['protocol_assertions']) for s in scenarios),
                'failed_assertions': sum(not passed for s in scenarios for passed in s['protocol_assertions'].values()),
                'failed_scenarios': sum(not all(s['protocol_assertions'].values()) for s in scenarios),
            },
            'scenarios': scenarios,
        }
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--modes', nargs='+', choices=['baseline', 'improved'], default=['baseline', 'improved'])
    parser.add_argument('--output', type=Path, required=True,
                        help='Explicit report path; historical evidence is never a default destination')
    args = parser.parse_args()
    result = evaluate(args.modes)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    for mode, stats in result['modes'].items():
        print(mode, json.dumps({key: value for key, value in stats.items() if key != 'scenarios'}))
    print(f'Full evidence: {args.output}')
    if 'improved' in result['modes'] and (result['modes']['improved']['failed_assertions'] or
                                       result['modes']['improved']['protocol']['failed_assertions']):
        raise SystemExit('Improved replay failed its assertions; inspect the evidence')
