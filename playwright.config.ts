import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';
const chrome = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
export default defineConfig({
  testDir: './tests/browser', timeout: 35000, fullyParallel: false, workers: 1,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173', viewport: { width: 1440, height: 1050 },
    launchOptions: existsSync(chrome) ? { executablePath: chrome } : {},
    screenshot: 'only-on-failure', trace: 'retain-on-failure',
  },
});
