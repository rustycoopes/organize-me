import { test, expect } from '@playwright/test';
import { registerNewUser } from '../utils/helpers';

/**
 * Slice R11 (#166) — the Upload page had no dedicated e2e coverage of its own (only as a means to
 * an end inside processing.spec.ts, which drives it purely to get a run started). Added while
 * closing the R11 verification gap for PRD stories 24-25. Deliberately doesn't re-assert the
 * upload -> successful-pipeline-run happy path end to end (a full SSE wait to a terminal state) -
 * that's processing.spec.ts's job; this file covers what's unique to the Upload page itself: the
 * ephemeral-storage warning and client-rejected-file feedback.
 */
test.describe('Upload page', () => {
  test('warns that storage is not connected and uploads still proceed (ephemeral fallback)', async ({
    page,
  }) => {
    await registerNewUser(page, 'upload-ephemeral');
    await page.goto('/upload');

    await expect(page.getByText('No storage provider is connected.')).toBeVisible();

    // The dropzone/file-input stay enabled regardless (issue #79's ephemeral fallback) - proven
    // by immediately being routed to the progress page after picking a file.
    await page.locator('#file-input').setInputFiles({
      name: 'ephemeral-chat.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('E2E upload ephemeral-fallback test.\n'),
    });
    await expect(page).toHaveURL(/\/processing\?run=/, { timeout: 30_000 });
  });

  test('rejects an unsupported file type with an inline error, without leaving the page', async ({
    page,
  }) => {
    await registerNewUser(page, 'upload-unsupported');
    await page.goto('/upload');

    // The picker's `accept` attribute only narrows the OS file dialog - setInputFiles bypasses
    // it, exercising the server-side extension check (app.api.v1.upload) the same way a drag-
    // and-dropped file with the wrong extension would.
    await page.locator('#file-input').setInputFiles({
      name: 'not-a-conversation.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 fake pdf content'),
    });

    await expect(page.getByText('Please upload a .txt, .zip, or .csv file.')).toBeVisible();
    await expect(page).toHaveURL(/\/upload$/);
  });

  test('rejects an empty file with an inline error', async ({ page }) => {
    await registerNewUser(page, 'upload-empty');
    await page.goto('/upload');

    await page.locator('#file-input').setInputFiles({
      name: 'empty.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from(''),
    });

    await expect(page.getByText('That file is empty.')).toBeVisible();
    await expect(page).toHaveURL(/\/upload$/);
  });
});
