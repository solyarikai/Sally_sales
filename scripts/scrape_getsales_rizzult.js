/**
 * Navigate to a specific flow's contacts tab and capture ALL API requests.
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const GS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20iLCJnYV90cmFja2luZ19pZCI6IjQ1OTY0OTcyMS4xNzQyNTY1Mzc4LiIsImZiX2NsaWNrX2lkIjpudWxsLCJmYl9icm93c2VyX2lkIjoiZmIuMS4xNzQyNTY1Mzc4NjIxLjI4ODI0NDQ5MjUzMzQ2NTgwNSIsIndoaXRlbGFiZWxfdXVpZCI6bnVsbCwiY3JlYXRlZF9hdCI6IjIwMjUtMDMtMjFUMTM6NTY6NTkuMDAwMDAwWiJ9LCJzcGVjaWZpY190ZWFtX2lkIjo3NDMwLCJ1c2VyX3RlYW1zIjp7Ijc0MzAiOjN9LCJ0b2tlbl90eXBlIjoiYXBpIn0.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc';

// Use "RIzzult big 5 agencies 27 02 26" (small flow, 159 contacts) for testing
const TEST_FLOW = '9515a70b-0020-4955-8bea-9c2f7b904be8';

async function main() {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
  });

  const allRequests = [];

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    page.on('request', (request) => {
      const url = request.url();
      if (!url.includes('getsales.io')) return;
      if (url.includes('.js') || url.includes('.css') || url.includes('.png') ||
          url.includes('.woff') || url.includes('firebase') || url.includes('intercom') ||
          url.includes('facebook') || url.includes('google') || url.includes('.svg')) return;
      allRequests.push({
        url: url.substring(0, 200),
        method: request.method(),
        body: request.postData() ? request.postData().substring(0, 1000) : null
      });
    });

    await page.setCookie({
      name: 'token', value: GS_TOKEN,
      domain: 'amazing.getsales.io', path: '/', secure: true
    });

    // Step 1: Go directly to the flow contacts page
    console.log('Navigating to flow contacts page...');
    await page.goto(`https://amazing.getsales.io/flow/automation/${TEST_FLOW}/contacts`, {
      waitUntil: 'networkidle2', timeout: 60000
    });
    await new Promise(r => setTimeout(r, 5000));

    // Take screenshot
    await page.screenshot({ path: '/tmp/gs_flow_contacts.png', fullPage: true });

    // Print all captured POST requests
    console.log(`\nCaptured ${allRequests.length} requests\n`);
    const postReqs = allRequests.filter(r => r.method === 'POST' || r.url.includes('flow'));
    for (const req of postReqs) {
      console.log(`${req.method} ${req.url}`);
      if (req.body) {
        try {
          const parsed = JSON.parse(req.body);
          console.log(`  Body: ${JSON.stringify(parsed).substring(0, 300)}`);
        } catch {
          console.log(`  Body: ${req.body.substring(0, 300)}`);
        }
      }
    }

    // Also check what the page shows
    const pageContent = await page.evaluate(() => {
      return document.body.innerText.substring(0, 3000);
    });
    console.log('\n=== Page content (first 1500 chars) ===');
    console.log(pageContent.substring(0, 1500));

  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
