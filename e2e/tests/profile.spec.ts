import { test, expect } from '@playwright/test';
import { registerNewUser } from '../utils/helpers';

test.describe('Profile', () => {
  test('editing name and phone persists across a reload', async ({ page }) => {
    await registerNewUser(page, 'profile');

    const name = 'Ada Lovelace';
    const phone = '+15551234567';
    await page.locator('#name').fill(name);
    await page.locator('#phone_number').fill(phone);
    await page.locator('form button[type="submit"]').click();
    await expect(page.getByText('Changes saved.')).toBeVisible();

    // Reload from the server to prove the values were persisted, not just held in client state.
    await page.reload();
    await expect(page.locator('#name')).toHaveValue(name);
    await expect(page.locator('#phone_number')).toHaveValue(phone);
  });

  test('dark-mode toggle persists server-side across a reload', async ({ page }) => {
    await registerNewUser(page, 'profile-dark');

    // A brand-new account defaults to light mode - no "dark" class on <html>.
    await expect(page.locator('html')).toHaveClass('');

    // Toggling fires a PATCH to /users/me; wait for it so the reload reflects saved state.
    const darkToggle = page.locator('input.toggle[type="checkbox"]');
    const savePatch = page.waitForResponse(
      (r) => r.url().includes('/api/v1/users/me') && r.request().method() === 'PATCH',
    );
    await darkToggle.check();
    await savePatch;

    // On reload the server renders class="dark" from the persisted dark_mode flag.
    await page.reload();
    await expect(page.locator('html')).toHaveClass('dark');
    await expect(page.locator('input.toggle[type="checkbox"]')).toBeChecked();
  });
});
