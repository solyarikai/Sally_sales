/**
 * GetSales flow contact exporter via Puppeteer.
 * Intercepts auth to bypass SPA login, navigates to each Rizzult flow,
 * and exports contacts CSVs.
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');
puppeteer.use(StealthPlugin());

const GS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20ifSwic3BlY2lmaWNfdGVhbV9pZCI6NzQzMCwidXNlcl90ZWFtcyI6eyI3NDMwIjozfSwidG9rZW5fdHlwZSI6ImFwaSJ9.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc';

// Mock user response (matches token claims)
const MOCK_USER = {
  id: 7988,
  uuid: "e0bd8318-4a0d-11f0-8bab-a8a159c0bfbc",
  first_name: "Serge",
  last_name: "Kuznetsov",
  email: "serge@inxydigital.com",
  team_id: 7430,
  teams: [{ id: 7430, role: 3 }],
};

async function main() {
  const downloadDir = path.resolve('/tmp/gs_exports');
  if (!fs.existsSync(downloadDir)) fs.mkdirSync(downloadDir, { recursive: true });

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    // Set download behavior
    const client = await page.createCDPSession();
    await client.send('Page.setDownloadBehavior', {
      behavior: 'allow',
      downloadPath: downloadDir,
    });

    // Intercept requests to inject auth
    await page.setRequestInterception(true);
    page.on('request', (request) => {
      const url = request.url();

      // Mock the user auth endpoint
      if (url.includes('/id/api/users/current')) {
        request.respond({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(MOCK_USER),
        });
        return;
      }

      // Mock the refresh token endpoint
      if (url.includes('/id/api/users/refresh-jwt-token')) {
        request.respond({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ token: GS_TOKEN }),
        });
        return;
      }

      // Add auth header to all getsales API calls
      if (url.includes('getsales.io') && !url.match(/\.(js|css|png|svg|woff|ico)$/)) {
        const headers = {
          ...request.headers(),
          'Authorization': `Bearer ${GS_TOKEN}`,
        };
        request.continue({ headers });
        return;
      }

      request.continue();
    });

    // Also set cookie for good measure
    await page.setCookie({
      name: 'token', value: GS_TOKEN,
      domain: 'amazing.getsales.io', path: '/', secure: true
    });

    // Navigate to automations page
    console.log('Navigating to GetSales automations...');
    await page.goto('https://amazing.getsales.io/flow/automations', {
      waitUntil: 'networkidle2', timeout: 60000
    });
    await new Promise(r => setTimeout(r, 3000));

    // Screenshot to see what we got
    await page.screenshot({ path: '/tmp/gs_automations.png', fullPage: true });
    console.log('Screenshot saved to /tmp/gs_automations.png');

    // Check page content
    const pageText = await page.evaluate(() => document.body.innerText.substring(0, 2000));
    console.log('\n=== Page content ===');
    console.log(pageText.substring(0, 1000));

    // Check if we're on the automations page or redirected to login
    const currentUrl = page.url();
    console.log(`\nCurrent URL: ${currentUrl}`);

    if (currentUrl.includes('login') || currentUrl.includes('sign-in')) {
      console.log('REDIRECTED TO LOGIN - auth mock failed');
      // Try checking what went wrong
      return;
    }

    // Try to find flow/automation elements
    const flowCount = await page.evaluate(() => {
      // Look for flow items in the list
      const rows = document.querySelectorAll('tr, [class*="flow"], [class*="automation"], [class*="row"]');
      return rows.length;
    });
    console.log(`Found ${flowCount} flow elements`);

    // Try to search for "rizzult"
    console.log('\nLooking for search input...');
    const searchInput = await page.$('input[type="text"], input[type="search"], input[placeholder*="search" i], input[placeholder*="Search" i]');
    if (searchInput) {
      await searchInput.click();
      await searchInput.type('rizzult', { delay: 50 });
      await new Promise(r => setTimeout(r, 3000));
      await page.screenshot({ path: '/tmp/gs_rizzult_search.png', fullPage: true });
      console.log('Search screenshot saved');
    } else {
      console.log('No search input found');
    }

  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
