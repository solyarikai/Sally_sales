/**
 * Clay CSV Upload + Findymail Enrichment
 *
 * Two scenarios:
 *   A) Upload domains CSV → "Find people at these companies" → Findymail email enrichment
 *   B) Upload contacts CSV (with LinkedIn URLs) → Findymail email enrichment
 *
 * ONLY uses Findymail enrichment. No Clay credits spent.
 * All UI interactions via Puppeteer stealth browser.
 *
 * Usage:
 *   # Scenario B: contacts with LinkedIn → enrich emails
 *   node clay_enrich.js --file contacts.csv --enrich findymail --linkedin-col "LinkedIn"
 *
 *   # Scenario A: domains → find people → enrich emails
 *   node clay_enrich.js --file domains.csv --find-people --titles "CEO,CFO,Founder" --enrich findymail
 *
 *   # Flags
 *   --auto          Close browser after completion
 *   --headless      Run headless (for server)
 *   --output path   Output file (default: exports/enriched_TIMESTAMP.json)
 *   --table-id ID   Skip upload, use existing Clay table
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
// Session management (shared with other clay scripts)
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
  try {
    fs.writeFileSync(SESSION_FILE, JSON.stringify({
      value: cookieValue,
      savedAt: new Date().toISOString(),
    }, null, 2));
    console.log('  Session saved');
  } catch (e) {
    console.log(`  WARNING: Cannot save session (${e.code || e.message}). Continuing with current session.`);
  }
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
  const fname = `enrich_${name}.png`;
  await page.screenshot({ path: path.join(OUT_DIR, fname), fullPage: false });
  console.log(`  [img] ${fname}`);
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

async function findClickableByText(page, text, exact = false) {
  return page.evaluate((text, exact) => {
    const els = [...document.querySelectorAll('button, div[role="button"], div[role="menuitem"], div[role="option"], a, li')];
    for (const el of els) {
      const t = el.textContent?.trim() || '';
      const match = exact ? t === text : t.toLowerCase().includes(text.toLowerCase());
      if (match && el.offsetParent !== null) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 10) return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: t.substring(0, 80) };
      }
    }
    return null;
  }, text, exact);
}

function extractIdsFromUrl(url) {
  const tableMatch = url.match(/tableId=([^&]+)/);
  const wbMatch = url.match(/workbookId=([^&]+)/);
  const pathMatch = url.match(/tables\/([^/?]+)/);
  return {
    tableId: tableMatch?.[1] || pathMatch?.[1] || null,
    workbookId: wbMatch?.[1] || null,
  };
}

async function listVisibleButtons(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('button, div[role="button"]')]
      .filter(b => b.offsetParent !== null)
      .map(b => b.textContent?.trim().substring(0, 80))
      .filter(t => t && t.length > 1)
  );
}

async function listVisibleInputs(page) {
  return page.evaluate(() =>
    [...document.querySelectorAll('input, textarea')]
      .filter(i => i.offsetParent !== null)
      .map(i => ({ placeholder: i.placeholder, type: i.type, name: i.name, id: i.id }))
  );
}

// ============================================================
// Step 1: Upload CSV to Clay
// ============================================================

async function uploadCSV(page, filePath) {
  console.log('\n[UPLOAD] Uploading CSV to Clay...');
  console.log(`  File: ${filePath}`);

  // Step 1: Navigate to workspace home
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  // Step 2: Create new workbook via "New" button
  console.log('  Creating new workbook...');
  const newBtn = await page.$('[data-testid="create-new"]');
  if (!newBtn) {
    await screenshot(page, 'upload_err_no_new_btn');
    throw new Error('"New" button (data-testid="create-new") not found on workspace home');
  }
  await newBtn.click();
  await humanDelay(1000, 2000);

  const wbBtn = await page.$('[data-testid="new-workbook"]');
  if (!wbBtn) {
    await screenshot(page, 'upload_err_no_workbook_btn');
    throw new Error('"Workbook" option (data-testid="new-workbook") not found in New menu');
  }
  await wbBtn.click();
  await humanDelay(3000, 5000);
  console.log(`  Workbook created: ${page.url()}`);
  await screenshot(page, 'upload_01_workbook_created');

  // Step 3: Click "Import from CSV" inside the workbook
  const csvBtn = await findClickableByText(page, 'Import from CSV');
  if (!csvBtn) {
    const btns = await listVisibleButtons(page);
    console.log('  Available buttons:', btns.join(' | '));
    await screenshot(page, 'upload_err_no_csv_btn');
    throw new Error('"Import from CSV" button not found in workbook');
  }
  console.log(`  Clicking: "${csvBtn.text}"`);
  await page.mouse.click(csvBtn.x, csvBtn.y);
  await humanDelay(2000, 3000);
  await screenshot(page, 'upload_02_csv_clicked');

  // Step 4: Find file input (may be hidden with display:none) and upload
  let fileInput = await page.$('input[type="file"]');
  if (!fileInput) {
    // Wait a bit more and retry
    await humanDelay(2000, 3000);
    fileInput = await page.$('input[type="file"]');
  }
  if (!fileInput) {
    await screenshot(page, 'upload_err_no_file_input');
    throw new Error('No file input found after clicking Import from CSV');
  }
  console.log('  Uploading file...');
  await fileInput.uploadFile(filePath);
  await humanDelay(3000, 5000);
  await screenshot(page, 'upload_03_file_uploaded');

  // Step 5: Click "Complete import" button
  for (const label of ['Complete import', 'Import', 'Continue', 'Create table', 'Confirm', 'Done']) {
    const btn = await findClickableByText(page, label);
    if (btn) {
      console.log(`  Clicking: "${btn.text}"`);
      await page.mouse.click(btn.x, btn.y);
      await humanDelay(3000, 5000);
      break;
    }
  }

  await screenshot(page, 'upload_04_imported');

  // Extract table ID from URL
  let tableId = null;
  for (let i = 0; i < 20; i++) {
    const ids = extractIdsFromUrl(page.url());
    if (ids.tableId) {
      tableId = ids.tableId;
      console.log(`  Table created: ${tableId}`);
      break;
    }
    await sleep(2000);
    if (i % 5 === 0 && i > 0) console.log(`  Waiting for table URL... (${i * 2}s)`);
  }

  if (!tableId) {
    await screenshot(page, 'upload_06_no_table_id');
    throw new Error('Table ID not found after upload');
  }

  // Wait for data to load
  await humanDelay(3000, 5000);
  await screenshot(page, 'upload_06_table_ready');

  return tableId;
}

// ============================================================
// Step 2: Find People at These Companies (Scenario A)
// ============================================================

async function findPeopleAtCompanies(page, tableId, titles) {
  console.log('\n[FIND PEOPLE] Finding people at companies...');
  console.log(`  Table: ${tableId}`);
  console.log(`  Titles: ${titles.join(', ')}`);

  // Make sure we're on the table page
  if (!page.url().includes(tableId)) {
    await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/tables/${tableId}`, { waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(3000, 5000);
  }

  // Open Tools panel (right sidebar)
  // Look for "Tools" button or the panel might already be visible
  const toolsBtn = await findClickableByText(page, 'Tools');
  if (toolsBtn) {
    console.log('  Opening Tools panel...');
    await page.mouse.click(toolsBtn.x, toolsBtn.y);
    await humanDelay(1000, 2000);
  }

  // Click "Sources" tab if visible
  const sourcesTab = await findClickableByText(page, 'Sources');
  if (sourcesTab) {
    await page.mouse.click(sourcesTab.x, sourcesTab.y);
    await humanDelay(1000, 1500);
  }

  await screenshot(page, 'find_01_tools_panel');

  // Click "Find people at these companies"
  const findPeopleBtn = await findClickableByText(page, 'Find people at these companies');
  if (!findPeopleBtn) {
    const btns = await listVisibleButtons(page);
    console.log('  Buttons:', btns.join(' | '));
    await screenshot(page, 'find_02_no_find_people');
    throw new Error('"Find people at these companies" not found');
  }
  console.log(`  Clicking: "${findPeopleBtn.text}"`);
  await page.mouse.click(findPeopleBtn.x, findPeopleBtn.y);
  await humanDelay(3000, 5000);

  await screenshot(page, 'find_02_filter_page');

  // Now we're on the "Refine with filters" page
  // Expand "Job title" section and add titles
  console.log('  Applying job title filters...');
  const jobTitleSection = await findClickableByText(page, 'Job title');
  if (jobTitleSection) {
    await page.mouse.click(jobTitleSection.x, jobTitleSection.y);
    await humanDelay(800, 1200);
  }

  // Find title input — try multiple placeholder patterns
  for (const placeholder of ['Add a job title', 'CEO', 'Search', 'Type to search', 'job title']) {
    const input = await page.$(`input[placeholder*="${placeholder}" i]`);
    if (input) {
      for (const title of titles) {
        await input.click();
        await humanDelay(200, 400);
        await input.type(title, { delay: 30 + Math.random() * 40 });
        await humanDelay(500, 800);
        await page.keyboard.press('Enter');
        await humanDelay(300, 500);
      }
      console.log(`    Added ${titles.length} titles`);
      // Dismiss any dropdown
      await page.keyboard.press('Escape');
      await humanDelay(300, 500);
      break;
    }
  }

  await humanDelay(2000, 3000);
  await screenshot(page, 'find_03_titles_applied');

  // Check result count
  const resultCount = await page.evaluate(() => {
    const text = document.body.textContent || '';
    const match = text.match(/([\d,]+)\s*(?:people|results|contacts|leads)/i);
    return match ? match[1] : null;
  });
  console.log(`  Results: ${resultCount || 'unknown'}`);

  // Click Continue → "Save to new workbook and table"
  console.log('  Clicking Continue dropdown...');
  const continueBtnInfo = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null);
    const btn = buttons.find(b => b.textContent?.trim().startsWith('Continue'));
    if (!btn) return null;
    const rect = btn.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, right: rect.x + rect.width - 8 };
  });

  if (!continueBtnInfo) {
    const btns = await listVisibleButtons(page);
    console.log('  Buttons:', btns.join(' | '));
    throw new Error('Continue button not found');
  }

  // Multi-attempt dropdown click (proven pattern from other scripts)
  let dropdownOption = null;
  for (let attempt = 0; attempt < 4 && !dropdownOption; attempt++) {
    if (attempt > 0) {
      await page.keyboard.press('Escape');
      await humanDelay(500, 800);
    }
    if (attempt < 2) {
      await page.mouse.click(continueBtnInfo.right, continueBtnInfo.y);
    } else {
      await page.mouse.click(continueBtnInfo.x, continueBtnInfo.y);
    }
    await humanDelay(1200, 2000);

    dropdownOption = await page.evaluate(() => {
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

  if (dropdownOption) {
    console.log(`  Found: "${dropdownOption.text}"`);
    await page.mouse.click(dropdownOption.x, dropdownOption.y);
  } else {
    await screenshot(page, 'find_04_no_dropdown');
    throw new Error('Dropdown "Save to new workbook and table" not found');
  }

  await humanDelay(5000, 8000);
  await screenshot(page, 'find_04_after_continue');

  // Skip enrichments → Create table
  const isEnrichPage = await page.evaluate(() =>
    document.body.textContent?.includes('Enrich') || document.body.textContent?.includes('enrichment')
  );

  let newTableId = extractIdsFromUrl(page.url()).tableId;

  if (isEnrichPage) {
    await humanDelay(1500, 2500);
    const createTableBtn = await findByText(page, 'Create table', false);
    if (createTableBtn) {
      console.log('  Clicking "Create table" (skip enrichments)...');
      await page.mouse.click(createTableBtn.x, createTableBtn.y);
      await humanDelay(8000, 12000);
    }
    newTableId = extractIdsFromUrl(page.url()).tableId;
  }

  // Poll for table ID if not found yet
  for (let i = 0; i < 15 && !newTableId; i++) {
    await sleep(2000);
    newTableId = extractIdsFromUrl(page.url()).tableId;
  }

  if (!newTableId) throw new Error('New table ID not found after Find People');

  console.log(`  New people table: ${newTableId}`);

  // Wait for table to populate
  await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(5000, 8000);
  await screenshot(page, 'find_05_people_table');

  return newTableId;
}

// ============================================================
// Step 3: Add Findymail Enrichment
// ============================================================

async function addFindymailEnrichment(page, tableId, linkedinColName) {
  console.log('\n[FINDYMAIL] Adding Findymail enrichment...');
  console.log(`  Table: ${tableId}`);
  console.log(`  LinkedIn column: ${linkedinColName}`);

  // Make sure we're on the table page
  if (!page.url().includes(tableId)) {
    await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/tables/${tableId}`, { waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(3000, 5000);
  }

  await screenshot(page, 'findymail_01_table');

  // Click "+ Add column"
  const addColBtn = await findClickableByText(page, 'Add column');
  if (!addColBtn) {
    // Try finding "+" button near table header
    const plusCol = await page.evaluate(() => {
      const els = [...document.querySelectorAll('button, div[role="button"]')];
      const el = els.find(e => {
        const t = e.textContent?.trim();
        return (t === '+' || t === '+ Add column') && e.offsetParent !== null;
      });
      if (!el) return null;
      const rect = el.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    });
    if (plusCol) {
      await page.mouse.click(plusCol.x, plusCol.y);
    } else {
      const btns = await listVisibleButtons(page);
      console.log('  Buttons:', btns.join(' | '));
      throw new Error('"+ Add column" not found');
    }
  } else {
    console.log(`  Clicking: "${addColBtn.text}"`);
    await page.mouse.click(addColBtn.x, addColBtn.y);
  }

  await humanDelay(1500, 2500);
  await screenshot(page, 'findymail_02_add_column_panel');

  // Right panel should now show enrichment search
  // Type "findymail" in the search input
  const searchInput = await page.evaluate(() => {
    // Look for the search input in the right panel
    const inputs = [...document.querySelectorAll('input[placeholder*="Search"], input[placeholder*="search"], input[type="search"]')];
    const visible = inputs.filter(i => i.offsetParent !== null);
    if (visible.length > 0) {
      const rect = visible[0].getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    }
    // Fallback: any focused or prominent input in right side of screen
    const rightInputs = [...document.querySelectorAll('input')]
      .filter(i => i.offsetParent !== null && i.getBoundingClientRect().x > 800);
    if (rightInputs.length > 0) {
      const rect = rightInputs[0].getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
    }
    return null;
  });

  if (searchInput) {
    await page.mouse.click(searchInput.x, searchInput.y);
    await humanDelay(300, 500);
    await page.keyboard.type('findymail', { delay: 50 + Math.random() * 30 });
    await humanDelay(1500, 2500);
  } else {
    // Try just typing — sometimes the search is auto-focused
    console.log('  No search input found, trying to type directly...');
    await page.keyboard.type('findymail', { delay: 50 + Math.random() * 30 });
    await humanDelay(1500, 2500);
  }

  await screenshot(page, 'findymail_03_search_results');

  // Click "Find Work Email from Profile URL" (Enrichment • Findymail)
  const findymailOption = await page.evaluate(() => {
    const allEls = [...document.querySelectorAll('div, button, li, a, span')];
    for (const el of allEls) {
      const t = el.textContent?.trim().toLowerCase() || '';
      if (t.includes('find work email from profile url') && el.offsetParent !== null) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 100 && rect.height > 20) {
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: el.textContent.trim().substring(0, 80) };
        }
      }
    }
    // Fallback: any element mentioning "profile url" + "findymail"
    for (const el of allEls) {
      const t = el.textContent?.trim().toLowerCase() || '';
      if (t.includes('profile url') && t.includes('findymail') && el.offsetParent !== null) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 100) return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: el.textContent.trim().substring(0, 80) };
      }
    }
    return null;
  });

  if (findymailOption) {
    console.log(`  Clicking: "${findymailOption.text}"`);
    await page.mouse.click(findymailOption.x, findymailOption.y);
  } else {
    // List what we see in the search results
    const results = await page.evaluate(() => {
      return [...document.querySelectorAll('div, li')]
        .filter(el => el.offsetParent !== null && el.textContent?.toLowerCase().includes('findymail'))
        .map(el => el.textContent.trim().substring(0, 100));
    });
    console.log('  Findymail results found:', results);
    await screenshot(page, 'findymail_04_not_found');
    throw new Error('"Find Work Email from Profile URL" not found in enrichment list');
  }

  await humanDelay(2000, 3500);
  await screenshot(page, 'findymail_04_config');

  // Now we need to map the LinkedIn column as input
  // Clay shows a configuration panel for the enrichment
  // Look for dropdown/select that maps the LinkedIn column
  console.log('  Configuring input mapping...');

  // Look for a dropdown or select that mentions "LinkedIn" or "Profile URL" or column selection
  // Usually Clay shows a dropdown with available columns
  const configureInput = await page.evaluate((linkedinCol) => {
    // Find any dropdown, select, or clickable element that could be the column selector
    const selects = [...document.querySelectorAll('select, [role="listbox"], [role="combobox"]')];
    for (const s of selects) {
      if (s.offsetParent !== null) {
        const rect = s.getBoundingClientRect();
        return { type: 'select', x: rect.x + rect.width / 2, y: rect.y + rect.height / 2 };
      }
    }

    // Look for buttons/divs that look like column selectors (often show "Select column" or a column name)
    const els = [...document.querySelectorAll('button, div[role="button"], div[class*="select"], div[class*="dropdown"]')];
    for (const el of els) {
      const t = el.textContent?.trim().toLowerCase() || '';
      if ((t.includes('select') || t.includes('column') || t.includes('choose') || t.includes('linkedin') || t.includes('profile'))
          && el.offsetParent !== null) {
        const rect = el.getBoundingClientRect();
        if (rect.width > 50 && rect.height > 15 && rect.x > 200) {
          return { type: 'dropdown', x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: t.substring(0, 50) };
        }
      }
    }

    return null;
  }, linkedinColName);

  if (configureInput) {
    console.log(`  Found config element (${configureInput.type}): ${configureInput.text || ''}`);
    await page.mouse.click(configureInput.x, configureInput.y);
    await humanDelay(800, 1500);

    // Now look for the LinkedIn column option in the dropdown
    const linkedinOption = await page.evaluate((colName) => {
      const options = [...document.querySelectorAll('div[role="option"], li, div[role="menuitem"], option')];
      for (const opt of options) {
        const t = opt.textContent?.trim() || '';
        if (t.toLowerCase().includes(colName.toLowerCase()) && opt.offsetParent !== null) {
          const rect = opt.getBoundingClientRect();
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: t.substring(0, 50) };
        }
      }
      // Broader search: any visible element matching the column name
      const els = [...document.querySelectorAll('div, span, li')];
      for (const el of els) {
        const t = el.textContent?.trim() || '';
        if (t === colName && el.offsetParent !== null) {
          const rect = el.getBoundingClientRect();
          if (rect.width > 20) return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: t };
        }
      }
      return null;
    }, linkedinColName);

    if (linkedinOption) {
      console.log(`  Selecting column: "${linkedinOption.text}"`);
      await page.mouse.click(linkedinOption.x, linkedinOption.y);
      await humanDelay(800, 1200);
    } else {
      console.log(`  WARNING: Column "${linkedinColName}" not found in dropdown`);
      await screenshot(page, 'findymail_05_no_column');
    }
  } else {
    // Clay might auto-detect the LinkedIn column — check if it's already mapped
    console.log('  No column selector found — Clay may have auto-mapped the column');
  }

  await screenshot(page, 'findymail_05_configured');

  // Click "Save" / "Run" / "Continue" / "Enrich" to start the enrichment
  for (const label of ['Save', 'Run enrichment', 'Enrich', 'Continue', 'Run', 'Apply']) {
    const btn = await findClickableByText(page, label);
    if (btn) {
      console.log(`  Clicking: "${btn.text}"`);
      await page.mouse.click(btn.x, btn.y);
      await humanDelay(2000, 3000);
      break;
    }
  }

  await screenshot(page, 'findymail_06_started');
  console.log('  Findymail enrichment started!');
}

// ============================================================
// Step 4: Wait for Enrichment to Complete
// ============================================================

async function waitForEnrichment(page, tableId, timeoutMs = 600000) {
  console.log(`\n[WAIT] Waiting for enrichment to complete (timeout: ${timeoutMs / 1000}s)...`);

  const startTime = Date.now();
  let lastFilledCount = 0;
  let staleRounds = 0;

  while (Date.now() - startTime < timeoutMs) {
    await sleep(15000);

    // Read table metadata to find the enrichment column
    const tableMeta = await page.evaluate(async (tid) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}`, {
          credentials: 'include', headers: { 'Accept': 'application/json' },
        });
        return await res.json();
      } catch (e) { return { error: e.message }; }
    }, tableId);

    const fields = tableMeta?.table?.fields || [];
    const totalRecords = await page.evaluate(async (tid) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}/count`, {
          credentials: 'include', headers: { 'Accept': 'application/json' },
        });
        const d = await res.json();
        return d.tableTotalRecordsCount || 0;
      } catch { return 0; }
    }, tableId);

    // Find the email/findymail column (usually last column or one named "email" / "work email")
    const emailField = fields.find(f =>
      f.name?.toLowerCase().includes('email') ||
      f.name?.toLowerCase().includes('findymail') ||
      f.name?.toLowerCase().includes('work email')
    );

    if (!emailField) {
      const elapsed = Math.round((Date.now() - startTime) / 1000);
      console.log(`  [${elapsed}s] No email column found yet. Fields: ${fields.map(f => f.name).join(', ')}`);
      continue;
    }

    // Sample some records to check enrichment progress
    const viewId = tableMeta?.table?.firstViewId;
    if (!viewId) continue;

    const idsData = await page.evaluate(async (tid, vid) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}/views/${vid}/records/ids`, {
          credentials: 'include', headers: { 'Accept': 'application/json' },
        });
        return await res.json();
      } catch { return {}; }
    }, tableId, viewId);

    const recordIds = idsData?.results || [];

    // Fetch a sample batch to count filled cells
    const sampleIds = recordIds.slice(0, Math.min(200, recordIds.length));
    const batchData = await page.evaluate(async (tid, ids) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}/bulk-fetch-records`, {
          method: 'POST', credentials: 'include',
          headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
          body: JSON.stringify({ recordIds: ids }),
        });
        return await res.json();
      } catch { return {}; }
    }, tableId, sampleIds);

    const records = batchData?.results || [];
    let filled = 0;
    for (const rec of records) {
      const cell = rec.cells?.[emailField.id];
      if (cell?.value && String(cell.value).includes('@')) filled++;
    }

    const elapsed = Math.round((Date.now() - startTime) / 1000);
    const pct = records.length > 0 ? Math.round(filled / records.length * 100) : 0;
    console.log(`  [${elapsed}s] Email enrichment: ${filled}/${records.length} sampled (${pct}%) | Total rows: ${totalRecords}`);

    if (filled === lastFilledCount) {
      staleRounds++;
    } else {
      staleRounds = 0;
      lastFilledCount = filled;
    }

    // Consider done if: high fill rate on sample, or stale for 3+ rounds (enrichment finished)
    if ((pct >= 80 && staleRounds >= 1) || staleRounds >= 4) {
      console.log('  Enrichment appears complete (or stalled).');
      break;
    }
  }

  console.log('  Enrichment wait complete.');
}

// ============================================================
// Step 5: Read & Export Results
// ============================================================

async function readTableRecords(page, tableId) {
  console.log(`\n[READ] Reading table data (${tableId})...`);

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

  const viewId = tableMeta?.table?.firstViewId;
  if (!viewId) throw new Error('No view ID found');

  const idsData = await page.evaluate(async (tid, vid) => {
    try {
      const res = await fetch(`https://api.clay.com/v3/tables/${tid}/views/${vid}/records/ids`, {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      return await res.json();
    } catch (e) { return { error: e.message }; }
  }, tableId, viewId);

  const recordIds = idsData?.results || [];
  console.log(`  Records: ${recordIds.length}`);

  // Fetch in batches of 200
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

    const batchRecords = batchData?.results || [];
    allRecords.push(...batchRecords);
    console.log(`  Batch ${Math.floor(i / batchSize) + 1}: +${batchRecords.length} (total: ${allRecords.length})`);
    await humanDelay(500, 1000);
  }

  // Parse records
  const parsed = allRecords.map(record => {
    const row = {};
    for (const [fieldId, cell] of Object.entries(record.cells || {})) {
      const fieldName = fieldMap[fieldId] || fieldId;
      let value = cell?.value;
      if (value && typeof value === 'object' && value.optionIds) {
        value = (cell?.metadata?.valueDisplay || cell?.metadata?.display || JSON.stringify(value.optionIds));
      }
      if (value !== null && value !== undefined) row[fieldName] = String(value).substring(0, 1000);
    }
    row._id = record.id;
    return row;
  });

  console.log(`  Parsed: ${parsed.length} records`);
  if (parsed.length > 0) {
    console.log(`  Columns: ${Object.keys(parsed[0]).join(', ')}`);
  }

  return { records: parsed, fieldMap, tableMeta };
}

// ============================================================
// Main
// ============================================================

async function main() {
  const args = process.argv.slice(2);

  // Parse CLI arguments
  const getArg = (flag) => {
    const idx = args.indexOf(flag);
    return idx >= 0 && idx + 1 < args.length ? args[idx + 1] : null;
  };
  const hasFlag = (flag) => args.includes(flag);

  const filePath = getArg('--file');
  const findPeople = hasFlag('--find-people');
  const enrich = getArg('--enrich') || (hasFlag('--enrich') ? 'findymail' : null);
  const titles = getArg('--titles')?.split(',').map(t => t.trim()) || ['CEO', 'CFO', 'Founder', 'CTO', 'COO', 'Head of Payments', 'VP of Finance', 'Director'];
  const linkedinCol = getArg('--linkedin-col') || 'LinkedIn';
  const autoClose = hasFlag('--auto');
  const headless = hasFlag('--headless');
  const existingTableId = getArg('--table-id');
  const outputPath = getArg('--output') || path.join(OUT_DIR, `enriched_${Date.now()}.json`);

  console.log('\n=== Clay CSV Upload + Findymail Enrichment ===\n');
  console.log(`  File: ${filePath || '(none — using --table-id)'}`);
  console.log(`  Find people: ${findPeople}`);
  console.log(`  Enrich: ${enrich}`);
  console.log(`  LinkedIn col: ${linkedinCol}`);
  console.log(`  Titles: ${titles.join(', ')}`);
  console.log(`  Headless: ${headless}`);
  console.log(`  Output: ${outputPath}`);

  if (!filePath && !existingTableId) {
    console.error('ERROR: Provide --file <path> or --table-id <id>');
    process.exit(1);
  }

  // Launch browser
  console.log('\n[1] Launching stealth browser...');
  const browser = await puppeteer.launch({
    headless: headless ? 'new' : false,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900', '--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.setUserAgent(USER_AGENT);
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
  });

  // Load & validate session
  const session = loadSession();
  if (!session.value) {
    console.log('  ERROR: No session. Run: node clay_tam_export.js --login-only');
    await browser.close();
    process.exit(1);
  }
  console.log(`  Session from: ${session.savedAt}`);
  await setSessionCookie(page, session.value);

  console.log('\n[2] Validating session...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  let sessionCheck = await validateSession(page);
  if (!sessionCheck.valid) {
    console.log('  Session expired! Waiting for manual login...');
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
    if (!sessionCheck.valid) throw new Error('Session still invalid after login');
  }

  const creditsBefore = sessionCheck.credits || await getCredits(page);
  console.log(`  Credits: ${JSON.stringify(creditsBefore)}`);

  let tableId = existingTableId;

  try {
    // Step 1: Upload CSV (if file provided)
    if (filePath && !existingTableId) {
      const absPath = path.resolve(filePath);
      if (!fs.existsSync(absPath)) throw new Error(`File not found: ${absPath}`);
      tableId = await uploadCSV(page, absPath);
    }

    // Step 2: Find People at Companies (Scenario A)
    if (findPeople) {
      tableId = await findPeopleAtCompanies(page, tableId, titles);
    }

    // Step 3: Add Findymail Enrichment
    if (enrich === 'findymail') {
      await addFindymailEnrichment(page, tableId, linkedinCol);

      // Step 4: Wait for enrichment
      await waitForEnrichment(page, tableId);
    }

    // Step 5: Read & Export results
    const { records, fieldMap } = await readTableRecords(page, tableId);

    // Save to JSON
    fs.mkdirSync(path.dirname(outputPath), { recursive: true });
    fs.writeFileSync(outputPath, JSON.stringify(records, null, 2));
    console.log(`\n  Saved ${records.length} records to ${outputPath}`);

    // Count enriched emails
    const emailKeys = Object.values(fieldMap).filter(n => n.toLowerCase().includes('email'));
    let enrichedCount = 0;
    for (const rec of records) {
      for (const key of emailKeys) {
        if (rec[key] && rec[key].includes('@')) { enrichedCount++; break; }
      }
    }
    console.log(`  Records with email: ${enrichedCount}/${records.length}`);

  } catch (err) {
    console.error(`\nERROR: ${err.message}`);
    await screenshot(page, 'error_final');
  }

  // Final credit check
  console.log('\n[CREDITS] Final check...');
  const creditsAfter = await getCredits(page);
  console.log(`  Before: ${JSON.stringify(creditsBefore)}`);
  console.log(`  After:  ${JSON.stringify(creditsAfter)}`);
  if (creditsBefore && creditsAfter) {
    const spent = (creditsBefore.basic || 0) - (creditsAfter.basic || 0);
    console.log(`  Clay credits spent: ${spent}`);
    if (spent > 0) console.log('  WARNING: Clay credits were spent!');
    else console.log('  OK: No Clay credits spent.');
  }

  // Save session
  const endCookies = await page.cookies('https://api.clay.com');
  const endSession = endCookies.find(c => c.name === 'claysession');
  if (endSession) saveSession(endSession.value);

  console.log('\n=== Done! ===');

  if (autoClose) {
    await browser.close();
  } else {
    console.log('Browser stays open. Press Ctrl+C to close.\n');
    await sleep(600000);
    await browser.close();
  }
}

main().catch(err => {
  console.error('Fatal error:', err.message);
  process.exit(1);
});
