#!/usr/bin/env node
/**
 * Overseas Decision Maker Search Pipeline
 *
 * Full automated flow:
 * 1. Upload CSV of company domains to Clay as a new table
 * 2. Run "Find People" enrichment with title filters (HR, CEO, Finance, etc.)
 * 3. Read results, cap at N people per company
 * 4. Export to JSON for XLSX builder
 *
 * Usage:
 *   node overseas_dm_search.js \
 *     --csv exports/missouri_dm_domains.csv \
 *     --table-name "[Missouri]-[11-50]-Companies_with_no_us_empl" \
 *     --people-table-name "People_[Missouri]-[11-50]-Companies_with_no_us_empl" \
 *     --titles "HR,CEO,COO,Payroll,Founder,Accountant,Finance,CFO,Head of HR,Human Resources,Controller" \
 *     --max-per-company 4 \
 *     --headless --auto
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

let WORKSPACE_ID = process.env.CLAY_WORKSPACE_ID || '588071';
const OUT_DIR = path.join(__dirname, 'exports');
const SESSION_FILE = path.join(__dirname, 'clay_session.json');
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36';

// ============================================================
// Helpers (same as other Clay scripts)
// ============================================================
function humanDelay(min = 800, max = 2500) {
  return new Promise(r => setTimeout(r, min + Math.random() * (max - min)));
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function loadSession() {
  try {
    if (fs.existsSync(SESSION_FILE)) {
      const data = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));
      if (data.value) return data;
    }
  } catch {}
  return { value: null };
}
function saveSession(cookieValue) {
  fs.writeFileSync(SESSION_FILE, JSON.stringify({ value: cookieValue, savedAt: new Date().toISOString() }, null, 2));
}
async function setSessionCookie(page, cookieValue) {
  await page.setCookie({
    name: 'claysession', value: cookieValue,
    domain: 'api.clay.com', path: '/', httpOnly: true, secure: true, sameSite: 'None',
  });
}
async function screenshot(page, name) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(OUT_DIR, `dm_${name}.png`), fullPage: false });
  console.log(`  [img] dm_${name}.png`);
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
async function getCredits(page) {
  return page.evaluate(async (wsId) => {
    try {
      const res = await fetch(`https://api.clay.com/v3/subscriptions/${wsId}`, {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      const d = await res.json();
      return d.creditBalances || null;
    } catch { return null; }
  }, WORKSPACE_ID);
}
async function validateSession(page) {
  return page.evaluate(async () => {
    try {
      const meRes = await fetch('https://api.clay.com/v3/me', {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      if (meRes.status === 401 || meRes.status === 403) return { valid: false };
      const me = await meRes.json();
      if (!me?.id) return { valid: false };
      const subId = me?.sessionState?.last_workspace_visited_id;
      const subRes = await fetch(`https://api.clay.com/v3/subscriptions/${subId}`, {
        credentials: 'include',
      });
      const sub = await subRes.json();
      return { valid: true, credits: sub.creditBalances, wsId: subId };
    } catch (e) { return { valid: false, error: e.message }; }
  });
}

// ============================================================
// Step 1: Upload CSV to Clay as a new table
// ============================================================
async function uploadCSVToTable(page, csvPath, tableName) {
  console.log(`\n[STEP 1] Uploading CSV to Clay as "${tableName}"...`);
  console.log(`  CSV: ${csvPath}`);

  // Navigate to workspace home
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  // Click "Import data"
  const importBtn = await findByText(page, 'Import data', false);
  if (importBtn) {
    await page.mouse.click(importBtn.x, importBtn.y);
    await humanDelay(1000, 1800);
  } else {
    console.log('  WARNING: "Import data" not found, trying alternatives...');
    // Try "+" or "New" button
    const newBtn = await findByText(page, 'New', false) || await findByText(page, 'Import', false);
    if (newBtn) await page.mouse.click(newBtn.x, newBtn.y);
    await humanDelay(1000, 1800);
  }

  // Click "Import CSV"
  const csvBtn = await findByText(page, 'Import CSV', false)
    || await findByText(page, 'CSV', false)
    || await findByText(page, 'Upload CSV', false);
  if (csvBtn) {
    await page.mouse.click(csvBtn.x, csvBtn.y);
    await humanDelay(1500, 2500);
  }
  await screenshot(page, '01_csv_dialog');

  // Upload the CSV file
  const fileInput = await page.$('input[type="file"]');
  if (!fileInput) {
    console.log('  ERROR: No file input found!');
    return null;
  }
  await humanDelay(400, 800);
  await fileInput.uploadFile(csvPath);
  console.log('  File uploaded, waiting for processing...');

  // Wait for upload to complete (up to 30s)
  for (let i = 0; i < 30; i++) {
    const completed = await page.evaluate(() =>
      document.body?.textContent?.includes('100% completed') ||
      document.body?.textContent?.includes('Upload complete') ||
      document.body?.textContent?.includes('rows imported')
    );
    if (completed) break;
    await sleep(1000);
  }
  console.log('  Upload finalized');
  await humanDelay(1000, 2000);
  await screenshot(page, '01b_uploaded');

  // Click Continue (post-upload)
  const continueBtn1 = await findByText(page, 'Continue', true);
  if (continueBtn1) {
    await page.mouse.click(continueBtn1.x, continueBtn1.y);
    await humanDelay(2000, 3500);
  }

  // Handle delimiter screen
  if (await page.evaluate(() => document.body?.textContent?.includes('Delimiter'))) {
    console.log('  Delimiter screen — clicking Continue');
    const delimBtn = await findByText(page, 'Continue', true);
    if (delimBtn) {
      await page.mouse.click(delimBtn.x, delimBtn.y);
      await humanDelay(2000, 3500);
    }
  }

  // Select "New blank table"
  if (await page.evaluate(() => document.body?.textContent?.includes('New blank table'))) {
    console.log('  Selecting "New blank table"...');
    const cardPos = await page.evaluate(() => {
      const allDivs = [...document.querySelectorAll('div')];
      for (const div of allDivs) {
        if (div.textContent?.trim() === 'New blank table' && div.children.length >= 1) {
          let card = div.parentElement;
          while (card && card.getBoundingClientRect().width < 100) card = card.parentElement;
          if (card) {
            const rect = card.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
          }
        }
      }
      return null;
    });
    if (cardPos) {
      await page.mouse.click(cardPos.x, cardPos.y);
      await humanDelay(500, 1000);
    } else {
      const nbt = await findByText(page, 'New blank table', false);
      if (nbt) await page.mouse.click(nbt.x, nbt.y);
      await humanDelay(500, 1000);
    }
    // Click Continue
    const continueBtn2 = await findByText(page, 'Continue', true);
    if (continueBtn2) {
      await page.mouse.click(continueBtn2.x, continueBtn2.y);
      await humanDelay(2000, 3500);
    }
  }
  await screenshot(page, '01c_table_destination');

  // Handle "Import" / final confirmation
  const importFinal = await findByText(page, 'Import', true)
    || await findByText(page, 'Create table', false)
    || await findByText(page, 'Finish', false);
  if (importFinal) {
    await page.mouse.click(importFinal.x, importFinal.y);
    await humanDelay(5000, 8000);
  }

  // Wait for table to load
  await humanDelay(5000, 8000);
  await screenshot(page, '01d_table_created');

  // Extract table ID from URL
  let tableId = null;
  for (let i = 0; i < 15; i++) {
    const url = page.url();
    const m = url.match(/tableId=([^&]+)/) || url.match(/tables\/([^/?]+)/);
    if (m) { tableId = m[1]; break; }
    await sleep(2000);
  }
  console.log(`  Table ID: ${tableId}`);

  // Rename the table
  if (tableName && tableId) {
    console.log(`  Renaming table to "${tableName}"...`);
    // Click the table name header to edit it
    const tableHeader = await page.evaluate(() => {
      // Look for editable table name in the breadcrumb or header
      const els = [...document.querySelectorAll('h1, h2, span, div')].filter(el => {
        const r = el.getBoundingClientRect();
        return el.offsetParent !== null && r.y < 60 && r.x > 50 && r.x < 600
          && el.textContent?.trim().length > 3 && el.textContent?.trim().length < 60;
      });
      // Find one that looks like a table name (not navigation)
      for (const el of els) {
        const t = el.textContent.trim();
        if (t.includes('Untitled') || t.includes('Import') || t.includes('Table')) {
          const r = el.getBoundingClientRect();
          return { x: r.x + r.width / 2, y: r.y + r.height / 2, text: t };
        }
      }
      return null;
    });

    if (tableHeader) {
      await page.mouse.click(tableHeader.x, tableHeader.y);
      await humanDelay(300, 500);
      await page.mouse.click(tableHeader.x, tableHeader.y); // Double-click to select
      await humanDelay(200, 400);
      // Select all and replace
      await page.keyboard.down('Control');
      await page.keyboard.press('a');
      await page.keyboard.up('Control');
      await humanDelay(100, 200);
      await page.keyboard.type(tableName, { delay: 20 });
      await page.keyboard.press('Enter');
      await humanDelay(500, 800);
      console.log(`  Table renamed to "${tableName}"`);
    } else {
      console.log('  WARNING: Could not find table name header to rename');
    }
  }

  await screenshot(page, '01e_table_ready');
  return tableId;
}

// ============================================================
// Step 2: Run "Find People" enrichment from companies table
// ============================================================
async function runFindPeopleEnrichment(page, tableId, titles, peoplTableName) {
  console.log(`\n[STEP 2] Running "Find People" enrichment on table ${tableId}...`);
  console.log(`  Titles: ${titles.join(', ')}`);

  // Navigate to the table
  const tableInfo = await page.evaluate(async (tid) => {
    try {
      const res = await fetch(`https://api.clay.com/v3/tables/${tid}`, {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      const data = await res.json();
      const t = data?.table || data;
      const meRes = await fetch('https://api.clay.com/v3/me', { credentials: 'include' });
      const me = await meRes.json();
      return { workbookId: t?.workbookId, firstViewId: t?.firstViewId, name: t?.name, wsId: me?.sessionState?.last_workspace_visited_id };
    } catch (e) { return { error: e.message }; }
  }, tableId);

  const wsId = tableInfo?.wsId || WORKSPACE_ID;
  const tableUrl = tableInfo?.workbookId && tableInfo?.firstViewId
    ? `https://app.clay.com/workspaces/${wsId}/workbooks/${tableInfo.workbookId}/tables/${tableId}/views/${tableInfo.firstViewId}`
    : `https://app.clay.com/workspaces/${wsId}/tables/${tableId}`;

  console.log(`  Navigating to: ${tableUrl}`);
  await page.goto(tableUrl, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(3000, 5000);
  await screenshot(page, '02_companies_table');

  // Click "+ Add" column
  console.log('  Clicking "+ Add" column...');
  // Scroll right to find the Add button (it's at the end of the table headers)
  const addBtn = await findByText(page, 'Add column', false)
    || await findByText(page, 'Add', true)
    || await page.evaluate(() => {
      const btns = [...document.querySelectorAll('button, div[role="button"]')].filter(el => {
        const t = (el.textContent || '').trim();
        const r = el.getBoundingClientRect();
        return el.offsetParent !== null && (t === '+' || t === 'Add' || t.includes('Add column'))
          && r.y < 100;
      });
      if (btns.length > 0) {
        const r = btns[0].getBoundingClientRect();
        return { x: r.x + r.width / 2, y: r.y + r.height / 2 };
      }
      return null;
    });

  if (!addBtn) {
    console.log('  ERROR: Add button not found');
    return null;
  }
  await page.mouse.click(addBtn.x, addBtn.y);
  await humanDelay(2000, 3000);
  await screenshot(page, '02b_add_menu');

  // Look for "Add enrichment" option
  const addEnrichBtn = await findByText(page, 'Add enrichment', false)
    || await findByText(page, 'Enrichment', false);
  if (addEnrichBtn) {
    await page.mouse.click(addEnrichBtn.x, addEnrichBtn.y);
    await humanDelay(2000, 3000);
  }

  // Search for "Find People"
  console.log('  Searching for "Find People"...');
  const searchInput = await page.$('input[placeholder*="Search"]')
    || await page.$('input[placeholder*="search"]')
    || await page.$('input[type="search"]');
  if (searchInput) {
    await searchInput.click();
    await humanDelay(200, 400);
    await searchInput.type('Find People', { delay: 30 + Math.random() * 40 });
    await humanDelay(1500, 2500);
  }
  await screenshot(page, '02c_find_people_search');

  // Click "Find people" SOURCE option (not Claygent, not enrichment)
  const findPeopleOpt = await page.evaluate(() => {
    const items = [...document.querySelectorAll('div, li, a, button')].filter(el => {
      if (!el.offsetParent) return false;
      const rect = el.getBoundingClientRect();
      return rect.width > 200 && rect.height > 30 && rect.height < 120;
    });
    // Prefer "Source" type (free People Search)
    for (const item of items) {
      const text = item.textContent?.trim() || '';
      if (text.includes('Find people') && text.includes('Source')) {
        const rect = item.getBoundingClientRect();
        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: text.substring(0, 80), type: 'source' };
      }
    }
    // Fallback
    for (const item of items) {
      const text = item.textContent?.trim() || '';
      if (text.includes('Find people') || text.includes('Find People')) {
        const rect = item.getBoundingClientRect();
        return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: text.substring(0, 80), type: 'fallback' };
      }
    }
    return null;
  });

  if (!findPeopleOpt) {
    console.log('  ERROR: "Find People" option not found');
    return null;
  }
  console.log(`  Found: "${findPeopleOpt.text}" (${findPeopleOpt.type})`);
  await page.mouse.click(findPeopleOpt.x, findPeopleOpt.y);
  await humanDelay(4000, 6000);
  await screenshot(page, '02d_find_people_opened');

  // Apply title filters (type each title individually)
  if (titles.length > 0) {
    console.log('  Applying title filters...');
    // Look for job title input
    const titleSection = await findByText(page, 'Job title', true)
      || await findByText(page, 'Job Title', true);
    if (titleSection) {
      await page.mouse.click(titleSection.x, titleSection.y);
      await humanDelay(800, 1200);
    }

    const titleInput = await page.$('input[placeholder*="CEO"]')
      || await page.$('input[placeholder*="VP"]')
      || await page.$('input[placeholder*="Director"]')
      || await page.$('input[placeholder*="title"]');

    if (titleInput) {
      for (const title of titles) {
        await titleInput.click();
        await humanDelay(100, 200);
        await titleInput.type(title, { delay: 25 + Math.random() * 30 });
        await humanDelay(500, 800);
        await page.keyboard.press('Enter');
        await humanDelay(300, 500);
      }
      console.log(`    Titles: ${titles.join(', ')}`);
    } else {
      console.log('    WARNING: Title input not found');
    }
    await page.keyboard.press('Escape');
    await humanDelay(300, 500);
  }

  await humanDelay(2000, 3000);
  await screenshot(page, '02e_filters_applied');

  // Read result count
  const resultText = await page.evaluate(() => {
    const text = document.body.textContent || '';
    const match = text.match(/([\d,]+)\s*(?:people|results|contacts)/i);
    return match ? match[0] : null;
  });
  console.log(`  Result count: ${resultText || 'unknown'}`);

  // Click Continue → Save to new table
  console.log('  Clicking Continue...');
  const continueBtnInfo = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null);
    const btn = buttons.find(b => b.textContent?.trim().startsWith('Continue'));
    if (!btn) return null;
    const rect = btn.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, right: rect.x + rect.width - 8 };
  });

  if (!continueBtnInfo) {
    // Try "Save" button for enrichment waterfall
    const saveBtn = await findByText(page, 'Save', true) || await findByText(page, 'Run', true);
    if (saveBtn) {
      await page.mouse.click(saveBtn.x, saveBtn.y);
      await humanDelay(5000, 8000);
    } else {
      console.log('  ERROR: No Continue/Save button found');
      return null;
    }
  } else {
    // Click dropdown arrow for "Save to new table" option
    let option = null;
    for (let attempt = 0; attempt < 4 && !option; attempt++) {
      if (attempt > 0) { await page.keyboard.press('Escape'); await humanDelay(500, 800); }
      await page.mouse.click(attempt < 2 ? continueBtnInfo.right : continueBtnInfo.x, continueBtnInfo.y);
      await humanDelay(1200, 2000);
      option = await page.evaluate(() => {
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
    if (option) {
      await page.mouse.click(option.x, option.y);
      await humanDelay(5000, 8000);
    }
  }
  await screenshot(page, '02f_enrich_page');

  // Extract new table ID
  let newTableId = null;
  for (let i = 0; i < 15; i++) {
    const url = page.url();
    const m = url.match(/tableId=([^&]+)/) || url.match(/tables\/([^/?]+)/);
    if (m) { newTableId = m[1]; break; }
    await sleep(2000);
  }
  console.log(`  People table ID: ${newTableId}`);

  // Skip enrichments → Create table
  const createBtn = await findByText(page, 'Create table', false);
  if (createBtn) {
    await page.mouse.click(createBtn.x, createBtn.y);
    await humanDelay(10000, 15000);
  }

  if (!newTableId) {
    const url = page.url();
    const m = url.match(/tableId=([^&]+)/) || url.match(/tables\/([^/?]+)/);
    if (m) newTableId = m[1];
  }

  // Wait and read results
  console.log('  Waiting for table to populate...');
  await humanDelay(12000, 15000);
  await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(5000, 8000);
  await screenshot(page, '02g_people_table');

  return newTableId;
}

// ============================================================
// Step 3: Read table data
// ============================================================
async function readTableData(page, tableId) {
  console.log(`\n[STEP 3] Reading table ${tableId}...`);

  const tableMeta = await page.evaluate(async (tid) => {
    const res = await fetch(`https://api.clay.com/v3/tables/${tid}`, {
      credentials: 'include', headers: { 'Accept': 'application/json' },
    });
    return await res.json();
  }, tableId);

  const fieldMap = {};
  for (const field of (tableMeta?.table?.fields || [])) {
    fieldMap[field.id] = field.name;
  }
  console.log(`  Fields: ${Object.values(fieldMap).join(', ')}`);

  const viewId = page.url().match(/views\/([^/?&]+)/)?.[1] || tableMeta?.table?.firstViewId;
  if (!viewId) {
    console.log('  ERROR: No viewId found');
    return [];
  }

  const idsData = await page.evaluate(async (tid, vid) => {
    const res = await fetch(`https://api.clay.com/v3/tables/${tid}/views/${vid}/records/ids`, {
      credentials: 'include',
    });
    return await res.json();
  }, tableId, viewId);

  const recordIds = idsData?.results || [];
  console.log(`  Records: ${recordIds.length}`);

  const allRecords = [];
  const batchSize = 200;
  for (let i = 0; i < recordIds.length; i += batchSize) {
    const batch = recordIds.slice(i, i + batchSize);
    const batchData = await page.evaluate(async (tid, ids) => {
      const res = await fetch(`https://api.clay.com/v3/tables/${tid}/bulk-fetch-records`, {
        method: 'POST', credentials: 'include',
        headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ recordIds: ids }),
      });
      return await res.json();
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
  const headless = args.includes('--headless');
  const autoClose = args.includes('--auto');
  const csvIdx = args.indexOf('--csv');
  const csvPath = csvIdx >= 0 ? path.resolve(args[csvIdx + 1]) : null;
  const tableNameIdx = args.indexOf('--table-name');
  const tableName = tableNameIdx >= 0 ? args[tableNameIdx + 1] : 'Imported companies';
  const peopleNameIdx = args.indexOf('--people-table-name');
  const peopleTableName = peopleNameIdx >= 0 ? args[peopleNameIdx + 1] : null;
  const titlesIdx = args.indexOf('--titles');
  const titlesArg = titlesIdx >= 0 ? args[titlesIdx + 1] : 'HR,CEO,COO,Payroll,Founder,Accountant,Finance,CFO,Head of HR,Human Resources,Controller';
  const titles = titlesArg.split(',').map(t => t.trim());
  const maxPerIdx = args.indexOf('--max-per-company');
  const maxPerCompany = maxPerIdx >= 0 ? parseInt(args[maxPerIdx + 1]) : 4;
  // Allow passing an existing table ID instead of uploading CSV
  const tableIdIdx = args.indexOf('--table-id');
  const existingTableId = tableIdIdx >= 0 ? args[tableIdIdx + 1] : null;

  if (!csvPath && !existingTableId) {
    console.log('Usage: node overseas_dm_search.js --csv path/to/domains.csv --table-name "Name" --headless --auto');
    console.log('   or: node overseas_dm_search.js --table-id t_xxxxx --headless --auto  (skip upload, use existing table)');
    process.exit(0);
  }

  console.log('\n=== Overseas Decision Maker Search ===');
  console.log(`  CSV: ${csvPath || '(using existing table)'}`);
  console.log(`  Table name: ${tableName}`);
  console.log(`  Titles: ${titles.join(', ')}`);
  console.log(`  Max per company: ${maxPerCompany}`);

  // Launch browser
  const browser = await puppeteer.launch({
    headless: headless ? 'new' : false,
    executablePath: headless ? (process.env.CHROME_PATH || '/usr/bin/google-chrome') : undefined,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900',
           '--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.setDefaultTimeout(600000);
  await page.setUserAgent(USER_AGENT);
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  });

  // Session
  let session = loadSession();
  if (!session.value) {
    console.log('ERROR: No session cookie. Update clay_session.json.');
    await browser.close();
    process.exit(1);
  }
  await setSessionCookie(page, session.value);

  // Validate
  console.log('\n[0] Validating session...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);
  const check = await validateSession(page);
  if (!check.valid) {
    console.log('ERROR: Session expired. Update clay_session.json.');
    await browser.close();
    process.exit(1);
  }
  if (check.wsId) WORKSPACE_ID = check.wsId;
  const creditsBefore = check.credits;
  console.log(`  Credits: ${JSON.stringify(creditsBefore)}`);

  // Step 1: Upload CSV or use existing table
  let companiesTableId = existingTableId;
  if (!companiesTableId) {
    companiesTableId = await uploadCSVToTable(page, csvPath, tableName);
    if (!companiesTableId) {
      console.log('FATAL: Failed to create companies table');
      await browser.close();
      process.exit(1);
    }
  }
  console.log(`  Companies table: ${companiesTableId}`);

  // Step 2: Run Find People enrichment
  const peopleTableId = await runFindPeopleEnrichment(page, companiesTableId, titles, peopleTableName);
  if (!peopleTableId) {
    console.log('FATAL: Failed to create people table');
    await browser.close();
    process.exit(1);
  }

  // Step 3: Read results
  const people = await readTableData(page, peopleTableId);
  console.log(`  Total people: ${people.length}`);

  // Cap at maxPerCompany
  const companyCounts = {};
  const capped = [];
  for (const p of people) {
    const domain = (p['Company Domain'] || '').toLowerCase();
    companyCounts[domain] = (companyCounts[domain] || 0) + 1;
    if (companyCounts[domain] <= maxPerCompany) {
      capped.push(p);
    }
  }
  console.log(`  After capping at ${maxPerCompany}/company: ${capped.length}`);

  // Save results
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const outPath = path.join(OUT_DIR, 'dm_people.json');
  fs.writeFileSync(outPath, JSON.stringify(capped, null, 2));
  console.log(`  Saved to ${outPath}`);

  // Final credit check
  const creditsAfter = await getCredits(page);
  const spent = (creditsBefore?.basic || 0) - (creditsAfter?.basic || 0);
  console.log(`\n  Credits before: ${JSON.stringify(creditsBefore)}`);
  console.log(`  Credits after:  ${JSON.stringify(creditsAfter)}`);
  console.log(`  CREDITS SPENT: ${spent}`);

  // Save session
  const endCookies = await page.cookies('https://api.clay.com');
  const sc = endCookies.find(c => c.name === 'claysession');
  if (sc) saveSession(sc.value);

  // Save summary
  fs.writeFileSync(path.join(OUT_DIR, 'dm_summary.json'), JSON.stringify({
    timestamp: new Date().toISOString(),
    companiesTableId, peopleTableId,
    totalPeople: people.length, cappedPeople: capped.length,
    maxPerCompany, titles,
    creditsBefore, creditsAfter, creditsSpent: spent,
  }, null, 2));

  console.log('\n=== Decision Maker Search Complete ===');
  console.log(`  Companies table: ${companiesTableId}`);
  console.log(`  People table: ${peopleTableId}`);
  console.log(`  People found: ${people.length} → ${capped.length} (capped)`);
  console.log(`  Credits spent: ${spent}`);
  console.log(`  Output: ${outPath}`);

  if (autoClose) await browser.close();
}

main().catch(e => { console.error('FATAL:', e); process.exit(1); });
