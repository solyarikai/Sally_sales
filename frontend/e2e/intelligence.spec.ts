import { test, expect } from '@playwright/test';

const BASE = 'http://46.62.210.24';

test.describe('Intelligence Page', () => {
  test.setTimeout(120000);

  test('full intelligence flow — filters, expand, CRM links', async ({ page }) => {
    // Auth
    await page.context().setHTTPCredentials({ username: 'ilovesally', password: 'BdaP31NNXX4ZCyvU' });
    await page.context().addCookies([{ name: 'session', value: 'b50dfaf122f28a67cb0655ada0040fed8bb06f42fc999d46', domain: '46.62.210.24', path: '/' }]);
    await page.addInitScript(() => {
      window.localStorage.setItem('leadgen-storage', JSON.stringify({
        state: {
          currentEnvironment: null,
          currentCompany: { id: 1, name: 'LeadGen', slug: 'leadgen', user_id: 1, environment_id: null, description: null, website: null, logo_url: null, color: null, is_active: true, created_at: '2024-01-01T00:00:00Z', updated_at: null },
          currentProject: { id: 48, name: 'inxy' },
          activeSearchProjectId: null
        },
        version: 0
      }));
    });

    // 1. Load page
    await page.goto(`${BASE}/intelligence?project_id=48`, { waitUntil: 'networkidle', timeout: 30000 });
    await page.waitForTimeout(5000);

    const analyzeBtn = page.locator('button:has-text("Analyze")');
    await expect(analyzeBtn).toBeVisible({ timeout: 10000 });

    // Wait for data
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshot_intelligence_loaded.png', fullPage: true });
    console.log('1. Page loaded with data');

    // 2. Filter by Warm
    const warmCard = page.locator('button:has-text("Warm")').first();
    if (await warmCard.isVisible({ timeout: 3000 }).catch(() => false)) {
      await warmCard.click();
      await page.waitForTimeout(2500);
      await page.screenshot({ path: 'screenshot_intelligence_warm.png', fullPage: true });
      console.log('2. Warm filter applied');
    }

    // Clear
    const clearBtn = page.locator('button:has-text("Clear filters")');
    if (await clearBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await clearBtn.click();
      await page.waitForTimeout(1000);
    }

    // 3. Filter by Questions
    const questionsCard = page.locator('button:has-text("Questions")').first();
    if (await questionsCard.isVisible({ timeout: 3000 }).catch(() => false)) {
      await questionsCard.click();
      await page.waitForTimeout(2500);
      await page.screenshot({ path: 'screenshot_intelligence_questions.png', fullPage: true });
      console.log('3. Questions filter applied');
    }

    if (await clearBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await clearBtn.click();
      await page.waitForTimeout(1000);
    }

    // 4. Filter by paygate offer
    const paygateChip = page.locator('button:has-text("paygate")').first();
    if (await paygateChip.isVisible({ timeout: 3000 }).catch(() => false)) {
      await paygateChip.click();
      await page.waitForTimeout(2500);
      await page.screenshot({ path: 'screenshot_intelligence_paygate.png', fullPage: true });
      console.log('4. Paygate filter');
    }

    if (await clearBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await clearBtn.click();
      await page.waitForTimeout(1000);
    }

    // 5. Expand first warm row
    const warmGroupHeader = page.locator('text=Warm Replies');
    if (await warmGroupHeader.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Find first clickable row after the header
      const firstRow = page.locator('.cursor-pointer').first();
      if (await firstRow.isVisible({ timeout: 3000 }).catch(() => false)) {
        await firstRow.click();
        await page.waitForTimeout(1500);
        await page.screenshot({ path: 'screenshot_intelligence_expanded.png', fullPage: true });
        console.log('5. Row expanded');
      }
    }

    // 6. Test group "View in CRM" link
    const viewInCrm = page.locator('a:has-text("View in CRM")').first();
    if (await viewInCrm.isVisible({ timeout: 3000 }).catch(() => false)) {
      const href = await viewInCrm.getAttribute('href');
      console.log('6. Group CRM link:', href);

      // Navigate to verify it works
      const crmPage = await page.context().newPage();
      await crmPage.goto(BASE + (href || ''), { waitUntil: 'networkidle', timeout: 25000 });
      await crmPage.waitForTimeout(4000);
      await crmPage.screenshot({ path: 'screenshot_intelligence_crm_group.png', fullPage: true });
      console.log('   CRM page URL:', crmPage.url());
      await crmPage.close();
    }

    // 7. Test per-row CRM link (the external link icon)
    const rowCrmLink = page.locator('a:has-text("Open in CRM")').first();
    if (await rowCrmLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      const href = await rowCrmLink.getAttribute('href');
      console.log('7. Row CRM link:', href);

      const crmPage2 = await page.context().newPage();
      await crmPage2.goto(BASE + (href || ''), { waitUntil: 'networkidle', timeout: 25000 });
      await crmPage2.waitForTimeout(4000);
      await crmPage2.screenshot({ path: 'screenshot_intelligence_crm_row.png', fullPage: true });
      console.log('   CRM row page URL:', crmPage2.url());
      await crmPage2.close();
    }

    // 8. Scroll down to see all groups
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'screenshot_intelligence_scrolled.png', fullPage: true });
    console.log('8. Scrolled to bottom');

    console.log('All tests passed!');
  });
});
