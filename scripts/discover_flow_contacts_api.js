/**
 * Navigate to a flow's contacts page and intercept ALL API requests/responses
 * to discover the flow-contacts endpoint.
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const GS_TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwOi8vYW1hemluZy5nZXRzYWxlcy5pby9hcGkvand0LXRva2Vucy9jcmVhdGUtYXBpLWtleSIsImlhdCI6MTc3MDA3MDE0OCwiZXhwIjoxODY0Njc4MTQ4LCJuYmYiOjE3NzAwNzAxNDgsImp0aSI6IjFpYlF4TW5ueFJhVGxlREMiLCJzdWIiOiI3OTg4IiwidXNyIjp7ImlkIjo3OTg4LCJ1dWlkIjoiZTBiZDgzMTgtNGEwZC0xMWYwLThiYWItYThhMTU5YzBiZmJjIiwiZmlyc3RfbmFtZSI6IlNlcmdlIiwibGFzdF9uYW1lIjoiS3V6bmV0c292IiwiZW1haWwiOiJzZXJnZUBpbnh5ZGlnaXRhbC5jb20ifSwic3BlY2lmaWNfdGVhbV9pZCI6NzQzMCwidXNlcl90ZWFtcyI6eyI3NDMwIjozfSwidG9rZW5fdHlwZSI6ImFwaSJ9.22W-xynV9M92S4gz1B0DohAEMpz26DrmU0KDXnz8qZc';

// Use a small flow for testing: RIzzult big 5 agencies (159 contacts)
const TEST_FLOW = '9515a70b-0020-4955-8bea-9c2f7b904be8';

async function main() {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1920,1080']
  });

  const apiCalls = [];

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });

    // Intercept responses to capture full response bodies
    page.on('response', async (response) => {
      const url = response.url();
      if (!url.includes('getsales.io')) return;
      if (url.includes('.js') || url.includes('.css') || url.includes('.png') ||
          url.includes('.woff') || url.includes('firebase') || url.includes('intercom') ||
          url.includes('facebook') || url.includes('google') || url.includes('.svg') ||
          url.includes('hot-update') || url.includes('favicon')) return;

      const req = response.request();
      const method = req.method();
      if (method === 'OPTIONS') return;

      try {
        const body = await response.text();
        apiCalls.push({
          method,
          url: url.substring(0, 300),
          status: response.status(),
          reqBody: req.postData() ? req.postData().substring(0, 500) : null,
          resBody: body.substring(0, 500),
        });
      } catch {}
    });

    await page.setCookie({
      name: 'token', value: GS_TOKEN,
      domain: 'amazing.getsales.io', path: '/', secure: true
    });

    // Navigate to flow contacts page
    console.log(`Navigating to flow contacts: ${TEST_FLOW}`);
    await page.goto(`https://amazing.getsales.io/flow/automation/${TEST_FLOW}/contacts`, {
      waitUntil: 'networkidle2', timeout: 60000
    });
    await new Promise(r => setTimeout(r, 5000));

    // Print all API calls
    console.log(`\nCaptured ${apiCalls.length} API calls\n`);
    for (const call of apiCalls) {
      console.log(`${call.method} ${call.status} ${call.url}`);
      if (call.reqBody) {
        console.log(`  REQ: ${call.reqBody}`);
      }
      // Only print response body for POST/PATCH calls or calls with leads/flow in URL
      if (call.method !== 'GET' || call.url.includes('lead') || call.url.includes('flow')) {
        console.log(`  RES: ${call.resBody}`);
      }
    }

  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
