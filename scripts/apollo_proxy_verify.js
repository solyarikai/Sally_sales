/**
 * Apollo Proxy Verification — one-time setup
 *
 * Logs into Apollo via Apify residential proxy, handles email verification,
 * and saves session cookies for reuse by all scrapers.
 *
 * Usage:
 *   APIFY_PROXY_PASSWORD=xxx node scripts/apollo_proxy_verify.js
 *   # Script will print "WAITING FOR CODE" — enter the 6-digit code from email
 *   # After verification, cookies saved to gathering-data/.apollo_cookies.json
 *
 *   Then run scrapers with --use-cookies flag (reads saved cookies)
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');
const readline = require('readline');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const COOKIES_FILE = path.join(__dirname, '..', 'gathering-data', '.apollo_cookies.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function askCode() {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise(resolve => {
    rl.question('Enter 6-digit code from email: ', answer => {
      rl.close();
      resolve(answer.trim());
    });
  });
}

async function main() {
  const proxyPwd = process.env.APIFY_PROXY_PASSWORD;
  if (!proxyPwd) {
    console.error('ERROR: Set APIFY_PROXY_PASSWORD env var');
    process.exit(1);
  }

  console.log('Launching browser with Apify residential proxy...');
  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--proxy-server=http://proxy.apify.com:8000',
    ],
  });

  const page = await browser.newPage();
  const sessionId = `apollo_verify_${Date.now()}`;
  await page.authenticate({
    username: `groups-RESIDENTIAL,session-${sessionId}`,
    password: proxyPwd,
  });
  await page.setViewport({ width: 1920, height: 1080 });

  // Login
  console.log('Logging in...');
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);
  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 50 });
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 50 });
  await page.click('button[type="submit"]');
  await sleep(5000);

  const url = page.url();
  console.log('After login: ' + url);

  if (url.includes('verify-email') || url.includes('ato')) {
    console.log('\n========================================');
    console.log('WAITING FOR VERIFICATION CODE');
    console.log('Check email: danila@getsally.io');
    console.log('Enter the 6-digit code below:');
    console.log('========================================\n');

    const code = await askCode();
    console.log('Entering code: ' + code);

    // Find and fill the code input
    const inputs = await page.$$('input');
    for (const input of inputs) {
      const type = await page.evaluate(el => el.type, input);
      if (type === 'text' || type === 'number' || type === 'tel') {
        await input.click();
        await input.type(code, { delay: 50 });
        break;
      }
    }

    // Click Continue
    const buttons = await page.$$('button');
    for (const btn of buttons) {
      const text = await page.evaluate(el => el.textContent, btn);
      if (text.includes('Continue') || text.includes('Verify')) {
        await btn.click();
        break;
      }
    }

    await sleep(5000);
    console.log('After verification: ' + page.url());
  }

  if (page.url().includes('/home') || page.url().includes('/people') || page.url().includes('/companies')) {
    console.log('SUCCESS — logged in and verified');

    // Save cookies
    const cookies = await page.cookies();
    fs.mkdirSync(path.dirname(COOKIES_FILE), { recursive: true });
    fs.writeFileSync(COOKIES_FILE, JSON.stringify(cookies, null, 2));
    console.log('Cookies saved to: ' + COOKIES_FILE);
    console.log('Cookies count: ' + cookies.length);

    // Quick test — can we access Companies tab?
    await page.goto('https://app.apollo.io/#/companies?organizationLocations[]=Miami%2C%20Florida%2C%20United%20States&qKeywords=agency', { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(5000);
    await page.screenshot({ path: '/tmp/apollo_after_verify.png' });
    console.log('Test screenshot saved');
  } else {
    console.log('FAILED — still at: ' + page.url());
    await page.screenshot({ path: '/tmp/apollo_verify_fail.png' });
  }

  await browser.close();
}

main().catch(e => { console.error('FATAL:', e); process.exit(1); });
