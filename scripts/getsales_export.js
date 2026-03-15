const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());
const fs = require('fs');
const path = require('path');

const EXPORT_DIR = path.join(__dirname, 'getsales_exports');

(async () => {
  if (!fs.existsSync(EXPORT_DIR)) fs.mkdirSync(EXPORT_DIR, { recursive: true });

  const token = process.env.GETSALES_JWT
    || fs.readFileSync(path.join(__dirname, 'getsales_token.txt'), 'utf-8').trim();

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });

  const page = await browser.newPage();

  // Set download directory via CDP
  const client = await page.createCDPSession();
  await client.send('Browser.setDownloadBehavior', {
    behavior: 'allow', downloadPath: EXPORT_DIR, eventsEnabled: true,
  });

  // Track downloads
  let downloadCount = 0;
  client.on('Browser.downloadProgress', (ev) => {
    if (ev.state === 'completed') {
      downloadCount++;
      console.log(`  [DL ${downloadCount}] completed: ${ev.guid}`);
    }
  });

  await page.setCookie({
    name: 'token', value: token,
    domain: 'amazing.getsales.io', path: '/',
    httpOnly: false, secure: true, sameSite: 'None',
  });

  console.log('Navigating to GetSales...');
  await page.goto('https://amazing.getsales.io/crm/contacts', {
    waitUntil: 'networkidle2', timeout: 60000,
  });
  await new Promise(r => setTimeout(r, 3000));

  if (page.url().includes('login')) {
    console.error('Not logged in — JWT expired');
    await browser.close();
    process.exit(1);
  }
  console.log('Logged in OK');

  // Open Action Queue
  console.log('Opening Action Queue...');
  await page.evaluate(() => {
    const el = [...document.querySelectorAll('button, span, div')]
      .find(b => b.textContent.trim() === 'Action Queue');
    if (el) el.click();
  });
  await new Promise(r => setTimeout(r, 2000));

  // Click "View 246 more files" to expand all CSV files
  console.log('Expanding all files...');
  const expanded = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('button, a, span')]
      .find(b => b.textContent.match(/view.*more.*file/i));
    if (btn) { btn.click(); return btn.textContent.trim(); }
    return null;
  });
  console.log(expanded ? `Expanded: ${expanded}` : 'No expand button found');
  await new Promise(r => setTimeout(r, 3000));

  // Find all contact CSV download buttons
  // Each CSV row has: <div>[icon] filename.csv</div> <button class="ant-btn">↓</button>
  // We need to click the button that's a sibling of the filename text
  const csvCount = await page.evaluate(() => {
    return [...document.querySelectorAll('*')]
      .filter(el => el.textContent.includes('contacts_export') && el.children.length === 0)
      .length;
  });
  console.log(`Found ${csvCount} CSV file entries`);

  // Click all download buttons for contacts CSVs
  // Strategy: find each row containing "contacts_export", then click the ant-btn sibling
  console.log('Starting downloads...');
  const totalClicked = await page.evaluate(() => {
    let clicked = 0;
    // Find all text nodes with contacts_export filenames
    const allElements = [...document.querySelectorAll('span, div, p')];
    const csvElements = allElements.filter(el => {
      const text = el.textContent.trim();
      return text.match(/^contacts_export.*\.csv$/) && el.children.length <= 1;
    });

    for (const el of csvElements) {
      // Walk up to find the row container, then find the download button
      let container = el.closest('div[class*="gs-"]') || el.parentElement?.parentElement;
      // The button is typically a sibling of the filename container
      while (container && !container.querySelector('button.ant-btn')) {
        container = container.parentElement;
        if (!container || container.tagName === 'BODY') break;
      }
      if (container) {
        const btn = container.querySelector('button.ant-btn');
        if (btn) {
          btn.click();
          clicked++;
        }
      }
    }
    return clicked;
  });
  console.log(`Clicked ${totalClicked} download buttons`);

  // Wait for downloads to complete
  console.log('Waiting for downloads...');
  let waitSec = 0;
  const maxWait = 600; // 10 minutes max
  while (waitSec < maxWait) {
    await new Promise(r => setTimeout(r, 5000));
    waitSec += 5;
    const files = fs.readdirSync(EXPORT_DIR).filter(f => f.endsWith('.csv'));
    const downloading = fs.readdirSync(EXPORT_DIR).filter(f => f.endsWith('.crdownload'));
    console.log(`  ${waitSec}s: ${files.length} CSVs, ${downloading.length} downloading`);
    if (files.length >= totalClicked && downloading.length === 0) break;
    if (files.length > 0 && downloading.length === 0 && waitSec > 30) break;
  }

  const finalFiles = fs.readdirSync(EXPORT_DIR).filter(f => f.endsWith('.csv'));
  console.log(`\nDone! ${finalFiles.length} CSV files downloaded to ${EXPORT_DIR}`);
  let totalSize = 0;
  for (const f of finalFiles) {
    const size = fs.statSync(path.join(EXPORT_DIR, f)).size;
    totalSize += size;
  }
  console.log(`Total size: ${(totalSize / 1024 / 1024).toFixed(1)} MB`);

  await browser.close();
})();
