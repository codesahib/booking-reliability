"""Regressions for BR-001: storage context, replay protocol, and CLI safety."""
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest

from backend import db, improved, replay


def payment():
    return {'event_id': 'review-payment', 'reservation_id': 'res-1001',
            'type': 'payment_succeeded', 'amount_cents': 9000}


@pytest.mark.parametrize('code,status', [
    (sqlite3.SQLITE_BUSY, 503), (sqlite3.SQLITE_LOCKED, 503),
    (sqlite3.SQLITE_BUSY | (1 << 8), 503), (sqlite3.SQLITE_IOERR, 500), (None, 500),
])
def test_storage_error_classification_logging_rollback_and_retry(client, monkeypatch, caplog, code, status):
    before = client.get('/api/improved/dashboard').json()
    original = improved.add_ledger
    error = sqlite3.OperationalError('Injected storage failure at /private/internal/demo.sqlite3')
    if code is not None:
        error.sqlite_errorcode = code

    def fail_after_insert(*args):
        original(*args)
        raise error

    with monkeypatch.context() as patch:
        patch.setattr(improved, 'add_ledger', fail_after_insert)
        with caplog.at_level(logging.ERROR, logger='booking'):
            response = client.post('/api/improved/webhooks', json=payment())
    assert response.status_code == status
    assert '/private/' not in response.text
    assert 'Injected' not in response.text
    assert ('busy' in response.text.lower()) == (status == 503)
    records = [record for record in caplog.records if record.name == 'booking']
    assert len(records) == 1
    record = records[0]
    assert record.event_id == 'review-payment'
    assert record.reservation_id == 'res-1001'
    assert record.mode == 'improved'
    assert record.exc_info[1] is error
    assert 'review-payment' in record.getMessage() and 'res-1001' in record.getMessage()
    assert client.get('/api/improved/dashboard').json() == before
    assert client.post('/api/improved/webhooks', json=payment()).status_code == 200
    assert len(client.get('/api/improved/dashboard').json()['ledger']) == 1


def test_actual_writer_contention_logs_and_can_retry(client, monkeypatch, caplog):
    path = client.app.state.data_dir / 'improved.sqlite3'
    original = db.connect

    def short_wait(path):
        con = original(path)
        con.execute('PRAGMA busy_timeout=1')
        return con

    with db.transaction(path):
        with monkeypatch.context() as patch:
            patch.setattr(db, 'connect', short_wait)
            with caplog.at_level(logging.ERROR, logger='booking'):
                response = client.post('/api/improved/webhooks', json=payment())
    assert response.status_code == 503
    assert any(record.name == 'booking' and record.exc_info and
               record.event_id == 'review-payment' for record in caplog.records)
    assert client.get('/api/improved/dashboard').json()['ledger'] == []
    assert client.post('/api/improved/webhooks', json=payment()).status_code == 200


@pytest.mark.parametrize('mutation', ['status', 'outcome', 'severity', 'correlation'])
def test_evaluator_detects_wrong_acknowledgement_and_incident_context(tmp_path, monkeypatch, mutation):
    # Only in-memory wrappers mutate behavior; all databases remain disposable.
    folder = tmp_path / 'fixtures'
    folder.mkdir()
    fixture = folder / 'replays.json'
    fixture.write_bytes(replay.FIXTURE_PATH.read_bytes())
    monkeypatch.setattr(replay, 'FIXTURE_PATH', fixture)
    original = improved.process

    def mutated(path, event):
        result = original(path, event)
        if event.type == 'authorized' and result['outcome'] == 'ignored':
            if mutation == 'status':
                result['http_status'] = 409
            elif mutation == 'outcome':
                result['outcome'] = 'applied'
        if event.type == 'refund_failed':
            with db.transaction(path) as con:
                if mutation == 'severity':
                    con.execute("UPDATE incidents SET severity='info' WHERE code='refund_failed'")
                elif mutation == 'correlation':
                    con.execute("UPDATE incidents SET delivery_id=1 WHERE code='refund_failed'")
        return result

    monkeypatch.setattr(improved, 'process', mutated)
    stats = replay.evaluate(['improved'])['modes']['improved']
    assert stats['failed_assertions'] == 0, 'Legacy 31 checks remain an explicitly separate measure'
    assert stats.get('protocol', {}).get('failed_assertions', 0) > 0


def test_bare_cli_requires_output_and_preserves_historical_diagnosis(tmp_path):
    # Execute an exact package copy so even the old unsafe CLI can only damage
    # the scratch sentinel, never the real historical evidence or shared data.
    root = Path(__file__).resolve().parents[2]
    shutil.copytree(root / 'backend', tmp_path / 'backend', ignore=shutil.ignore_patterns('__pycache__', 'tests'))
    shutil.copytree(root / 'fixtures', tmp_path / 'fixtures')
    historical = tmp_path / 'evidence' / 'diagnosis.json'
    historical.parent.mkdir()
    historical.write_bytes(b'{"historical_baseline":"preserve exactly"}\n')
    before = historical.read_bytes()
    response = subprocess.run([sys.executable, '-m', 'backend.replay'], cwd=tmp_path,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                              capture_output=True, text=True)
    assert response.returncode == 2, response.stdout + response.stderr
    assert '--output' in response.stderr and 'required' in response.stderr
    assert historical.read_bytes() == before
