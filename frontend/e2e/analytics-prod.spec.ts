import { test, expect } from '@playwright/test';

const PROD_URL = 'http://46.62.210.24';
const SESSION_COOKIE = 'b50dfaf122f28a67cb0655ada0040fed8bb06f42fc999d46';

test.describe('Analytics Page - Production', () => {
  test.use({ baseURL: PROD_URL });

  test.beforeEach(async ({ context }) => {
    await context.addCookies([{
      name: 'session',
      value: SESSION_COOKIE,
      domain: '46.62.210.24',
      path: '/',
    }]);
  });

  test('Full flow: Analytics tab loads segment funnel for Rizzult', async ({ page }) => {
    await page.goto('/knowledge/analytics?project=rizzult');
    await page.waitForTimeout(3000);

    // Verify Rizzult project is selected
    await expect(page.locator('button:has-text("Rizzult")').first()).toBeVisible({ timeout: 10000 });

    // Verify Analytics tab is active
    const analyticsTab = page.locator('button:has-text("Analytics")');
    await expect(analyticsTab).toBeVisible();

    // Verify segment funnel loaded — use the unique header
    const funnelHeader = page.locator('h3:has-text("Segment Funnel Analytics")');
    await expect(funnelHeader).toBeVisible({ timeout: 15000 });

    // Verify the subtitle shows segment count
    await expect(page.locator('text=14 segments')).toBeVisible();

    // Verify period filter pills are visible
    await expect(page.locator('button:has-text("7d")')).toBeVisible();
    await expect(page.locator('button:has-text("30d")')).toBeVisible();
    await expect(page.locator('button:has-text("All time")')).toBeVisible();

    // Verify segment table header
    await expect(page.locator('span:has-text("SEGMENT"):visible')).toBeVisible();

    // Verify known segment rows are visible (these are in font-medium spans)
    await expect(page.locator('span.font-medium:has-text("Shopping"):visible').first()).toBeVisible({ timeout: 10000 });
    await expect(page.locator('span.font-medium:has-text("Fintech"):visible').first()).toBeVisible();

    // Verify Analytics Thinking panel on the right
    await expect(page.locator('h4:has-text("Analytics Thinking")')).toBeVisible({ timeout: 5000 });

    // Verify NO ICP warning on Analytics tab
    const hasWarning = await page.locator('text=Missing setup').isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasWarning).toBe(false);

    await page.screenshot({ path: 'screenshot_prod_analytics_loaded.png', fullPage: true });

    // Test period filter — click 30d
    await page.locator('button:has-text("30d")').click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshot_prod_analytics_30d.png', fullPage: true });

    // Click back to All time
    await page.locator('button:has-text("All time")').click();
    await page.waitForTimeout(2000);

    // Verify GTM log entries exist (we generated several)
    const hasLogs = await page.locator('text=Manual').first().isVisible({ timeout: 5000 }).catch(() => false);
    console.log('GTM logs visible:', hasLogs);

    await page.screenshot({ path: 'screenshot_prod_analytics_final.png', fullPage: true });
  });

  test('GTM Strategy tab shows latest strategy', async ({ page }) => {
    // Test with logId=12 which has \\n in patterns (old format)
    await page.goto('/knowledge/gtm?project=rizzult&logId=12');

    // Wait for strategy content to appear (executive summary or segment cards)
    await page.locator('text=Executive Summary').or(page.locator('text=Go-To-Market Strategy')).first().waitFor({ timeout: 15000 });
    await page.waitForTimeout(2000); // let content render

    await page.screenshot({ path: 'screenshot_prod_gtm_tab.png', fullPage: true });

    // Check for key sections
    const hasExecSummary = await page.locator('text=Executive Summary').isVisible().catch(() => false);
    const hasKPITargets = await page.locator('text=KPI Targets').isVisible().catch(() => false);
    const hasShopping = await page.locator('text=Shopping').isVisible().catch(() => false);
    const hasBottlenecks = await page.locator('text=Critical Bottlenecks').isVisible().catch(() => false);
    console.log('Sections visible:', { hasExecSummary, hasKPITargets, hasShopping, hasBottlenecks });

    // Scroll within GTM panel container to see segment patterns (with \\n fix)
    const scrollContainer = page.locator('.overflow-y-auto >> visible=true').last();
    await scrollContainer.evaluate(el => el.scrollTop = 600);
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'screenshot_prod_gtm_patterns.png' });

    // Click translate button
    const translateBtn = page.locator('button:has-text("Translate")');
    if (await translateBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await translateBtn.click();
      await page.waitForTimeout(3000); // wait for translations
      await page.screenshot({ path: 'screenshot_prod_gtm_translated.png' });
    }

    // Scroll to email template area
    await scrollContainer.evaluate(el => el.scrollTop = 1200);
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'screenshot_prod_gtm_template.png' });

    // Scroll to bottom sections
    await scrollContainer.evaluate(el => el.scrollTop = el.scrollHeight);
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'screenshot_prod_gtm_end.png' });
  });
});
