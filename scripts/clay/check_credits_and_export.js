/**
 * Check Clay credits and test safe export (no emails = no credit cost)
 * 1. Open credits panel, screenshot balance
 * 2. Navigate to the new gaming table
 * 3. Try to add "Find People" — but STOP before running (check credit cost)
 * 4. Only proceed if confirmed safe
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const WORKSPACE_ID = '889252';
const TABLE_ID = 't_0tbi2ipFbAmbrrEMgEe'; // New gaming table
const OUT_DIR = path.join(__dirname, 'discovery');
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36';

function humanDelay(minMs = 800, maxMs = 2500) {
  return new Promise(r => setTimeout(r, minMs + Math.random() * (maxMs - minMs)));
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function screenshot(page, name) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(OUT_DIR, `${name}.png`), fullPage: false });
  console.log(`  [img] ${name}.png`);
}

async function findByText(page, text, exactMatch = true) {
  return page.evaluate((text, exactMatch) => {
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walk.nextNode()) {
      const node = walk.currentNode;
      const match = exactMatch ? node.textContent.trim() === text : node.textContent.trim().includes(text);
      if (match) {
        const el = node.parentElement;
        if (el && el.offsetParent !== null) {
          const rect = el.getBoundingClientRect();
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: el.textContent.trim().substring(0, 80) };
        }
      }
    }
    return null;
  }, text, exactMatch);
}

async function main() {
  console.log('Launching stealth browser...');
  const browser = await puppeteer.launch({
    headless: false,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900', '--disable-blink-features=AutomationControlled'],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.setUserAgent(USER_AGENT);
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  });

  await page.setCookie({
    name: 'claysession',
    value: 's%3AsydgrI74YLdGMrU8LWzQSmCv-IrJgDYg.FYCecoCtfmRICI19MVyPsTXRxlfUAfoeKSLns5ofeGw',
    domain: 'api.clay.com', path: '/', httpOnly: true, secure: true, sameSite: 'None',
  });

  // Track API responses for credit info
  page.on('response', async (res) => {
    if (res.url().includes('billingplans') || res.url().includes('credit') || res.url().includes('subscription')) {
      try {
        const body = await res.text();
        if (body.length < 5000) {
          console.log(`  [api] ${res.url().split('/').slice(-2).join('/')}: ${body.substring(0, 300)}`);
        }
      } catch {}
    }
  });

  // ====== STEP 1: Go to workspace to see credits ======
  console.log('\n[1] Navigate to workspace...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  // Click on credits banner at top right ("Use extra credits by 3/12")
  console.log('\n[2] Check credits panel...');
  const creditsLink = await findByText(page, 'Use extra credits', false);
  if (creditsLink) {
    await page.mouse.click(creditsLink.x, creditsLink.y);
    await humanDelay(2000, 3000);
    await screenshot(page, 'credits_panel');
  }

  // Also try the profile/settings area
  await screenshot(page, 'credits_01_home');

  // ====== STEP 2: Check billing/credits via API ======
  console.log('\n[3] Fetching credit balance via API...');
  const creditInfo = await page.evaluate(async () => {
    try {
      const res = await fetch('https://api.clay.com/v3/billingplans/889252?source=frontend', {
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
      });
      return await res.json();
    } catch (e) { return { error: e.message }; }
  });
  console.log('  Credit info:', JSON.stringify(creditInfo, null, 2).substring(0, 1000));

  // Also check subscription
  const subInfo = await page.evaluate(async () => {
    try {
      const res = await fetch('https://api.clay.com/v3/subscriptions/889252', {
        credentials: 'include',
        headers: { 'Accept': 'application/json' }
      });
      return await res.json();
    } catch (e) { return { error: e.message }; }
  });
  console.log('  Subscription:', JSON.stringify(subInfo, null, 2).substring(0, 500));

  // ====== STEP 3: Navigate to gaming table ======
  console.log('\n[4] Navigate to gaming table...');
  await page.goto(
    `https://app.clay.com/workspaces/${WORKSPACE_ID}/workbooks/wb_0tbi2ipy72ouqyVTSq9/tables/${TABLE_ID}`,
    { waitUntil: 'networkidle2', timeout: 30000 }
  );
  await humanDelay(2000, 3500);
  await screenshot(page, 'credits_02_table');

  // ====== STEP 4: Close actions panel if open, look at the table ======
  console.log('\n[5] Analyzing table state...');
  // Press Escape to close any panels
  await page.keyboard.press('Escape');
  await humanDelay(500, 1000);
  await screenshot(page, 'credits_03_table_clean');

  // ====== STEP 5: Check what's in the table ======
  const tableInfo = await page.evaluate(() => {
    const rows = document.querySelectorAll('tr, [class*="row"]');
    const cols = document.querySelectorAll('th, [class*="header"]');
    return { rowCount: rows.length, colCount: cols.length };
  });
  console.log(`  Table has ~${tableInfo.rowCount} visible rows, ${tableInfo.colCount} columns`);

  console.log('\n=== CREDITS CHECK COMPLETE ===');
  console.log('Browser stays open for manual inspection.');
  console.log('Press Ctrl+C to close.\n');

  await sleep(600000);
  await browser.close();
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
