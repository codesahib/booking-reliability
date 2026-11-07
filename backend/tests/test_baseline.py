def event(kind='payment_succeeded', event_id='evt-success'):
    return {'event_id': event_id, 'reservation_id': 'res-1001', 'type': kind, 'amount_cents': 9000}


def test_original_booking_payment_and_history(client):
    assert client.get('/api/health').json()['payments'] == 'simulated'
    assert client.post('/api/baseline/webhooks', json=event('authorized', 'evt-auth')).status_code == 200
    assert client.post('/api/baseline/webhooks', json=event()).json()['status'] == 'paid'
    data = client.get('/api/baseline/dashboard').json()
    assert len(data['ledger']) == 1
    assert data['ledger'][0]['amount_cents'] == 9000
    assert data['reservations'][0]['status'] == 'paid'
    assert len(data['history']) == 5


def test_booking_validation_and_idempotency(client):
    booking = {'campsite_id': 'pine-01', 'guest_label': 'Synthetic camper',
               'arrival': '2027-07-01', 'departure': '2027-07-03', 'idempotency_key': 'booking-test-01'}
    first = client.post('/api/baseline/bookings', json=booking)
    assert first.status_code == 201
    assert first.json()['amount_cents'] == 9000
    assert client.post('/api/baseline/bookings', json=booking).json()['id'] == first.json()['id']
    assert client.post('/api/baseline/bookings', json={**booking, 'idempotency_key': 'booking-test-02'}).status_code == 409
    assert client.post('/api/baseline/bookings', json={**booking, 'departure': '2027-06-01'}).status_code == 422
    assert client.post('/api/baseline/webhooks', json={**event(), 'amount_cents': -1}).status_code == 422
    assert client.post('/api/baseline/webhooks', json={**event(), 'reservation_id': 'missing'}).status_code == 404
