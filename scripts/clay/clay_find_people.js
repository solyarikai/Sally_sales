/**
 * Clay People Search — Find people at gaming skin/item companies
 *
 * Uses Clay "Find leads" → "People" tab with gaming ICP filters.
 * Search is FREE (0 credits). We skip enrichments.
 *
 * Flow:
 * 1. Open Clay → Find leads → People tab
 * 2. Apply filters (industries, keywords, titles, company keywords)
 * 3. Save to new workbook and table (skip enrichments)
 * 4. Read all people records via internal API
 * 5. Match against known company domains (xlsx + Clay TAM)
 * 6. Export to Google Sheets
 *
 * Usage: node clay_find_people.js
 *        node clay_find_people.js --auto  (close browser after)
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const WORKSPACE_ID = '889252';
const OUT_DIR = path.join(__dirname, 'exports');
const SESSION_FILE = path.join(__dirname, 'clay_session.json');
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36';

// ============================================================
// Session management (shared with clay_tam_export.js)
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
    value: cookieValue,
    savedAt: new Date().toISOString(),
  }, null, 2));
  console.log('  Session saved');
}

async function setSessionCookie(page, cookieValue) {
  await page.setCookie({
    name: 'claysession',
    value: cookieValue,
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
      if (res.status === 401 || res.status === 403) return { valid: false, status: res.status };
      const data = await res.json();
      return { valid: !!data.creditBalances, status: res.status, credits: data.creditBalances };
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
// Main
// ============================================================

async function main() {
  const args = process.argv.slice(2);

  console.log('\n=== Clay People Search — Gaming Skins ICP ===\n');

  // Launch browser
  console.log('[1] Launching stealth browser...');
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

  // Load session
  const session = loadSession();
  if (!session.value) {
    console.log('  ERROR: No session found. Run: node clay_tam_export.js --login-only');
    await browser.close();
    process.exit(1);
  }
  console.log(`  Session from: ${session.savedAt}`);
  await setSessionCookie(page, session.value);

  // Validate session
  console.log('\n[2] Validating session...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  let sessionCheck = await validateSession(page);
  if (!sessionCheck.valid) {
    console.log('  Session expired! Run: node clay_tam_export.js --login-only');
    console.log('  Or log in manually — waiting...');
    await page.goto('https://app.clay.com/login', { waitUntil: 'networkidle2', timeout: 30000 });
    for (let i = 0; i < 100; i++) {
      await sleep(3000);
      const url = page.url();
      if (url.includes('/workspaces/') || url.includes('/home')) {
        const cookies = await page.cookies('https://api.clay.com');
        const sc = cookies.find(c => c.name === 'claysession');
        if (sc) { saveSession(sc.value); break; }
      }
      if (i % 10 === 0 && i > 0) console.log(`  Waiting for login... (${i * 3}s)`);
    }
    await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(2000, 3000);
    sessionCheck = await validateSession(page);
    if (!sessionCheck.valid) throw new Error('Session still invalid');
  }

  const creditsBefore = sessionCheck.credits || await getCredits(page);
  console.log(`  Credits before: ${JSON.stringify(creditsBefore)}`);
  await screenshot(page, '01_home');

  // Step 3: Navigate to Find leads → People tab
  console.log('\n[3] Opening Find leads → People...');
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
    console.log('  Clicked People tab');
  } else {
    console.log('  People tab not found, checking current state...');
  }
  await screenshot(page, '02_people_tab');

  // Step 4: Take screenshot to see what filters are available
  console.log('\n[4] Analyzing available filters...');

  // List all input placeholders to understand the filter layout
  const filterInputs = await page.evaluate(() => {
    return [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null).map(i => ({
      placeholder: i.placeholder,
      type: i.type,
      value: i.value,
    }));
  });
  console.log('  Available filter inputs:');
  for (const inp of filterInputs) {
    console.log(`    "${inp.placeholder}" (${inp.type})`);
  }

  // List all visible section labels
  const sectionLabels = await page.evaluate(() => {
    return [...document.querySelectorAll('h3, h4, label, span')]
      .filter(el => el.offsetParent !== null && el.textContent?.trim().length > 2 && el.textContent?.trim().length < 50)
      .map(el => el.textContent.trim())
      .filter((v, i, a) => a.indexOf(v) === i)
      .slice(0, 30);
  });
  console.log('  Section labels:', sectionLabels.join(' | '));

  // Step 5: Apply People filters for gaming ICP
  console.log('\n[5] Applying People filters...');

  // Company industry keywords (match gaming companies)
  const companyKeywords = [
    'gaming', 'esports', 'CS2', 'CSGO', 'skins',
    'marketplace', 'virtual items', 'gaming platform',
  ];

  // Try to fill company-related filters
  // People tab typically has: Job Title, Seniority, Department, Company Industry, Company Size, Location
  await fillFilterField(page, 'Software development', ['Online gaming', 'Computer games', 'E-commerce']);
  await humanDelay(500, 1000);

  // Description keywords for the COMPANY
  await fillFilterField(page, 'sales, data, outbound', companyKeywords);
  await humanDelay(500, 1000);

  // Job titles — we want decision-makers
  const jobTitles = ['CEO', 'CTO', 'CFO', 'COO', 'Founder', 'Co-Founder', 'VP', 'Head of', 'Director', 'CPO'];
  await fillFilterField(page, 'CEO', jobTitles);
  await humanDelay(500, 1000);

  await screenshot(page, '03_filters_applied');

  // Check how many results
  await humanDelay(2000, 3000);
  const resultCount = await page.evaluate(() => {
    const text = document.body.textContent || '';
    const match = text.match(/([\d,]+)\s*(?:people|results|contacts|leads)/i);
    return match ? match[1] : null;
  });
  console.log(`  Results count: ${resultCount || 'unknown'}`);
  await screenshot(page, '04_result_count');

  // Step 6: Click Continue → "Save to new workbook and table"
  console.log('\n[6] Opening Continue dropdown...');

  const continueBtnInfo = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null);
    const btn = buttons.find(b => b.textContent?.trim().startsWith('Continue'));
    if (!btn) return null;
    const rect = btn.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, right: rect.x + rect.width - 8 };
  });

  if (continueBtnInfo) {
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
      if (attempt > 0) {
        await page.keyboard.press('Escape');
        await humanDelay(500, 800);
      }
      if (attempt < 2) {
        console.log(`  Attempt ${attempt + 1}: clicking dropdown arrow...`);
        await page.mouse.click(continueBtnInfo.right, continueBtnInfo.y);
      } else {
        console.log(`  Attempt ${attempt + 1}: clicking Continue main...`);
        await page.mouse.click(continueBtnInfo.x, continueBtnInfo.y);
      }
      await humanDelay(1200, 2000);
      option = await findDropdownOption();
    }

    if (option) {
      console.log(`  Found: "${option.text}" — clicking...`);
      await page.mouse.click(option.x, option.y);
    } else {
      console.log('  Dropdown option not found. Taking screenshot for debug.');
      await screenshot(page, '05_dropdown_debug');
    }
  } else {
    console.log('  Continue button not found!');
    // List visible buttons for debugging
    const btns = await page.evaluate(() =>
      [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null)
        .map(b => b.textContent?.trim().substring(0, 60)).filter(t => t)
    );
    console.log('  Visible buttons:', btns.join(' | '));
    await screenshot(page, '05_no_continue');
  }

  // Wait for enrichment/table creation page
  console.log('  Waiting for enrichment page...');
  await humanDelay(5000, 8000);
  await screenshot(page, '06_after_save');

  // Extract table ID
  let tableId = null;
  let workbookId = null;

  function extractIdsFromUrl(url) {
    const tableMatch = url.match(/tableId=([^&]+)/);
    const wbMatch = url.match(/workbookId=([^&]+)/);
    return { tableId: tableMatch?.[1], workbookId: wbMatch?.[1] };
  }

  for (let i = 0; i < 15; i++) {
    const currentUrl = page.url();
    const ids = extractIdsFromUrl(currentUrl);
    if (ids.tableId) {
      tableId = ids.tableId;
      workbookId = ids.workbookId;
      console.log(`  Table ID: ${tableId}`);
      break;
    }
    const pathMatch = currentUrl.match(/tables\/([^/?]+)/);
    if (pathMatch) { tableId = pathMatch[1]; break; }
    await sleep(2000);
    console.log(`  Waiting for table... (${i + 1}/15)`);
  }

  // Skip enrichments → Create table
  console.log('\n[7] Skipping enrichments...');
  const isEnrichPage = await page.evaluate(() =>
    document.body.textContent?.includes('Enrich') || document.body.textContent?.includes('enrichment')
  );

  if (isEnrichPage) {
    await humanDelay(1500, 2500);
    const createTableBtn = await findByText(page, 'Create table', false);
    if (createTableBtn) {
      console.log('  Clicking "Create table"...');
      await page.mouse.click(createTableBtn.x, createTableBtn.y);
      await humanDelay(8000, 12000);
      await screenshot(page, '07_table_created');

      const newUrl = page.url();
      const newIds = extractIdsFromUrl(newUrl);
      if (newIds.tableId) { tableId = newIds.tableId; workbookId = newIds.workbookId; }
      const pathMatch = newUrl.match(/tables\/([^/?]+)/);
      if (pathMatch) tableId = pathMatch[1];
    } else {
      console.log('  "Create table" not found');
      const btns = await page.evaluate(() =>
        [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null)
          .map(b => b.textContent?.trim().substring(0, 50)).filter(t => t)
      );
      console.log('  Buttons:', btns.join(' | '));
    }
  }

  // Step 8: Read table data via API
  console.log(`\n[8] Reading people data (table: ${tableId})...`);

  if (tableId) {
    await humanDelay(10000, 15000);
    await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(5000, 8000);
    await screenshot(page, '08_table_data');

    // Get table metadata
    const tableMeta = await page.evaluate(async (tid) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}`, {
          credentials: 'include', headers: { 'Accept': 'application/json' },
        });
        return await res.json();
      } catch (e) { return { error: e.message }; }
    }, tableId);

    const fieldMap = {};
    const fields = tableMeta?.table?.fields || [];
    for (const field of fields) fieldMap[field.id] = field.name;
    console.log(`  Fields: ${Object.values(fieldMap).join(', ')}`);

    // Get record count
    const countData = await page.evaluate(async (tid) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}/count`, {
          credentials: 'include', headers: { 'Accept': 'application/json' },
        });
        return await res.json();
      } catch (e) { return { error: e.message }; }
    }, tableId);
    const totalRecords = countData?.tableTotalRecordsCount || 0;
    console.log(`  Total records: ${totalRecords}`);

    // Get record IDs
    const viewIdMatch = page.url().match(/views\/([^/?&]+)/);
    const viewId = viewIdMatch?.[1] || tableMeta?.table?.firstViewId;
    console.log(`  View ID: ${viewId}`);

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
      console.log(`  Record IDs: ${recordIds.length}`);
    }

    // Fetch records in batches
    const allRawRecords = [];
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

      const batchRecords = batchData?.results || [];
      allRawRecords.push(...batchRecords);
      console.log(`  Batch ${Math.floor(i / batchSize) + 1}: +${batchRecords.length} (total: ${allRawRecords.length})`);
      await humanDelay(500, 1000);
    }

    // Parse records
    const people = allRawRecords.map(record => {
      const person = {};
      for (const [fieldId, cell] of Object.entries(record.cells || {})) {
        const fieldName = fieldMap[fieldId] || fieldId;
        let value = cell?.value;
        if (value && typeof value === 'object' && value.optionIds) {
          value = (cell?.metadata?.valueDisplay || cell?.metadata?.display || JSON.stringify(value.optionIds));
        }
        if (value !== null && value !== undefined) person[fieldName] = String(value).substring(0, 1000);
      }
      person._id = record.id;
      return person;
    });

    console.log(`\n  Parsed people: ${people.length}`);
    if (people.length > 0) {
      console.log('  Columns:', Object.keys(people[0]).join(', '));
      console.log('  Sample:', JSON.stringify(people[0]).substring(0, 500));
    }

    // Save data
    fs.mkdirSync(OUT_DIR, { recursive: true });
    fs.writeFileSync(path.join(OUT_DIR, 'people_companies.json'), JSON.stringify(people, null, 2));
    fs.writeFileSync(path.join(OUT_DIR, 'people_table_meta.json'), JSON.stringify({ tableMeta, fieldMap, totalRecords }, null, 2));
    console.log(`  Saved to people_companies.json`);
  } else {
    console.log('  No table ID found!');
    await screenshot(page, '08_no_table');
  }

  // Final credit check
  console.log('\n[9] Final credit check...');
  const creditsAfter = await getCredits(page);
  console.log(`  Credits before: ${JSON.stringify(creditsBefore)}`);
  console.log(`  Credits after:  ${JSON.stringify(creditsAfter)}`);
  if (creditsBefore && creditsAfter) {
    const spent = (creditsBefore.basic || 0) - (creditsAfter.basic || 0);
    console.log(`\n  === CREDITS SPENT: ${spent} ===`);
    if (spent > 0) console.log('  WARNING: Credits were spent!');
    else console.log('  SAFE: No credits spent.');
  }

  // Save results
  fs.writeFileSync(path.join(OUT_DIR, 'people_results.json'), JSON.stringify({
    creditsBefore, creditsAfter,
    tableUrl: page.url(),
    tableId,
    timestamp: new Date().toISOString(),
  }, null, 2));

  // Save session
  const endCookies = await page.cookies('https://api.clay.com');
  const endSession = endCookies.find(c => c.name === 'claysession');
  if (endSession) saveSession(endSession.value);

  console.log('\n=== People search complete! ===');

  if (args.includes('--auto')) {
    await browser.close();
  } else {
    console.log('Browser stays open. Press Ctrl+C to close.\n');
    await sleep(600000);
    await browser.close();
  }
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
