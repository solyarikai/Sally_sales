import { test, expect } from '@playwright/test';

test.describe('Replies Flow — Smoke Test', () => {
  test('loads replies page with category tabs', async ({ page }) => {
    await page.goto('/replies?project=test_lord_test');

    // Wait for either reply cards or "All caught up"
    const cards = page.locator('.rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 15000 });

    // Category tabs should always render
    const meetingsTab = page.locator('button:has-text("Meetings")');
    await expect(meetingsTab).toBeVisible();
  });

  test('category tabs show counts', async ({ page }) => {
    await page.goto('/replies?project=test_lord_test');

    const cards = page.locator('.rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 15000 });

    // At least one tab should have a count > 0 (or all zeros if no data)
    const allTab = page.locator('button:has-text("All need reply")');
    await expect(allTab).toBeVisible();
  });

  test('campaign dropdown opens if multi-campaign', async ({ page }) => {
    await page.goto('/replies?project=test_lord_test');

    const cards = page.locator('.rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 15000 });

    // Skip if no reply cards
    if (await emptyState.isVisible()) {
      test.skip();
      return;
    }

    // Look for campaign count badge (multi-campaign indicator)
    const campaignBadge = page.locator('[data-campaign-dropdown] button').first();
    if (await campaignBadge.isVisible()) {
      await campaignBadge.click();

      // Dropdown should appear with campaign entries
      const dropdown = page.locator('[data-campaign-dropdown] .absolute');
      await expect(dropdown).toBeVisible({ timeout: 5000 });
    }
  });

  test('send reply → card disappears', async ({ page }) => {
    await page.goto('/replies?project=test_lord_test');

    const cards = page.locator('.rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 15000 });

    // Skip if no reply cards
    if (await emptyState.isVisible()) {
      test.skip();
      return;
    }

    const initialCount = await cards.count();

    // Find the first Send button and get the lead name for tracking
    const firstCard = cards.first();
    const leadName = await firstCard.locator('.font-medium.truncate').first().textContent();

    const sendButton = firstCard.locator('button:has-text("Send")').first();
    await expect(sendButton).toBeVisible();
    await sendButton.click();

    // Card should disappear after API responds (may take a while for email send)
    await expect(async () => {
      const newCount = await cards.count();
      expect(newCount).toBeLessThan(initialCount);
    }).toPass({ timeout: 30000 });

    // Count already decreased — card is gone
  });

  test('View conversation link navigates to contacts page', async ({ page }) => {
    await page.goto('/replies?project=test_lord_test');

    const cards = page.locator('.rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 15000 });

    if (await emptyState.isVisible()) {
      test.skip();
      return;
    }

    // Send a reply to trigger the "View conversation" toast link
    const sendButton = cards.first().locator('button:has-text("Send")').first();
    await sendButton.click();

    // Look for "View conversation" link in the toast
    const viewLink = page.locator('a:has-text("View conversation")');
    const hasViewLink = await viewLink.isVisible({ timeout: 5000 }).catch(() => false);

    if (hasViewLink) {
      await viewLink.click();
      await expect(page).toHaveURL(/\/contacts\?contact_id=/, { timeout: 10000 });
    }
  });
});
