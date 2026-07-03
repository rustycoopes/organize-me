import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config for the OrganizeMe E2E suite (issue #23).
 *
 * These tests drive the REAL deployed QA Cloud Run app end-to-end - there is no local web
 * server started here. `PLAYWRIGHT_BASE_URL` must point at the QA instance (set in CI after
 * `deploy-qa` succeeds); it falls back to the known QA URL for convenient local runs.
 */
const baseURL =
  process.env.PLAYWRIGHT_BASE_URL ??
  'https://organizeme-qa-170051512639.northamerica-northeast1.run.app';

export default defineConfig({
  testDir: './tests',
  // Unique-per-run emails mean tests never collide, so they can run fully in parallel.
  fullyParallel: true,
  // Fail the CI build if a `test.only` was left in the source.
  forbidOnly: !!process.env.CI,
  // A remote target can have transient blips; one retry in CI keeps flakes from failing the run.
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [['list'], ['html', { open: 'never' }]],
  // Registration + login each do a (deliberately slow) bcrypt hash plus a Supabase round-trip,
  // and several flows chain register -> login -> redirect, so give assertions and whole tests
  // generous ceilings rather than the tight 5s/30s defaults.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL,
    // Capture a trace + screenshot only when a test fails and is retried, to keep artifacts small.
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
