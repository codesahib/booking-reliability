"""Frozen legacy-like handler: trusts each valid delivery as a new business event.

This simulated weakness is deliberate and documented, not a real-company incident.
"""
from .db import transaction
from .models import Event


def process(path, event: Event):
    with transaction(path) as con:
        reservation = con.execute('SELECT * FROM reservations WHERE id=?', (event.reservation_id,)).fetchone()
        if reservation is None:
            raise LookupError('Reservation not found')
        status = reservation['status']
        if event.type == 'authorized':
            status = 'authorized'
        elif event.type == 'payment_succeeded':
            con.execute('INSERT INTO ledger (reservation_id,event_id,kind,amount_cents) VALUES (?,?,?,?)',
                        (event.reservation_id, event.event_id, 'charge', event.amount_cents))
            status = 'paid'
        elif event.type == 'refund_succeeded':
            con.execute('INSERT INTO ledger (reservation_id,event_id,kind,amount_cents) VALUES (?,?,?,?)',
                        (event.reservation_id, event.event_id, 'refund', -event.amount_cents))
            status = 'refunded'
        con.execute('UPDATE reservations SET status=? WHERE id=?', (status, event.reservation_id))
        detail = 'Provider event applied' if event.type != 'refund_failed' else 'Provider reported refund failure'
        con.execute('INSERT INTO history (reservation_id,event_id,status,detail) VALUES (?,?,?,?)',
                    (event.reservation_id, event.event_id, status, detail))
        cursor = con.execute('INSERT INTO deliveries (reservation_id,event_id,event_type,amount_cents,outcome,detail) VALUES (?,?,?,?,?,?)',
                             (event.reservation_id, event.event_id, event.type, event.amount_cents, 'applied', detail))
        return {'delivery_id': cursor.lastrowid, 'event_id': event.event_id,
                'reservation_id': event.reservation_id, 'outcome': 'applied', 'detail': detail, 'status': status}
