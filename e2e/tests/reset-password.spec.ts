import { test, expect } from '@playwright/test';
import { fetchResetToken, login, logout, registerNewUser } from '../utils/helpers';

test.describe('Forgot / reset password', () => {
  test('a user can reset their password and log in with the new one', async ({ page, request }) => {
    const { email } = await registerNewUser(page, 'reset');
    const newPassword = 'brand-new-password-123';

    // Log out so the flow starts unauthenticated, like a real user who forgot their password.
    await logout(page);

    // Request the reset email via the real forgot-password form.
    await page.goto('/forgot-password');
    await page.locator('#email').fill(email);
    await page.locator('form button[type="submit"]').click();

    // Instead of reading an inbox, pull the freshly-issued token from the test-only endpoint,
    // then drive the real reset-password page with it.
    const token = await fetchResetToken(request, email);
    await page.goto(`/reset-password?token=${encodeURIComponent(token)}`);
    await page.locator('#password').fill(newPassword);
    await page.locator('#confirm_password').fill(newPassword);
    await page.locator('form button[type="submit"]').click();

    // The reset endpoint confirms success in its response body.
    await expect(page.getByText(/password has been reset/i)).toBeVisible();

    // The new password now works end-to-end.
    await login(page, email, newPassword);
    await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
  });
});
