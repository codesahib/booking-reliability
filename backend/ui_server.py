"""Dedicated Playwright server with a disposable, isolated synthetic database."""
from pathlib import Path

import uvicorn

from .seed import reset
from .main import create_app

root = Path(__file__).resolve().parents[1] / 'data' / 'ui-smoke'
reset(root)
uvicorn.run(create_app(root), host='127.0.0.1', port=8003)
