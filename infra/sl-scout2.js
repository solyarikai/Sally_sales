const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {
  const userDataDir = path.join(require('os').tmpdir(), 'sl_scout2_' + Date.now());
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

  if (page.url().includes('/login')) {
    console.log('OTP required — enter in the browser. Waiting...');
    await page.waitForFunction(() => !window.location.href.includes('/login'), { timeout: 180000, polling: 1000 });
  }

  await new Promise(r => setTimeout(r, 3000));
  console.log('Logged in! URL:', page.url());

  // Try known Smartlead routes for email accounts
  const candidates = [
    'https://app.smartlead.ai/app/email-accounts',
    'https://app.smartlead.ai/app/settings/email-accounts',
    'https://app.smartlead.ai/app/mailboxes',
    'https://app.smartlead.ai/app/settings/mailboxes',
    'https://app.smartlead.ai/app/sender-accounts',
  ];

  for (const url of candidates) {
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 15000 }).catch(() => {});
    await new Promise(r => setTimeout(r, 1000));
    const finalUrl = page.url();
    const title = await page.title();
    const h1 = await page.$eval('h1, h2', el => el.textContent.trim()).catch(() => '');
    console.log(`${url} → ${finalUrl} | ${title} | ${h1}`);
    if (!finalUrl.includes('/login') && !finalUrl.includes('404') && !finalUrl.includes('not-found')) {
      const name = url.split('/').pop();
      await page.screenshot({ path: path.join(__dirname, `sl-${name}.png`) });
      const buttons = await page.evaluate(() =>
        [...document.querySelectorAll('button, [role="button"]')].map(el => el.textContent.trim()).filter(Boolean)
      );
      console.log('  Buttons:', buttons.slice(0, 10));
    }
  }

  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
