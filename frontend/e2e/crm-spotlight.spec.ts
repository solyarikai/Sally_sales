import { test, expect } from '@playwright/test';

test.describe('CRM Spotlight', () => {
  test('Spotlight button appears when project is selected on CRM page', async ({ page }) => {
    // Navigate to CRM page
    await page.goto('/contacts');
    // Wait for grid to render (don't use networkidle — it never settles due to polling)
    await page.waitForSelector('.ag-body-viewport', { timeout: 15000 });
    await page.waitForTimeout(1000);

    // Select a project from the navbar dropdown
    const projectSelector = page.locator('button:has(svg.lucide-folder-open)').first();
    await projectSelector.click();
    await page.waitForTimeout(500);

    // Pick any project (not "All Projects")
    const projectButtons = page.locator('.max-h-60 button');
    const count = await projectButtons.count();
    if (count > 1) {
      await projectButtons.nth(1).click(); // first real project
    }
    await page.waitForTimeout(2000);

    // Take screenshot before checking
    await page.screenshot({ path: 'screenshot_crm_spotlight_project_selected.png', fullPage: true });

    // Now verify the Spotlight button is visible
    const spotlightBtn = page.locator('button[title*="CRM Spotlight"]');
    await expect(spotlightBtn).toBeVisible({ timeout: 5000 });

    // Click the button to open the modal
    await spotlightBtn.click();
    await page.waitForTimeout(500);

    // Take screenshot of the modal
    await page.screenshot({ path: 'screenshot_crm_spotlight_modal.png', fullPage: true });

    // Verify the modal opened
    const modalTitle = page.locator('text=CRM Spotlight');
    await expect(modalTitle).toBeVisible({ timeout: 3000 });

    // Verify the textarea is present
    const textarea = page.locator('textarea[placeholder*="Ask about these contacts"]');
    await expect(textarea).toBeVisible();

    // Verify the context badge shows warm replies info
    const contextBadge = page.locator('text=warm replies');
    await expect(contextBadge).toBeVisible();

    // Close with Escape
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    await expect(modalTitle).not.toBeVisible();
  });

  test('Cmd+K opens CRM Spotlight when project is selected', async ({ page }) => {
    await page.goto('/contacts');
    await page.waitForSelector('.ag-body-viewport', { timeout: 15000 });
    await page.waitForTimeout(1000);

    // Select a project
    const projectSelector = page.locator('button:has(svg.lucide-folder-open)').first();
    await projectSelector.click();
    await page.waitForTimeout(500);
    const projectButtons = page.locator('.max-h-60 button');
    const count = await projectButtons.count();
    if (count > 1) {
      await projectButtons.nth(1).click();
    }
    await page.waitForTimeout(2000);

    // Press Cmd+K
    await page.keyboard.press('Meta+k');
    await page.waitForTimeout(500);

    // Take screenshot
    await page.screenshot({ path: 'screenshot_crm_spotlight_cmdk.png', fullPage: true });

    // Verify CRM Spotlight opened (not the default SpotlightFeedback)
    const crmTitle = page.locator('text=CRM Spotlight');
    await expect(crmTitle).toBeVisible({ timeout: 3000 });
  });
});
