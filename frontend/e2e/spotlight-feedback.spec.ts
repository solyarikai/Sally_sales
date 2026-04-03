import { test, expect } from '@playwright/test';

/**
 * E2E test for the Spotlight feedback → Learning Logs deep-link flow.
 *
 * Flow: Cmd+K → type feedback → submit → see "View in Learning Logs" link
 *       → click → navigate to /knowledge/logs with logId → log is expanded
 *       → if processing, shows spinner; after completion, shows details.
 */

const BASE_URL = process.env.PW_BASE_URL || 'http://localhost:5179';
const PROJECT_SLUG = 'easystaff-ru';
const PROJECT_NAME = 'easystaff ru';

test.describe('Spotlight Feedback → Learning Logs', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to a page where a project can be selected
    await page.goto(`/knowledge/icp?project=${PROJECT_SLUG}`);
    // Wait for the project name to appear in the header
    await expect(
      page.locator(`text=${PROJECT_NAME}`).first()
        .or(page.locator('text=Select a project'))
    ).toBeVisible({ timeout: 15000 });
  });

  test('Cmd+K opens Spotlight feedback modal', async ({ page }) => {
    // Click on the page body first to ensure focus
    await page.locator('body').click();
    await page.waitForTimeout(200);

    // Trigger Cmd+K
    await page.keyboard.press('Meta+k');

    // Modal should appear with feedback input
    const modal = page.locator('text=Feedback for');
    await expect(modal).toBeVisible({ timeout: 5000 });

    const textarea = page.locator('textarea[placeholder*="Tell the AI"]');
    await expect(textarea).toBeVisible();
    // Focus is set via setTimeout(50), give it time
    await page.waitForTimeout(200);
    await expect(textarea).toBeFocused();
  });

  test('Submit requires minimum 5 characters', async ({ page }) => {
    await page.keyboard.press('Meta+k');

    const textarea = page.locator('textarea[placeholder*="Tell the AI"]');
    await expect(textarea).toBeVisible({ timeout: 5000 });

    // Type less than 5 chars — submit button should be disabled
    await textarea.fill('abc');
    const submitBtn = page.locator('button:has-text("Submit")');
    await expect(submitBtn).toBeDisabled();

    // Type enough chars
    await textarea.fill('Always reply in Russian');
    await expect(submitBtn).toBeEnabled();
  });

  test('Escape closes the modal', async ({ page }) => {
    await page.locator('body').click();
    await page.waitForTimeout(200);

    await page.keyboard.press('Meta+k');
    const modal = page.locator('text=Feedback for');
    await expect(modal).toBeVisible({ timeout: 5000 });

    // Focus the textarea first so Escape is captured by the component
    const textarea = page.locator('textarea[placeholder*="Tell the AI"]');
    await expect(textarea).toBeVisible();
    await textarea.focus();
    await page.keyboard.press('Escape');
    await expect(modal).not.toBeVisible({ timeout: 3000 });
  });

  test('full flow: submit feedback → see success → navigate to learning log', async ({ page }) => {
    // Intercept the feedback API call to mock a response
    await page.route('**/learning/feedback', async (route) => {
      // Return a mock learning log response
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          learning_log_id: 999,
          status: 'processing',
          message: 'Processing feedback...',
        }),
      });
    });

    // Intercept the learning logs list
    await page.route('**/learning/logs?*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 999,
              trigger: 'feedback',
              status: 'processing',
              change_type: null,
              change_summary: null,
              conversations_analyzed: null,
              feedback_text: 'Always reply in Russian and be friendly',
              created_at: new Date().toISOString(),
            },
          ],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      });
    });

    // Intercept log detail
    await page.route('**/learning/logs/999', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 999,
          trigger: 'feedback',
          status: 'processing',
          change_type: null,
          change_summary: null,
          conversations_analyzed: null,
          feedback_text: 'Always reply in Russian and be friendly',
          created_at: new Date().toISOString(),
          before_snapshot: null,
          after_snapshot: null,
          ai_reasoning: null,
          error_message: null,
          template_id: null,
        }),
      });
    });

    // Intercept status polling
    let pollCount = 0;
    await page.route('**/learning/analyze/999/status', async (route) => {
      pollCount++;
      // After 2 polls, return completed
      const isComplete = pollCount >= 2;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 999,
          status: isComplete ? 'completed' : 'processing',
          change_summary: isComplete ? 'Updated reply template to always use Russian' : null,
          conversations_analyzed: isComplete ? 5 : null,
          error_message: null,
        }),
      });
    });

    // Step 1: Open Spotlight and type feedback
    await page.keyboard.press('Meta+k');
    const textarea = page.locator('textarea[placeholder*="Tell the AI"]');
    await expect(textarea).toBeVisible({ timeout: 5000 });
    await textarea.fill('Always reply in Russian and be friendly');

    // Step 2: Submit
    const submitBtn = page.locator('button:has-text("Submit")');
    await submitBtn.click();

    // Step 3: See success state with "View in Learning Logs" link
    const successText = page.locator('text=Feedback submitted');
    await expect(successText).toBeVisible({ timeout: 10000 });

    const processingText = page.locator('text=AI is processing');
    await expect(processingText).toBeVisible();

    const viewLogBtn = page.locator('button:has-text("View in Learning Logs")');
    await expect(viewLogBtn).toBeVisible();

    // Step 4: Click "View in Learning Logs"
    await viewLogBtn.click();

    // Step 5: Should navigate to knowledge/logs page with logId param
    await page.waitForURL(/\/knowledge\/logs.*logId=999/, { timeout: 10000 });

    // Step 6: The log entry should be auto-expanded with feedback content visible
    // Check the feedback text appears in the expanded detail
    const feedbackContent = page.locator('text=Always reply in Russian and be friendly');
    await expect(feedbackContent).toBeVisible({ timeout: 10000 });

    // The "Feedback" trigger label and "processing" badge should be visible
    const feedbackLabel = page.locator('text=Feedback').first();
    await expect(feedbackLabel).toBeVisible();
    const processingBadge = page.locator('text=processing').first();
    await expect(processingBadge).toBeVisible();
  });

  test('feedback modal shows project name', async ({ page }) => {
    await page.keyboard.press('Meta+k');

    const header = page.locator('text=Feedback for');
    await expect(header).toBeVisible({ timeout: 5000 });

    // Should show the project name
    const projectLabel = page.locator(`text=Feedback for ${PROJECT_NAME}`);
    await expect(projectLabel).toBeVisible();
  });
});
