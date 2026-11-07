# Baseline gate execution

Executed on Windows, Python 3.13.14 / Node 24.22.0. Ubuntu/WSL commands are in the baseline doc.

- `python -m pytest -q`: **2 passed**, one upstream Starlette/AnyIO deprecation warning.
- `npm run build`: TypeScript and Vite production build passed.
- `PLAYWRIGHT_CHANNEL=chrome npm run test:ui`: **1 passed**, screenshot `baseline-ui.png`.
- Initial `npm install` identified an advisory in Vite 7.2.2; updated to 7.3.7. Subsequent install audit: **0 vulnerabilities**.
- Managed Chromium installation was attempted but failed with `ENOSPC` on the host C: drive. The smoke test used installed Chrome successfully. No browser dependency is needed by the runtime product.
- First Playwright invocation exposed Windows shell handling of a relative Python path; corrected to a quoted absolute path and reran successfully.

The baseline screenshot shows a real simulated payment applied to a seeded reservation. It is not a rendering with hard-coded dashboard totals.
