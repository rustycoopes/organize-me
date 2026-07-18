import { test, expect } from '@playwright/test';
import { registerNewUser } from '../utils/helpers';

// Documented sidebar order from packages/chrome (organizeme_chrome.registry).
const EXPECTED_NAV = [
  'Dashboard',
  'Upload',
  'Processing',
  'Logs',
  'Prompt',
  'Doc Library',
  'Settings',
  'Profile',
];

test.describe('Sidebar navigation', () => {
  test('sidebar shows all nav items in order and links work across authenticated routes', async ({
    page,
  }) => {
    await registerNewUser(page, 'sidebar');

    const navLinks = page.locator('#sidebar-nav a');
    await expect(navLinks).toHaveText(EXPECTED_NAV);

    // Navigate to two different authenticated routes via the sidebar and confirm they render
    // (rather than bouncing to /login).
    await page.locator('#sidebar-nav').getByRole('link', { name: 'Dashboard' }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();

    await page.locator('#sidebar-nav').getByRole('link', { name: 'Settings' }).click();
    await expect(page).toHaveURL(/\/settings$/);
    await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
  });

  test('sidebar and shell markup carry no leftover DaisyUI classes (design-refresh)', async ({
    page,
  }) => {
    await registerNewUser(page, 'sidebar-design');

    // design-refresh Slice 2 restyled the shell onto plain Tailwind + design tokens; DaisyUI's
    // component classes must be completely gone from the rendered page, not just re-themed.
    const daisyUiSelector = [
      '.drawer',
      '.drawer-toggle',
      '.drawer-content',
      '.drawer-side',
      '.drawer-overlay',
      '.menu',
      '.btn',
      '.navbar',
      '.tabs',
      '.tab',
    ].join(', ');

    await expect(page.locator(daisyUiSelector)).toHaveCount(0);
  });

  test('hitting an authenticated route while logged out redirects to /login', async ({ page }) => {
    // Fresh browser context (test isolation) => no auth cookie.
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login$/);
  });
});
