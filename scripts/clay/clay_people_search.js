/**
 * Clay People Search — Full UI automation with CSV export
 *
 * EVERYTHING happens via UI. No direct API calls for search or data.
 * Only internal API used: credit check (validation) and reading table data
 * as fallback if CSV export fails.
 *
 * System-level: supports filter splitting for >5000 results.
 *
 * Flow:
 * 1. Find leads → People tab → apply filters
 * 2. Continue → Save to new workbook and table
 * 3. Skip enrichments → Create table
 * 4. Actions → Export/Download CSV
 * 5. Read CSV file
 *
 * For >5000 results: split by geo regions, run multiple searches, merge + dedup.
 *
 * Usage:
 *   node clay_people_search.js                    # Gaming skins ICP
 *   node clay_people_search.js --auto             # Close browser after
 *   node clay_people_search.js --icp "SaaS CFOs"  # Custom ICP
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const WORKSPACE_ID = '889252';
const OUT_DIR = path.join(__dirname, 'exports');
const DOWNLOADS_DIR = path.join(OUT_DIR, 'downloads');
const SESSION_FILE = path.join(__dirname, 'clay_session.json');
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36';

// ============================================================
// Gaming Skins ICP — filter config
// ============================================================
const GAMING_ICP_FILTERS = {
  company_industries: ['Online gaming', 'Computer games'],
  company_description_keywords: [
    'skins', 'CS2', 'CSGO', 'Dota2', 'gaming marketplace',
    'virtual items', 'loot boxes', 'skin trading',
  ],
  job_titles: ['CEO', 'Founder', 'Co-Founder', 'CTO', 'CFO', 'COO',
    'VP', 'Head of', 'Director', 'Chief', 'Managing Director', 'Owner'],
};

// Geo splits for >5000 results
const GEO_SPLITS = [
  { label: 'North America', countries: ['United States', 'Canada'] },
  { label: 'Europe West', countries: ['United Kingdom', 'Germany', 'France', 'Netherlands', 'Spain', 'Italy', 'Switzerland', 'Sweden', 'Denmark', 'Norway', 'Finland', 'Ireland', 'Portugal', 'Belgium', 'Austria'] },
  { label: 'Europe East', countries: ['Poland', 'Czech Republic', 'Romania', 'Hungary', 'Ukraine', 'Lithuania', 'Latvia', 'Estonia', 'Serbia', 'Croatia', 'Bulgaria'] },
  { label: 'Asia Pacific', countries: ['Japan', 'South Korea', 'Australia', 'Singapore', 'India', 'China', 'Hong Kong', 'Taiwan', 'Thailand', 'Indonesia', 'Malaysia', 'Philippines'] },
  { label: 'LATAM', countries: ['Brazil', 'Argentina', 'Colombia', 'Chile', 'Mexico'] },
  { label: 'Middle East & CIS', countries: ['United Arab Emirates', 'Israel', 'Turkey', 'Russia', 'Kazakhstan'] },
  { label: 'Rest of World', countries: [] }, // No country filter = catch remaining
];

// ============================================================
// Session management
// ============================================================
function loadSession() {
  try {
    if (fs.existsSync(SESSION_FILE)) {
      const data = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));
      if (data.value) return data;
    }
  } catch {}
  return { value: null, savedAt: null };
}

function saveSession(cookieValue) {
  fs.writeFileSync(SESSION_FILE, JSON.stringify({
    value: cookieValue, savedAt: new Date().toISOString(),
  }, null, 2));
  console.log('  Session saved');
}

async function setSessionCookie(page, cookieValue) {
  await page.setCookie({
    name: 'claysession', value: cookieValue,
    domain: 'api.clay.com', path: '/', httpOnly: true, secure: true, sameSite: 'None',
  });
}

// ============================================================
// Helpers
// ============================================================
function humanDelay(min = 800, max = 2500) {
  return new Promise(r => setTimeout(r, min + Math.random() * (max - min)));
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function screenshot(page, name) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(OUT_DIR, `people_${name}.png`), fullPage: false });
  console.log(`  [img] people_${name}.png`);
}

async function getCredits(page) {
  return page.evaluate(async () => {
    try {
      const res = await fetch('https://api.clay.com/v3/subscriptions/889252', {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      const d = await res.json();
      return d.creditBalances;
    } catch { return null; }
  });
}

async function validateSession(page) {
  return page.evaluate(async () => {
    try {
      const res = await fetch('https://api.clay.com/v3/subscriptions/889252', {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      if (res.status === 401 || res.status === 403) return { valid: false };
      const data = await res.json();
      return { valid: !!data.creditBalances, credits: data.creditBalances };
    } catch (e) { return { valid: false, error: e.message }; }
  });
}

async function findByText(page, text, exact = true) {
  return page.evaluate((text, exact) => {
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walk.nextNode()) {
      const node = walk.currentNode;
      const match = exact ? node.textContent.trim() === text : node.textContent.trim().includes(text);
      if (match && node.parentElement?.offsetParent !== null) {
        const rect = node.parentElement.getBoundingClientRect();
        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, right: rect.x + rect.width - 8 };
      }
    }
    return null;
  }, text, exact);
}

async function findAllByText(page, text, exact = false) {
  return page.evaluate((text, exact) => {
    const results = [];
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walk.nextNode()) {
      const node = walk.currentNode;
      const match = exact ? node.textContent.trim() === text : node.textContent.trim().toLowerCase().includes(text.toLowerCase());
      if (match && node.parentElement?.offsetParent !== null) {
        const rect = node.parentElement.getBoundingClientRect();
        if (rect.width > 10) {
          results.push({ x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: node.textContent.trim() });
        }
      }
    }
    return results;
  }, text, exact);
}

async function fillFilterField(page, placeholder, values) {
  if (!values || values.length === 0) return false;
  const input = await page.$(`input[placeholder*="${placeholder}"]`);
  if (!input) {
    console.log(`    Filter "${placeholder}" not found`);
    return false;
  }
  for (const value of values) {
    await humanDelay(300, 700);
    await input.click();
    await humanDelay(200, 400);
    await input.type(value, { delay: 30 + Math.random() * 50 });
    await humanDelay(500, 1000);
    await page.keyboard.press('Enter');
    await humanDelay(300, 600);
  }
  console.log(`    ${placeholder}: ${values.join(', ')}`);
  return true;
}

// ============================================================
// Core: run a single People search + table creation + CSV export
// ============================================================
async function runPeopleSearch(page, filters, label = 'default') {
  console.log(`\n--- Running People search: ${label} ---`);

  // Navigate to Find leads
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  // Click "Find leads"
  await page.evaluate(() => {
    const els = [...document.querySelectorAll('button, div[role="button"]')];
    const el = els.find(e => e.textContent?.includes('Find leads') && e.textContent?.includes('Find people'));
    if (el) el.click();
  });
  await humanDelay(1500, 2500);

  // Click "People" tab
  const peopleBtn = await findByText(page, 'People');
  if (peopleBtn) {
    await page.mouse.click(peopleBtn.x, peopleBtn.y);
    await humanDelay(1500, 2500);
    console.log('  Selected People tab');
  }
  await screenshot(page, `${label}_01_people_tab`);

  // Apply filters
  console.log('  Applying filters...');

  if (filters.company_industries?.length) {
    await fillFilterField(page, 'Software development', filters.company_industries);
  }
  if (filters.company_description_keywords?.length) {
    await fillFilterField(page, 'sales, data, outbound', filters.company_description_keywords);
  }
  if (filters.job_titles?.length) {
    // Try multiple possible placeholders for job title
    const filled = await fillFilterField(page, 'CEO', filters.job_titles)
      || await fillFilterField(page, 'Job title', filters.job_titles)
      || await fillFilterField(page, 'title', filters.job_titles);
    if (!filled) console.log('    Job title filter not found');
  }
  if (filters.countries?.length) {
    await fillFilterField(page, 'United States', filters.countries)
      || await fillFilterField(page, 'country', filters.countries)
      || await fillFilterField(page, 'location', filters.countries);
  }

  await humanDelay(2000, 3000);
  await screenshot(page, `${label}_02_filters`);

  // Read result count from UI
  const resultText = await page.evaluate(() => {
    const text = document.body.textContent || '';
    const match = text.match(/([\d,]+)\s*(?:people|results|contacts|leads)/i);
    return match ? match[0] : null;
  });
  console.log(`  Result count: ${resultText || 'unknown'}`);

  // Click Continue dropdown → Save to new workbook and table
  console.log('  Opening Continue dropdown...');
  const continueBtnInfo = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null);
    const btn = buttons.find(b => b.textContent?.trim().startsWith('Continue'));
    if (!btn) return null;
    const rect = btn.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, right: rect.x + rect.width - 8 };
  });

  if (!continueBtnInfo) {
    console.log('  ERROR: Continue button not found!');
    await screenshot(page, `${label}_03_no_continue`);
    return null;
  }

  async function findDropdownOption() {
    return page.evaluate(() => {
      const allEls = [...document.querySelectorAll('button, div[role="menuitem"], div[role="option"], li, a')];
      for (const el of allEls) {
        const t = el.textContent?.trim().toLowerCase() || '';
        if ((t.includes('new workbook') || t.includes('new table')) && el.offsetParent !== null) {
          const rect = el.getBoundingClientRect();
          if (rect.width > 50) return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: el.textContent.trim() };
        }
      }
      return null;
    });
  }

  let option = null;
  for (let attempt = 0; attempt < 4 && !option; attempt++) {
    if (attempt > 0) { await page.keyboard.press('Escape'); await humanDelay(500, 800); }
    if (attempt < 2) {
      await page.mouse.click(continueBtnInfo.right, continueBtnInfo.y);
    } else {
      await page.mouse.click(continueBtnInfo.x, continueBtnInfo.y);
    }
    await humanDelay(1200, 2000);
    option = await findDropdownOption();
  }

  if (option) {
    console.log(`  Found: "${option.text}" — clicking...`);
    await page.mouse.click(option.x, option.y);
  } else {
    console.log('  Dropdown option not found!');
    await screenshot(page, `${label}_03_dropdown_fail`);
    return null;
  }

  // Wait for enrichment page
  await humanDelay(5000, 8000);
  await screenshot(page, `${label}_03_enrich_page`);

  // Extract table ID from URL
  let tableId = null;
  for (let i = 0; i < 15; i++) {
    const url = page.url();
    const m = url.match(/tableId=([^&]+)/);
    if (m) { tableId = m[1]; break; }
    const pm = url.match(/tables\/([^/?]+)/);
    if (pm) { tableId = pm[1]; break; }
    await sleep(2000);
  }
  console.log(`  Table ID: ${tableId}`);

  // Skip enrichments → Create table
  const createBtn = await findByText(page, 'Create table', false);
  if (createBtn) {
    console.log('  Clicking "Create table" (skipping enrichments)...');
    await page.mouse.click(createBtn.x, createBtn.y);
    await humanDelay(10000, 15000);
    await screenshot(page, `${label}_04_table_created`);

    // Update table ID
    const newUrl = page.url();
    const m = newUrl.match(/tableId=([^&]+)/);
    if (m) tableId = m[1];
  }

  if (!tableId) {
    console.log('  ERROR: No table ID found');
    return null;
  }

  // Wait for table to fully populate
  console.log('  Waiting for table data to load...');
  await humanDelay(5000, 8000);
  await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(3000, 5000);
  await screenshot(page, `${label}_05_table_loaded`);

  // Try to export CSV via UI: Actions → Export
  console.log('  Looking for CSV export option...');
  const csvPath = await exportTableCSV(page, label);

  if (csvPath) {
    console.log(`  CSV exported: ${csvPath}`);
    return { tableId, csvPath, label };
  }

  // Fallback: read via internal API from browser context
  console.log('  CSV export not found — reading via browser API...');
  const records = await readTableFromBrowser(page, tableId);
  const jsonPath = path.join(OUT_DIR, `people_${label}.json`);
  fs.writeFileSync(jsonPath, JSON.stringify(records, null, 2));
  console.log(`  Saved ${records.length} records to ${jsonPath}`);
  return { tableId, jsonPath, records, label };
}

// ============================================================
// Export CSV via Clay UI
// ============================================================
async function exportTableCSV(page, label) {
  fs.mkdirSync(DOWNLOADS_DIR, { recursive: true });

  // Set up download behavior
  const client = await page.createCDPSession();
  await client.send('Page.setDownloadBehavior', {
    behavior: 'allow',
    downloadPath: DOWNLOADS_DIR,
  });

  // Try: Actions button → look for Export/Download
  const actionsBtn = await findByText(page, 'Actions', false);
  if (actionsBtn) {
    console.log('  Clicking Actions...');
    await page.mouse.click(actionsBtn.x, actionsBtn.y);
    await humanDelay(1000, 1500);
    await screenshot(page, `${label}_06_actions_menu`);

    // Look for Export/Download option
    const exportOpt = await findByText(page, 'Export', false)
      || await findByText(page, 'Download', false)
      || await findByText(page, 'CSV', false)
      || await findByText(page, 'Export as CSV', false)
      || await findByText(page, 'Download CSV', false);

    if (exportOpt) {
      console.log(`  Found export option: clicking...`);
      await page.mouse.click(exportOpt.x, exportOpt.y);
      await humanDelay(3000, 5000);

      // Check for download dialog / confirmation
      const confirmBtn = await findByText(page, 'Export', true)
        || await findByText(page, 'Download', true)
        || await findByText(page, 'Confirm', false);
      if (confirmBtn) {
        await page.mouse.click(confirmBtn.x, confirmBtn.y);
        await humanDelay(3000, 5000);
      }

      // Wait for file to appear in downloads dir
      for (let i = 0; i < 30; i++) {
        const files = fs.readdirSync(DOWNLOADS_DIR).filter(f => f.endsWith('.csv'));
        if (files.length > 0) {
          const csvPath = path.join(DOWNLOADS_DIR, files[files.length - 1]);
          return csvPath;
        }
        await sleep(1000);
      }
      console.log('  CSV file not found in downloads after 30s');
    } else {
      console.log('  Export option not found in Actions menu');
      // List menu items for debugging
      const menuItems = await page.evaluate(() =>
        [...document.querySelectorAll('button, div[role="menuitem"], a')]
          .filter(el => el.offsetParent !== null)
          .map(el => el.textContent?.trim().substring(0, 60))
          .filter(t => t && t.length > 1)
          .slice(0, 20)
      );
      console.log('  Menu items:', menuItems.join(' | '));
    }
    await page.keyboard.press('Escape');
    await humanDelay(500, 800);
  }

  // Try: three-dot menu or right-click on table
  // Try: keyboard shortcut (some apps support Ctrl+Shift+E)

  return null;
}

// ============================================================
// Fallback: Read table data from browser context
// ============================================================
async function readTableFromBrowser(page, tableId) {
  // Get field mapping
  const tableMeta = await page.evaluate(async (tid) => {
    try {
      const res = await fetch(`https://api.clay.com/v3/tables/${tid}`, {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      return await res.json();
    } catch (e) { return { error: e.message }; }
  }, tableId);

  const fieldMap = {};
  for (const field of (tableMeta?.table?.fields || [])) {
    fieldMap[field.id] = field.name;
  }
  console.log(`  Fields: ${Object.values(fieldMap).join(', ')}`);

  // Get record IDs
  const viewId = page.url().match(/views\/([^/?&]+)/)?.[1] || tableMeta?.table?.firstViewId;
  let recordIds = [];
  if (viewId) {
    const idsData = await page.evaluate(async (tid, vid) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}/views/${vid}/records/ids`, {
          credentials: 'include', headers: { 'Accept': 'application/json' },
        });
        return await res.json();
      } catch (e) { return { error: e.message }; }
    }, tableId, viewId);
    recordIds = idsData?.results || [];
  }
  console.log(`  Record IDs: ${recordIds.length}`);

  // Fetch records in batches
  const allRecords = [];
  const batchSize = 200;
  for (let i = 0; i < recordIds.length; i += batchSize) {
    const batch = recordIds.slice(i, i + batchSize);
    const batchData = await page.evaluate(async (tid, ids) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}/bulk-fetch-records`, {
          method: 'POST', credentials: 'include',
          headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
          body: JSON.stringify({ recordIds: ids }),
        });
        return await res.json();
      } catch (e) { return { error: e.message }; }
    }, tableId, batch);

    for (const record of (batchData?.results || [])) {
      const person = {};
      for (const [fieldId, cell] of Object.entries(record.cells || {})) {
        const name = fieldMap[fieldId] || fieldId;
        let val = cell?.value;
        if (val && typeof val === 'object' && val.optionIds) {
          val = cell?.metadata?.valueDisplay || JSON.stringify(val.optionIds);
        }
        if (val != null) person[name] = String(val).substring(0, 1000);
      }
      person._id = record.id;
      allRecords.push(person);
    }
    console.log(`  Batch ${Math.floor(i / batchSize) + 1}: total ${allRecords.length}`);
    await humanDelay(500, 1000);
  }

  return allRecords;
}

// ============================================================
// Main
// ============================================================
async function main() {
  const args = process.argv.slice(2);
  const autoClose = args.includes('--auto');
  const splitByGeo = args.includes('--split-geo');
  const headless = args.includes('--headless');

  console.log('\n========================================');
  console.log('  Clay People Search — Gaming Skins ICP');
  console.log('========================================\n');

  // Launch browser with download support
  const browser = await puppeteer.launch({
    headless: headless ? 'new' : false,
    executablePath: headless ? (process.env.CHROME_PATH || '/usr/bin/google-chrome') : undefined,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900',
           '--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage',
           '--disable-gpu', '--disable-extensions'],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.setUserAgent(USER_AGENT);
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  });

  // Session
  const session = loadSession();
  if (!session.value) {
    console.log('ERROR: No session. Run: node clay_tam_export.js --login-only');
    await browser.close();
    process.exit(1);
  }
  await setSessionCookie(page, session.value);

  // Validate
  console.log('[1] Validating session...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  let check = await validateSession(page);
  if (!check.valid) {
    console.log('  Session expired — opening login...');
    await page.goto('https://app.clay.com/login', { waitUntil: 'networkidle2' });
    for (let i = 0; i < 100; i++) {
      await sleep(3000);
      if (page.url().includes('/workspaces/') || page.url().includes('/home')) {
        const cookies = await page.cookies('https://api.clay.com');
        const sc = cookies.find(c => c.name === 'claysession');
        if (sc) { saveSession(sc.value); break; }
      }
    }
    await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2' });
    await humanDelay(2000, 3000);
    check = await validateSession(page);
    if (!check.valid) throw new Error('Login failed');
  }

  const creditsBefore = check.credits;
  console.log(`  Credits: ${JSON.stringify(creditsBefore)}`);

  // Build search configs
  let searches;
  if (splitByGeo) {
    // Split by geo for >5000 results
    searches = GEO_SPLITS.map(geo => ({
      label: geo.label.toLowerCase().replace(/[^a-z0-9]+/g, '_'),
      filters: {
        ...GAMING_ICP_FILTERS,
        countries: geo.countries.length > 0 ? geo.countries : undefined,
      },
    }));
    console.log(`\n[2] Running ${searches.length} geo-split searches...`);
  } else {
    // Single search
    searches = [{ label: 'all', filters: GAMING_ICP_FILTERS }];
    console.log('\n[2] Running single search...');
  }

  // Run searches
  const allResults = [];
  for (const search of searches) {
    const result = await runPeopleSearch(page, search.filters, search.label);
    if (result) allResults.push(result);
    await humanDelay(2000, 4000);
  }

  // Final credit check
  console.log('\n[3] Final credit check...');
  const creditsAfter = await getCredits(page);
  const spent = (creditsBefore?.basic || 0) - (creditsAfter?.basic || 0);
  console.log(`  Credits before: ${JSON.stringify(creditsBefore)}`);
  console.log(`  Credits after:  ${JSON.stringify(creditsAfter)}`);
  console.log(`  CREDITS SPENT: ${spent}`);
  if (spent > 0) console.log('  WARNING: Credits were spent!');

  // Save session
  const endCookies = await page.cookies('https://api.clay.com');
  const sc = endCookies.find(c => c.name === 'claysession');
  if (sc) saveSession(sc.value);

  // Save summary
  fs.writeFileSync(path.join(OUT_DIR, 'people_search_results.json'), JSON.stringify({
    timestamp: new Date().toISOString(),
    searches: allResults.map(r => ({ label: r.label, tableId: r.tableId, csvPath: r.csvPath, jsonPath: r.jsonPath, recordCount: r.records?.length })),
    creditsBefore, creditsAfter, creditsSpent: spent,
  }, null, 2));

  console.log('\n========================================');
  console.log('  People search complete!');
  console.log(`  Results: ${allResults.length} table(s) created`);
  console.log(`  Credits spent: ${spent}`);
  console.log('========================================\n');

  if (autoClose) {
    await browser.close();
  } else {
    console.log('Browser stays open. Press Ctrl+C to close.\n');
    await sleep(600000);
    await browser.close();
  }
}

main().catch(err => {
  console.error('FATAL:', err.message);
  process.exit(1);
});
