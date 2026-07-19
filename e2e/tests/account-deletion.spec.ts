import { test, expect } from '@playwright/test';
import { registerNewUser } from '../utils/helpers';

test.describe('Account deletion', () => {
  test('deleting the account logs the user out and invalidates the session', async ({ page }) => {
    await registerNewUser(page, 'delete');

    // Capture the live auth cookie BEFORE deletion so we can prove the token itself stops
    // authenticating afterwards - not merely that the browser dropped its copy.
    const authCookie = (await page.context().cookies()).find((c) => c.name === 'organizeme_auth');
    expect(authCookie?.value, 'expected an auth cookie after registration').toBeTruthy();

    // Open the confirmation modal (an HTML <dialog>, not a blocking browser confirm) and confirm.
    // "Delete account" is plain-text; the confirm button wraps its label in x-show spans, so
    // target it by id within the dialog.
    await page.getByRole('button', { name: 'Delete account' }).click();
    await page.locator('#confirm-delete-account-button').click();

    // Deletion redirects to /login...
    await expect(page).toHaveURL(/\/login$/);

    // ...a protected page bounces back to /login (the browser's cookie was cleared)...
    await page.goto('/profile');
    await expect(page).toHaveURL(/\/login$/);

    // ...and even replaying the exact pre-deletion cookie no longer authenticates against the
    // API, since the user it referenced is gone (matches the acceptance criterion precisely).
    const meResponse = await page.request.get('/api/v1/users/me', {
      headers: { Cookie: `organizeme_auth=${authCookie!.value}` },
    });
    expect(meResponse.status()).toBe(401);
  });
});
