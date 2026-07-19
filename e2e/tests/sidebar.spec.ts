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

    // design-refresh Slice 2 restyled only the chrome shell (sidebar/header/tab-bar) onto plain
    // Tailwind + design tokens - page *content* was a later slice's concern (now also migrated,
    // see Slice 4), so this check is scoped to the shell elements this slice actually touched,
    // not the whole page.
    const daisyUiTokens = [
      'drawer',
      'drawer-toggle',
      'drawer-content',
      'drawer-side',
      'drawer-overlay',
      'menu',
      'btn',
      'navbar',
      'tabs',
      'tab',
    ];

    const shellClassLists = await page
      .locator('aside, label[for="sidebar-drawer-toggle"], [role="tablist"], #sidebar-nav *')
      .evaluateAll((elements) => elements.map((el) => el.className));

    for (const classList of shellClassLists) {
      const classes = String(classList).split(/\s+/);
      for (const token of daisyUiTokens) {
        expect(classes).not.toContain(token);
      }
    }
  });

  test('mobile drawer opens via the hamburger and closes via the overlay (design-refresh)', async ({
    page,
  }) => {
    // design-refresh Slice 2 replaced DaisyUI's `.drawer` component (which handled mobile
    // open/close purely in CSS) with a hand-rolled `peer`/`peer-checked:` pattern - this is the
    // one behavior actually re-implemented from scratch, not just re-themed, so it needs its own
    // functional coverage rather than relying on the no-DaisyUI-classes smoke test above.
    await page.setViewportSize({ width: 500, height: 800 });
    await registerNewUser(page, 'sidebar-drawer');

    const sidebar = page.locator('aside');
    const toggle = page.locator('#sidebar-drawer-toggle');

    await expect(toggle).not.toBeChecked();
    await expect(sidebar).not.toBeInViewport();

    await page.getByLabel('Open navigation').click();
    await expect(toggle).toBeChecked();
    await expect(sidebar).toBeInViewport();

    await page.getByLabel('Close navigation').click();
    await expect(toggle).not.toBeChecked();
    await expect(sidebar).not.toBeInViewport();
  });

  test('hitting an authenticated route while logged out redirects to /login', async ({ page }) => {
    // Fresh browser context (test isolation) => no auth cookie.
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/login$/);
  });
});
