/**
 * Clay Lookalike Export Pipeline
 *
 * Flow:
 * 1. Takes a list of seed domains as input (up to 10 per batch)
 * 2. Opens Clay via Puppeteer stealth, expands "Lookalike companies" section
 * 3. Inputs seed domains comma-separated into the Lookalike input field
 * 4. Exports companies WITHOUT enrichments (free, 0 credits)
 * 5. If >10 domains, runs multiple batches and merges results (dedup by domain)
 *
 * Usage:
 *   node clay_lookalike_export.js "domain1.com,domain2.com,domain3.com"
 *   node clay_lookalike_export.js --file domains.txt
 *   node clay_lookalike_export.js --test
 *   node clay_lookalike_export.js --login-only
 *
 * Output:
 *   exports/lookalike_results.json  — merged + deduped companies
 *   exports/lookalike_batch_N.json  — per-batch raw results
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const WORKSPACE_ID = '889252';
const OUT_DIR = path.join(__dirname, 'exports');
const SESSION_FILE = path.join(__dirname, '../clay/clay_session.json');
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36';
const BATCH_SIZE = 10; // Clay allows max 10 domains per lookalike search

// ============================================================
// Session management (same as clay_tam_export.js)
// ============================================================

function loadSession() {
  try {
    if (fs.existsSync(SESSION_FILE)) {
      const data = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));
      if (data.value) return data;
    }
  } catch {}
  return {
    value: 's%3AsydgrI74YLdGMrU8LWzQSmCv-IrJgDYg.FYCecoCtfmRICI19MVyPsTXRxlfUAfoeKSLns5ofeGw',
    savedAt: null,
  };
}

function saveSession(cookieValue) {
  fs.writeFileSync(SESSION_FILE, JSON.stringify({ value: cookieValue, savedAt: new Date().toISOString() }, null, 2));
  console.log('  Session saved to clay_session.json');
}

async function setSessionCookie(page, cookieValue) {
  await page.setCookie({
    name: 'claysession', value: cookieValue,
    domain: 'api.clay.com', path: '/', httpOnly: true, secure: true, sameSite: 'None',
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

async function refreshSession(browser, page) {
  console.log('\n[AUTH] Session expired — opening Clay login page...');
  await page.goto('https://app.clay.com/login', { waitUntil: 'networkidle2', timeout: 30000 });
  for (let i = 0; i < 100; i++) {
    await sleep(3000);
    const cookies = await page.cookies('https://api.clay.com');
    const sc = cookies.find(c => c.name === 'claysession');
    if (sc) {
      const check = await validateSession(page);
      if (check.valid) {
        console.log('  [AUTH] Login detected!');
        saveSession(sc.value);
        return sc.value;
      }
    }
    if (i % 10 === 0 && i > 0) console.log(`  [AUTH] Still waiting... (${i * 3}s)`);
  }
  throw new Error('Login timeout after 5 minutes');
}

// ============================================================
// Puppeteer helpers
// ============================================================

function humanDelay(min = 800, max = 2500) {
  return new Promise(r => setTimeout(r, min + Math.random() * (max - min)));
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function screenshot(page, name) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(OUT_DIR, `${name}.png`), fullPage: false });
  console.log(`  [img] ${name}.png`);
}

async function findByText(page, text, exact = true) {
  return page.evaluate((text, exact) => {
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walk.nextNode()) {
      const node = walk.currentNode;
      const match = exact ? node.textContent.trim() === text : node.textContent.trim().includes(text);
      if (match && node.parentElement?.offsetParent !== null) {
        const rect = node.parentElement.getBoundingClientRect();
        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
      }
    }
    return null;
  }, text, exact);
}

// Type tag-style values into a Clay filter input (industries, sizes, keywords)
async function fillFilterField(page, placeholder, values) {
  if (!values || values.length === 0) return false;
  const input = await page.$(`input[placeholder*="${placeholder}"]`);
  if (!input) { console.log(`    Filter "${placeholder}" not found`); return false; }
  for (const value of values) {
    await humanDelay(300, 600);
    await input.click();
    await humanDelay(200, 400);
    await input.type(value, { delay: 30 + Math.random() * 40 });
    await humanDelay(500, 900);
    await page.keyboard.press('Enter');
    await humanDelay(300, 500);
  }
  console.log(`    ${placeholder}: ${values.join(', ')}`);
  return true;
}

// ============================================================
// Apply optional filters: geo, size, industries_exclude, keywords_exclude
// ============================================================

async function applyFilters(page, filters) {
  const { geo, size, industriesExclude, keywordsExclude } = filters;
  const hasFilters = (geo?.length || size?.length || industriesExclude?.length || keywordsExclude?.length);
  if (!hasFilters) return;

  console.log('\n  Applying filters...');

  // Size — "Company sizes" section, placeholder "11-50 employees"
  if (size?.length) {
    await fillFilterField(page, '11-50 employees', size);
  }

  // Industries exclude — placeholder "Advertising services"
  if (industriesExclude?.length) {
    await fillFilterField(page, 'Advertising services', industriesExclude);
  }

  // Description keywords exclude — placeholder "agency, marketing"
  if (keywordsExclude?.length) {
    await fillFilterField(page, 'agency, marketing', keywordsExclude);
  }

  // Geo — Location section needs to be expanded first
  if (geo?.length) {
    // Scroll sidebar to find Location section
    await page.evaluate(() => {
      const scrollables = [...document.querySelectorAll('*')].filter(el => {
        const s = window.getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return (s.overflowY === 'auto' || s.overflowY === 'scroll') && r.x < 400 && r.width > 150 && r.height > 200;
      });
      scrollables.forEach(el => { el.scrollTop = 0; }); // scroll back to top first
    });
    await humanDelay(500, 800);

    // Find and click Location section
    const locCoords = await page.evaluate(() => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        if (walker.currentNode.textContent?.trim() === 'Location') {
          const el = walker.currentNode.parentElement;
          if (!el) continue;
          const rect = el.getBoundingClientRect();
          if (rect.x > 400) continue;
          el.scrollIntoView({ behavior: 'instant', block: 'center' });
          let target = el;
          for (let i = 0; i < 5; i++) {
            if (!target.parentElement) break;
            target = target.parentElement;
            const r = target.getBoundingClientRect();
            if (r.width > 150 && r.height > 20 && r.height < 80) {
              return { x: r.x + r.width / 2, y: r.y + r.height / 2, found: true };
            }
          }
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, found: true };
        }
      }
      return { found: false };
    });

    if (locCoords.found) {
      const checkCountryInput = async () =>
        await page.$('input[placeholder*="United States"]')
        || await page.$('input[placeholder*="country"]')
        || await page.$('input[placeholder*="Country"]')
        || await page.$('input[placeholder*="location"]');

      // Try up to 4 times to expand Location section
      let countryInput = null;
      for (let attempt = 0; attempt < 4 && !countryInput; attempt++) {
        if (attempt === 0) {
          await page.mouse.click(locCoords.x, locCoords.y);
        } else if (attempt === 1) {
          // Try clicking slightly left (on the text, not the chevron)
          await page.mouse.click(locCoords.x - 30, locCoords.y);
        } else if (attempt === 2) {
          // Try React dispatchEvent
          await page.evaluate((x, y) => {
            const el = document.elementFromPoint(x, y);
            if (el) {
              el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
              let p = el.parentElement;
              for (let i = 0; i < 4 && p; i++, p = p.parentElement) {
                p.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
              }
            }
          }, locCoords.x, locCoords.y);
        } else {
          // Last resort: find Location text and walk up further
          await page.evaluate(() => {
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            while (walker.nextNode()) {
              if (walker.currentNode.textContent?.trim() === 'Location') {
                let el = walker.currentNode.parentElement;
                for (let i = 0; i < 6 && el; i++, el = el.parentElement) {
                  el.click();
                  el.dispatchEvent(new MouseEvent('click', { bubbles: true }));
                }
                break;
              }
            }
          });
        }
        await humanDelay(1000, 1500);
        countryInput = await checkCountryInput();
        if (!countryInput) console.log(`    Location expand attempt ${attempt + 1} failed, retrying...`);
      }

      if (countryInput) {
        for (const country of geo) {
          await countryInput.click();
          await humanDelay(200, 400);
          await countryInput.type(country, { delay: 25 });
          await humanDelay(600, 1000);
          await page.keyboard.press('Enter');
          await humanDelay(300, 500);
        }
        console.log(`    Geo: ${geo.join(', ')}`);
      } else {
        console.log('    WARNING: Country input not found after 4 attempts');
      }
    } else {
      console.log('    WARNING: Location section not found');
    }
  }

  await screenshot(page, 'lookalike_01b_filters_applied');
  console.log('  Filters applied.');
}

// ============================================================
// Expand "Lookalike companies" section and fill domains
// ============================================================

async function fillLookalikeSection(page, domains) {
  console.log(`  Filling lookalike section with ${domains.length} domains...`);

  // Step 1: Scroll sidebar all the way down to make "Lookalike companies" visible
  // Order in Clay sidebar: Company attrs → Location → Exclude companies → Lookalike companies → Products → AI
  console.log('    Scrolling sidebar to bottom...');
  await page.evaluate(() => {
    // Find all scrollable containers in the left sidebar (x < 400)
    const scrollables = [...document.querySelectorAll('*')].filter(el => {
      const s = window.getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return (s.overflowY === 'auto' || s.overflowY === 'scroll')
        && r.x < 400 && r.width > 150 && r.height > 200;
    });
    scrollables.forEach(el => { el.scrollTop = el.scrollHeight; });
  });
  await humanDelay(1500, 2000);
  await screenshot(page, 'lookalike_02a_sidebar_scrolled');

  // Step 2: Find "Lookalike companies" text and scrollIntoView + click
  const clickResult = await page.evaluate(() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.textContent?.trim() === 'Lookalike companies') {
        const parent = node.parentElement;
        if (!parent) continue;

        // ScrollIntoView to make it visible
        parent.scrollIntoView({ behavior: 'instant', block: 'center' });

        // Walk up to find clickable row
        let target = parent;
        for (let i = 0; i < 6; i++) {
          if (!target.parentElement) break;
          target = target.parentElement;
          const r = target.getBoundingClientRect();
          if (r.width > 150 && r.height > 20 && r.height < 80) {
            return { x: r.x + r.width / 2, y: r.y + r.height / 2, found: true };
          }
        }
        const r = parent.getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2, found: true, fallback: true };
      }
    }
    return { found: false };
  });

  if (!clickResult.found) {
    console.log('    ERROR: "Lookalike companies" section not found in DOM!');
    await screenshot(page, 'lookalike_02b_not_found');
    return false;
  }

  await humanDelay(500, 800);
  console.log(`    Clicking "Lookalike companies" at (${Math.round(clickResult.x)}, ${Math.round(clickResult.y)})`);
  await page.mouse.click(clickResult.x, clickResult.y);
  await humanDelay(1500, 2500);
  await screenshot(page, 'lookalike_02_section_expanded');

  // Step 3: Find the Company URLs input — placeholder: "e.g. linkedin.com/company/grow-with-clay"
  let urlInput = await page.$('input[placeholder*="linkedin.com"]')
    || await page.$('input[placeholder*="grow-with-clay"]')
    || await page.$('input[placeholder*="Company URL"]')
    || await page.$('input[placeholder*="company URL"]')
    || await page.$('input[placeholder*="Navigator"]');

  if (!urlInput) {
    // Dump all inputs for debugging
    const allInputs = await page.evaluate(() =>
      [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null)
        .map(i => ({ ph: i.placeholder, y: Math.round(i.getBoundingClientRect().y) }))
    );
    console.log('    All visible inputs:', JSON.stringify(allInputs));

    // Scroll the Lookalike section header back into view, then find its input
    await page.evaluate(() => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        if (walker.currentNode.textContent?.trim() === 'Lookalike companies') {
          walker.currentNode.parentElement?.scrollIntoView({ behavior: 'instant', block: 'start' });
          break;
        }
      }
    });
    await humanDelay(800, 1200);

    // Now find all visible inputs in the sidebar and pick the first non-bad one below y=200
    const inputCoords = await page.evaluate(() => {
      const BAD = ['e.g. 10', 'Min', 'Max', '$1M', '$5M', 'employees', 'Privately',
                   'France', 'Spain', 'New York', 'San Francisco', 'Software development',
                   'Advertising', 'outbound', 'marketing'];
      const inputs = [...document.querySelectorAll('input, textarea')].filter(inp => {
        if (!inp.offsetParent) return false;
        const r = inp.getBoundingClientRect();
        if (r.x >= 500 || r.y < 100 || r.y > 600) return false;
        return !BAD.some(bad => inp.placeholder.includes(bad));
      });
      if (inputs.length === 0) return null;
      // Prefer inputs with URL-like placeholder, otherwise take first
      const urlInput = inputs.find(i => i.placeholder.includes('linkedin') || i.placeholder.includes('http') || i.placeholder.includes('.com'));
      const target = urlInput || inputs[0];
      const r = target.getBoundingClientRect();
      return { x: r.x + 10, y: r.y + r.height / 2, placeholder: target.placeholder };
    });

    if (!inputCoords) {
      console.log('    ERROR: Company URLs input not found after section expand!');
      // Dump visible inputs for debugging
      const debugInputs = await page.evaluate(() =>
        [...document.querySelectorAll('input, textarea')].filter(i => i.offsetParent !== null)
          .map(i => ({ ph: i.placeholder, y: Math.round(i.getBoundingClientRect().y), x: Math.round(i.getBoundingClientRect().x) }))
          .filter(i => i.x < 500)
      );
      console.log('    Debug inputs:', JSON.stringify(debugInputs));
      return false;
    }

    console.log(`    Found input via proximity: "${inputCoords.placeholder}"`);
    await page.mouse.click(inputCoords.x, inputCoords.y);
    await humanDelay(300, 500);
    await page.keyboard.type(domains.join(', '), { delay: 20 });
    await humanDelay(800, 1200);
    await screenshot(page, 'lookalike_03_domains_entered');
    console.log(`    Typed: ${domains.join(', ')}`);
    return true;
  }

  // Step 4: Type domains into the Company URLs input
  await urlInput.click();
  await humanDelay(300, 500);
  await urlInput.type(domains.join(', '), { delay: 25 });
  await humanDelay(800, 1200);
  await screenshot(page, 'lookalike_03_domains_entered');
  console.log(`    Domains entered: ${domains.join(', ')}`);
  return true;
}

// ============================================================
// Continue → Table creation (same logic as clay_tam_export.js)
// ============================================================

async function proceedToTable(page) {
  console.log('\n  Clicking Continue → Save to new workbook and table...');

  const continueBtnInfo = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null);
    const btn = buttons.find(b => b.textContent?.trim().startsWith('Continue'));
    if (!btn) return null;
    const rect = btn.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, right: rect.x + rect.width - 8 };
  });

  if (!continueBtnInfo) {
    console.log('  Continue button not found!');
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
    const clickX = attempt < 2 ? continueBtnInfo.right : continueBtnInfo.x;
    await page.mouse.click(clickX, continueBtnInfo.y);
    await humanDelay(1200, 2000);
    option = await findDropdownOption();
  }

  if (option) {
    console.log(`  Found: "${option.text}" — clicking...`);
    await page.mouse.click(option.x, option.y);
  } else {
    console.log('  Dropdown not found — trying direct Continue click');
    await page.mouse.click(continueBtnInfo.x, continueBtnInfo.y);
  }

  await humanDelay(5000, 8000);

  // Extract table ID from URL
  const extractIdsFromUrl = (url) => {
    const tableMatch = url.match(/tableId=([^&]+)/);
    const pathMatch = url.match(/tables\/([^/?]+)/);
    return tableMatch?.[1] || pathMatch?.[1] || null;
  };

  let tableId = null;
  for (let i = 0; i < 15 && !tableId; i++) {
    tableId = extractIdsFromUrl(page.url());
    if (!tableId) { await sleep(2000); console.log(`  Waiting for table... (${i + 1}/15)`); }
  }

  // Handle "Enrich Companies" page — skip enrichments, create table
  const isEnrichPage = await page.evaluate(() =>
    document.body.textContent?.includes('Enrich Companies') ||
    document.body.textContent?.includes('Select enrichments')
  );

  if (isEnrichPage) {
    console.log('  On Enrich page — skipping enrichments, clicking Create table...');
    await humanDelay(1500, 2500);
    const createBtn = await findByText(page, 'Create table', false);
    if (createBtn) {
      await page.mouse.click(createBtn.x, createBtn.y);
      await humanDelay(8000, 12000);
      // Update tableId from new URL
      const newTableId = extractIdsFromUrl(page.url());
      if (newTableId) tableId = newTableId;
    }
  }

  console.log(`  Table ID: ${tableId}`);
  return tableId;
}

// ============================================================
// Read table data via Clay internal API
// ============================================================

async function readTableData(page, tableId) {
  console.log(`\n  Reading table data (${tableId})...`);
  await humanDelay(10000, 15000);
  await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(5000, 8000);

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
  for (const field of tableMeta?.table?.fields || []) {
    fieldMap[field.id] = field.name;
  }
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

  // Get view ID and record IDs
  const viewIdMatch = page.url().match(/views\/([^/?&]+)/);
  const viewId = viewIdMatch?.[1] || tableMeta?.table?.firstViewId;

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

  // Fetch records in batches of 200, with retry if data not yet loaded
  const allRawRecords = [];
  for (let i = 0; i < recordIds.length; i += 200) {
    const batch = recordIds.slice(i, i + 200);

    let batchData = null;
    for (let attempt = 0; attempt < 5; attempt++) {
      batchData = await page.evaluate(async (tid, ids) => {
        try {
          const res = await fetch(`https://api.clay.com/v3/tables/${tid}/bulk-fetch-records`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
            body: JSON.stringify({ recordIds: ids }),
          });
          const json = await res.json();
          return { status: res.status, json, keys: Object.keys(json) };
        } catch (e) { return { error: e.message }; }
      }, tableId, batch);

      // Log raw response on first attempt
      if (attempt === 0) {
        console.log(`  Raw response keys: ${JSON.stringify(batchData?.keys)}`);
        console.log(`  Status: ${batchData?.status}, sample: ${JSON.stringify(batchData?.json)?.substring(0, 200)}`);
      }

      // API returns { results: [...] } with cells, not { records: [...] } with cellValuesByFieldId
      const fetched = batchData?.json?.results || [];
      if (fetched.length > 0) { batchData = batchData.json; break; }

      // Data not ready yet — wait and retry
      console.log(`  Batch ${i/200 + 1}: empty (attempt ${attempt + 1}/5), waiting 15s...`);
      await sleep(15000);
    }
    batchData = batchData?.json || batchData;

    allRawRecords.push(...(batchData?.results || []));
    console.log(`  Fetched ${allRawRecords.length}/${recordIds.length} records...`);
  }

  // Normalize: cells[fieldId].value → fieldName
  return allRawRecords.map(record => {
    const normalized = {};
    for (const [fieldId, cell] of Object.entries(record.cells || {})) {
      const fieldName = fieldMap[fieldId] || fieldId;
      // cells structure: { value: { ... }, metadata: { ... } }
      const raw = cell?.value;
      // Handle option values (dropdowns)
      if (raw && typeof raw === 'object' && raw.optionIds) {
        normalized[fieldName] = raw.optionIds;
      } else {
        normalized[fieldName] = raw ?? null;
      }
    }
    return normalized;
  });
}

// ============================================================
// Main
// ============================================================

async function main() {
  const args = process.argv.slice(2);
  const isTest = args.includes('--test');
  const isLoginOnly = args.includes('--login-only');
  const headless = args.includes('--headless');

  // Parse domains
  let domains = [];

  // Parse filter flags
  // --geo "United States,India"
  // --size "11-50 employees,51-200 employees"
  // --exclude-industries "Staffing and Recruiting,Education"
  // --exclude-keywords "agency,freelance,job board"
  const parseFlag = (flag) => {
    const idx = args.indexOf(flag);
    if (idx === -1 || !args[idx + 1]) return [];
    return args[idx + 1].split(',').map(s => s.trim()).filter(Boolean);
  };

  let filters = { geo: [], size: [], industriesExclude: [], keywordsExclude: [] };

  if (isTest) {
    domains = ['grin.co', 'creatoriq.com', 'aspireiq.com', 'mavrck.co', 'traackr.com',
               'captiv8.io', 'izea.com', 'upfluence.com', 'linqia.com', 'influential.co'];
    filters = {
      geo: ['United States', 'United Kingdom', 'Canada'],
      size: ['11-50 employees', '51-200 employees', '201-500 employees'],
      industriesExclude: ['Staffing and Recruiting', 'Higher Education'],
      keywordsExclude: ['agency', 'freelance'],
    };
    console.log('  [TEST] Using 10 seed domains + test filters');
  } else if (!isLoginOnly) {
    filters = {
      geo: parseFlag('--geo'),
      size: parseFlag('--size'),
      industriesExclude: parseFlag('--exclude-industries'),
      keywordsExclude: parseFlag('--exclude-keywords'),
    };

    // Check for --file flag
    const fileFlag = args.indexOf('--file');
    if (fileFlag !== -1 && args[fileFlag + 1]) {
      const filePath = args[fileFlag + 1];
      const content = fs.readFileSync(filePath, 'utf-8');
      domains = content.split(/[\n,]+/).map(d => d.trim().replace(/^https?:\/\//, '')).filter(Boolean);
    } else {
      // Domains as first positional arg, comma-separated
      const domainArg = args.filter(a => !a.startsWith('--') && !args[args.indexOf(a) - 1]?.startsWith('--')).join(' ');
      domains = domainArg.split(/[\s,]+/).map(d => d.trim().replace(/^https?:\/\//, '')).filter(Boolean);
    }
  }

  if (!domains.length && !isLoginOnly) {
    console.log('Usage:');
    console.log('  node clay_lookalike_export.js "domain1.com,domain2.com,..."');
    console.log('  node clay_lookalike_export.js --file domains.txt');
    console.log('  node clay_lookalike_export.js --geo "United States,India" --size "11-50 employees,51-200 employees"');
    console.log('  node clay_lookalike_export.js --exclude-industries "Staffing" --exclude-keywords "agency,freelance"');
    console.log('  node clay_lookalike_export.js --test');
    process.exit(0);
  }

  // Split into batches of BATCH_SIZE (max 10)
  const batches = [];
  for (let i = 0; i < domains.length; i += BATCH_SIZE) {
    batches.push(domains.slice(i, i + BATCH_SIZE));
  }

  console.log(`\n=== Clay Lookalike Export Pipeline ===`);
  console.log(`Seed domains: ${domains.length} total → ${batches.length} batch(es) of max ${BATCH_SIZE}`);
  console.log(`Domains: ${domains.join(', ')}`);

  fs.mkdirSync(OUT_DIR, { recursive: true });

  // Launch browser
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

  // Load session
  const session = loadSession();
  await setSessionCookie(page, session.value);

  // Validate / refresh session
  console.log('\n[1] Validating session...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  let sessionCheck = await validateSession(page);
  if (!sessionCheck.valid) {
    const newCookie = await refreshSession(browser, page);
    await setSessionCookie(page, newCookie);
    await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(2000, 3000);
    sessionCheck = await validateSession(page);
    if (!sessionCheck.valid) throw new Error('Session still invalid after re-login');
  }

  console.log(`  Session valid. Credits: ${JSON.stringify(sessionCheck.credits)}`);

  if (isLoginOnly) {
    const cookies = await page.cookies('https://api.clay.com');
    const sc = cookies.find(c => c.name === 'claysession');
    if (sc) saveSession(sc.value);
    await browser.close();
    console.log('\n=== Login-only mode done ===');
    return;
  }

  // Process each batch
  const allResults = [];
  const seenDomains = new Set();

  for (let batchIdx = 0; batchIdx < batches.length; batchIdx++) {
    const batch = batches[batchIdx];
    console.log(`\n=== BATCH ${batchIdx + 1}/${batches.length}: ${batch.join(', ')} ===`);

    // Navigate to Find Companies (fresh each batch)
    console.log('\n[2] Opening Find Companies...');
    await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(2000, 3000);

    // Click "Find leads"
    await page.evaluate(() => {
      const els = [...document.querySelectorAll('button, div[role="button"], a')];
      const el = els.find(e => e.textContent?.includes('Find leads'));
      if (el) el.click();
    });
    await humanDelay(1500, 2500);

    // Select Companies tab
    const compBtn = await findByText(page, 'Companies');
    if (compBtn) {
      await page.mouse.click(compBtn.x, compBtn.y);
      await humanDelay(1500, 2500);
    }

    await screenshot(page, `lookalike_01_batch${batchIdx + 1}_find_companies`);

    // Apply filters (geo, size, industries exclude, keywords exclude)
    await applyFilters(page, filters);

    // Fill lookalike section
    const filled = await fillLookalikeSection(page, batch);
    if (!filled) {
      console.log(`  Batch ${batchIdx + 1} FAILED: could not fill lookalike section`);
      continue;
    }

    // Log result count
    await humanDelay(2000, 3000);
    const resultCountText = await page.evaluate(() => {
      const el = [...document.querySelectorAll('*')].find(e =>
        e.textContent?.includes('results') && e.innerText?.length < 50
      );
      return el?.innerText?.trim() || 'unknown';
    });
    console.log(`  Results preview: ${resultCountText}`);

    // Proceed to table
    const tableId = await proceedToTable(page);
    if (!tableId) {
      console.log(`  Batch ${batchIdx + 1} FAILED: no table ID`);
      continue;
    }

    // Read table data
    const records = await readTableData(page, tableId);
    console.log(`  Batch ${batchIdx + 1}: ${records.length} companies found`);

    // Save batch results
    const batchFile = path.join(OUT_DIR, `lookalike_batch_${batchIdx + 1}.json`);
    fs.writeFileSync(batchFile, JSON.stringify({ batch, tableId, records }, null, 2));
    console.log(`  Saved: ${batchFile}`);

    // Merge with dedup by domain
    let newCount = 0;
    for (const rec of records) {
      const domain = rec['Company Domain'] || rec['domain'] || rec['Domain'] || rec['Website'] || '';
      const key = domain.toLowerCase().replace(/^https?:\/\//, '').replace(/\/$/, '');
      if (key && seenDomains.has(key)) continue;
      if (key) seenDomains.add(key);
      allResults.push(rec);
      newCount++;
    }
    console.log(`  New after dedup: ${newCount} (total: ${allResults.length})`);

    // Save session cookie after each batch
    const cookies = await page.cookies('https://api.clay.com');
    const sc = cookies.find(c => c.name === 'claysession');
    if (sc) saveSession(sc.value);

    // Small pause between batches
    if (batchIdx < batches.length - 1) {
      console.log('\n  Pausing 5s before next batch...');
      await sleep(5000);
    }
  }

  await browser.close();

  // Save merged results
  const outputFile = path.join(OUT_DIR, 'lookalike_results.json');
  fs.writeFileSync(outputFile, JSON.stringify({
    meta: {
      seed_domains: domains,
      total_batches: batches.length,
      total_results: allResults.length,
      exported_at: new Date().toISOString(),
    },
    companies: allResults,
  }, null, 2));

  console.log(`\n=== Done ===`);
  console.log(`Total companies found: ${allResults.length} (deduped)`);
  console.log(`Output: ${outputFile}`);
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
