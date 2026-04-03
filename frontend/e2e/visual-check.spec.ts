import { test, expect } from '@playwright/test';

/**
 * Visual verification screenshots for Tasks page + Replies flow.
 */
test.describe('Visual Verification', () => {
  test.setTimeout(60_000);

  test('Tasks page — all 3 tabs', async ({ page }) => {
    await page.goto('/tasks?project=test_lord_test');
    await page.waitForTimeout(4000);
    await page.screenshot({ path: 'test-results/vis-01-tasks-replies-tab.png', fullPage: true });

    // Use first() to target the pill tab (not the category sub-tab inside ReplyQueue)
    await page.locator('button:has-text("Meetings")').first().click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/vis-02-tasks-meetings-tab.png', fullPage: true });

    await page.locator('button:has-text("Qualified")').first().click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'test-results/vis-03-tasks-qualified-tab.png', fullPage: true });
  });

  test('Replies page — thread expansion + multiple campaigns', async ({ page }) => {
    await page.goto('/replies?project=test_lord_test');

    const cards = page.locator('.rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 20000 });

    if (await emptyState.isVisible()) {
      await page.screenshot({ path: 'test-results/vis-04-replies-empty.png', fullPage: true });
      return;
    }

    await page.screenshot({ path: 'test-results/vis-04-replies-initial.png', fullPage: true });

    // Click "All need reply" to show all categories
    const allTab = page.locator('button:has-text("All need reply")');
    if (await allTab.isVisible({ timeout: 2000 }).catch(() => false)) {
      await allTab.click();
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'test-results/vis-05-replies-all-categories.png', fullPage: true });
    }

    // Expand first card's history
    const firstHistoryBtn = cards.first().locator('button:has-text("History")').first();
    if (await firstHistoryBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await firstHistoryBtn.click();
      await page.waitForTimeout(3000);
      await page.screenshot({ path: 'test-results/vis-06-thread-expanded.png', fullPage: true });
    }
  });

  test('Contact modal — conversation history with campaign selector', async ({ page }) => {
    // Find pn@getsally.io contact
    const searchResp = await page.request.get('/api/contacts?search=pn%40getsally.io&page=1&page_size=1');
    if (!searchResp.ok()) return;
    const data = await searchResp.json();
    const contacts = data.contacts || [];
    if (contacts.length === 0) return;

    const contactId = contacts[0].id;
    await page.goto(`/contacts?contact_id=${contactId}`);

    const modal = page.locator('.rounded-2xl.shadow-2xl');
    await expect(modal).toBeVisible({ timeout: 20000 });
    await page.waitForTimeout(4000);

    await page.screenshot({ path: 'test-results/vis-07-contact-modal.png', fullPage: false });
  });
});
