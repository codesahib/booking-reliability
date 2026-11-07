"""Dedicated Playwright server with a disposable, isolated synthetic database."""
import os
from pathlib import Path

import uvicorn

from .seed import reset

root = Path(__file__).resolve().parents[1] / 'data' / 'ui-smoke'
reset(root)
os.environ['BOOKING_DATA_DIR'] = str(root)
uvicorn.run('backend.main:app', host='127.0.0.1', port=8003)
