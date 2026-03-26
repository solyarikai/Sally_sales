const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

(async () => {
  const userDataDir = path.join(require('os').tmpdir(), 'sl_scout3_' + Date.now());
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
  console.log('Logged in!');

  await page.goto('https://app.smartlead.ai/app/email-accounts', { waitUntil: 'networkidle2', timeout: 20000 });
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(__dirname, 'sl-ea-before.png') });
  console.log('Screenshot: sl-ea-before.png');

  // Click "Add Account(s)"
  const clicked = await page.evaluate(() => {
    for (const btn of document.querySelectorAll('button, [role="button"]')) {
      if (btn.textContent.includes('Add Account')) {
        btn.click();
        return btn.textContent.trim();
      }
    }
    return null;
  });
  console.log('Clicked:', clicked);
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(__dirname, 'sl-ea-modal1.png') });
  console.log('Screenshot: sl-ea-modal1.png');

  // Get all visible text in modal/dialog
  const modalText = await page.evaluate(() => {
    const modal = document.querySelector('[role="dialog"], .modal, [class*="modal"], [class*="dialog"], [class*="Modal"]');
    return modal ? modal.innerText : document.body.innerText.substring(0, 2000);
  });
  console.log('Modal content:', modalText.substring(0, 1000));

  const allButtons = await page.evaluate(() =>
    [...document.querySelectorAll('button, [role="button"], li, [class*="option"], [class*="card"]')]
      .map(el => el.textContent.trim()).filter(t => t.length > 0 && t.length < 100)
  );
  console.log('All clickables:', JSON.stringify([...new Set(allButtons)].slice(0, 30), null, 2));

  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
