"""Run release checks sequentially and preserve their actual outputs and exits."""
import argparse
import json
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Vite emits Unicode progress glyphs; Windows pipes can default to cp1252.
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser()
    parser.add_argument('--ui', action='store_true', help='Also launch the Playwright browser smoke suite')
    args = parser.parse_args()
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if not npm:
        raise SystemExit('npm is required; install Node and run from the activated Python virtualenv')
    checks = [
        ('backend-tests', [sys.executable, '-m', 'pytest', '-q']),
        ('frontend-typecheck', [npm, 'run', 'typecheck']),
        ('frontend-build', [npm, 'run', 'build']),
        ('replay-comparison', [sys.executable, '-m', 'backend.replay', '--modes', 'baseline', 'improved', '--output', 'evidence/comparison.json']),
        ('python-dependencies', [sys.executable, '-m', 'pip', 'check']),
        ('npm-audit', [npm, 'audit', '--audit-level=high']),
    ]
    if args.ui:
        checks.append(('ui-smoke', [npm, 'run', 'test:ui']))
    evidence = ROOT / 'evidence'
    evidence.mkdir(exist_ok=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    report = {'executed_at_utc': datetime.now(timezone.utc).isoformat(),
              'runtime_source_commit': commit, 'platform': platform.platform(),
              'python_version': platform.python_version(),
              'node_version': subprocess.check_output(['node', '--version'], text=True).strip(),
              'browser_channel': os.environ.get('PLAYWRIGHT_CHANNEL', 'managed chromium'),
              'checks': []}
    failed = False
    for name, command in checks:
        print(f'Running {name}', flush=True)
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        output = (result.stdout + result.stderr).replace(str(ROOT), '<repo>')
        (evidence / f'{name}.txt').write_text(output, encoding='utf-8')
        display = [('python' if part == sys.executable else 'npm' if part == npm else part) for part in command]
        report['checks'].append({'name': name, 'command': display, 'exit_code': result.returncode,
                                 'output': f'evidence/{name}.txt'})
        print(output, end='')
        failed |= result.returncode != 0
    (evidence / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
