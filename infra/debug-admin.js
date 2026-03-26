const puppeteer = require('puppeteer');
const os = require('os'), path = require('path'), fs = require('fs');

(async () => {
  const userDataDir = path.join(os.tmpdir(), 'chrome_debug_' + Date.now());
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
  await page.goto('https://admin.google.com/ac/domains/home', { waitUntil: 'networkidle2', timeout: 30000 });
  console.log('URL:', page.url());
  console.log('Title:', await page.title());

  if (!page.url().includes('admin.google.com/ac')) {
    console.log('Waiting for login (up to 2 min)...');
    await page.waitForFunction(() => window.location.href.includes('admin.google.com/ac'), { timeout: 120000, polling: 1000 });
    await new Promise(r => setTimeout(r, 3000));
    console.log('Logged in! URL:', page.url());
  }

  const screenshotPath = path.join(os.tmpdir(), 'admin_console.png');
  await page.screenshot({ path: screenshotPath });
  console.log('Screenshot:', screenshotPath);

  // Navigate to first crona domain verify page and check content
  await page.goto('https://admin.google.com/ac/domains/verify?domainName=cronaplatform.com', { waitUntil: 'networkidle2', timeout: 20000 });
  console.log('Verify URL:', page.url());
  const content = await page.content();
  const tokenMatch = content.match(/google-site-verification[\s\S]{0,5}([A-Za-z0-9_-]{20,})/i);
  console.log('Token found:', tokenMatch ? tokenMatch[0] : 'NOT FOUND');
  console.log('Content snippet:', content.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').substring(0, 800));

  await browser.close();
})().catch(e => { console.error(e.message); process.exit(1); });
