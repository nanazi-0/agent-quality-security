import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: '*.spec.ts',
  retries: process.env.CI ? 1 : 0,
  reporter: [
    ['html', { outputFolder: '../reports/playwright/html', open: 'never' }],
    ['json', { outputFile: '../reports/playwright/results.json' }],
    ['list'],
  ],
  use: {
    baseURL: process.env.WEB_BASE_URL ?? 'http://127.0.0.1:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
