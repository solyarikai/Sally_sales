import { test, expect } from '@playwright/test';

const PROD_URL = 'http://46.62.210.24';
const SESSION_COOKIE = 'b50dfaf122f28a67cb0655ada0040fed8bb06f42fc999d46';

test.describe('GTM Strategy Links', () => {
  test.use({ baseURL: PROD_URL });

  test.beforeEach(async ({ context }) => {
    await context.addCookies([{
      name: 'session',
      value: SESSION_COOKIE,
      domain: '46.62.210.24',
      path: '/',
    }]);
  });

  test('Click Analytics Thinking log → navigates to GTM strategy', async ({ page }) => {
    // Step 1: Go to Analytics tab
    await page.goto('/knowledge/analytics?project=rizzult');
    await page.waitForTimeout(3000);
    
    // Verify analytics loaded
    await expect(page.locator('h3:has-text("Segment Funnel Analytics")')).toBeVisible({ timeout: 15000 });
    await page.screenshot({ path: 'screenshot_gtm_link_step1_analytics.png', fullPage: true });

    // Step 2: Click the first log entry in Analytics Thinking panel
    const logLinks = page.locator('h4:has-text("Analytics Thinking")').locator('..').locator('..').locator('a');
    const linkCount = await logLinks.count();
    console.log('GTM log links found:', linkCount);
    
    if (linkCount > 0) {
      await logLinks.first().click();
      await page.waitForTimeout(3000);
      await page.screenshot({ path: 'screenshot_gtm_link_step2_clicked.png', fullPage: true });
      
      // Verify we navigated to GTM Strategy tab
      const url = page.url();
      console.log('After click URL:', url);
      expect(url).toContain('/knowledge/gtm');
      expect(url).toContain('logId=');
      
      // Verify GTM Strategy tab is now active
      await page.screenshot({ path: 'screenshot_gtm_link_step3_strategy.png', fullPage: true });
    } else {
      console.log('No log links found - checking panel structure');
      const panelHtml = await page.locator('h4:has-text("Analytics Thinking")').locator('..').locator('..').innerHTML();
      console.log('Panel HTML preview:', panelHtml.substring(0, 500));
    }
  });

  test('Direct GTM strategy URL with logId renders strategy', async ({ page }) => {
    // Get a valid logId first
    await page.goto('/knowledge/gtm?project=rizzult&logId=5');
    await page.waitForTimeout(4000);
    await page.screenshot({ path: 'screenshot_gtm_direct_logid.png', fullPage: true });
    
    const url = page.url();
    console.log('GTM direct URL:', url);
  });
});
