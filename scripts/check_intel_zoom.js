const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({
    httpCredentials: { username: 'ilovesally', password: 'BdaP31NNXX4ZCyvU' },
    viewport: { width: 1920, height: 1080 },
    deviceScaleFactor: 2,
  });
  await ctx.addCookies([
    { name: 'session', value: 'b50dfaf122f28a67cb0655ada0040fed8bb06f42fc999d46', domain: '46.62.210.24', path: '/' },
  ]);
  const page = await ctx.newPage();
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

  await page.goto('http://46.62.210.24/knowledge/intelligence?project=inxy', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await page.waitForTimeout(7000);

  // 1. Full page — summary + top of table
  await page.screenshot({ path: 'screenshot_intel_hd_top.png', fullPage: false });
  console.log('1. HD top');

  // 2. Scroll to see warm replies with tags
  await page.mouse.wheel(0, 400);
  await page.waitForTimeout(500);
  await page.screenshot({ path: 'screenshot_intel_hd_warm.png', fullPage: false });
  console.log('2. HD warm section');

  // 3. Open debug panel
  try {
    await page.getByText('Debug Panel').click({ timeout: 3000 });
    await page.waitForTimeout(3000);
    // Scroll to bottom to see debug panel
    await page.mouse.wheel(0, 50000);
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'screenshot_intel_hd_debug.png', fullPage: false });
    console.log('3. HD debug panel');
  } catch(e) {
    console.log('3. Debug error:', e.message.slice(0, 80));
  }

  await browser.close();
})();
