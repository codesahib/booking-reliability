"""Deterministic local reset. Run only with the demo server stopped."""
import argparse
from pathlib import Path

from .db import initialize
from .main import DEFAULT_DATA


def reset(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    for mode in ['baseline']:
        target = root / f'{mode}.sqlite3'
        for suffix in ['', '-wal', '-shm']:
            target.with_name(target.name + suffix).unlink(missing_ok=True)
        (root / 'logs' / f'{mode}.jsonl').unlink(missing_ok=True)
        initialize(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    reset(args.data_dir)
    print(f'Deterministic synthetic demo reset: {args.data_dir}')
