// Shared session: reuses the same Chrome profile so OTP is only needed once.
// Usage: require('./sl-base').launch() → { browser, page }

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

const SESSION_FILE = path.join(__dirname, 'sl-session-dir.txt');
const CHROME = require('puppeteer').executablePath();

function getOrCreateSessionDir() {
  let dir = '';
  try { dir = fs.readFileSync(SESSION_FILE, 'utf8').trim(); } catch (_) {}
  if (!dir || !fs.existsSync(dir)) {
    dir = path.join(require('os').tmpdir(), 'sl_session_' + Date.now());
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(SESSION_FILE, dir);
    console.log('Created new session dir:', dir);
  } else {
    console.log('Reusing session dir:', dir);
  }
  return dir;
}

async function launch() {
  const userDataDir = getOrCreateSessionDir();

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: CHROME,
    userDataDir,
    pipe: true,
    args: ['--no-sandbox', '--no-first-run', '--start-maximized'],
    defaultViewport: null,
  });

  const page = await browser.newPage();
  await page.goto('https://app.smartlead.ai/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1000));

  if (page.url().includes('/login')) {
    // Need to log in
    await page.waitForSelector('input[type="email"]', { timeout: 10000 });
    await page.click('input[type="email"]', { clickCount: 3 });
    await page.type('input[type="email"]', 'services@getsally.io', { delay: 60 });
    await new Promise(r => setTimeout(r, 300));
    await page.click('input[type="password"]', { clickCount: 3 });
    await page.type('input[type="password"]', 'SallySarrh7231', { delay: 60 });
    await page.keyboard.press('Enter');
    await new Promise(r => setTimeout(r, 2000));

    if (page.url().includes('/login')) {
      console.log('\nOTP required — enter the code in the browser. Waiting up to 3 minutes...');
      await page.waitForFunction(
        () => !window.location.href.includes('/login'),
        { timeout: 180000, polling: 1000 }
      );
    }
    await new Promise(r => setTimeout(r, 2000));
    console.log('Logged in! Session saved — no OTP needed next time.');
  } else {
    console.log('Session active — already logged in.');
  }

  return { browser, page };
}

module.exports = { launch };
