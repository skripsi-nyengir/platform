/// <reference types="node" />

import { defineConfig, devices } from '@playwright/test'
import { env } from 'node:process'

export type DesktopProject = 'desktop-1280' | 'desktop-1440' | 'desktop-1920'

const baseURL = 'http://127.0.0.1:5173'

export default defineConfig({
  testDir: './tests/e2e',
  snapshotPathTemplate: '{testDir}/{testFilePath}-snapshots/{arg}{ext}',
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.01,
    },
  },
  use: {
    baseURL,
  },
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1',
    url: baseURL,
    reuseExistingServer: !env.CI,
  },
  projects: ([1280, 1440, 1920] as const).map((width) => ({
    name: `desktop-${width}` satisfies DesktopProject,
    testMatch: width === 1440 ? undefined : /layout\.spec\.ts/,
    use: {
      ...devices['Desktop Chrome'],
      viewport: { width, height: 900 },
    },
  })),
})
