import os
import sqlite3
from contextlib import asynccontextmanager, closing
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from . import baseline
from .db import append_log, connect, initialize, transaction
from .models import Booking, Event

Mode = Literal['baseline']
DEFAULT_DATA = Path(__file__).resolve().parents[1] / 'data'


def create_app(data_dir: Path | None = None):
    root = Path(data_dir or os.environ.get('BOOKING_DATA_DIR', DEFAULT_DATA))

    @asynccontextmanager
    async def lifespan(app):
        initialize(root / 'baseline.sqlite3')
        yield

    app = FastAPI(title='Campground Reliability Lab', lifespan=lifespan)
    app.state.data_dir = root

    def path(mode):
        return root / f'{mode}.sqlite3'

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'payments': 'simulated'}

    @app.get('/api/{mode}/dashboard')
    def dashboard(mode: Mode):
        with closing(connect(path(mode))) as con:
            def rows(query):
                return [dict(row) for row in con.execute(query)]
            return {
                'mode': mode,
                'campsites': rows('SELECT * FROM campsites ORDER BY id'),
                'reservations': rows('SELECT r.*, c.name AS campsite_name FROM reservations r JOIN campsites c ON c.id=r.campsite_id ORDER BY r.id'),
                'ledger': rows('SELECT * FROM ledger ORDER BY id DESC'),
                'deliveries': rows('SELECT * FROM deliveries ORDER BY id DESC'),
                'history': rows('SELECT * FROM history ORDER BY id DESC'),
            }

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
            result = baseline.process(path(mode), event)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        except sqlite3.OperationalError as exc:
            raise HTTPException(503, 'Local database busy; retry this event') from exc
        append_log(root, mode, result)
        return result

    return app


app = create_app()
