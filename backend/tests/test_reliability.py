from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from itertools import permutations
from types import SimpleNamespace
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend import improved
from backend import main
from backend.db import connect, transaction
from backend.invariants import invariant_violations
from backend.main import create_app
from backend.replay import fixtures, scenario_assertions, protocol_assertions


def payment(**changes):
    return {'event_id': 'evt-payment', 'reservation_id': 'res-1001',
            'type': 'payment_succeeded', 'amount_cents': 9000, **changes}


def snapshot(client):
    return client.get('/api/improved/dashboard').json()


@pytest.mark.parametrize('mode', ['baseline', 'improved'])
def test_dashboard_is_one_consistent_snapshot_during_payment(client, monkeypatch, mode):
    db = client.app.state.data_dir / f'{mode}.sqlite3'
    # WAL permits a writer to commit while a reader holds its snapshot. A second
    # connection deterministically commits between reservation and ledger reads.
    with closing(connect(db)) as con:
        con.execute('PRAGMA journal_mode=WAL')
    original_connect = main.connect
    committed = []
    closed_readers = []

    def dashboard_connection(path):
        con = original_connect(path)

        def concurrent_payment(statement):
            if statement == 'SELECT * FROM ledger ORDER BY id DESC' and not committed:
                handler = main.baseline if mode == 'baseline' else improved
                committed.append(handler.process(db, main.Event(**payment())))

        con.set_trace_callback(concurrent_payment)

        def close_reader():
            con.close()
            closed_readers.append(path)

        return SimpleNamespace(execute=con.execute, close=close_reader)

    monkeypatch.setattr(main, 'connect', dashboard_connection)
    data = client.get(f'/api/{mode}/dashboard').json()
    assert len(committed) == 1, 'The overlapping payment must actually commit'
    assert data['reservations'][0]['status'] == 'pending'
    assert data['ledger'] == []
    assert data['deliveries'] == []
    assert len(data['history']) == 3
    assert data['violations'] == []
    assert data['metrics']['invariant_violations'] == 0
    if mode == 'improved':
        assert data['provider_events'] == []
        assert data['incidents'] == []
    assert closed_readers == [db], 'Release the snapshot before response rendering'

    latest = client.get(f'/api/{mode}/dashboard').json()
    assert latest['reservations'][0]['status'] == 'paid'
    assert len(latest['ledger']) == len(latest['deliveries']) == 1
    assert latest['violations'] == []


@pytest.mark.parametrize('scenario', fixtures(), ids=lambda scenario: scenario['id'])
def test_identical_replay_fixtures_pass(client, scenario):
    responses = []
    for event in scenario['events']:
        response = client.post('/api/improved/webhooks', json=event)
        responses.append(response)
        assert not invariant_violations(snapshot(client)), 'Every delivery prefix must remain safe'
    checks = scenario_assertions(scenario, snapshot(client))
    assert all(checks.values()), checks
    protocol = protocol_assertions(scenario, responses, snapshot(client))
    assert all(protocol.values()), protocol


@pytest.mark.parametrize('order', list(permutations(['authorized', 'payment_succeeded', 'refund_succeeded'])))
def test_all_event_orders_and_retries_converge(client, order):
    for kind in order:
        event = payment(type=kind, event_id=f'evt-{kind}')
        for _ in range(2):
            assert client.post('/api/improved/webhooks', json=event).status_code == 200
            assert not invariant_violations(snapshot(client))
    data = snapshot(client)
    assert len(data['ledger']) == 2
    assert data['reservations'][0]['status'] == 'refunded'
    assert sum(row['amount_cents'] for row in data['ledger']) == 0
    assert data['metrics']['deferred_events'] == 0
    assert not any(row['code'] == 'refund_deferred' and not row['resolved'] for row in data['incidents'])


def test_concurrent_deliveries_apply_exactly_once(client):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: client.post('/api/improved/webhooks', json=payment()), range(24)))
    assert all(response.status_code == 200 for response in responses)
    assert sum(response.json()['outcome'] == 'applied' for response in responses) == 1
    assert sum(response.json()['outcome'] == 'duplicate' for response in responses) == 23
    data = snapshot(client)
    assert len(data['ledger']) == 1
    assert len(data['deliveries']) == 24
    assert data['metrics']['open_alerts'] == 0


def test_deduplication_survives_app_restart(tmp_path):
    with TestClient(create_app(tmp_path)) as first:
        assert first.post('/api/improved/webhooks', json=payment()).json()['outcome'] == 'applied'
    with TestClient(create_app(tmp_path)) as second:
        assert second.post('/api/improved/webhooks', json=payment()).json()['outcome'] == 'duplicate'
        assert len(snapshot(second)['ledger']) == 1


def test_new_event_ids_cannot_double_charge_or_double_refund(client):
    for identity in ['charge-one', 'charge-two']:
        assert client.post('/api/improved/webhooks', json=payment(event_id=identity)).status_code == 200
    for identity in ['refund-one', 'refund-two']:
        assert client.post('/api/improved/webhooks', json=payment(event_id=identity, type='refund_succeeded')).status_code == 200
    data = snapshot(client)
    assert len(data['ledger']) == 2
    assert data['reservations'][0]['status'] == 'refunded'


def test_rejected_payload_stays_rejected_and_identity_is_immutable(client):
    wrong = payment(amount_cents=4500)
    assert client.post('/api/improved/webhooks', json=wrong).status_code == 409
    retry = client.post('/api/improved/webhooks', json=wrong)
    assert retry.status_code == 409
    assert retry.json()['original_outcome'] == 'rejected'
    assert client.post('/api/improved/webhooks', json=payment()).status_code == 409
    data = snapshot(client)
    assert not data['ledger']
    assert data['provider_events'][0]['outcome'] == 'rejected'
    assert data['metrics']['open_alerts'] == 2


def test_unknown_reservation_and_invalid_transition_have_context(client):
    unknown = client.post('/api/improved/webhooks', json=payment(reservation_id='missing'))
    assert unknown.status_code == 409
    assert client.post('/api/improved/webhooks', json=payment(type='refund_failed', event_id='evt-refund-fail')).status_code == 409
    data = snapshot(client)
    assert {row['code'] for row in data['incidents']} == {'unknown_reservation', 'invalid_transition'}
    assert all(row['event_id'] and row['reservation_id'] and row['delivery_id'] for row in data['incidents'])
    assert not data['ledger']


def test_failure_during_deferred_refund_reconciliation_rolls_back_everything(client, monkeypatch):
    assert client.post('/api/improved/webhooks', json=payment(type='refund_succeeded', event_id='evt-refund')).json()['outcome'] == 'deferred'
    before = snapshot(client)
    original = improved.add_ledger

    def fail_on_refund(con, event_id, reservation_id, kind, amount):
        if kind == 'refund':
            raise RuntimeError('Injected storage failure after charge insert')
        return original(con, event_id, reservation_id, kind, amount)

    monkeypatch.setattr(improved, 'add_ledger', fail_on_refund)
    with pytest.raises(RuntimeError, match='Injected storage failure'):
        client.post('/api/improved/webhooks', json=payment())
    assert snapshot(client) == before
    monkeypatch.setattr(improved, 'add_ledger', original)
    assert client.post('/api/improved/webhooks', json=payment()).status_code == 200
    assert snapshot(client)['reservations'][0]['status'] == 'refunded'


def test_database_constraints_guard_business_effects(client):
    client.post('/api/improved/webhooks', json=payment())
    db = client.app.state.data_dir / 'improved.sqlite3'
    with pytest.raises(sqlite3.IntegrityError):
        with transaction(db) as con:
            con.execute("INSERT INTO ledger (reservation_id,event_id,kind,amount_cents) VALUES ('res-1001','different-event','charge',9000)")
    with closing(connect(db)) as con:
        assert con.execute('SELECT count(*) FROM ledger').fetchone()[0] == 1


def test_log_file_failure_does_not_retry_committed_business_effect(client, monkeypatch):
    def unavailable(*args):
        raise OSError('Injected log filesystem failure')
    monkeypatch.setattr('backend.main.append_log', unavailable)
    assert client.post('/api/improved/webhooks', json=payment()).status_code == 200
    assert client.post('/api/improved/webhooks', json=payment()).json()['outcome'] == 'duplicate'
    assert len(snapshot(client)['ledger']) == 1


@pytest.mark.parametrize('change', [
    {'amount_cents': 0}, {'amount_cents': -5}, {'amount_cents': 9000.0},
    {'amount_cents': True}, {'type': 'unknown'}, {'event_id': '../bad'},
    {'extra': 'not-allowed'},
])
def test_malformed_events_are_validation_errors(client, change):
    assert client.post('/api/improved/webhooks', json=payment(**change)).status_code == 422
    assert snapshot(client)['deliveries'] == []


def test_concurrent_bookings_do_not_overlap(client):
    booking = {'campsite_id': 'pine-01', 'guest_label': 'Demo group',
               'arrival': '2027-08-01', 'departure': '2027-08-03'}
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda i: client.post('/api/improved/bookings', json={**booking, 'idempotency_key': f'booking-{i:04}'}), range(8)))
    assert sum(response.status_code == 201 for response in responses) == 1
    assert sum(response.status_code == 409 for response in responses) == 7


def test_adjacent_stays_allowed_and_booking_key_conflicts_rejected(client):
    booking = {'campsite_id': 'pine-01', 'guest_label': 'Demo adjacent',
               'arrival': '2027-06-14', 'departure': '2027-06-15', 'idempotency_key': 'adjacent-test'}
    first = client.post('/api/improved/bookings', json=booking)
    assert first.status_code == 201
    assert first.json()['amount_cents'] == 4500
    assert client.post('/api/improved/bookings', json=booking).json()['id'] == first.json()['id']
    assert client.post('/api/improved/bookings', json={**booking, 'departure': '2027-06-16'}).status_code == 409
