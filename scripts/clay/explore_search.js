/**
 * Explore Clay's "Find leads" search to understand:
 * 1. How company search filters work (API calls)
 * 2. How people search works
 * 3. What can be exported without credits
 *
 * Opens browser, navigates to Find leads, captures all API calls
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const WORKSPACE_ID = '889252';
const OUT_DIR = path.join(__dirname, 'discovery');
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36';

function humanDelay(min = 800, max = 2500) {
  return new Promise(r => setTimeout(r, min + Math.random() * (max - min)));
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function screenshot(page, name) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(OUT_DIR, `${name}.png`), fullPage: false });
  console.log(`  [img] ${name}.png`);
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
    value: 's%3AoeHYspFaX_rWio-gNpEzJqU0orl2bpKO.7p7qhi2GBcQGunHh2w3OC8NwycWCkGMjDz0LEkLJxRQ',
    domain: 'api.clay.com', path: '/', httpOnly: true, secure: true, sameSite: 'None',
  });

  // Capture ALL API calls with full request/response
  const apiCalls = [];
  page.on('request', req => {
    if (req.url().includes('api.clay.com')) {
      apiCalls.push({
        method: req.method(),
        url: req.url(),
        postData: req.postData()?.substring(0, 2000),
      });
    }
  });

  // Also capture responses for search-related endpoints
  const apiResponses = [];
  page.on('response', async (res) => {
    const url = res.url();
    if (url.includes('api.clay.com') && (
      url.includes('source') || url.includes('search') || url.includes('find') ||
      url.includes('filter') || url.includes('action') || url.includes('people') ||
      url.includes('company') || url.includes('field')
    )) {
      try {
        const body = await res.text();
        if (body.length < 10000) {
          apiResponses.push({ url, status: res.status(), body: body.substring(0, 3000) });
        } else {
          apiResponses.push({ url, status: res.status(), bodyLength: body.length, bodyPreview: body.substring(0, 500) });
        }
      } catch {}
    }
  });

  // Step 1: Go to workspace
  console.log('\n[1] Navigate to workspace...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  // Step 2: Click "Find leads"
  console.log('\n[2] Click "Find leads"...');
  const findLeads = await page.evaluate(() => {
    const els = [...document.querySelectorAll('button, a, div[role="button"]')];
    const el = els.find(e => e.textContent?.includes('Find leads') && e.textContent?.includes('Find people'));
    if (el) { el.click(); return true; }
    // Try sidebar
    const sidebar = els.find(e => e.textContent?.trim() === 'Find leads');
    if (sidebar) { sidebar.click(); return true; }
    return false;
  });
  console.log(`  ${findLeads ? 'clicked' : 'NOT FOUND'}`);
  await humanDelay(2000, 3500);
  await screenshot(page, 'search_01_find_leads');

  // Step 3: Look for "Find companies" option
  console.log('\n[3] Looking for search options...');
  const searchOptions = await page.evaluate(() => {
    const all = [...document.querySelectorAll('button, a, div[role="button"], div[role="menuitem"], li, span')];
    return all
      .filter(e => {
        const t = e.textContent?.toLowerCase() || '';
        return (t.includes('company') || t.includes('people') || t.includes('job')) && t.length < 50;
      })
      .map(e => ({ tag: e.tagName, text: e.textContent?.trim().substring(0, 50) }))
      .slice(0, 15);
  });
  console.log('  Options:', JSON.stringify(searchOptions, null, 2));

  // Click "Find companies" if available
  const compClicked = await page.evaluate(() => {
    const els = [...document.querySelectorAll('button, a, div, span')];
    const el = els.find(e => {
      const t = e.textContent?.trim();
      return t === 'Find companies' || t === 'Companies';
    });
    if (el) { el.click(); return true; }
    return false;
  });
  console.log(`  Find companies: ${compClicked ? 'clicked' : 'NOT FOUND'}`);
  await humanDelay(2000, 3500);
  await screenshot(page, 'search_02_find_companies');

  // Step 4: Explore filter options
  console.log('\n[4] Exploring filter UI...');
  await screenshot(page, 'search_03_filters');

  // Look for filter/industry/keyword elements
  const filterElements = await page.evaluate(() => {
    const all = [...document.querySelectorAll('input, select, [class*="filter"], [class*="search"], [role="combobox"], [role="listbox"]')];
    return all
      .filter(e => e.offsetParent !== null)
      .map(e => ({
        tag: e.tagName,
        type: e.type,
        placeholder: e.placeholder,
        name: e.name,
        text: e.textContent?.trim().substring(0, 60),
        classes: e.className?.substring?.(0, 80),
      }))
      .slice(0, 20);
  });
  console.log('  Filter elements:', JSON.stringify(filterElements, null, 2));

  // Step 5: Save everything
  console.log('\n[5] Saving data...');
  fs.writeFileSync(path.join(OUT_DIR, 'search_api_calls.json'), JSON.stringify(apiCalls, null, 2));
  fs.writeFileSync(path.join(OUT_DIR, 'search_api_responses.json'), JSON.stringify(apiResponses, null, 2));
  console.log(`  ${apiCalls.length} calls, ${apiResponses.length} responses saved`);

  // Show key search-related calls
  const searchCalls = apiCalls.filter(c =>
    c.url.includes('source') || c.url.includes('search') || c.url.includes('find') ||
    c.url.includes('people') || c.url.includes('company') || c.url.includes('filter')
  );
  console.log('\n  Search-related API calls:');
  searchCalls.forEach(c => {
    console.log(`    ${c.method} ${c.url}`);
    if (c.postData) console.log(`      ${c.postData.substring(0, 200)}`);
  });

  console.log('\n=== Browser open for manual exploration ===');
  console.log('Try: Find leads → Companies → add filters → observe API calls');
  console.log('Press Ctrl+C to close.\n');

  await sleep(600000);
  await browser.close();
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
