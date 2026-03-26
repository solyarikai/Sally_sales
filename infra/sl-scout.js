const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {
  const userDataDir = path.join(require('os').tmpdir(), 'sl_scout_' + Date.now());
  fs.mkdirSync(userDataDir, { recursive: true });

  const browser = await puppeteer.launch({
    headless: false,
    executablePath: 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    userDataDir,
    pipe: true,
    args: ['--no-sandbox', '--no-first-run', '--start-maximized'],
    defaultViewport: null,
  });

  const page = await browser.newPage();
  await page.goto('https://app.smartlead.ai/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 1000));

  await page.waitForSelector('input[type="email"]', { timeout: 15000 });
  await page.type('input[type="email"]', 'services@getsally.io', { delay: 60 });
  await new Promise(r => setTimeout(r, 400));
  await page.type('input[type="password"]', 'SallySarrh7231', { delay: 60 });
  await page.keyboard.press('Enter');
  await new Promise(r => setTimeout(r, 2000));

  // Wait for OTP if needed
  if (page.url().includes('/login')) {
    console.log('OTP required — enter the code in the browser. Waiting up to 3 minutes...');
    await page.waitForFunction(
      () => !window.location.href.includes('/login'),
      { timeout: 180000, polling: 1000 }
    );
  }

  await new Promise(r => setTimeout(r, 3000));
  console.log('Logged in! URL:', page.url());
  await page.screenshot({ path: path.join(__dirname, 'sl-dashboard.png') });
  console.log('Screenshot: sl-dashboard.png');

  // Get all links to find correct URLs
  const links = await page.evaluate(() =>
    [...document.querySelectorAll('a[href]')].map(a => ({ text: a.textContent.trim(), href: a.href })).filter(l => l.text)
  );
  console.log('Nav links:', JSON.stringify(links.slice(0, 30), null, 2));

  const buttons = await page.evaluate(() =>
    [...document.querySelectorAll('button, [role="button"]')].map(el => el.textContent.trim()).filter(Boolean)
  );
  console.log('Buttons:', JSON.stringify(buttons.slice(0, 20), null, 2));

  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
