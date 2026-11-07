import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8003' },
    // SQLite, Python dependencies and evidence are not frontend source. Avoid
    // watching generated/locked files while running backend checks on Windows.
    watch: { ignored: ['**/.venv/**', '**/data/**', '**/backend/**', '**/evidence/**',
      '**/docs/**', '**/portfolio/**', '**/requirements*.txt', '**/test-results/**', '**/playwright-report/**'] },
  },
})
