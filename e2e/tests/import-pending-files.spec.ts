import { test, expect } from '@playwright/test';
import { registerNewUser } from '../utils/helpers';

/**
 * Slice 7 (#110) — Import pending files button on /upload and /dashboard.
 *
 * Under E2E_TEST_MODE the storage provider resolves to a fresh in-memory FakeStorageProvider per
 * request (same seam #52/#53 use), so there's no way to make a file genuinely "pending" across
 * requests without a real connected Drive account - that part stays out of e2e, per the standing
 * #23 decision to keep real Google OAuth out of the suite. What *is* deterministic under
 * E2E_TEST_MODE is that the button is enabled (E2E always counts as "storage connected") and the
 * scan always finds nothing, so clicking it reliably surfaces the "no pending files" error -
 * exercising the full fetch -> API -> error-message round trip live.
 */
test.describe('Import pending files', () => {
  test('is enabled and reports no pending files on the Upload page', async ({ page }) => {
    await registerNewUser(page, 'import-pending-upload');
    await page.goto('/upload');

    const button = page.locator('#import-pending-files-btn');
    await expect(button).toBeEnabled();
    await button.click();

    await expect(page.getByText('No pending files found in your storage watch folder.')).toBeVisible();
  });

  // Skipped since Slice R6: /dashboard now routes to Event Creator's own placeholder page (real
  // Dashboard content, including this button, lands in the R9 parity slice - see
  // app/pages/dashboard.py in the event-creator repo). This only started actually failing once
  // e2e's PLAYWRIGHT_BASE_URL was fixed (R7) to go through the shared LB instead of hitting the
  // Host's Cloud Run URL directly, which had been masking the routing change. Re-enable once R9
  // gives event-creator's Dashboard this button - see issue #185.
  test.skip('is enabled and reports no pending files on the Dashboard page', async ({ page }) => {
    await registerNewUser(page, 'import-pending-dashboard');
    await page.goto('/dashboard');

    const button = page.locator('#import-pending-files-btn');
    await expect(button).toBeEnabled();
    await button.click();

    await expect(page.getByText('No pending files found in your storage watch folder.')).toBeVisible();
  });
});
