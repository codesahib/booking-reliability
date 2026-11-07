import os
import json
import logging
import sqlite3
from collections import Counter
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from . import baseline, improved
from .db import append_log, connect, initialize, transaction
from .invariants import invariant_violations
from .models import Booking, Event

Mode = Literal['baseline', 'improved']
DEFAULT_DATA = Path(__file__).resolve().parents[1] / 'data'


def create_app(data_dir: Path | None = None):
    root = Path(data_dir or os.environ.get('BOOKING_DATA_DIR', DEFAULT_DATA))

    @asynccontextmanager
    async def lifespan(app):
        initialize(root / 'baseline.sqlite3')
        initialize(root / 'improved.sqlite3', improved=True)
        yield

    app = FastAPI(title='Campground Reliability Lab', lifespan=lifespan)
    app.state.data_dir = root

    def path(mode):
        return root / f'{mode}.sqlite3'

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'payments': 'simulated'}

    @app.get('/api/fixtures')
    def replay_fixtures():
        source = Path(__file__).resolve().parents[1] / 'fixtures' / 'replays.json'
        return json.loads(source.read_text(encoding='utf-8'))

    @app.get('/api/{mode}/dashboard')
    def dashboard(mode: Mode):
        with closing(connect(path(mode))) as con:
            # One read snapshot keeps status, accounting and diagnostics coherent
            # when a webhook commits between these queries. Closing ends the
            # transaction before FastAPI renders the response.
            con.execute('BEGIN')
            def rows(query):
                return [dict(row) for row in con.execute(query)]
            data = {
                'mode': mode,
                'campsites': rows('SELECT * FROM campsites ORDER BY id'),
                'reservations': rows('SELECT r.*, c.name AS campsite_name FROM reservations r JOIN campsites c ON c.id=r.campsite_id ORDER BY r.id'),
                'ledger': rows('SELECT * FROM ledger ORDER BY id DESC'),
                'deliveries': rows('SELECT * FROM deliveries ORDER BY id DESC'),
                'history': rows('SELECT * FROM history ORDER BY id DESC'),
                'incidents': rows('SELECT * FROM incidents ORDER BY id DESC') if mode == 'improved' else [],
                'provider_events': rows('SELECT event_id,reservation_id,event_type,outcome FROM provider_events ORDER BY rowid DESC') if mode == 'improved' else [],
            }
            counts = Counter(row['event_id'] for row in data['ledger'])
            data['violations'] = invariant_violations(data)
            data['metrics'] = {
                'duplicate_ledger_entries': sum(max(0, count - 1) for count in counts.values()),
                'invariant_violations': len(data['violations']),
                'duplicates_suppressed': sum(row['outcome'] == 'duplicate' for row in data['deliveries']),
                'open_alerts': sum(not row['resolved'] and row['severity'] != 'info' for row in data['incidents']),
                'deferred_events': sum(row['outcome'] == 'deferred' for row in data['provider_events']),
            }
            return data

    @app.post('/api/{mode}/bookings', status_code=201)
    def book(mode: Mode, booking: Booking):
        payload = booking.model_dump_json(exclude={'idempotency_key'})
        with transaction(path(mode)) as con:
            existing = con.execute('SELECT * FROM reservations WHERE booking_key=?', (booking.idempotency_key,)).fetchone()
            if existing:
                if existing['booking_payload'] != payload:
                    raise HTTPException(409, 'Booking key already used with different details')
                return dict(existing)
            site = con.execute('SELECT * FROM campsites WHERE id=?', (booking.campsite_id,)).fetchone()
            if not site:
                raise HTTPException(404, 'Campsite not found')
            overlap = con.execute('SELECT 1 FROM reservations WHERE campsite_id=? AND arrival<? AND departure>? AND status<>?',
                                  (booking.campsite_id, str(booking.departure), str(booking.arrival), 'refunded')).fetchone()
            if overlap:
                raise HTTPException(409, 'Campsite is already reserved for these dates')
            rid = f'res-{uuid4().hex[:12]}'
            amount = (booking.departure - booking.arrival).days * site['nightly_cents']
            con.execute('INSERT INTO reservations VALUES (?,?,?,?,?,?,?,?,?)',
                        (rid, booking.campsite_id, booking.guest_label, str(booking.arrival), str(booking.departure), amount, 'pending', booking.idempotency_key, payload))
            con.execute('INSERT INTO history (reservation_id,status,detail) VALUES (?,?,?)',
                        (rid, 'pending', 'Synthetic booking confirmed; awaiting simulated payment'))
            return dict(con.execute('SELECT * FROM reservations WHERE id=?', (rid,)).fetchone())

    @app.post('/api/{mode}/webhooks')
    def webhook(mode: Mode, event: Event):
        try:
            handler = baseline if mode == 'baseline' else improved
            result = handler.process(path(mode), event)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except sqlite3.OperationalError as exc:
            code = getattr(exc, 'sqlite_errorcode', None)
            # Extended SQLite result codes retain their primary code in the
            # low byte. Never infer contention from exception text/paths.
            contention = code is not None and (code & 0xff) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
            logging.getLogger('booking').exception(
                'Webhook storage failure mode=%s event_id=%s reservation_id=%s sqlite_code=%s',
                mode, event.event_id, event.reservation_id, code,
                extra={'mode': mode, 'event_id': event.event_id,
                       'reservation_id': event.reservation_id, 'sqlite_code': code})
            if contention:
                raise HTTPException(503, 'Local database busy; retry this event') from exc
            raise HTTPException(500, 'Local storage unavailable; inspect server diagnostics before retrying') from exc
        # Diagnostic DB rows are authoritative and transactional. An optional file
        # mirror must not turn a committed webhook into a retryable HTTP failure.
        try:
            append_log(root, mode, {'event_type': event.type, **result})
        except OSError:
            logging.getLogger('booking').exception('JSON log mirror unavailable; delivery_id=%s event_id=%s reservation_id=%s',
                                                    result['delivery_id'], event.event_id, event.reservation_id)
        return JSONResponse(result, status_code=result.get('http_status', 200))

    return app


app = create_app()
