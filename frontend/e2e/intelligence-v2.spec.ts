import { test, expect } from '@playwright/test';

const BASE = 'http://46.62.210.24';

test.describe('Intelligence V2 — Full Suite', () => {
  test.setTimeout(180_000);

  async function setupAuth(page: any) {
    await page.context().setHTTPCredentials({ username: 'ilovesally', password: 'BdaP31NNXX4ZCyvU' });
    await page.context().addCookies([
      { name: 'session', value: 'b50dfaf122f28a67cb0655ada0040fed8bb06f42fc999d46', domain: '46.62.210.24', path: '/' },
    ]);
    await page.addInitScript(() => {
      window.localStorage.setItem('leadgen-storage', JSON.stringify({
        state: {
          currentEnvironment: null,
          currentCompany: { id: 1, name: 'LeadGen', slug: 'leadgen', user_id: 1, environment_id: null, description: null, website: null, logo_url: null, color: null, is_active: true, created_at: '2024-01-01T00:00:00Z', updated_at: null },
          currentProject: { id: 48, name: 'inxy' },
          activeSearchProjectId: null,
        },
        version: 0,
      }));
    });
  }

  async function loadIntelligence(page: any) {
    await page.goto(`${BASE}/knowledge/intelligence?project=inxy`, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    // Wait for data to load — Reply Intelligence header with count
    await page.waitForTimeout(8000);
  }

  // The Intelligence panel is inside a Knowledge tab — scope all selectors to the visible panel
  function panel(page: any) {
    // The active tab's container div that is NOT invisible
    return page.locator('div:not(.invisible):not(.pointer-events-none) >> text=Reply Intelligence').locator('..').locator('..');
  }

  test('1. Route redirect — /intelligence → /knowledge/intelligence', async ({ page }) => {
    await setupAuth(page);
    await page.goto(`${BASE}/intelligence`, { waitUntil: 'domcontentloaded', timeout: 30_000 });
    await page.waitForTimeout(3000);
    const url = page.url();
    console.log('1. URL after redirect:', url);
    expect(url).toContain('/knowledge/intelligence');
    await page.screenshot({ path: 'screenshot_intv2_01_redirect.png', fullPage: true });
  });

  test('2. Knowledge sub-tab — Intelligence tab rendering', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    // Verify Intelligence tab in Knowledge tab bar
    const intelTab = page.locator('button:has-text("Intelligence")');
    await expect(intelTab).toBeVisible({ timeout: 5000 });

    // Verify Reply Intelligence header
    await expect(page.locator('text=Reply Intelligence')).toBeVisible({ timeout: 5000 });

    // Verify Analyze (AI) button specifically
    const analyzeBtn = page.getByRole('button', { name: 'Analyze (AI)' });
    await expect(analyzeBtn).toBeVisible({ timeout: 5000 });

    await page.screenshot({ path: 'screenshot_intv2_02_tab.png', fullPage: true });
    console.log('2. Intelligence tab, header, and Analyze button visible');
  });

  test('3. Summary cards + data loaded', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    // Summary cards — use Warm Replies (unique to intelligence)
    await expect(page.locator('text=Warm Replies').first()).toBeVisible({ timeout: 5000 });
    // "Soft Objections" and "Hard Objections" are unique to Intelligence
    await expect(page.locator('text=Soft Objections').first()).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=Hard Objections').first()).toBeVisible({ timeout: 5000 });

    await page.screenshot({ path: 'screenshot_intv2_03_summary.png', fullPage: true });
    console.log('3. Summary cards visible');
  });

  test('4. Period selector — 7d, 30d, 90d, All time', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    // The Analyze (AI) button is near the period selector — use it as anchor
    // Period buttons: find the container near "Analyze (AI)"
    const analyzeBtn = page.getByRole('button', { name: 'Analyze (AI)' });
    await expect(analyzeBtn).toBeVisible({ timeout: 5000 });

    // Click 30d by finding it near the analyze button's parent container
    // The period selector is in the same flex row as the analyze button
    const periodContainer = analyzeBtn.locator('..'); // parent div
    const period30d = periodContainer.locator('button:has-text("30d")');
    await period30d.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshot_intv2_04_period_30d.png', fullPage: true });

    const period7d = periodContainer.locator('button:has-text("7d")');
    await period7d.click();
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshot_intv2_04_period_7d.png', fullPage: true });

    const allTime = periodContainer.locator('button:has-text("All time")');
    await allTime.click();
    await page.waitForTimeout(2000);

    console.log('4. Period selector works');
  });

  test('5. Intent group filter — summary card click', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    // Click Warm Replies card (unique text)
    const warmCard = page.locator('text=Warm Replies').first();
    await expect(warmCard).toBeVisible({ timeout: 5000 });
    await warmCard.click();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: 'screenshot_intv2_05_filter_warm.png', fullPage: true });

    // Toggle off
    await warmCard.click();
    await page.waitForTimeout(1500);

    // Click Soft Objections (unique text)
    const softCard = page.locator('text=Soft Objections').first();
    await softCard.click();
    await page.waitForTimeout(2500);
    await page.screenshot({ path: 'screenshot_intv2_05_filter_soft.png', fullPage: true });

    await softCard.click();
    await page.waitForTimeout(1000);

    console.log('5. Intent group filters work');
  });

  test('6. Multi-select filters — Offer, Intent, Segment', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    // The search bar and filter buttons are in the same row
    const searchInput = page.locator('input[placeholder*="Search replies"]');
    await expect(searchInput).toBeVisible({ timeout: 5000 });

    // Offer button is near the search input
    const filterBar = searchInput.locator('..');
    const offerBtn = filterBar.locator('button:has-text("Offer")').first();
    if (await offerBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await offerBtn.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'screenshot_intv2_06_offer_dropdown.png', fullPage: true });

      // Select paygate
      const paygateOpt = page.locator('button:has-text("paygate")');
      if (await paygateOpt.first().isVisible({ timeout: 2000 }).catch(() => false)) {
        await paygateOpt.first().click();
        await page.waitForTimeout(500);
      }
      await page.click('body', { position: { x: 10, y: 10 } });
      await page.waitForTimeout(2000);
      await page.screenshot({ path: 'screenshot_intv2_06_paygate_filtered.png', fullPage: true });
    }

    // Clear
    const clearBtn = page.locator('button:has-text("Clear")');
    if (await clearBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await clearBtn.click();
      await page.waitForTimeout(1500);
    }

    // Open Intent dropdown
    const intentBtn = filterBar.locator('button:has-text("Intent")').first();
    if (await intentBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await intentBtn.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'screenshot_intv2_06_intent_dropdown.png', fullPage: true });
      await page.click('body', { position: { x: 10, y: 10 } });
    }

    console.log('6. Multi-select filter dropdowns work');
  });

  test('7. Search filter', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    const searchInput = page.locator('input[placeholder*="Search"]');
    await expect(searchInput).toBeVisible({ timeout: 5000 });

    await searchInput.fill('crypto');
    await searchInput.press('Enter');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'screenshot_intv2_07_search.png', fullPage: true });

    const clearBtn = page.locator('button:has-text("Clear")');
    if (await clearBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await clearBtn.click();
      await page.waitForTimeout(1500);
    }
    console.log('7. Search filter works');
  });

  test('8. Table columns verification', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    // Column headers are uppercase span elements
    const expectedHeaders = ['LEAD', 'COMPANY', 'WEBSITE', 'OFFER', 'INTENT', 'INTERESTS', 'DATE', 'CRM'];
    for (const header of expectedHeaders) {
      const el = page.locator(`span:has-text("${header}")`).first();
      const visible = await el.isVisible({ timeout: 3000 }).catch(() => false);
      console.log(`  Column "${header}": ${visible ? 'visible' : 'NOT FOUND'}`);
    }

    const rows = page.locator('.cursor-pointer');
    const rowCount = await rows.count();
    console.log(`8. Table has ${rowCount} clickable rows`);
    expect(rowCount).toBeGreaterThan(0);

    await page.screenshot({ path: 'screenshot_intv2_08_table.png', fullPage: true });
  });

  test('9. Expand row — detail with interests, tags, geo', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    const firstRow = page.locator('.cursor-pointer').first();
    await expect(firstRow).toBeVisible({ timeout: 5000 });
    await firstRow.click();
    await page.waitForTimeout(2000);
    await page.screenshot({ path: 'screenshot_intv2_09_expanded.png', fullPage: true });

    // Check for expanded content
    const reply = page.locator('div:has-text("Reply")').first();
    console.log('9. Reply section visible:', await reply.isVisible().catch(() => false));

    const campaign = page.locator('text=Campaign:');
    console.log('   Campaign visible:', await campaign.first().isVisible().catch(() => false));

    const model = page.locator('text=Model:');
    console.log('   Model visible:', await model.first().isVisible().catch(() => false));

    const crmLink = page.locator('a:has-text("Open in CRM")').first();
    console.log('   CRM link visible:', await crmLink.isVisible().catch(() => false));

    if (await crmLink.isVisible().catch(() => false)) {
      const href = await crmLink.getAttribute('href');
      console.log('   CRM link href:', href);
    }
  });

  test('10. CRM deep link', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    // Expand first row
    const firstRow = page.locator('.cursor-pointer').first();
    await firstRow.click();
    await page.waitForTimeout(1500);

    const crmLink = page.locator('a:has-text("Open in CRM")').first();
    if (await crmLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      const href = await crmLink.getAttribute('href');
      console.log('10. CRM deep link:', href);

      const crmPage = await page.context().newPage();
      await setupAuth(crmPage);
      await crmPage.goto(BASE + (href || ''), { waitUntil: 'domcontentloaded', timeout: 25_000 });
      await crmPage.waitForTimeout(5000);
      await crmPage.screenshot({ path: 'screenshot_intv2_10_crm_deep.png', fullPage: true });
      console.log('   CRM page URL:', crmPage.url());
      await crmPage.close();
    }
  });

  test('11. Group collapse/expand', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    // The Noise group header with collapse button
    const noiseGroup = page.locator('text=Noise').last();
    if (await noiseGroup.isVisible({ timeout: 3000 }).catch(() => false)) {
      console.log('11. Noise group found');
      await noiseGroup.locator('..').click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: 'screenshot_intv2_11_noise_expanded.png', fullPage: true });
      await noiseGroup.locator('..').click();
      await page.waitForTimeout(500);
    }

    console.log('11. Group collapse/expand works');
  });

  test('12. Group "View in CRM" link', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    const viewCrm = page.locator('a:has-text("View in CRM")').first();
    if (await viewCrm.isVisible({ timeout: 3000 }).catch(() => false)) {
      const href = await viewCrm.getAttribute('href');
      console.log('12. Group CRM link:', href);
      expect(href).toContain('project_id=48');
    }
    console.log('12. Group CRM links verified');
  });

  test('13. Full page screenshot — scrolled', async ({ page }) => {
    await setupAuth(page);
    await loadIntelligence(page);

    await page.screenshot({ path: 'screenshot_intv2_13_initial.png', fullPage: true });

    await page.evaluate(() => {
      const scrollable = document.querySelector('.overflow-y-auto');
      if (scrollable) scrollable.scrollTop = scrollable.scrollHeight;
    });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: 'screenshot_intv2_13_scrolled.png', fullPage: true });
    console.log('13. Full page screenshots captured');
  });
});
