import { test, expect } from '@playwright/test';
import { login, logout, registerNewUser, TEST_PASSWORD } from '../utils/helpers';

test.describe('Register / login / logout', () => {
  test('a new user can register, log out and log back in', async ({ page }) => {
    const { email } = await registerNewUser(page, 'auth');

    // Registration auto-logs-in and lands on /profile; the profile page proves the session.
    await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();

    // Log out via the sidebar button -> back to /login, and the profile is no longer reachable.
    await logout(page);
    await page.goto('/profile');
    await expect(page).toHaveURL(/\/login$/);

    // Log back in with the same credentials.
    await login(page, email, TEST_PASSWORD);
    await expect(page.getByRole('heading', { name: 'Your profile' })).toBeVisible();
  });

  test('logging in with a wrong password shows an error and stays on /login', async ({ page }) => {
    const { email } = await registerNewUser(page, 'auth-badpw');
    await logout(page);

    await page.goto('/login');
    await page.locator('#email').fill(email);
    await page.locator('#password').fill('definitely-the-wrong-password');
    await page.locator('form button[type="submit"]').click();

    await expect(page.getByText('Incorrect email or password.')).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });
});
