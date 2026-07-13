import { test, expect } from '@playwright/test';
import { registerNewUser, logout } from '../utils/helpers';
import { tamperedToken } from '../utils/jwt';

const AUTH_COOKIE_NAME = 'organizeme_auth';

/**
 * Slice R10 (#165): the P0 evidence gate proving the Host<->Event Creator split introduced no
 * regressions in the seams it created - single sign-on, logout propagation, and the JWT trust
 * boundary. Runs through the real shared Load Balancer domain (playwright.config.ts's baseURL),
 * driving `/dashboard` - Event Creator's own route since the R6 tracer bullet - not a mocked
 * service.
 *
 * Two of the four "trust boundary"/SSO acceptance criteria are already asserted elsewhere and
 * aren't repeated here:
 * - Login-once SSO (a Host session is honoured by Event Creator with no second login):
 *   sidebar.spec.ts's first test already proves this by clicking through to `/dashboard` right
 *   after `registerNewUser` and asserting it renders instead of bouncing to `/login`.
 * - No-cookie rejection: sidebar.spec.ts's second test already asserts a fresh (unauthenticated)
 *   context hitting `/dashboard` redirects to `/login`.
 *
 * This file adds the two trust-boundary cases those don't cover (a malformed cookie value, and a
 * well-formed-but-wrongly-signed token) plus logout propagation, which no existing spec asserts
 * against an Event-Creator-owned route.
 *
 * The remaining acceptance criteria are covered outside this file entirely:
 * - "A Host Profile field reaches an Event-Creator-owned dependency": notifications.spec.ts's
 *   SMS-toggle test - the phone number is a Host Profile field, and the Notifications tab it
 *   gates has been Event-Creator-owned content since Slice R7.
 * - "Account deletion at the Host removes the user's Event Creator data": account-deletion.spec.ts
 *   covers the Host-side session invalidation; the Event-Creator-side half (deleting a Host user
 *   cascades to event_creator's own tables) is a DB-level guarantee that isn't observable over
 *   HTTP through Event Creator's stateless JWT trust (it never queries the Host's `users` table -
 *   see app.core.auth.current_user_id_optional in the event-creator repo), so it's asserted
 *   directly against the schema in that repo's own test suite (test_user_settings_model.py,
 *   test_storage_config_model.py, test_llm_prompt_model.py, test_event_model.py).
 */
test.describe('Host<->Event Creator boundary', () => {
  test('logging out at the Host ends the Event Creator session too', async ({ page }) => {
    await registerNewUser(page, 'boundary-logout');
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    await logout(page);

    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login$/);
  });

  test('Event Creator redirects to Host login for a garbage cookie value', async ({
    page,
    baseURL,
  }) => {
    await page.goto('/');
    const domain = new URL(baseURL ?? page.url()).hostname;
    await page.context().addCookies([
      { name: AUTH_COOKIE_NAME, value: 'not-a-jwt', domain, path: '/' },
    ]);

    await page.goto('/dashboard');

    await expect(page).toHaveURL(/\/login$/);
  });

  test('Event Creator redirects to Host login for a tampered-signature token', async ({
    page,
    baseURL,
  }) => {
    await page.goto('/');
    const domain = new URL(baseURL ?? page.url()).hostname;
    await page.context().addCookies([
      { name: AUTH_COOKIE_NAME, value: tamperedToken(), domain, path: '/' },
    ]);

    await page.goto('/dashboard');

    await expect(page).toHaveURL(/\/login$/);
  });
});
