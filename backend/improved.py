"""Transactional inbox + one-charge/one-full-refund state machine.

SQLite is the source of truth. Every accepted, ignored, deferred or rejected
delivery and its diagnostic context commit together with business effects.
"""
import json

from .db import transaction
from .models import Event


def add_ledger(con, event_id, reservation_id, kind, amount):
    con.execute('INSERT INTO ledger (reservation_id,event_id,kind,amount_cents) VALUES (?,?,?,?)',
                (reservation_id, event_id, kind, amount))


def set_status(con, rid, event_id, status, detail):
    con.execute('UPDATE reservations SET status=? WHERE id=?', (status, rid))
    con.execute('INSERT INTO history (reservation_id,event_id,status,detail) VALUES (?,?,?,?)',
                (rid, event_id, status, detail))


def process(path, event: Event):
    payload = json.dumps(event.model_dump(), sort_keys=True, separators=(',', ':'))
    with transaction(path) as con:
        cursor = con.execute('INSERT INTO deliveries (reservation_id,event_id,event_type,amount_cents,outcome,detail) VALUES (?,?,?,?,?,?)',
                             (event.reservation_id, event.event_id, event.type, event.amount_cents, 'received', 'Processing'))
        delivery_id = cursor.lastrowid

        def incident(code, detail, severity='error', resolved=False):
            con.execute("INSERT INTO incidents (reservation_id,event_id,delivery_id,severity,code,detail,resolved,resolved_at) VALUES (?,?,?,?,?,?,?,CASE WHEN ? THEN strftime('%Y-%m-%dT%H:%M:%fZ','now') END)",
                        (event.reservation_id, event.event_id, delivery_id, severity, code, detail, int(resolved), int(resolved)))

        def finish(outcome, detail, *, http_status=200, original_outcome=None):
            con.execute('UPDATE deliveries SET outcome=?,detail=? WHERE id=?', (outcome, detail, delivery_id))
            reservation = con.execute('SELECT status FROM reservations WHERE id=?', (event.reservation_id,)).fetchone()
            diagnostic = con.execute('SELECT code,severity FROM incidents WHERE delivery_id=? ORDER BY id DESC LIMIT 1', (delivery_id,)).fetchone()
            timestamp = con.execute('SELECT created_at FROM deliveries WHERE id=?', (delivery_id,)).fetchone()[0]
            return {'delivery_id': delivery_id, 'event_id': event.event_id,
                    'reservation_id': event.reservation_id, 'event_type': event.type,
                    'outcome': outcome, 'detail': detail, 'http_status': http_status,
                    'original_outcome': original_outcome, 'status': reservation['status'] if reservation else None,
                    'code': diagnostic['code'] if diagnostic else None,
                    'severity': diagnostic['severity'] if diagnostic else 'info', 'created_at': timestamp}

        existing = con.execute('SELECT * FROM provider_events WHERE event_id=?', (event.event_id,)).fetchone()
        if existing:
            if existing['payload'] != payload:
                detail = f"Event ID belongs to reservation {existing['reservation_id']} / {existing['event_type']} with a different payload; no business effects applied"
                incident('event_id_conflict', detail)
                return finish('rejected', detail, http_status=409)
            detail = f"Identical delivery suppressed; original outcome: {existing['outcome']}"
            incident('duplicate_event', detail, 'info', True)
            code = 409 if existing['outcome'] == 'rejected' else 200
            return finish('duplicate', detail, http_status=code, original_outcome=existing['outcome'])

        con.execute('INSERT INTO provider_events VALUES (?,?,?,?,?,?)',
                    (event.event_id, event.reservation_id, event.type, event.amount_cents, payload, 'received'))

        def complete(outcome, detail, *, code=None, severity='error', resolved=False, http_status=200):
            con.execute('UPDATE provider_events SET outcome=? WHERE event_id=?', (outcome, event.event_id))
            if code:
                incident(code, detail, severity, resolved)
            return finish(outcome, detail, http_status=http_status)

        reservation = con.execute('SELECT * FROM reservations WHERE id=?', (event.reservation_id,)).fetchone()
        if reservation is None:
            return complete('rejected', 'Reservation not found; event retained for investigation',
                            code='unknown_reservation', http_status=409)
        if event.amount_cents != reservation['amount_cents']:
            return complete('rejected', f"Expected {reservation['amount_cents']} fictional cents; received {event.amount_cents}",
                            code='amount_mismatch', http_status=409)

        ledger = {row['kind']: row for row in con.execute('SELECT * FROM ledger WHERE reservation_id=?', (event.reservation_id,))}
        status = reservation['status']

        if event.type == 'authorized':
            if status in ('paid', 'refunded'):
                return complete('ignored', 'Late authorization cannot reverse settled accounting',
                                code='stale_authorization', severity='info', resolved=True)
            if status != 'authorized':
                set_status(con, event.reservation_id, event.event_id, 'authorized', 'Synthetic authorization accepted')
            return complete('applied', 'Authorization recorded; no accounting movement')

        if event.type == 'refund_failed':
            if status != 'paid':
                return complete('rejected', 'Refund failure is only valid for a paid, unrefunded reservation',
                                code='invalid_transition', http_status=409)
            return complete('failed', 'Provider reports refund failure; charge retained; human follow-up required', code='refund_failed')

        if event.type == 'payment_succeeded':
            if 'charge' in ledger:
                return complete('ignored', 'Reservation already has its full charge; additional charge identity ignored',
                                code='redundant_charge', severity='info', resolved=True)
            add_ledger(con, event.event_id, event.reservation_id, 'charge', event.amount_cents)
            set_status(con, event.reservation_id, event.event_id, 'paid', 'Full synthetic charge recorded')
            deferred = con.execute("SELECT * FROM provider_events WHERE reservation_id=? AND event_type='refund_succeeded' AND outcome='deferred' ORDER BY rowid LIMIT 1",
                                   (event.reservation_id,)).fetchone()
            if deferred:
                add_ledger(con, deferred['event_id'], event.reservation_id, 'refund', -deferred['amount_cents'])
                set_status(con, event.reservation_id, deferred['event_id'], 'refunded', 'Deferred refund applied after matching charge')
                con.execute("UPDATE provider_events SET outcome='applied' WHERE event_id=?", (deferred['event_id'],))
                con.execute("UPDATE incidents SET resolved=1,resolved_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE event_id=? AND code='refund_deferred'", (deferred['event_id'],))
                return complete('applied', 'Charge recorded and deferred refund reconciled atomically')
            return complete('applied', 'Full synthetic charge recorded exactly once')

        # Only refund_succeeded remains: models.Event rejects unknown event types.
        if 'refund' in ledger:
            return complete('ignored', 'Reservation already fully refunded; additional refund identity ignored',
                            code='redundant_refund', severity='info', resolved=True)
        if 'charge' not in ledger:
            pending = con.execute("SELECT 1 FROM provider_events WHERE reservation_id=? AND outcome='deferred' AND event_type='refund_succeeded'",
                                  (event.reservation_id,)).fetchone()
            if pending:
                return complete('ignored', 'A full refund is already awaiting its charge',
                                code='redundant_refund', severity='info', resolved=True)
            return complete('deferred', 'Refund retained until its matching charge arrives; no ledger entry created',
                            code='refund_deferred', severity='warning')
        add_ledger(con, event.event_id, event.reservation_id, 'refund', -event.amount_cents)
        set_status(con, event.reservation_id, event.event_id, 'refunded', 'Full synthetic refund recorded')
        return complete('applied', 'Full synthetic refund recorded exactly once')
