const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    httpCredentials: { username: 'ilovesally', password: 'BdaP31NNXX4ZCyvU' },
    viewport: { width: 1600, height: 1000 },
  });

  // Add session cookie
  await ctx.addCookies([
    { name: 'session', value: 'b50dfaf122f28a67cb0655ada0040fed8bb06f42fc999d46', domain: '46.62.210.24', path: '/' },
  ]);

  const page = await ctx.newPage();

  // Set localStorage
  await page.addInitScript(() => {
    window.localStorage.setItem('leadgen-storage', JSON.stringify({
      state: {
        currentEnvironment: null,
        currentCompany: { id: 1, name: 'LeadGen', slug: 'leadgen', user_id: 1 },
        currentProject: { id: 48, name: 'inxy' },
        activeSearchProjectId: null,
      },
      version: 0,
    }));
  });

  // Go to intelligence page
  await page.goto('http://46.62.210.24/knowledge/intelligence?project=inxy', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(6000);
  await page.screenshot({ path: 'screenshot_intel_v3_top.png', fullPage: false });
  console.log('1. Top of page captured');

  // Scroll down to see data
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(1000);
  await page.screenshot({ path: 'screenshot_intel_v3_scrolled.png', fullPage: false });
  console.log('2. Scrolled view');

  // Try debug panel
  try {
    const debugBtn = page.getByText('Debug Panel');
    if (await debugBtn.isVisible({ timeout: 2000 })) {
      await debugBtn.click();
      await page.waitForTimeout(2500);
      await page.screenshot({ path: 'screenshot_intel_v3_debug.png', fullPage: false });
      console.log('3. Debug panel opened');
    } else {
      console.log('3. Debug panel not visible');
    }
  } catch(e) {
    console.log('3. Debug panel error:', e.message.slice(0, 60));
  }

  // Full page screenshot
  await page.screenshot({ path: 'screenshot_intel_v3_full.png', fullPage: true });
  console.log('4. Full page done');

  await browser.close();
})();
