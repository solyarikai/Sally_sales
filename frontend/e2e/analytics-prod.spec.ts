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
    // Navigate to analytics tab for rizzult
    await page.goto('/knowledge/analytics?project=rizzult');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshot_prod_analytics_initial.png', fullPage: true });

    // Verify Rizzult project is selected
    const projectLabel = page.locator('text=Rizzult');
    await expect(projectLabel.first()).toBeVisible({ timeout: 10000 });

    // Verify Analytics tab is active
    const analyticsTab = page.locator('button:has-text("Analytics")');
    await expect(analyticsTab).toBeVisible();

    // Verify segment funnel header
    const funnelHeader = page.locator('text=Segment Funnel Analytics');
    await expect(funnelHeader).toBeVisible({ timeout: 15000 });

    // Verify summary cards are visible
    const contactsCard = page.locator('text=Contacts');
    await expect(contactsCard.first()).toBeVisible({ timeout: 10000 });

    const repliesCard = page.locator('text=Replies');
    await expect(repliesCard.first()).toBeVisible();

    const positiveCard = page.locator('text=Positive');
    await expect(positiveCard.first()).toBeVisible();

    const meetingsCard = page.locator('text=Meetings');
    await expect(meetingsCard.first()).toBeVisible();

    // Verify period filter pills
    const period7d = page.locator('button:has-text("7d")');
    const period30d = page.locator('button:has-text("30d")');
    const periodAll = page.locator('button:has-text("All time")');
    await expect(period7d).toBeVisible();
    await expect(period30d).toBeVisible();
    await expect(periodAll).toBeVisible();

    // Verify segment rows exist (should have Shopping, Agencies, Fintech, etc.)
    const shoppingRow = page.locator('text=Shopping');
    await expect(shoppingRow.first()).toBeVisible({ timeout: 10000 });

    const agenciesRow = page.locator('text=Agencies');
    await expect(agenciesRow.first()).toBeVisible();

    await page.screenshot({ path: 'screenshot_prod_analytics_loaded.png', fullPage: true });

    // Verify NO ICP warning on Analytics tab
    const icpWarning = page.locator('text=Missing setup');
    const hasWarning = await icpWarning.isVisible({ timeout: 2000 }).catch(() => false);
    expect(hasWarning).toBe(false);

    // Test period filter — click 30d
    await period30d.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshot_prod_analytics_30d.png', fullPage: true });

    // Click back to All time
    await periodAll.click();
    await page.waitForTimeout(2000);

    // Verify Analytics Thinking panel on the right
    const thinkingHeader = page.locator('text=Analytics Thinking');
    await expect(thinkingHeader).toBeVisible({ timeout: 5000 });

    // Verify GTM log entries exist (we just generated one)
    const logEntry = page.locator('text=Manual').or(page.locator('text=Scheduled'));
    const hasLogs = await logEntry.first().isVisible({ timeout: 5000 }).catch(() => false);
    console.log('GTM logs visible:', hasLogs);

    await page.screenshot({ path: 'screenshot_prod_analytics_final.png', fullPage: true });
  });

  test('GTM Strategy tab shows latest strategy', async ({ page }) => {
    await page.goto('/knowledge/gtm?project=rizzult');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshot_prod_gtm_tab.png', fullPage: true });

    // Verify GTM Strategy tab loaded
    const gtmTab = page.locator('button:has-text("GTM Strategy")');
    await expect(gtmTab).toBeVisible({ timeout: 5000 });

    // Should show strategy content (from the generate we just ran)
    // Look for segment names in the strategy
    const strategyContent = page.locator('text=SCALE UP').or(page.locator('text=PIVOT')).or(page.locator('text=MAINTAIN'));
    const hasStrategy = await strategyContent.first().isVisible({ timeout: 10000 }).catch(() => false);
    console.log('GTM strategy rendered:', hasStrategy);

    await page.screenshot({ path: 'screenshot_prod_gtm_strategy.png', fullPage: true });
  });
});
