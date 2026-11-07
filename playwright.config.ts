import { defineConfig } from '@playwright/test'
import { resolve } from 'node:path'

const python = resolve(process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python')
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  use: { baseURL: 'http://127.0.0.1:5175', trace: 'retain-on-failure',
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined },
  webServer: [
    { command: `"${python}" -m backend.ui_server`, url: 'http://127.0.0.1:8003/api/health', reuseExistingServer: false },
    { command: 'npm run dev', url: 'http://127.0.0.1:5175', reuseExistingServer: false },
  ],
})
