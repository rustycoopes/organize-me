import { test, expect } from '@playwright/test';

test.describe('Landing page', () => {
  test('loads and shows hero, features and CTA sections', async ({ page }) => {
    await page.goto('/');

    await expect(page).toHaveTitle(/OrganizeMe/);
    await expect(page.locator('#hero')).toBeVisible();
    await expect(page.locator('#features')).toBeVisible();
    await expect(page.locator('#cta')).toBeVisible();

    // Primary hero CTA and the top-nav sign-up both route into registration.
    await expect(page.locator('#hero').getByRole('link', { name: /get started/i })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Sign up' })).toHaveAttribute('href', '/register');
    await expect(page.getByRole('link', { name: 'Log in' }).first()).toHaveAttribute(
      'href',
      '/login',
    );
  });

  test('serves the compiled stylesheet and no longer references the Tailwind CDN or DaisyUI', async ({
    page,
    request,
  }) => {
    await page.goto('/');

    const html = await page.content();
    expect(html).not.toContain('cdn.tailwindcss.com');
    expect(html.toLowerCase()).not.toContain('daisyui');

    const cssResponse = await request.get('/static/css/app.css');
    expect(cssResponse.status()).toBe(200);
  });
});
