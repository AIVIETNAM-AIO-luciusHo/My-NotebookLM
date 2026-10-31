/* global process */
import { defineConfig } from '@playwright/test';

const API_PORT = 8765;
const WEB_PORT = 5199;

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  use: { baseURL: `http://127.0.0.1:${WEB_PORT}`, browserName: 'chromium' },
  webServer: [
    { command: 'node e2e/fake-backend.mjs', url: `http://127.0.0.1:${API_PORT}/health`, reuseExistingServer: !process.env.CI },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort --host 127.0.0.1`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { VITE_BACKEND: `http://127.0.0.1:${API_PORT}` },
      reuseExistingServer: false,
    },
  ],
});
