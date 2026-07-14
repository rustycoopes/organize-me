import { expect, type Page, type APIRequestContext } from '@playwright/test';

/** Password used for every generated test account. Meets the app's 8-char minimum. */
export const TEST_PASSWORD = 'correct-horse-battery';

/**
 * A fresh, globally-unique email per call so parallel tests and repeated CI runs never collide
 * on the shared QA database. Combines a timestamp with random hex.
 */
export function uniqueEmail(prefix = 'e2e'): string {
  const rand = Math.random().toString(16).slice(2, 10);
  return `${prefix}-${Date.now()}-${rand}@example.com`;
}

/**
 * Register a brand-new account through the real /register UI. The register page auto-logs-in
 * on success and redirects to /profile, so on return the page is authenticated and sitting on
 * the profile page. Returns the credentials for later re-login.
 */
export async function registerNewUser(
  page: Page,
  prefix = 'e2e',
): Promise<{ email: string; password: string }> {
  const email = uniqueEmail(prefix);
  await page.goto('/register');
  await page.locator('#email').fill(email);
  await page.locator('#password').fill(TEST_PASSWORD);
  // The submit buttons wrap their label in Alpine x-show/x-cloak spans, which leaves them with
  // no stable accessible name, so target them by type rather than by name throughout the suite.
  await page.locator('form button[type="submit"]').click();
  // Register does register -> auto-login -> redirect: two chained auth round-trips, so allow
  // extra time beyond the default expect ceiling.
  await expect(page).toHaveURL(/\/profile$/, { timeout: 30_000 });
  return { email, password: TEST_PASSWORD };
}

/** Log in through the real /login UI and assert the redirect to /profile. */
export async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login');
  await page.locator('#email').fill(email);
  await page.locator('#password').fill(password);
  await page.locator('form button[type="submit"]').click();
  await expect(page).toHaveURL(/\/profile$/, { timeout: 30_000 });
}

/** Log out via the sidebar (the only button in the authenticated <aside>). */
export async function logout(page: Page): Promise<void> {
  await page.locator('aside button').click();
  await expect(page).toHaveURL(/\/login$/);
}

/**
 * Upload a file through the real Upload page and wait for the redirect to the live progress page.
 * Doesn't wait for a terminal state - callers that need to assert on the run's outcome should use
 * `uploadFileAndWaitForCompletion` below, or (like processing.spec.ts) interleave their own
 * mid-flight assertions between this and a terminal-state wait.
 */
export async function uploadFile(page: Page, filename: string, content: string): Promise<void> {
  await page.goto('/upload');
  await page.locator('#file-input').setInputFiles({
    name: filename,
    mimeType: 'text/plain',
    buffer: Buffer.from(content),
  });
  await expect(page).toHaveURL(/\/processing\?run=/, { timeout: 30_000 });
}

/**
 * Upload a file and wait for the pipeline to reach a successful terminal state, via the upload ->
 * /processing?run= -> SSE-success pattern proven by processing.spec.ts. E2E_TEST_MODE's fake
 * Gemini client deterministically extracts 2 events for any input, so every run started this way
 * succeeds.
 */
export async function uploadFileAndWaitForCompletion(
  page: Page,
  filename: string,
  content: string,
): Promise<void> {
  await uploadFile(page, filename, content);
  await expect(page.locator('[data-run-status="success"]')).toBeVisible({ timeout: 45_000 });
}

/**
 * Fetch a currently-valid password-reset token for an email via the test-only backend endpoint
 * (gated behind E2E_TEST_MODE on QA). Replaces reading a real inbox.
 */
export async function fetchResetToken(
  request: APIRequestContext,
  email: string,
): Promise<string> {
  const response = await request.get('/api/v1/internal/e2e/last-reset-token', {
    params: { email },
  });
  expect(
    response.ok(),
    `last-reset-token returned ${response.status()} - is E2E_TEST_MODE=true on QA?`,
  ).toBeTruthy();
  const body = (await response.json()) as { token: string };
  expect(body.token).toBeTruthy();
  return body.token;
}
