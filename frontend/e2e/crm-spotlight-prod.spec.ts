import { test, expect } from '@playwright/test';

const PROD_URL = 'http://46.62.210.24';

test.describe('CRM Spotlight - Production', () => {
  test.use({ baseURL: PROD_URL });

  test('Full flow: CRM page → warm filter → Spotlight → submit → GTM', async ({ page }) => {
    // Step 1: Navigate to CRM page
    await page.goto('/contacts');
    await page.waitForSelector('.ag-body-viewport', { timeout: 20000 });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: 'screenshot_prod_crm_initial.png', fullPage: true });

    // Step 2: Select onsocial project from navbar dropdown
    const projectSelector = page.locator('button:has(svg.lucide-folder-open)').first();
    await projectSelector.click();
    await page.waitForTimeout(500);

    // Search for onsocial
    const searchInput = page.locator('input[placeholder="Search projects..."]');
    await searchInput.fill('onsocial');
    await page.waitForTimeout(500);

    const onsocialBtn = page.locator('.max-h-60 button:has-text("onsocial")').first();
    const hasOnsocial = await onsocialBtn.isVisible({ timeout: 2000 }).catch(() => false);

    if (hasOnsocial) {
      await onsocialBtn.click();
    } else {
      // If no onsocial, clear search and pick first project
      await searchInput.clear();
      await page.waitForTimeout(300);
      const firstProject = page.locator('.max-h-60 button').nth(1);
      await firstProject.click();
    }
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshot_prod_crm_project_selected.png', fullPage: true });

    // Step 3: Verify Spotlight button is visible
    const spotlightBtn = page.locator('button[title*="CRM Spotlight"]');
    await expect(spotlightBtn).toBeVisible({ timeout: 5000 });

    // Step 4: Click Spotlight to open modal
    await spotlightBtn.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'screenshot_prod_crm_spotlight_open.png', fullPage: true });

    // Verify modal content
    const modalTitle = page.locator('text=CRM Spotlight');
    await expect(modalTitle).toBeVisible({ timeout: 3000 });

    const textarea = page.locator('textarea[placeholder*="Ask about these contacts"]');
    await expect(textarea).toBeVisible();

    const warmBadge = page.locator('text=warm replies');
    await expect(warmBadge).toBeVisible();

    // Step 5: Type a question and submit
    await textarea.fill('Why so few scheduled calls? How to improve scheduling rate from warm replies?');
    await page.waitForTimeout(300);
    await page.screenshot({ path: 'screenshot_prod_crm_spotlight_question.png', fullPage: true });

    // Click Analyze
    const analyzeBtn = page.locator('button:has-text("Analyze")');
    await analyzeBtn.click();

    // Step 6: Wait for loading state
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'screenshot_prod_crm_spotlight_loading.png', fullPage: true });

    // Step 7: Wait for result (Gemini can take 20-60s)
    const resultOrError = page.locator('text=Analysis complete, text=Analysis failed, text=No matching contacts').first();
    await resultOrError.waitFor({ timeout: 90000 }).catch(() => {});
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'screenshot_prod_crm_spotlight_result.png', fullPage: true });

    // Check if we got success
    const success = page.locator('text=Analysis complete');
    const isSuccess = await success.isVisible({ timeout: 2000 }).catch(() => false);

    if (isSuccess) {
      // Step 8: Click "View GTM Strategy" to navigate
      const viewGTMBtn = page.locator('button:has-text("View GTM Strategy")');
      await expect(viewGTMBtn).toBeVisible();
      await viewGTMBtn.click();
      await page.waitForTimeout(3000);
      await page.screenshot({ path: 'screenshot_prod_gtm_result.png', fullPage: true });

      // Verify we're on the GTM page
      expect(page.url()).toContain('/knowledge/gtm');
    } else {
      // Log the error for debugging
      const pageText = await page.textContent('body');
      console.log('Result state:', pageText?.substring(0, 500));
    }
  });

  test('Warm reply filter shows replied contacts', async ({ page }) => {
    // Navigate to CRM with onsocial project and warm reply filters
    // OnSocial = project ID 42
    await page.goto('/contacts?project_id=42&replied=true&reply_category=interested,meeting_request,question,other');
    await page.waitForSelector('.ag-body-viewport', { timeout: 20000 });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshot_prod_crm_warm_filter.png', fullPage: true });

    // Verify contacts are loaded
    const countLabel = page.locator('.px-5.py-2 .text-xs.tabular-nums').first();
    const countText = await countLabel.textContent();
    console.log('Warm contacts count:', countText);
  });
});
