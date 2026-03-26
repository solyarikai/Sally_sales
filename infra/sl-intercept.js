// Intercepts Smartlead network requests during the "Add Account" flow
// to find the exact API call for connecting a Google account.
// After login, manually go through adding ONE account and this script logs the API call.

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const SESSION_FILE = path.join(__dirname, 'sl-session-dir.txt');
const CHROME = 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe';

(async () => {
  let dir = '';
  try { dir = fs.readFileSync(SESSION_FILE, 'utf8').trim(); } catch (_) {}
  if (!dir || !fs.existsSync(dir)) {
    dir = path.join(require('os').tmpdir(), 'sl_intercept_' + Date.now());
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(SESSION_FILE, dir);
  }
  console.log('Session dir:', dir);

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: CHROME,
    userDataDir: dir,
    pipe: true,
    args: ['--no-sandbox', '--no-first-run', '--start-maximized'],
    defaultViewport: null,
  });

  const page = await browser.newPage();

  // Intercept all API requests
  const captured = [];
  await page.setRequestInterception(true);
  page.on('request', req => {
    const url = req.url();
    const method = req.method();
    if (url.includes('smartlead') && (method === 'POST' || method === 'PUT') && url.includes('email-account')) {
      const body = req.postData();
      console.log('\n🎯 API REQUEST CAPTURED:');
      console.log('  URL:', url);
      console.log('  Method:', method);
      console.log('  Body:', body);
      captured.push({ url, method, body });
      fs.writeFileSync(path.join(__dirname, 'sl-api-capture.json'), JSON.stringify(captured, null, 2));
    }
    req.continue();
  });

  // Also intercept responses
  page.on('response', async res => {
    const url = res.url();
    if (url.includes('smartlead') && url.includes('email-account')) {
      const body = await res.text().catch(() => '');
      console.log('\n📥 API RESPONSE:');
      console.log('  URL:', url);
      console.log('  Status:', res.status());
      console.log('  Body:', body.substring(0, 500));
    }
  });

  await page.goto('https://app.smartlead.ai/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1000));

  if (page.url().includes('/login')) {
    // Fill credentials
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });
    await page.click('input[type="email"]', { clickCount: 3 });
    await page.type('input[type="email"]', 'services@getsally.io', { delay: 60 });
    await new Promise(r => setTimeout(r, 300));
    await page.click('input[type="password"]', { clickCount: 3 });
    await page.type('input[type="password"]', 'SallySarrh7231', { delay: 60 });
    await page.keyboard.press('Enter');
    await new Promise(r => setTimeout(r, 2000));

    if (page.url().includes('/login')) {
      console.log('\nOTP required — enter in the browser. Waiting up to 10 minutes...');
      try {
        await page.waitForFunction(() => !window.location.href.includes('/login'), { timeout: 600000, polling: 1000 });
      } catch (_) {
        console.log('Still on login. Check the browser window and enter OTP manually.');
        await new Promise(() => {}); // keep waiting
      }
    }
  }

  console.log('\n✓ Logged in!');
  console.log('\n=== NOW: manually add ONE email account via Add Account(s) → Smartlead Infrastructure → Google oAuth ===');
  console.log('=== Fill in petr@cronaplatform.com and password ===');
  console.log('=== This script will capture the API call automatically ===\n');
  console.log('Waiting for you to complete the flow... (press Ctrl+C when done)\n');

  // Keep running — don't close browser
  await new Promise(() => {}); // Wait forever
})().catch(e => { console.error(e.message); process.exit(1); });
