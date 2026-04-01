/**
 * Clay People Search — Full UI automation with CSV export
 *
 * EVERYTHING happens via UI. No direct API calls for search or data.
 * Only internal API used: credit check (validation) and reading table data
 * as fallback if CSV export fails.
 *
 * System-level: supports filter splitting for >5000 results.
 *
 * Two modes:
 * A) ENRICHMENT MODE (--table-id): Navigate to companies table → Add column → Find People
 *    1. Open TAM companies table by ID
 *    2. Click "+ Add" → search "Find People" enrichment
 *    3. Clay opens People search with table pre-linked
 *    4. Apply filters (countries-exclude, job titles)
 *    5. Continue → Create table → read results
 *    This is the CORRECT Clay workflow — table is pre-linked, no dropdown needed.
 *
 * B) LEGACY DOMAIN MODE (--domains-file or default): Types domains one by one into UI.
 *    Slow fallback — only use if you don't have a companies table.
 *
 * Usage:
 *   node clay_people_search.js --table-id t_xxxxx --auto --headless                          # Enrichment mode (fast)
 *   node clay_people_search.js --table-id t_xxxxx --countries-exclude "United States" --auto  # Exclude US people
 *   node clay_people_search.js --domains-file domains.csv --auto                              # Legacy domain mode
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

let WORKSPACE_ID = process.env.CLAY_WORKSPACE_ID || '588071'; // Will be resolved dynamically from /me API
const OUT_DIR = path.join(__dirname, 'exports');
const DOWNLOADS_DIR = path.join(OUT_DIR, 'downloads');
const SESSION_FILE = path.join(__dirname, 'clay_session.json');
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36';

// ============================================================
// Gaming Skins ICP — filter config
// ============================================================
// Strategy: use the "Companies" domain input to target SPECIFIC known gaming companies
// rather than broad industry filters (which don't work well in People tab).
// Load domains from pipeline CSV (verified gaming ICP).

function loadKnownDomains() {
  const domains = new Set();
  // Pipeline CSV = verified gaming ICP domains (team xlsx + Yandex/Google search)
  const csvPath = path.join(__dirname, 'inxy_gaming_companies.csv');
  if (fs.existsSync(csvPath)) {
    const lines = fs.readFileSync(csvPath, 'utf-8').split('\n');
    for (const line of lines) {
      const d = line.trim().toLowerCase();
      if (d && d !== 'website' && d.includes('.')) {
        domains.add(d.replace(/^www\./, ''));
      }
    }
  }
  // Clay TAM domains
  const tamPath = path.join(OUT_DIR, 'tam_companies.json');
  if (fs.existsSync(tamPath)) {
    const companies = JSON.parse(fs.readFileSync(tamPath, 'utf-8'));
    for (const c of companies) {
      const d = (c.Domain || '').toLowerCase().trim().replace(/^www\./, '');
      if (d) domains.add(d);
    }
  }
  return [...domains];
}

const GAMING_ICP_FILTERS = {
  // company_domains will be filled from CSV at runtime
  company_domains: [],
  // job_titles: pass --titles flag to enable title filtering
  job_titles: [],
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
  return page.evaluate(async (wsId) => {
    try {
      const res = await fetch(`https://api.clay.com/v3/subscriptions/${wsId}`, {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      const d = await res.json();
      return d.creditBalances;
    } catch { return null; }
  }, WORKSPACE_ID);
}

async function validateSession(page) {
  return page.evaluate(async (wsId) => {
    try {
      const res = await fetch(`https://api.clay.com/v3/subscriptions/${wsId}`, {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      if (res.status === 401 || res.status === 403) return { valid: false };
      const data = await res.json();
      return { valid: !!data.creditBalances, credits: data.creditBalances };
    } catch (e) { return { valid: false, error: e.message }; }
  }, WORKSPACE_ID);
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
// Table mode: create domains-only table from TAM table
// ============================================================

// ============================================================
// ENRICHMENT MODE: Add "Find People" column from companies table
// ============================================================
// This is the CORRECT Clay workflow:
// 1. Navigate to companies table
// 2. Click "+ Add" column
// 3. Select "Find People" enrichment
// 4. Clay opens People search with table pre-linked
// 5. Apply filters (countries-exclude, etc.)
// 6. Continue → Create table → read results

async function navigateToTable(page, tableId) {
  // Get table metadata to build correct URL
  console.log('  Fetching table metadata...');
  const tableInfo = await page.evaluate(async (tid) => {
    try {
      const tableRes = await fetch(`https://api.clay.com/v3/tables/${tid}`, {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      const tableData = await tableRes.json();
      const table = tableData?.table || tableData;
      const meRes = await fetch('https://api.clay.com/v3/me', {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      const me = await meRes.json();
      return {
        workbookId: table?.workbookId,
        firstViewId: table?.firstViewId,
        name: table?.name,
        wsId: me?.sessionState?.last_workspace_visited_id,
      };
    } catch (e) { return { error: e.message }; }
  }, tableId);

  const wsId = tableInfo?.wsId || WORKSPACE_ID;
  let tableUrl;
  if (tableInfo?.workbookId && tableInfo?.firstViewId) {
    tableUrl = `https://app.clay.com/workspaces/${wsId}/workbooks/${tableInfo.workbookId}/tables/${tableId}/views/${tableInfo.firstViewId}`;
  } else {
    tableUrl = `https://app.clay.com/workspaces/${wsId}/tables/${tableId}`;
  }
  console.log(`  Table: "${tableInfo?.name}" → ${tableUrl}`);
  await page.goto(tableUrl, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(3000, 5000);
  return tableInfo;
}

async function runEnrichmentPeopleSearch(page, tableId, filters, label = 'enrichment') {
  console.log(`\n=== ENRICHMENT MODE: Find People from companies table ===`);
  console.log(`  Table: ${tableId}`);
  console.log(`  Filters: ${JSON.stringify(filters)}`);

  // Step 1: Navigate to the companies table
  console.log('\n[1] Navigating to companies table...');
  const tableInfo = await navigateToTable(page, tableId);
  await screenshot(page, `${label}_01_companies_table`);

  // Step 2: Click "+ Add" column button
  // The "Add column" button is at the far right of the table header — often off-screen.
  // Strategy: scroll it into view first, then click.
  console.log('\n[2] Looking for "Add" column button...');

  const addBtn = await page.evaluate(() => {
    // Find ALL elements containing "Add column" text
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const text = node.textContent?.trim();
      if (text === 'Add column' || text === '+ Add column') {
        const el = node.parentElement;
        if (el && el.offsetParent !== null) {
          // Scroll it into view first!
          el.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' });
          // Wait a frame for reflow
          return new Promise(resolve => {
            requestAnimationFrame(() => {
              const r = el.getBoundingClientRect();
              resolve({ x: r.x + r.width / 2, y: r.y + r.height / 2, text });
            });
          });
        }
      }
    }

    // Fallback: scroll the table grid container to the far right to reveal the button
    const gridContainers = [...document.querySelectorAll('*')].filter(el => {
      const s = window.getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return (s.overflowX === 'auto' || s.overflowX === 'scroll') && r.width > 400 && r.height > 200;
    });
    for (const gc of gridContainers) {
      gc.scrollLeft = gc.scrollWidth;
    }
    return null;
  });

  if (addBtn) {
    // Need a small delay after scrollIntoView
    await humanDelay(500, 800);
    // Re-read position after scroll
    const freshPos = await page.evaluate((text) => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        if (walker.currentNode.textContent?.trim() === text || walker.currentNode.textContent?.trim() === '+ Add column') {
          const el = walker.currentNode.parentElement;
          if (el && el.offsetParent !== null) {
            const r = el.getBoundingClientRect();
            if (r.x > 0 && r.x < window.innerWidth && r.y > 0 && r.y < window.innerHeight) {
              return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
            }
          }
        }
      }
      return null;
    }, addBtn.text || 'Add column');

    const clickTarget = freshPos || addBtn;
    console.log(`  Found "Add column" at (${Math.round(clickTarget.x)}, ${Math.round(clickTarget.y)})`);
    await page.mouse.click(clickTarget.x, clickTarget.y);
    await humanDelay(1500, 2500);
    await screenshot(page, `${label}_02_add_menu`);
  } else {
    // After scrolling right, try again
    await humanDelay(1000, 1500);
    const addBtn2 = await findByText(page, 'Add column', false)
      || await findByText(page, '+ Add column', false);
    if (addBtn2) {
      console.log(`  Found "Add column" after scroll at (${Math.round(addBtn2.x)}, ${Math.round(addBtn2.y)})`);
      await page.mouse.click(addBtn2.x, addBtn2.y);
      await humanDelay(1500, 2500);
      await screenshot(page, `${label}_02_add_menu`);
    } else {
      console.log('  ERROR: "Add column" button not found');
      const buttons = await page.evaluate(() =>
        [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null)
          .map(b => ({ text: b.textContent?.trim().substring(0, 30), y: Math.round(b.getBoundingClientRect().y) }))
          .filter(b => b.y < 150)
      );
      console.log('  Top buttons:', JSON.stringify(buttons));
      await screenshot(page, `${label}_02_no_add_button`);
      return null;
    }
  }

  // Step 3: Click "Add enrichment" then find "Find People"
  console.log('\n[3] Looking for "Add enrichment"...');

  // First click "Add enrichment" to open the enrichment browser
  const addEnrichBtn = await findByText(page, 'Add enrichment', false);
  if (addEnrichBtn) {
    console.log('  Clicking "Add enrichment"...');
    await page.mouse.click(addEnrichBtn.x, addEnrichBtn.y);
    await humanDelay(2000, 3000);
    await screenshot(page, `${label}_03_enrichment_browser`);
  } else {
    console.log('  "Add enrichment" not found, trying direct search...');
  }

  // Now search for "Find People" in the enrichment browser
  console.log('  Searching for "Find People"...');
  const searchInput = await page.$('input[placeholder*="Search"]')
    || await page.$('input[placeholder*="search"]')
    || await page.$('input[placeholder*="enrichment"]')
    || await page.$('input[type="search"]');

  if (searchInput) {
    await searchInput.click();
    await humanDelay(200, 400);
    await searchInput.type('Find People', { delay: 30 + Math.random() * 40 });
    await humanDelay(1500, 2500);
    await screenshot(page, `${label}_03b_search_results`);
  }

  // Click "Find people" SOURCE option (not Claygent AI, not enrichment)
  // Search results show: 1) "Create a column with AI..." (Claygent), 2) "Find People at Company" (enrichment),
  // 3) "Find people" (Source • Companies, People, Jobs) — we want #3, the real People Search with filters.
  const findPeopleOpt = await page.evaluate(() => {
    // Find all clickable items in the search results panel
    const items = [...document.querySelectorAll('div, li, a, button')].filter(el => {
      if (!el.offsetParent) return false;
      const rect = el.getBoundingClientRect();
      // Must be in the right-side Tools panel area (x > 900)
      return rect.x > 900 && rect.width > 200 && rect.height > 30 && rect.height < 120;
    });

    for (const item of items) {
      const text = item.textContent?.trim() || '';
      // Match "Find people" with "Source" in the description — this is the real People Search
      if (text.includes('Find people') && text.includes('Source')) {
        const rect = item.getBoundingClientRect();
        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: text.substring(0, 80), type: 'source' };
      }
    }

    // Fallback: look for "Find People at Company" enrichment
    for (const item of items) {
      const text = item.textContent?.trim() || '';
      if (text.includes('Find People at Company')) {
        const rect = item.getBoundingClientRect();
        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: text.substring(0, 80), type: 'enrichment' };
      }
    }

    return null;
  });

  if (!findPeopleOpt) {
    console.log('  ERROR: "Find People" source option not found');
    const menuItems = await page.evaluate(() =>
      [...document.querySelectorAll('div, span, button, a')]
        .filter(el => {
          if (!el.offsetParent) return false;
          const r = el.getBoundingClientRect();
          return r.x > 900 && r.width > 100 && el.textContent?.trim().length > 2 && el.textContent.trim().length < 80;
        })
        .map(el => el.textContent.trim())
        .filter((v, i, arr) => arr.indexOf(v) === i)
        .slice(0, 20)
    );
    console.log('  Panel items:', menuItems.join(' | '));
    await screenshot(page, `${label}_03_no_find_people`);
    return null;
  }

  console.log(`  Found: "${findPeopleOpt.text}" (${findPeopleOpt.type})`);
  await page.mouse.click(findPeopleOpt.x, findPeopleOpt.y);
  await humanDelay(3000, 5000);
  await screenshot(page, `${label}_03_find_people_opened`);

  // Step 4: Configure People search filters
  // The People search should open with the companies table already linked
  console.log('\n[4] Configuring People search filters...');

  // Verify table is pre-selected (informational)
  const tableCheck = await page.evaluate(() => {
    const text = document.body.textContent || '';
    // Look for indicators that a table is linked
    if (text.includes('Table of companies') || text.includes('company table')) {
      return 'Table section visible';
    }
    return 'Table section not found';
  });
  console.log(`  Table check: ${tableCheck}`);

  // Apply "Countries to exclude" filter
  if (filters.countries_exclude?.length) {
    console.log(`  Applying countries to exclude: ${filters.countries_exclude.join(', ')}...`);

    // The left sidebar has collapsible accordion sections. We need to:
    // 1. Find and click "Location" section header to expand it
    // 2. Inside expanded Location, find the "Countries to exclude" input

    // First, find the sidebar scrollable container
    const sidebarInfo = await page.evaluate(() => {
      // The filter sidebar is the left panel (x < 400, has overflow-y)
      const scrollable = [...document.querySelectorAll('*')].filter(el => {
        const s = window.getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return (s.overflowY === 'auto' || s.overflowY === 'scroll') && r.x < 50 && r.width > 200 && r.width < 500 && r.height > 200;
      });
      if (scrollable.length > 0) {
        const sb = scrollable[0];
        return { found: true, scrollTop: sb.scrollTop, scrollHeight: sb.scrollHeight, clientHeight: sb.clientHeight };
      }
      return { found: false };
    });
    console.log(`    Sidebar: ${JSON.stringify(sidebarInfo)}`);

    // Scroll sidebar to make "Location" visible and click it
    const locationClicked = await page.evaluate(() => {
      // Find sidebar scrollable
      const scrollable = [...document.querySelectorAll('*')].filter(el => {
        const s = window.getComputedStyle(el);
        const r = el.getBoundingClientRect();
        return (s.overflowY === 'auto' || s.overflowY === 'scroll') && r.x < 50 && r.width > 200 && r.width < 500 && r.height > 200;
      })[0];

      // Find "Location" text node in the sidebar
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walk.nextNode()) {
        const node = walk.currentNode;
        if (node.textContent?.trim() === 'Location') {
          const el = node.parentElement;
          if (!el || !el.offsetParent) continue;
          const rect = el.getBoundingClientRect();
          // Must be in the left sidebar area
          if (rect.x < 400 && rect.width > 50) {
            // Scroll it into view
            el.scrollIntoView({ behavior: 'instant', block: 'center' });
            return { found: true, tag: el.tagName, x: rect.x, y: rect.y };
          }
        }
      }
      return { found: false };
    });
    console.log(`    Location section: ${JSON.stringify(locationClicked)}`);

    await humanDelay(500, 800);

    // Now click the Location section header to expand it
    const locPos = await page.evaluate(() => {
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walk.nextNode()) {
        if (walk.currentNode.textContent?.trim() === 'Location') {
          const el = walk.currentNode.parentElement;
          if (!el || !el.offsetParent) continue;
          const rect = el.getBoundingClientRect();
          if (rect.x < 400 && rect.width > 50 && rect.y > 0 && rect.y < window.innerHeight) {
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
          }
        }
      }
      return null;
    });

    if (locPos) {
      console.log(`    Clicking Location at (${Math.round(locPos.x)}, ${Math.round(locPos.y)})...`);
      await page.mouse.click(locPos.x, locPos.y);
      await humanDelay(1500, 2500);
      await screenshot(page, `${label}_04a_location_expanded`);
    } else {
      console.log('    WARNING: Location section not found on screen');
    }

    // After expanding Location, look for "Countries to exclude" or similar
    // Debug: list all visible text in the sidebar area
    const sidebarText = await page.evaluate(() => {
      const items = [];
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      while (walk.nextNode()) {
        const node = walk.currentNode;
        const el = node.parentElement;
        if (!el || !el.offsetParent) continue;
        const rect = el.getBoundingClientRect();
        // Left sidebar only (x < 400)
        if (rect.x < 400 && rect.y > 0 && rect.y < window.innerHeight && node.textContent.trim().length > 1) {
          items.push({ text: node.textContent.trim().substring(0, 60), y: Math.round(rect.y) });
        }
      }
      // Deduplicate and sort by y
      return items.filter((v, i, arr) => arr.findIndex(a => a.text === v.text) === i).sort((a, b) => a.y - b.y);
    });
    console.log(`    Sidebar text after Location expand:`);
    for (const item of sidebarText.slice(0, 30)) {
      console.log(`      [y=${item.y}] ${item.text}`);
    }

    // Now find the "Countries to exclude" input
    // Strategy: find text containing "exclude" near the Location section, then find the nearest input/combobox
    const excludeResult = await page.evaluate(() => {
      // Look for any element with "exclude" in its text within the sidebar
      const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      const excludeLabels = [];
      while (walk.nextNode()) {
        const text = walk.currentNode.textContent?.trim().toLowerCase() || '';
        if (text.includes('exclude') && text.includes('countr')) {
          const el = walk.currentNode.parentElement;
          if (el?.offsetParent) {
            const rect = el.getBoundingClientRect();
            if (rect.x < 400 && rect.y > 0 && rect.y < window.innerHeight) {
              excludeLabels.push({ text: walk.currentNode.textContent.trim(), y: rect.y, el });
            }
          }
        }
      }

      if (excludeLabels.length === 0) return { found: false, reason: 'no exclude label found' };

      // For each exclude label, find the nearest input below it
      for (const label of excludeLabels) {
        const container = label.el.closest('div[class]') || label.el.parentElement?.parentElement;
        if (!container) continue;

        // Look for input, combobox, or clickable area near the label
        const inputs = container.querySelectorAll('input, [role="combobox"], [contenteditable]');
        for (const input of inputs) {
          if (input.offsetParent) {
            const rect = input.getBoundingClientRect();
            return { found: true, x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: input.placeholder || '', type: 'direct-child' };
          }
        }

        // Wider search: look for inputs below the label text
        const allInputs = [...document.querySelectorAll('input')].filter(i => {
          if (!i.offsetParent) return false;
          const rect = i.getBoundingClientRect();
          return rect.x < 400 && rect.y > label.y && rect.y < label.y + 100;
        });
        if (allInputs.length > 0) {
          const rect = allInputs[0].getBoundingClientRect();
          return { found: true, x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: allInputs[0].placeholder || '', type: 'below-label' };
        }
      }

      return { found: false, reason: 'found exclude label but no input nearby', labels: excludeLabels.map(l => l.text) };
    });

    console.log(`    Exclude input search: ${JSON.stringify(excludeResult)}`);

    if (excludeResult.found) {
      console.log(`    Found exclude input (${excludeResult.type}): "${excludeResult.placeholder}"`);
      for (const country of filters.countries_exclude) {
        await page.mouse.click(excludeResult.x, excludeResult.y);
        await humanDelay(200, 400);
        await page.keyboard.type(country, { delay: 25 + Math.random() * 30 });
        await humanDelay(1200, 1800); // Wait longer for autocomplete dropdown to fully load

        // IMPORTANT: Don't just press Enter — that selects "United States Minor Outlying Islands"
        // Instead, find and click the EXACT match in the dropdown
        const exactMatch = await page.evaluate((targetCountry) => {
          const options = [...document.querySelectorAll('[role="option"], [role="menuitem"], li, div')].filter(el => {
            if (!el.offsetParent) return false;
            const text = el.textContent?.trim();
            // Exact match — the text should be exactly the country name (not a longer variant)
            return text === targetCountry;
          });
          if (options.length > 0) {
            const rect = options[0].getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: options[0].textContent.trim() };
          }
          return null;
        }, country);

        if (exactMatch) {
          console.log(`      Clicking exact match: "${exactMatch.text}"`);
          await page.mouse.click(exactMatch.x, exactMatch.y);
        } else {
          // Fallback: use arrow keys to navigate past "Minor Outlying Islands" to the real match
          console.log(`      No exact match found, using keyboard navigation...`);
          await page.keyboard.press('ArrowDown');
          await humanDelay(200, 400);
          await page.keyboard.press('Enter');
        }
        await humanDelay(500, 800);
      }
      console.log(`    Countries excluded: ${filters.countries_exclude.join(', ')}`);
    } else {
      console.log(`    WARNING: Countries exclude input not found — ${excludeResult.reason}`);
      // Fallback: try using Sculptor AI chat to apply the filter
      console.log('    Trying Sculptor chat fallback...');
      const sculptorInput = await page.$('input[placeholder*="What are you looking for"]')
        || await page.$('textarea[placeholder*="What are you looking for"]')
        || await page.$('input[placeholder*="looking for"]');
      if (sculptorInput) {
        await sculptorInput.click();
        await humanDelay(200, 400);
        await sculptorInput.type(`Exclude people from ${filters.countries_exclude.join(', ')}`, { delay: 30 });
        await humanDelay(500, 800);
        await page.keyboard.press('Enter');
        await humanDelay(3000, 5000);
        console.log('    Sculptor command sent');
        await screenshot(page, `${label}_04b_sculptor_exclude`);
      } else {
        console.log('    Sculptor input not found either');
      }
    }
  }

  // Apply job title filter if provided
  if (filters.job_titles?.length) {
    const titleInput = await page.$('input[placeholder*="CEO"]')
      || await page.$('input[placeholder*="VP"]')
      || await page.$('input[placeholder*="Director"]');
    if (titleInput) {
      for (const title of filters.job_titles) {
        await titleInput.click();
        await humanDelay(100, 200);
        await titleInput.type(title, { delay: 25 });
        await humanDelay(300, 600);
        await page.keyboard.press('Enter');
        await humanDelay(200, 400);
      }
      console.log(`    Job titles: ${filters.job_titles.join(', ')}`);
    }
  }

  await humanDelay(2000, 3000);
  await screenshot(page, `${label}_04_filters_applied`);

  // Read result count
  const resultText = await page.evaluate(() => {
    const text = document.body.textContent || '';
    const match = text.match(/([\d,]+)\s*(?:people|results|contacts|leads)/i);
    return match ? match[0] : null;
  });
  console.log(`  Result count: ${resultText || 'unknown'}`);

  // Step 5: Click Continue → Save to new workbook and table
  console.log('\n[5] Clicking Continue...');
  const continueBtnInfo = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null);
    const btn = buttons.find(b => b.textContent?.trim().startsWith('Continue'));
    if (!btn) return null;
    const rect = btn.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, right: rect.x + rect.width - 8 };
  });

  if (!continueBtnInfo) {
    console.log('  ERROR: Continue button not found!');
    await screenshot(page, `${label}_05_no_continue`);
    return null;
  }

  // Click the dropdown arrow on Continue button
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
    await screenshot(page, `${label}_05_dropdown_fail`);
    return null;
  }

  // Wait for enrichment page
  await humanDelay(5000, 8000);
  await screenshot(page, `${label}_05_enrich_page`);

  // Extract table ID
  let newTableId = null;
  for (let i = 0; i < 15; i++) {
    const url = page.url();
    const m = url.match(/tableId=([^&]+)/);
    if (m) { newTableId = m[1]; break; }
    const pm = url.match(/tables\/([^/?]+)/);
    if (pm) { newTableId = pm[1]; break; }
    await sleep(2000);
  }
  console.log(`  New table ID: ${newTableId}`);

  // Skip enrichments → Create table
  const createBtn = await findByText(page, 'Create table', false);
  if (createBtn) {
    console.log('  Clicking "Create table"...');
    await page.mouse.click(createBtn.x, createBtn.y);
    await humanDelay(10000, 15000);
    await screenshot(page, `${label}_06_table_created`);
  }

  if (!newTableId) {
    const newUrl = page.url();
    const m = newUrl.match(/tableId=([^&]+)/) || newUrl.match(/tables\/([^/?]+)/);
    if (m) newTableId = m[1];
  }

  if (!newTableId) {
    console.log('  ERROR: No table ID found');
    return null;
  }

  // Step 6: Wait and read results
  console.log('\n[6] Reading results...');
  await humanDelay(12000, 15000);
  await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(5000, 8000);
  await screenshot(page, `${label}_07_table_loaded`);

  // Try CSV export first
  const csvPath = await exportTableCSV(page, label);
  if (csvPath) {
    console.log(`  CSV exported: ${csvPath}`);
    return { tableId: newTableId, csvPath, label };
  }

  // Fallback: read via API
  const records = await readTableFromBrowser(page, newTableId);
  const jsonPath = path.join(OUT_DIR, `people_${label}.json`);
  fs.writeFileSync(jsonPath, JSON.stringify(records, null, 2));
  console.log(`  Saved ${records.length} records to ${jsonPath}`);
  return { tableId: newTableId, jsonPath, records, label };
}

// ============================================================
// LEGACY: Create domains table for standalone People search (deprecated)
// ============================================================

/**
 * Navigate to a TAM companies table, use Tools → Send table data → New table
 * to create a domains-only table that Clay People search can reference.
 *
 * @param {Page} page - Puppeteer page
 * @param {string} tableId - TAM companies table ID (e.g., "t_0tcppy1bH2FqaFgfFYM")
 * @param {string} tableName - Name for the new domains table (e.g., "Arkansas domains")
 * @param {string} [directUrl] - Optional direct URL to navigate to (skips metadata lookup)
 * @returns {string|null} - Name of the created table, or null on failure
 */
async function createDomainsTable(page, tableId, tableName, directUrl) {
  console.log(`\n[TABLE MODE] Creating domains-only table from ${tableId}...`);

  // If a direct URL was provided, use it and skip metadata lookup
  if (directUrl) {
    console.log(`  Navigating to table (direct URL): ${directUrl}`);
    await page.goto(directUrl, { waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(3000, 5000);
    await screenshot(page, 'table_mode_01_source_table');
  } else {
  // Get table metadata via API to build the correct full URL
  console.log('  Fetching table metadata via API...');
  const tableInfo = await page.evaluate(async (tid) => {
    try {
      // Get table metadata
      const tableRes = await fetch(`https://api.clay.com/v3/tables/${tid}`, {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      const tableData = await tableRes.json();
      const table = tableData?.table || tableData;
      // Get user workspace info
      const meRes = await fetch('https://api.clay.com/v3/me', {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      const me = await meRes.json();
      return {
        workbookId: table?.workbookId,
        firstViewId: table?.firstViewId,
        name: table?.name,
        wsId: me?.sessionState?.last_workspace_visited_id,
        tableStatus: tableRes.status,
        meStatus: meRes.status,
      };
    } catch (e) { return { error: e.message }; }
  }, tableId);

  console.log(`  Table metadata: workbook=${tableInfo?.workbookId}, view=${tableInfo?.firstViewId}, ws=${tableInfo?.wsId}, name="${tableInfo?.name}"`);
  if (tableInfo?.error) {
    console.log(`  WARNING: Metadata fetch failed: ${tableInfo.error}`);
  }

  // Build full table URL — Clay REQUIRES /workspaces/{ws}/workbooks/{wb}/tables/{t}/views/{v}
  const wsId = tableInfo?.wsId || WORKSPACE_ID;
  let tableUrl;
  if (tableInfo?.workbookId && tableInfo?.firstViewId) {
    tableUrl = `https://app.clay.com/workspaces/${wsId}/workbooks/${tableInfo.workbookId}/tables/${tableId}/views/${tableInfo.firstViewId}`;
  } else {
    console.log('  WARNING: Missing workbookId or firstViewId — using simple URL (may fail)');
    tableUrl = `https://app.clay.com/workspaces/${wsId}/tables/${tableId}`;
  }
  console.log(`  Navigating to table: ${tableUrl}`);
  await page.goto(tableUrl, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(3000, 5000);
  await screenshot(page, 'table_mode_01_source_table');
  } // end else (no directUrl)

  // Click "Tools" button (top right of table view)
  console.log('  Looking for Tools button...');
  const toolsBtn = await findByText(page, 'Tools', true)
    || await findByText(page, 'Tools', false);
  if (!toolsBtn) {
    console.log('  ERROR: Tools button not found');
    const buttons = await page.evaluate(() =>
      [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null)
        .map(b => b.textContent?.trim().substring(0, 40))
        .filter(t => t && t.length > 1)
    );
    console.log('  Visible buttons:', buttons.join(' | '));
    return null;
  }
  await page.mouse.click(toolsBtn.x, toolsBtn.y);
  await humanDelay(1500, 2500);
  await screenshot(page, 'table_mode_02_tools_panel');

  // The Tools panel has tabs: Sources, Enrichments, Signals, Exports
  // "Send table data" is under the Exports tab
  console.log('  Clicking Exports tab...');
  const exportsTab = await findByText(page, 'Exports', true)
    || await findByText(page, 'Exports', false);
  if (exportsTab) {
    await page.mouse.click(exportsTab.x, exportsTab.y);
    await humanDelay(1000, 1500);
    await screenshot(page, 'table_mode_02b_exports_tab');
  } else {
    console.log('  WARNING: Exports tab not found — trying to find Send table data directly');
  }

  // Look for "Send table data" option
  console.log('  Looking for "Send table data"...');
  const sendDataOpt = await findByText(page, 'Send table data', false)
    || await findByText(page, 'Send to table', false)
    || await findByText(page, 'Export to table', false)
    || await findByText(page, 'Send data', false);
  if (!sendDataOpt) {
    console.log('  ERROR: "Send table data" option not found');
    // Debug: list all visible text in the tools panel
    const panelItems = await page.evaluate(() =>
      [...document.querySelectorAll('div, span, button, a')]
        .filter(el => {
          const r = el.getBoundingClientRect();
          return el.offsetParent !== null && r.x > 300 && el.textContent?.trim().length > 2 && el.textContent.trim().length < 60;
        })
        .map(el => el.textContent.trim())
        .filter((v, i, arr) => arr.indexOf(v) === i)
        .slice(0, 30)
    );
    console.log('  Panel items:', panelItems.join(' | '));
    await page.keyboard.press('Escape');
    return null;
  }
  await page.mouse.click(sendDataOpt.x, sendDataOpt.y);
  await humanDelay(1500, 2500);
  await screenshot(page, 'table_mode_03_send_table_data');

  // Select "New table" option (or similar)
  console.log('  Looking for "New table"...');
  const newTableOpt = await findByText(page, 'New table', false)
    || await findByText(page, 'new table', false)
    || await findByText(page, 'Create new table', false);
  if (newTableOpt) {
    await page.mouse.click(newTableOpt.x, newTableOpt.y);
    await humanDelay(1500, 2500);
  }
  await screenshot(page, 'table_mode_04_new_table_dialog');

  // Name the table if a name input is available
  if (tableName) {
    console.log(`  Setting table name: "${tableName}"...`);
    // Look for name/title input in the dialog
    const nameInput = await page.evaluate(() => {
      const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null);
      for (const input of inputs) {
        const ph = (input.placeholder || '').toLowerCase();
        if (ph.includes('name') || ph.includes('table') || ph.includes('title') || ph === '') {
          const rect = input.getBoundingClientRect();
          // Only consider inputs in the dialog area (center of screen)
          if (rect.width > 100 && rect.y > 100 && rect.y < 700) {
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: input.placeholder };
          }
        }
      }
      return null;
    });
    if (nameInput) {
      await page.mouse.click(nameInput.x, nameInput.y);
      await humanDelay(200, 400);
      // Select all existing text and replace
      await page.keyboard.down('Control');
      await page.keyboard.press('a');
      await page.keyboard.up('Control');
      await humanDelay(100, 200);
      await page.keyboard.type(tableName, { delay: 25 + Math.random() * 30 });
      await humanDelay(500, 800);
      console.log(`    Table name set: "${tableName}"`);
    } else {
      console.log('    Name input not found — using default name');
    }
  }

  // Deselect all columns except Domain
  // Clay's "Send table data" dialog shows checkboxes for each column.
  // Strategy: look for column checkboxes/toggles and uncheck all except "Domain".
  console.log('  Configuring columns (Domain only)...');

  // First, try to find a "Deselect all" or "Select none" option
  const deselectAll = await findByText(page, 'Deselect all', false)
    || await findByText(page, 'Select none', false)
    || await findByText(page, 'Uncheck all', false);
  if (deselectAll) {
    await page.mouse.click(deselectAll.x, deselectAll.y);
    await humanDelay(500, 800);
    console.log('    Deselected all columns');
  }

  // Now find and check only the Domain column
  // Look for checkboxes/labels containing "Domain"
  const domainCheckbox = await page.evaluate(() => {
    // Strategy 1: find checkbox or label with "Domain" text
    const allEls = [...document.querySelectorAll('label, span, div, input[type="checkbox"]')];
    for (const el of allEls) {
      if (el.offsetParent === null) continue;
      const text = el.textContent?.trim();
      if (text === 'Domain' || text === 'domain') {
        const rect = el.getBoundingClientRect();
        if (rect.width > 5 && rect.height > 5) {
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text };
        }
      }
    }
    // Strategy 2: check for a list of items with checkboxes
    const items = [...document.querySelectorAll('[class*="checkbox"], [role="checkbox"], input[type="checkbox"]')];
    for (const item of items) {
      const parent = item.closest('label, div, li');
      if (parent?.textContent?.trim().includes('Domain')) {
        const rect = parent.getBoundingClientRect();
        return { x: rect.x + 15, y: rect.y + rect.height / 2, text: parent.textContent.trim().substring(0, 30) };
      }
    }
    return null;
  });

  if (domainCheckbox) {
    await page.mouse.click(domainCheckbox.x, domainCheckbox.y);
    await humanDelay(500, 800);
    console.log(`    Selected Domain column: "${domainCheckbox.text}"`);
  } else {
    console.log('    WARNING: Domain column checkbox not found — all columns may be included');
    // Debug: list visible text in dialog
    const dialogText = await page.evaluate(() => {
      const dialog = document.querySelector('[role="dialog"]') || document.querySelector('.modal') || document.body;
      return [...dialog.querySelectorAll('span, label, div')]
        .filter(el => el.offsetParent !== null && el.textContent?.trim().length > 1 && el.textContent.trim().length < 40)
        .map(el => el.textContent.trim())
        .slice(0, 30);
    });
    console.log('    Dialog text:', dialogText.join(' | '));
  }

  await screenshot(page, 'table_mode_05_columns_configured');

  // Click "Run for all" / "Save and run" / confirmation button
  console.log('  Looking for run/save button...');
  const runBtn = await findByText(page, 'Run for all', false)
    || await findByText(page, 'Run all', false)
    || await findByText(page, 'Save and run', false)
    || await findByText(page, 'Save', true)
    || await findByText(page, 'Create', false)
    || await findByText(page, 'Confirm', false);

  if (runBtn) {
    console.log(`  Clicking "${runBtn.text || 'run button'}"...`);
    await page.mouse.click(runBtn.x, runBtn.y);
    await humanDelay(5000, 8000);
  } else {
    console.log('  WARNING: Run/save button not found — trying Enter key');
    await page.keyboard.press('Enter');
    await humanDelay(5000, 8000);
  }

  await screenshot(page, 'table_mode_06_running');

  // Wait for the new table to be created and domains to populate
  console.log('  Waiting for domains table to populate...');
  await humanDelay(10000, 15000);

  // Check if we navigated to a new table
  const newUrl = page.url();
  const newTableId = newUrl.match(/tableId=([^&]+)/)?.[1]
    || newUrl.match(/tables\/([^/?]+)/)?.[1];

  if (newTableId && newTableId !== tableId) {
    console.log(`  New domains table created: ${newTableId}`);
  }

  await screenshot(page, 'table_mode_07_domains_table_ready');

  // Navigate back to workspace home to reset page state before People search
  console.log('  Navigating back to workspace home to reset page state...');
  const homeWsId = await page.evaluate(async () => {
    const res = await fetch('https://api.clay.com/v3/me', { credentials: 'include' });
    const me = await res.json();
    return me?.sessionState?.last_workspace_visited_id;
  }) || WORKSPACE_ID;
  await page.goto(`https://app.clay.com/workspaces/${homeWsId}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  console.log(`  Domains table "${tableName}" ready`);
  return tableName;
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

  // Apply filters — People tab uses sidebar sections
  // IMPORTANT: Apply job titles FIRST, then domains.
  // Typing 200+ domains makes other inputs hard to find.
  console.log('  Applying filters...');

  // Step A: Job title filter (MUST be before domains)
  if (filters.job_titles?.length) {
    let titleInput = await page.$('input[placeholder*="CEO"]')
      || await page.$('input[placeholder*="VP"]')
      || await page.$('input[placeholder*="Director"]');

    if (!titleInput) {
      // Try clicking "Job title" section to expand it
      const titleSection = await findByText(page, 'Job title', true);
      if (titleSection) {
        await page.mouse.click(titleSection.x, titleSection.y);
        await humanDelay(800, 1200);
      }
      titleInput = await page.$('input[placeholder*="CEO"]')
        || await page.$('input[placeholder*="VP"]')
        || await page.$('input[placeholder*="Director"]');
    }

    if (titleInput) {
      for (const title of filters.job_titles) {
        await titleInput.click();
        await humanDelay(100, 200);
        await titleInput.type(title, { delay: 25 + Math.random() * 30 });
        await humanDelay(300, 600);
        await page.keyboard.press('Enter');
        await humanDelay(200, 400);
      }
      console.log(`    Job titles: ${filters.job_titles.join(', ')}`);
    } else {
      console.log('    WARNING: Job title input not found');
      const allInputs = await page.evaluate(() =>
        [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null)
          .map(i => ({ placeholder: i.placeholder }))
      );
      console.log('    Available inputs:', allInputs.map(i => `"${i.placeholder}"`).join(', '));
    }
    // Dismiss any open dropdown by pressing Escape and clicking neutral area
    await page.keyboard.press('Escape');
    await humanDelay(300, 500);
    await page.mouse.click(650, 400); // Click in the preview area to deselect
    await humanDelay(500, 800);
    await screenshot(page, `${label}_02a_titles`);
  }

  // Step A2: Name filter (last name / surname search)
  if (filters.person_name) {
    console.log(`  Setting name filter: "${filters.person_name}"...`);
    // Look for the Name input — Clay People Search has a "Name" section near the top
    const nameSection = await findByText(page, 'Name', true);
    if (nameSection) {
      await page.mouse.click(nameSection.x, nameSection.y);
      await humanDelay(800, 1200);
    }
    // Find the name input via placeholder patterns
    const nameInputPos = await page.evaluate(() => {
      const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null);
      for (const input of inputs) {
        const ph = (input.placeholder || '').toLowerCase();
        if (ph.includes('john') || ph.includes('name') || ph.includes('person')) {
          const rect = input.getBoundingClientRect();
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: input.placeholder };
        }
      }
      return null;
    });
    if (nameInputPos) {
      console.log(`    Found name input: "${nameInputPos.placeholder}"`);
      await page.mouse.click(nameInputPos.x, nameInputPos.y);
      await humanDelay(100, 200);
      await page.keyboard.type(filters.person_name, { delay: 25 + Math.random() * 30 });
      await humanDelay(500, 800);
      await page.keyboard.press('Enter');
      await humanDelay(300, 500);
      console.log(`    Name filter set: ${filters.person_name}`);
    } else {
      // Try broader search — find any remaining input near top of sidebar
      console.log('    Name input not found by placeholder — trying first unfilled input');
      const allInputs = await page.evaluate(() =>
        [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null)
          .map(i => ({ placeholder: i.placeholder, rect: i.getBoundingClientRect() }))
      );
      console.log('    Available inputs:', allInputs.map(i => `"${i.placeholder}"`).join(', '));
    }
    await page.keyboard.press('Escape');
    await humanDelay(300, 500);
    await page.mouse.click(650, 400);
    await humanDelay(500, 800);
    await screenshot(page, `${label}_02a2_name`);
  }

  // Step B: Company targeting — either via "Table of companies" (fast) or domain typing (legacy)
  if (filters.company_table_name) {
    // TABLE MODE: Select the domains table in "Table of companies" filter
    console.log(`  Selecting table "${filters.company_table_name}" in Table of companies filter...`);

    // Scroll sidebar down to find Companies section
    await page.evaluate(() => {
      const sections = [...document.querySelectorAll('div, section')].filter(el => {
        const style = window.getComputedStyle(el);
        return style.overflowY === 'auto' || style.overflowY === 'scroll';
      });
      for (const s of sections) {
        if (s.scrollHeight > s.clientHeight && s.clientHeight > 200) {
          s.scrollTop = s.scrollHeight;
          break;
        }
      }
    });
    await humanDelay(800, 1200);

    // Expand Companies section
    const compSection = await findByText(page, 'Companies', true)
      || await findByText(page, 'Companies', false);
    if (compSection) {
      await page.mouse.click(compSection.x, compSection.y);
      await humanDelay(1200, 1800);
    }

    // The "Table of companies" section has a dropdown labeled "Select company table"
    // It's a custom React dropdown (not <select> or <input>), so we need to:
    // 1. Click "Select company table" to open the dropdown list
    // 2. Find and click the table name in the dropdown

    // First, try to expand "Table of companies" subsection if collapsed
    const tableOfCompanies = await findByText(page, 'Table of companies', false);
    if (tableOfCompanies) {
      await page.mouse.click(tableOfCompanies.x, tableOfCompanies.y);
      await humanDelay(800, 1200);
      console.log('    Clicked "Table of companies" section');
    }

    await screenshot(page, `${label}_02b_table_section`);

    // Find and click the "Select company table" dropdown
    console.log('    Looking for "Select company table" dropdown...');
    const selectDropdown = await findByText(page, 'Select company table', false)
      || await findByText(page, 'select company table', false)
      || await findByText(page, 'Select table', false);

    if (selectDropdown) {
      console.log(`    Found dropdown at (${Math.round(selectDropdown.x)}, ${Math.round(selectDropdown.y)})`);
      await page.mouse.click(selectDropdown.x, selectDropdown.y);
      await humanDelay(1500, 2000);
      await screenshot(page, `${label}_02b_table_dropdown_open`);

      // The dropdown should now show a list of tables. Find ours by name.
      const tableOption = await findByText(page, filters.company_table_name, false);
      if (tableOption) {
        console.log(`    Found table "${filters.company_table_name}" in dropdown`);
        await page.mouse.click(tableOption.x, tableOption.y);
        await humanDelay(1500, 2000);
        console.log(`    Selected table: "${filters.company_table_name}"`);
      } else {
        console.log(`    Table "${filters.company_table_name}" not found in dropdown. Trying to type and search...`);
        // Some dropdowns have a search input — try typing
        await page.keyboard.type(filters.company_table_name, { delay: 30 + Math.random() * 40 });
        await humanDelay(1000, 1500);
        // Try clicking the first matching option
        const searchResult = await findByText(page, filters.company_table_name, false);
        if (searchResult) {
          await page.mouse.click(searchResult.x, searchResult.y);
          await humanDelay(1000, 1500);
          console.log(`    Selected table via search: "${filters.company_table_name}"`);
        } else {
          await page.keyboard.press('Enter');
          await humanDelay(500, 800);
          console.log(`    Pressed Enter (hoping for first match)`);
        }
      }
    } else {
      // Fallback: look for any dropdown or clickable in the Companies section
      console.log('    "Select company table" not found. Looking for dropdown alternatives...');
      const dropdownAlt = await page.evaluate(() => {
        // Find elements that look like dropdown triggers in the sidebar
        const els = [...document.querySelectorAll('div, button, span')].filter(el => {
          const r = el.getBoundingClientRect();
          const t = (el.textContent || '').toLowerCase().trim();
          return el.offsetParent !== null && r.x < 400 && r.y > 200
            && (t.includes('select') || t.includes('choose') || t.includes('table'))
            && t.length < 40 && r.width > 50;
        });
        for (const el of els) {
          const r = el.getBoundingClientRect();
          return { x: r.x + r.width / 2, y: r.y + r.height / 2, text: el.textContent.trim().substring(0, 40) };
        }
        return null;
      });
      if (dropdownAlt) {
        console.log(`    Found alternative: "${dropdownAlt.text}" — clicking...`);
        await page.mouse.click(dropdownAlt.x, dropdownAlt.y);
        await humanDelay(1500, 2000);
        const tableOpt = await findByText(page, filters.company_table_name, false);
        if (tableOpt) {
          await page.mouse.click(tableOpt.x, tableOpt.y);
          await humanDelay(1000, 1500);
          console.log(`    Selected table: "${filters.company_table_name}"`);
        }
      } else {
        console.log('    WARNING: No dropdown found for table selection!');
        // Debug: dump sidebar content
        const sidebarText = await page.evaluate(() =>
          [...document.querySelectorAll('div, span, label, button')]
            .filter(el => {
              const r = el.getBoundingClientRect();
              return el.offsetParent !== null && r.x < 400 && el.textContent?.trim().length > 2 && el.textContent.trim().length < 50;
            })
            .map(el => el.textContent.trim())
            .filter((v, i, arr) => arr.indexOf(v) === i)
            .slice(0, 30)
        );
        console.log('    Sidebar text:', sidebarText.join(' | '));
      }
    }
    await screenshot(page, `${label}_02b_table_selected`);

  } else if (filters.company_domains?.length) {
    // LEGACY MODE: Type company domains one by one
    console.log(`  [LEGACY] Typing ${filters.company_domains.length} company domains...`);

    // "Companies" section is near the bottom of the sidebar — scroll down to it
    await page.evaluate(() => {
      const sections = [...document.querySelectorAll('div, section')].filter(el => {
        const style = window.getComputedStyle(el);
        return style.overflowY === 'auto' || style.overflowY === 'scroll';
      });
      for (const s of sections) {
        if (s.scrollHeight > s.clientHeight && s.clientHeight > 200) {
          s.scrollTop = s.scrollHeight;
          break;
        }
      }
    });
    await humanDelay(800, 1200);

    const compSection = await findByText(page, 'Companies', true)
      || await findByText(page, 'Companies', false);
    if (compSection) {
      await page.mouse.click(compSection.x, compSection.y);
      await humanDelay(1200, 1800);
    }

    async function findDomainInput() {
      return page.evaluate(() => {
        const selectors = [
          'input[placeholder*="amazon"]',
          'input[placeholder*="microsoft"]',
          'input[placeholder*=".com"]',
        ];
        for (const sel of selectors) {
          const el = document.querySelector(sel);
          if (el && el.offsetParent !== null) {
            const rect = el.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: el.placeholder };
          }
        }
        return null;
      });
    }

    let domainInputPos = await findDomainInput();
    await screenshot(page, `${label}_02b_companies_expanded`);

    if (domainInputPos) {
      console.log(`    Found domain input: "${domainInputPos.placeholder}"`);
      const domainsToType = filters.company_domains.slice(0, 500); // Safety limit
      let typed = 0;

      for (const domain of domainsToType) {
        // Re-find input every 100 domains (it may shift as tags are added)
        if (typed > 0 && typed % 100 === 0) {
          const newPos = await findDomainInput();
          if (newPos) domainInputPos = newPos;
        }
        await page.mouse.click(domainInputPos.x, domainInputPos.y);
        await humanDelay(80, 150);
        await page.keyboard.type(domain, { delay: 15 + Math.random() * 20 });
        await humanDelay(150, 300);
        await page.keyboard.press('Enter');
        await humanDelay(100, 250);
        typed++;
        if (typed % 50 === 0) {
          console.log(`    Typed ${typed}/${domainsToType.length} domains...`);
          await humanDelay(300, 600); // Brief pause every 50
        }
      }
      console.log(`    Companies: typed ${typed} domains`);
    } else {
      console.log('    WARNING: Company domain input not found!');
      const allInputs = await page.evaluate(() =>
        [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null)
          .map(i => ({ placeholder: i.placeholder, rect: i.getBoundingClientRect() }))
      );
      console.log('    Available inputs:', JSON.stringify(allInputs.map(i => i.placeholder)));
    }
    await screenshot(page, `${label}_02b_companies`);
  }

  // Schools section (for university-based search)
  if (filters.schools?.length) {
    // Scroll sidebar down to find Schools section
    await page.evaluate(() => {
      const sections = [...document.querySelectorAll('div, section')].filter(el => {
        const style = window.getComputedStyle(el);
        return style.overflowY === 'auto' || style.overflowY === 'scroll';
      });
      for (const s of sections) {
        if (s.scrollHeight > s.clientHeight && s.clientHeight > 200) {
          s.scrollTop = s.scrollHeight;
          break;
        }
      }
    });
    await humanDelay(800, 1200);

    // Try to find and click Schools section header to expand it
    const schoolSection = await findByText(page, 'Schools', true)
      || await findByText(page, 'School', true)
      || await findByText(page, 'Education', true)
      || await findByText(page, 'Schools', false);
    if (schoolSection) {
      await page.mouse.click(schoolSection.x, schoolSection.y);
      await humanDelay(800, 1200);
      console.log('    Clicked Schools section');
    } else {
      console.log('    Schools section header not found — trying direct input');
    }
    // Find school input via evaluate (more reliable than CSS selector)
    const schoolInputPos = await page.evaluate(() => {
      const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null);
      for (const input of inputs) {
        const ph = (input.placeholder || '').toLowerCase();
        if (ph.includes('mcgill') || ph.includes('mcmaster') || ph.includes('university') || ph.includes('school')) {
          const rect = input.getBoundingClientRect();
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: input.placeholder };
        }
      }
      return null;
    });
    if (schoolInputPos) {
      console.log(`    Found school input: "${schoolInputPos.placeholder}"`);
      for (const school of filters.schools) {
        await page.mouse.click(schoolInputPos.x, schoolInputPos.y);
        await humanDelay(100, 200);
        await page.keyboard.type(school, { delay: 25 + Math.random() * 30 });
        await humanDelay(800, 1200);
        // Wait for dropdown, then press Enter to select first option
        await page.keyboard.press('Enter');
        await humanDelay(400, 700);
      }
      console.log(`    Schools: ${filters.schools.join(', ')}`);
    } else {
      console.log('    WARNING: School input not found');
      const allInputs = await page.evaluate(() =>
        [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null)
          .map(i => ({ placeholder: i.placeholder }))
      );
      console.log('    Available inputs:', allInputs.map(i => `"${i.placeholder}"`).join(', '));
    }
    await page.keyboard.press('Escape');
    await humanDelay(300, 500);
    await page.mouse.click(650, 400);
    await humanDelay(500, 800);
    await screenshot(page, `${label}_02c_schools`);
  }

  // Language section (for diaspora search — e.g., Urdu speakers in UAE = Pakistani)
  if (filters.languages?.length) {
    console.log(`  Setting language filter: ${filters.languages.join(', ')}...`);
    // Scroll sidebar down to find Language section
    await page.evaluate(() => {
      const sections = [...document.querySelectorAll('div, section')].filter(el => {
        const style = window.getComputedStyle(el);
        return style.overflowY === 'auto' || style.overflowY === 'scroll';
      });
      for (const s of sections) {
        if (s.scrollHeight > s.clientHeight && s.clientHeight > 200) {
          s.scrollTop = s.scrollHeight;
          break;
        }
      }
    });
    await humanDelay(800, 1200);

    const langSection = await findByText(page, 'Language', true)
      || await findByText(page, 'Languages', true)
      || await findByText(page, 'Language', false);
    if (langSection) {
      await page.mouse.click(langSection.x, langSection.y);
      await humanDelay(800, 1200);
      console.log('    Clicked Language section');
    }
    // Find language input
    const langInputPos = await page.evaluate(() => {
      const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null);
      for (const input of inputs) {
        const ph = (input.placeholder || '').toLowerCase();
        if (ph.includes('english') || ph.includes('language') || ph.includes('spanish')) {
          const rect = input.getBoundingClientRect();
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: input.placeholder };
        }
      }
      return null;
    });
    if (langInputPos) {
      console.log(`    Found language input: "${langInputPos.placeholder}"`);
      for (const lang of filters.languages) {
        await page.mouse.click(langInputPos.x, langInputPos.y);
        await humanDelay(100, 200);
        await page.keyboard.type(lang, { delay: 25 + Math.random() * 30 });
        await humanDelay(800, 1200);
        await page.keyboard.press('Enter');
        await humanDelay(400, 700);
      }
      console.log(`    Languages: ${filters.languages.join(', ')}`);
    } else {
      console.log('    WARNING: Language input not found');
      const allInputs = await page.evaluate(() =>
        [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null)
          .map(i => ({ placeholder: i.placeholder }))
      );
      console.log('    Available inputs:', allInputs.map(i => `"${i.placeholder}"`).join(', '));
    }
    await page.keyboard.press('Escape');
    await humanDelay(300, 500);
    await page.mouse.click(650, 400);
    await humanDelay(500, 800);
    await screenshot(page, `${label}_02d_language`);
  }

  // Location section (for geo splits and exclude)
  if (filters.countries?.length || filters.cities?.length || filters.countries_exclude?.length) {
    const locSection = await findByText(page, 'Location', true);
    if (locSection) {
      await page.mouse.click(locSection.x, locSection.y);
      await humanDelay(800, 1200);
    }

    // Countries filter — "Countries to include" field (placeholder: "United States, Canada" etc.)
    if (filters.countries?.length) {
      const countryInput = await page.$('input[placeholder*="United States"]')
        || await page.$('input[placeholder*="country"]');
      if (countryInput) {
        for (const country of filters.countries) {
          await countryInput.click();
          await countryInput.type(country, { delay: 25 });
          await humanDelay(400, 700);
          await page.keyboard.press('Enter');
          await humanDelay(200, 400);
        }
        console.log(`    Countries: ${filters.countries.join(', ')}`);
      } else {
        console.log('    WARNING: Country input not found');
      }
    }

    // Countries EXCLUDE filter — Clay People has an "Exclude" toggle/section in Location
    // that reveals a separate input for countries to exclude.
    if (filters.countries_exclude?.length) {
      // Look for "Exclude" text/button in the Location section to expand exclude inputs
      const excludeToggle = await page.evaluate(() => {
        const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walk.nextNode()) {
          const node = walk.currentNode;
          const text = node.textContent.trim().toLowerCase();
          if ((text === 'exclude' || text === 'exclude locations' || text === 'exclude location') && node.parentElement?.offsetParent !== null) {
            const rect = node.parentElement.getBoundingClientRect();
            if (rect.x < 400 && rect.width > 10) {
              return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: node.textContent.trim() };
            }
          }
        }
        return null;
      });

      if (excludeToggle) {
        console.log(`    Found exclude toggle: "${excludeToggle.text}" — clicking...`);
        await page.mouse.click(excludeToggle.x, excludeToggle.y);
        await humanDelay(800, 1200);
      }

      // Find the exclude country input.
      // Clay People Location section has labeled fields:
      //   "Countries to include" → placeholder "e.g. United States, Canada"
      //   "Countries to exclude" → placeholder "e.g. France, Spain"
      // Strategy: find the label "Countries to exclude" text, then find the nearest input below it.
      const excludeInput = await page.evaluate(() => {
        const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null);

        // Strategy 1: Find "Countries to exclude" label and get the nearest input
        const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walk.nextNode()) {
          const text = walk.currentNode.textContent.trim();
          if (text === 'Countries to exclude') {
            const labelEl = walk.currentNode.parentElement;
            if (!labelEl || labelEl.offsetParent === null) continue;
            const labelRect = labelEl.getBoundingClientRect();
            if (labelRect.x > 400) continue;
            // Find the closest input below this label
            let closestInput = null;
            let closestDist = 999;
            for (const inp of inputs) {
              const inpRect = inp.getBoundingClientRect();
              if (inpRect.x > 400) continue;
              const dist = inpRect.y - labelRect.y;
              if (dist > 0 && dist < closestDist && dist < 80) {
                closestDist = dist;
                closestInput = inp;
              }
            }
            if (closestInput) {
              const rect = closestInput.getBoundingClientRect();
              return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: closestInput.placeholder, method: 'label' };
            }
          }
        }

        // Strategy 2: Look for input with placeholder "e.g. France, Spain" (Clay's default for exclude)
        for (const input of inputs) {
          const ph = (input.placeholder || '').toLowerCase();
          if (ph.includes('france') && ph.includes('spain') && input.getBoundingClientRect().x < 400) {
            const rect = input.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: input.placeholder, method: 'placeholder' };
          }
        }

        // Strategy 3: Find the second country-style input (first = include, second = exclude)
        const countryInputs = inputs.filter(i => {
          const ph = (i.placeholder || '').toLowerCase();
          return (ph.includes('united states') || ph.includes('france') || ph.includes('e.g.'))
            && i.getBoundingClientRect().x < 400
            && i.getBoundingClientRect().width > 100;
        });
        if (countryInputs.length >= 2) {
          const rect = countryInputs[1].getBoundingClientRect();
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: countryInputs[1].placeholder, method: 'second-input' };
        }

        return null;
      });

      if (excludeInput) {
        console.log(`    Exclude country input: "${excludeInput.placeholder}" (method: ${excludeInput.method})`);
        for (const country of filters.countries_exclude) {
          await page.mouse.click(excludeInput.x, excludeInput.y);
          await humanDelay(200, 400);
          await page.keyboard.type(country, { delay: 25 + Math.random() * 30 });
          await humanDelay(800, 1200);
          // Don't press Enter — it selects the first highlighted option which may be wrong
          // (e.g. "United States Minor Outlying Islands" instead of "United States").
          // Instead, find the exact matching dropdown option and click via page.mouse.click()
          // (page.evaluate el.click() doesn't trigger React event handlers properly).
          const optionCoords = await page.evaluate((targetCountry) => {
            const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
            const candidates = [];
            while (walk.nextNode()) {
              const text = walk.currentNode.textContent.trim();
              if (text === targetCountry) {
                const el = walk.currentNode.parentElement;
                if (el?.offsetParent !== null) {
                  const rect = el.getBoundingClientRect();
                  // Must be in a dropdown area (reasonable height, visible)
                  if (rect.height > 5 && rect.height < 60 && rect.width > 50) {
                    candidates.push({ x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text, h: rect.height, w: rect.width });
                  }
                }
              }
            }
            // Return the best candidate — prefer the one that looks like a dropdown item
            // (typically has a clickable row parent with reasonable dimensions)
            if (candidates.length > 0) {
              // If multiple exact matches, prefer ones lower on the page (dropdown items)
              // over sidebar labels that might also say "United States"
              candidates.sort((a, b) => b.y - a.y);
              // The dropdown item is usually narrower than the sidebar
              const dropdownItem = candidates.find(c => c.w < 350) || candidates[0];
              return dropdownItem;
            }
            return null;
          }, country);

          if (optionCoords) {
            console.log(`      Clicking "${country}" at (${Math.round(optionCoords.x)}, ${Math.round(optionCoords.y)})`);
            await page.mouse.click(optionCoords.x, optionCoords.y);
          } else {
            // Fallback: press Enter and hope for the best
            console.log(`      WARNING: Could not find exact "${country}" in dropdown, pressing Enter`);
            await page.keyboard.press('Enter');
          }
          await humanDelay(400, 700);
        }
        console.log(`    Countries EXCLUDED: ${filters.countries_exclude.join(', ')}`);
      } else {
        // Try direct Puppeteer selector as last resort
        const directExclude = await page.$('input[placeholder*="Exclude"]')
          || await page.$('input[placeholder*="exclude"]');
        if (directExclude) {
          for (const country of filters.countries_exclude) {
            await directExclude.click();
            await directExclude.type(country, { delay: 25 });
            await humanDelay(800, 1200);
            // Same dropdown click approach via page.mouse.click
            const fallbackCoords = await page.evaluate((targetCountry) => {
              const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
              while (walk.nextNode()) {
                if (walk.currentNode.textContent.trim() === targetCountry) {
                  const el = walk.currentNode.parentElement;
                  if (el?.offsetParent !== null) {
                    const rect = el.getBoundingClientRect();
                    if (rect.height > 5 && rect.height < 60 && rect.width > 50) {
                      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
                    }
                  }
                }
              }
              return null;
            }, country);
            if (fallbackCoords) {
              await page.mouse.click(fallbackCoords.x, fallbackCoords.y);
            } else {
              await page.keyboard.press('Enter');
            }
            await humanDelay(300, 500);
          }
          console.log(`    Countries EXCLUDED (direct): ${filters.countries_exclude.join(', ')}`);
        } else {
          console.log('    WARNING: Exclude country input not found');
          // Dump all sidebar inputs for debugging
          const allInputs = await page.evaluate(() => {
            return [...document.querySelectorAll('input')].filter(i => {
              const r = i.getBoundingClientRect();
              return i.offsetParent !== null && r.x < 400;
            }).map(i => ({ placeholder: i.placeholder, y: Math.round(i.getBoundingClientRect().y) }));
          });
          console.log(`    Sidebar inputs: ${JSON.stringify(allInputs)}`);
        }
      }
      await screenshot(page, `${label}_02c_exclude_location`);
    }

    // Cities filter — "Cities to include" field (placeholder: "New York, Paris" etc.)
    // CRITICAL: This is a SEPARATE input from countries. City names typed into the
    // country input are silently ignored by Clay, returning worldwide results.
    if (filters.cities?.length) {
      const cityInput = await page.evaluate(() => {
        const inputs = [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null);
        for (const input of inputs) {
          const ph = (input.placeholder || '').toLowerCase();
          if (ph.includes('new york') || ph.includes('paris') || ph.includes('city') || ph.includes('cities')) {
            const rect = input.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, placeholder: input.placeholder };
          }
        }
        return null;
      });
      if (cityInput) {
        for (const city of filters.cities) {
          await page.mouse.click(cityInput.x, cityInput.y);
          await humanDelay(100, 200);
          await page.keyboard.type(city, { delay: 25 + Math.random() * 30 });
          await humanDelay(800, 1200);
          await page.keyboard.press('Enter');
          await humanDelay(400, 700);
        }
        console.log(`    Cities: ${filters.cities.join(', ')}`);
      } else {
        console.log('    WARNING: City input not found, falling back to location input');
        const locInput = await page.$('input[placeholder*="location"]');
        if (locInput) {
          for (const city of filters.cities) {
            await locInput.click();
            await locInput.type(city, { delay: 25 });
            await humanDelay(400, 700);
            await page.keyboard.press('Enter');
            await humanDelay(200, 400);
          }
          console.log(`    Cities (fallback): ${filters.cities.join(', ')}`);
        }
      }
    }
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

  // Wait for table to fully populate (Clay async population takes 15-60s)
  console.log('  Waiting for table data to load...');
  await humanDelay(12000, 15000);
  await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(5000, 8000);
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

  if (tableMeta?.error) {
    console.log(`  WARNING: Table metadata fetch failed: ${tableMeta.error}`);
  }

  const fieldMap = {};
  for (const field of (tableMeta?.table?.fields || [])) {
    fieldMap[field.id] = field.name;
  }
  console.log(`  Fields: ${Object.values(fieldMap).join(', ')}`);

  // Get viewId with retry — URL may not have updated yet
  let viewId = null;
  for (let viewAttempt = 0; viewAttempt < 3; viewAttempt++) {
    viewId = page.url().match(/views\/([^/?&]+)/)?.[1] || tableMeta?.table?.firstViewId || null;
    if (viewId) {
      console.log(`  ViewId found: ${viewId} (attempt ${viewAttempt + 1})`);
      break;
    }
    console.log(`  WARNING: ViewId not found in URL or table metadata (attempt ${viewAttempt + 1}/3), waiting 5s...`);
    console.log(`  Current URL: ${page.url()}`);
    console.log(`  Table firstViewId: ${tableMeta?.table?.firstViewId || 'undefined'}`);
    await sleep(5000);
    // Reload and re-check URL
    await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(2000, 3000);
  }

  if (!viewId) {
    console.log('  ERROR: ViewId not found after 3 attempts. Cannot read records.');
    return [];
  }

  // Get record IDs with retry if empty (table may still be populating)
  let recordIds = [];
  for (let idsAttempt = 0; idsAttempt < 2; idsAttempt++) {
    const idsData = await page.evaluate(async (tid, vid) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}/views/${vid}/records/ids`, {
          credentials: 'include', headers: { 'Accept': 'application/json' },
        });
        return await res.json();
      } catch (e) { return { error: e.message }; }
    }, tableId, viewId);

    if (idsData?.error) {
      console.log(`  WARNING: Record IDs fetch failed: ${idsData.error}`);
    }
    recordIds = idsData?.results || [];

    if (recordIds.length > 0) {
      console.log(`  Record IDs: ${recordIds.length} (attempt ${idsAttempt + 1})`);
      break;
    }

    if (idsAttempt === 0) {
      console.log(`  WARNING: 0 record IDs returned (attempt 1/2). Table may still be populating. Waiting 10s and retrying...`);
      await sleep(10000);
      await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
      await humanDelay(3000, 5000);
    } else {
      console.log(`  WARNING: 0 record IDs returned after retry. Table may be empty.`);
    }
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
  const useTitles = args.includes('--titles');
  const tableIdIdx = args.indexOf('--table-id');
  const sourceTableId = tableIdIdx >= 0 ? args[tableIdIdx + 1] : null;
  const tableNameIdx = args.indexOf('--table-name');
  const domainsTableName = tableNameIdx >= 0 ? args[tableNameIdx + 1] : null;
  const tableUrlIdx = args.indexOf('--table-url');
  const sourceTableUrl = tableUrlIdx >= 0 ? args[tableUrlIdx + 1] : null;
  const domainsFileIdx = args.indexOf('--domains-file');
  const externalDomainsFile = domainsFileIdx >= 0 ? args[domainsFileIdx + 1] : null;
  const countriesIdx = args.indexOf('--countries');
  const countriesArg = countriesIdx >= 0 ? args[countriesIdx + 1] : null;
  const customCountries = countriesArg ? countriesArg.split(',').map(c => c.trim()) : null;
  const schoolsIdx = args.indexOf('--schools');
  const schoolsArg = schoolsIdx >= 0 ? args[schoolsIdx + 1] : null;
  const customSchools = schoolsArg ? schoolsArg.split('|').map(s => s.trim()) : null;
  const nameIdx = args.indexOf('--name');
  const nameArg = nameIdx >= 0 ? args[nameIdx + 1] : null;
  const customName = nameArg ? nameArg.trim() : null;
  const jobTitleIdx = args.indexOf('--job-title');
  const jobTitleArg = jobTitleIdx >= 0 ? args[jobTitleIdx + 1] : null;
  const customJobTitle = jobTitleArg ? jobTitleArg.trim() : null;
  const languageIdx = args.indexOf('--language');
  const languageArg = languageIdx >= 0 ? args[languageIdx + 1] : null;
  const customLanguages = languageArg ? languageArg.split(',').map(l => l.trim()) : null;
  const citiesIdx = args.indexOf('--cities');
  const citiesArg = citiesIdx >= 0 ? args[citiesIdx + 1] : null;
  const customCities = citiesArg ? citiesArg.split(',').map(c => c.trim()) : null;
  const countriesExIdx = args.indexOf('--countries-exclude');
  const countriesExArg = countriesExIdx >= 0 ? args[countriesExIdx + 1] : null;
  const customCountriesExclude = countriesExArg ? countriesExArg.split(',').map(c => c.trim()) : null;

  // Custom titles via env var (for orchestration scripts)
  const envTitles = process.env.CLAY_CUSTOM_TITLES;
  if (envTitles) {
    try {
      GAMING_ICP_FILTERS.job_titles = JSON.parse(envTitles);
      console.log(`  Title filter: CUSTOM (${GAMING_ICP_FILTERS.job_titles.length} titles from env)`);
    } catch (e) {
      console.log(`  WARNING: Could not parse CLAY_CUSTOM_TITLES: ${e.message}`);
    }
  } else if (useTitles) {
    GAMING_ICP_FILTERS.job_titles = ['CEO', 'Founder', 'Co-Founder', 'CTO', 'CFO', 'COO',
      'VP', 'Head of', 'Director', 'Chief', 'Managing Director', 'Owner'];
    console.log('  Title filter: ON (decision-makers only)');
  } else {
    console.log('  Title filter: OFF (all roles)');
  }

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
  await page.setDefaultTimeout(600000); // 10 min timeout for large table reads
  await page.setUserAgent(USER_AGENT);
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  });

  // Session — use `let` so we can update if refreshed during login
  let session = loadSession();
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
        if (sc) { session = { value: sc.value }; saveSession(sc.value); break; }
      }
    }
    await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2' });
    await humanDelay(2000, 3000);
    check = await validateSession(page);
    if (!check.valid) throw new Error('Login failed');
  }

  const creditsBefore = check.credits;
  console.log(`  Credits: ${JSON.stringify(creditsBefore)}`);

  // Resolve correct workspace ID from /me API
  const resolvedWsId = check.wsId || await page.evaluate(async () => {
    const res = await fetch('https://api.clay.com/v3/me', { credentials: 'include' });
    const me = await res.json();
    return me?.sessionState?.last_workspace_visited_id;
  });
  if (resolvedWsId && resolvedWsId !== WORKSPACE_ID) {
    console.log(`  Workspace ID resolved: ${resolvedWsId} (was ${WORKSPACE_ID})`);
    WORKSPACE_ID = resolvedWsId;
  }

  // ENRICHMENT MODE (primary): Navigate to companies table → Add column → Find People
  if (sourceTableId) {
    console.log(`\n[ENRICHMENT MODE] Source table: ${sourceTableId}`);

    // Parse countries-exclude from args
    const countriesExcludeIdx = args.indexOf('--countries-exclude');
    const countriesExcludeArg = countriesExcludeIdx >= 0 ? args[countriesExcludeIdx + 1] : null;
    const countriesExclude = countriesExcludeArg ? countriesExcludeArg.split(',').map(c => c.trim()) : ['United States'];

    const enrichFilters = {
      countries_exclude: countriesExclude,
      job_titles: customJobTitle ? [customJobTitle] : (useTitles ? ['CEO', 'Founder', 'CTO', 'CFO', 'VP', 'Director'] : []),
    };

    const result = await runEnrichmentPeopleSearch(page, sourceTableId, enrichFilters);

    // Final credit check
    console.log('\n[FINAL] Credit check...');
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
      mode: 'enrichment',
      sourceTableId,
      result: result ? { tableId: result.tableId, csvPath: result.csvPath, jsonPath: result.jsonPath, recordCount: result.records?.length } : null,
      creditsBefore, creditsAfter, creditsSpent: spent,
    }, null, 2));

    console.log('\n========================================');
    console.log('  People search complete (ENRICHMENT MODE)!');
    console.log(`  Results: ${result ? '1 table created' : 'FAILED'}`);
    console.log(`  Credits spent: ${spent}`);
    console.log('========================================');

    if (autoClose) await browser.close();
    return;
  }

  // LEGACY MODE: Standalone People search with domain typing (fallback)
  let companyTableName = null;

  // Load domains — only needed for legacy mode (no --table-id)
  let allDomains = [];
  if (!companyTableName) {
    if (externalDomainsFile && fs.existsSync(externalDomainsFile)) {
      const lines = fs.readFileSync(externalDomainsFile, 'utf-8').split('\n');
      allDomains = lines.map(l => l.trim().toLowerCase().replace(/^www\./, '')).filter(d => d && d.includes('.'));
      console.log(`  External domains file: ${externalDomainsFile} (${allDomains.length} domains)`);
    } else if (customSchools || customCountries) {
      allDomains = [];
      console.log(`  Filter-based search (no domains). Schools: ${customSchools?.length || 0}, Countries: ${customCountries?.length || 0}`);
    } else {
      allDomains = loadKnownDomains();
      console.log(`  Known gaming ICP domains: ${allDomains.length}`);
    }
  }
  GAMING_ICP_FILTERS.company_domains = allDomains;

  // Set table name in filters if table mode
  if (companyTableName) {
    GAMING_ICP_FILTERS.company_table_name = companyTableName;
    GAMING_ICP_FILTERS.company_domains = []; // Don't type domains in table mode
  }

  // Build search configs
  let searches;

  // Inject custom countries into all searches if provided
  if (customCountries) {
    GAMING_ICP_FILTERS.countries = customCountries;
    console.log(`  Country filter: ${customCountries.join(', ')}`);
  }
  if (customSchools) {
    GAMING_ICP_FILTERS.schools = customSchools;
    console.log(`  School filter: ${customSchools.join(', ')}`);
  }
  if (customName) {
    GAMING_ICP_FILTERS.person_name = customName;
    console.log(`  Name filter: ${customName}`);
  }
  if (customJobTitle) {
    GAMING_ICP_FILTERS.job_titles = [customJobTitle];
    console.log(`  Single job title filter: ${customJobTitle}`);
  }
  if (customLanguages) {
    GAMING_ICP_FILTERS.languages = customLanguages;
    console.log(`  Language filter: ${customLanguages.join(', ')}`);
  }
  if (customCities) {
    GAMING_ICP_FILTERS.cities = customCities;
    console.log(`  City filter: ${customCities.join(', ')}`);
  }
  if (customCountriesExclude) {
    GAMING_ICP_FILTERS.countries_exclude = customCountriesExclude;
    console.log(`  Country EXCLUDE filter: ${customCountriesExclude.join(', ')}`);
  }

  if (companyTableName) {
    // TABLE MODE: single search using "Table of companies" filter — no batching needed
    searches = [{ label: 'table_mode', filters: GAMING_ICP_FILTERS }];
    console.log(`\n[2] Running table-mode search (using "${companyTableName}")...`);
  } else if (allDomains.length === 0) {
    // No domains — filter-based search (schools + countries + titles)
    searches = [{ label: 'filter_based', filters: GAMING_ICP_FILTERS }];
    console.log('\n[2] Running filter-based search (no domains)...');
  } else if (allDomains.length > 200) {
    // Split domains into batches (legacy mode)
    const DOMAIN_BATCH_SIZE = 200;
    searches = [];
    for (let i = 0; i < allDomains.length; i += DOMAIN_BATCH_SIZE) {
      const batch = allDomains.slice(i, i + DOMAIN_BATCH_SIZE);
      searches.push({
        label: `batch_${Math.floor(i / DOMAIN_BATCH_SIZE) + 1}`,
        filters: { ...GAMING_ICP_FILTERS, company_domains: batch },
      });
    }
    console.log(`\n[2] Running ${searches.length} domain-batch searches (${DOMAIN_BATCH_SIZE} domains each)...`);
  } else if (splitByGeo) {
    searches = GEO_SPLITS.map(geo => ({
      label: geo.label.toLowerCase().replace(/[^a-z0-9]+/g, '_'),
      filters: {
        ...GAMING_ICP_FILTERS,
        countries: geo.countries.length > 0 ? geo.countries : undefined,
      },
    }));
    console.log(`\n[2] Running ${searches.length} geo-split searches...`);
  } else {
    searches = [{ label: 'all', filters: GAMING_ICP_FILTERS }];
    console.log('\n[2] Running single search...');
  }

  // Run searches — use a FRESH page for each batch to avoid stale UI state
  const allResults = [];
  for (let si = 0; si < searches.length; si++) {
    const search = searches[si];
    // Create a fresh page (new tab) for each batch to avoid Clay's stale DOM
    let batchPage;
    if (si === 0) {
      batchPage = page; // Reuse the validated page for the first batch
    } else {
      console.log(`\n  Opening fresh tab for ${search.label}...`);
      batchPage = await browser.newPage();
      await batchPage.setDefaultTimeout(600000);
      await batchPage.setUserAgent(USER_AGENT);
      await batchPage.evaluateOnNewDocument(() => {
        Object.defineProperty(navigator, 'webdriver', { get: () => false });
      });
      await setSessionCookie(batchPage, session.value);
      // Navigate to workspace home to initialize session
      await batchPage.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
      await humanDelay(2000, 3000);
    }

    const result = await runPeopleSearch(batchPage, search.filters, search.label);
    if (result) allResults.push(result);

    // Close the batch page (except the first one which we keep for final checks)
    if (si > 0) {
      await batchPage.close();
    }
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
