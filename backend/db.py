"""Small, inspectable SQLite store. All amounts are fictional integer cents."""
import json
import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS campsites (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, setting TEXT NOT NULL,
 nightly_cents INTEGER NOT NULL CHECK(nightly_cents > 0));
CREATE TABLE IF NOT EXISTS reservations (
 id TEXT PRIMARY KEY, campsite_id TEXT NOT NULL REFERENCES campsites(id),
 guest_label TEXT NOT NULL, arrival TEXT NOT NULL, departure TEXT NOT NULL,
 amount_cents INTEGER NOT NULL CHECK(amount_cents > 0),
 status TEXT NOT NULL CHECK(status IN ('pending','authorized','paid','refunded')),
 booking_key TEXT UNIQUE, booking_payload TEXT);
CREATE TABLE IF NOT EXISTS ledger (
 id INTEGER PRIMARY KEY, reservation_id TEXT NOT NULL REFERENCES reservations(id),
 event_id TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('charge','refund')),
 amount_cents INTEGER NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS deliveries (
 id INTEGER PRIMARY KEY, reservation_id TEXT NOT NULL, event_id TEXT NOT NULL,
 event_type TEXT NOT NULL, amount_cents INTEGER NOT NULL, outcome TEXT NOT NULL,
 detail TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
CREATE TABLE IF NOT EXISTS history (
 id INTEGER PRIMARY KEY, reservation_id TEXT NOT NULL REFERENCES reservations(id),
 event_id TEXT, status TEXT NOT NULL, detail TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
"""

IMPROVED_SCHEMA = """
CREATE TABLE IF NOT EXISTS provider_events (
 event_id TEXT PRIMARY KEY, reservation_id TEXT NOT NULL, event_type TEXT NOT NULL,
 amount_cents INTEGER NOT NULL, payload TEXT NOT NULL, outcome TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ledger_event_unique ON ledger(event_id);
CREATE UNIQUE INDEX IF NOT EXISTS ledger_business_effect_unique ON ledger(reservation_id,kind);
CREATE TABLE IF NOT EXISTS incidents (
 id INTEGER PRIMARY KEY, reservation_id TEXT NOT NULL, event_id TEXT NOT NULL,
 delivery_id INTEGER NOT NULL REFERENCES deliveries(id),
 severity TEXT NOT NULL CHECK(severity IN ('info','warning','error')),
 code TEXT NOT NULL, detail TEXT NOT NULL,
 resolved INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
 resolved_at TEXT);
CREATE INDEX IF NOT EXISTS incidents_reservation ON incidents(reservation_id,event_id);
CREATE INDEX IF NOT EXISTS deliveries_event ON deliveries(event_id,reservation_id);
"""


def connect(path: Path):
    con = sqlite3.connect(path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


@contextmanager
def transaction(path: Path):
    con = connect(path)
    try:
        con.execute('BEGIN IMMEDIATE')
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def initialize(path: Path, *, improved=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as con, con:
        con.executescript(SCHEMA)
        if improved:
            con.executescript(IMPROVED_SCHEMA)
        if not con.execute('SELECT 1 FROM campsites').fetchone():
            con.executemany('INSERT INTO campsites VALUES (?,?,?,?)', [
                ('pine-01', 'Pine Hollow', 'Forest · electric', 4500),
                ('lake-02', 'Stillwater Point', 'Lakeside · tent', 5500),
                ('ridge-03', 'Juniper Ridge', 'Ridge · camper', 6500),
            ])
            for rid, cid, guest, arrival, departure, amount in [
                ('res-1001', 'pine-01', 'Demo camper A', '2027-06-12', '2027-06-14', 9000),
                ('res-1002', 'lake-02', 'Demo camper B', '2027-06-15', '2027-06-17', 11000),
                ('res-1003', 'ridge-03', 'Demo camper C', '2027-06-20', '2027-06-22', 13000),
            ]:
                con.execute('INSERT INTO reservations (id,campsite_id,guest_label,arrival,departure,amount_cents,status) VALUES (?,?,?,?,?,?,?)',
                            (rid, cid, guest, arrival, departure, amount, 'pending'))
                con.execute('INSERT INTO history (reservation_id,status,detail) VALUES (?,?,?)',
                            (rid, 'pending', 'Synthetic booking confirmed; awaiting simulated payment'))


def append_log(root: Path, mode: str, record: dict):
    folder = root / 'logs'
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f'{mode}.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'mode': mode, **record}, sort_keys=True) + '\n')
