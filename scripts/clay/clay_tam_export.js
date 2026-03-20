/**
 * Clay TAM Export Pipeline
 *
 * Flow:
 * 1. Takes ICP context as text (operator chat, description, etc.)
 * 2. Uses GPT-4o-mini to map ICP → Clay filter parameters
 * 3. Opens Clay via Puppeteer stealth, applies filters
 * 4. Exports contacts WITHOUT emails (free, no credits)
 * 5. Checks credits before/after to verify 0 spent
 *
 * Usage: node clay_tam_export.js "Companies selling gaming skins for CS2, Dota2, Roblox etc."
 *   or:  node clay_tam_export.js --test  (runs with gaming skins ICP, exports max 5)
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
// Session management — persistent cookie storage + auto-refresh
// ============================================================

function loadSession() {
  try {
    if (fs.existsSync(SESSION_FILE)) {
      const data = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));
      if (data.value) return data;
    }
  } catch {}
  // Fallback to hardcoded (initial setup)
  return {
    value: 's%3AsydgrI74YLdGMrU8LWzQSmCv-IrJgDYg.FYCecoCtfmRICI19MVyPsTXRxlfUAfoeKSLns5ofeGw',
    savedAt: null,
  };
}

function saveSession(cookieValue) {
  fs.writeFileSync(SESSION_FILE, JSON.stringify({
    value: cookieValue,
    savedAt: new Date().toISOString(),
  }, null, 2));
  console.log('  Session saved to clay_session.json');
}

async function setSessionCookie(page, cookieValue) {
  await page.setCookie({
    name: 'claysession',
    value: cookieValue,
    domain: 'api.clay.com', path: '/', httpOnly: true, secure: true, sameSite: 'None',
  });
}

async function validateSession(page) {
  const result = await page.evaluate(async () => {
    try {
      const res = await fetch('https://api.clay.com/v3/subscriptions/889252', {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      if (res.status === 401 || res.status === 403) return { valid: false, status: res.status };
      const data = await res.json();
      return { valid: !!data.creditBalances, status: res.status, credits: data.creditBalances };
    } catch (e) { return { valid: false, error: e.message }; }
  });
  return result;
}

async function refreshSession(browser, page) {
  console.log('\n[AUTH] Session expired — opening Clay login page for re-authentication...');
  console.log('  Please log in manually in the browser window.');
  console.log('  The script will detect login automatically and continue.\n');

  // Navigate to Clay login
  await page.goto('https://app.clay.com/login', { waitUntil: 'networkidle2', timeout: 30000 });

  // Poll for successful auth (check every 3s for up to 5 minutes)
  for (let i = 0; i < 100; i++) {
    await sleep(3000);
    const cookies = await page.cookies('https://api.clay.com');
    const sessionCookie = cookies.find(c => c.name === 'claysession');
    if (sessionCookie) {
      // Verify it works
      const check = await validateSession(page);
      if (check.valid) {
        console.log(`  [AUTH] Login detected! Session refreshed.`);
        saveSession(sessionCookie.value);
        return sessionCookie.value;
      }
    }
    // Also check if URL changed away from login (user logged in via UI)
    const url = page.url();
    if (url.includes('/workspaces/') || url.includes('/home')) {
      const cookies2 = await page.cookies('https://api.clay.com');
      const sc = cookies2.find(c => c.name === 'claysession');
      if (sc) {
        saveSession(sc.value);
        return sc.value;
      }
    }
    if (i % 10 === 0 && i > 0) console.log(`  [AUTH] Still waiting for login... (${i * 3}s)`);
  }

  throw new Error('Login timeout — no valid session after 5 minutes');
}

// ============================================================
// GPT / Gemini: Map ICP text → Clay filters
// ============================================================

const CLAY_FILTER_SCHEMA = {
  industries: { type: 'array', description: 'Clay industry tags, e.g. ["Online gaming", "E-commerce", "Computer games"]' },
  industries_exclude: { type: 'array', description: 'Industries to exclude' },
  sizes: { type: 'array', description: 'Company size ranges, e.g. ["1-10", "11-50", "51-200"]' },
  types: { type: 'array', description: 'Company types, e.g. ["Privately held"]' },
  country_names: { type: 'array', description: 'Countries to include, e.g. ["United States", "Germany"]' },
  country_names_exclude: { type: 'array', description: 'Countries to exclude' },
  annual_revenues: { type: 'array', description: 'Revenue ranges, e.g. ["$1M - $5M", "$5M - $10M"]' },
  description_keywords: { type: 'array', description: 'Keywords that must appear in company description' },
  description_keywords_exclude: { type: 'array', description: 'Keywords to exclude from description' },
  minimum_member_count: { type: 'number', description: 'Min employees' },
  maximum_member_count: { type: 'number', description: 'Max employees' },
  semantic_description: { type: 'string', description: 'Free-text semantic search for company type' },
};

async function mapIcpToFilters(icpText) {
  // Try Gemini first (free), fallback to GPT-4o-mini
  const apiKey = process.env.OPENAI_API_KEY || '';
  const geminiKey = process.env.GOOGLE_GEMINI_API_KEY || process.env.GEMINI_API_KEY || '';

  const systemPrompt = `You are a Clay.com search filter expert. Given an ICP (Ideal Customer Profile) description, output a JSON object with Clay search filters.

Available filter fields:
${JSON.stringify(CLAY_FILTER_SCHEMA, null, 2)}

Rules:
- Use description_keywords for niche-specific terms the company description would contain
- Use semantic_description for a natural language description of the company type
- Be specific with industries — use Clay's industry taxonomy (LinkedIn-style industries)
- For gaming skin companies: use keywords like "skins", "CS2", "CSGO", "gaming marketplace", "virtual items"
- Only include filters that are clearly specified or strongly implied by the ICP
- Output ONLY valid JSON, no explanation

Example output for "SaaS companies in US, 50-200 employees":
{"industries":["Software development","SaaS"],"sizes":["51-200"],"country_names":["United States"],"description_keywords":["software","SaaS","platform"]}`;

  const userPrompt = `Map this ICP to Clay search filters:\n\n${icpText}`;

  let filters = null;

  // Try OpenAI GPT-4o-mini
  if (apiKey) {
    try {
      const res = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'gpt-4o-mini',
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userPrompt },
          ],
          temperature: 0.1,
          response_format: { type: 'json_object' },
        }),
      });
      const data = await res.json();
      filters = JSON.parse(data.choices[0].message.content);
      console.log('  [GPT-4o-mini] Filters generated');
    } catch (e) {
      console.log(`  [GPT] Error: ${e.message}`);
    }
  }

  // Fallback: Try Gemini
  if (!filters && geminiKey) {
    try {
      const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${geminiKey}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          contents: [{ parts: [{ text: `${systemPrompt}\n\n${userPrompt}` }] }],
          generationConfig: { temperature: 0.1 },
        }),
      });
      const data = await res.json();
      const text = data.candidates?.[0]?.content?.parts?.[0]?.text || '';
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (jsonMatch) {
        filters = JSON.parse(jsonMatch[0]);
        console.log('  [Gemini] Filters generated');
      }
    } catch (e) {
      console.log(`  [Gemini] Error: ${e.message}`);
    }
  }

  if (!filters) {
    console.error('  No API key available. Set OPENAI_API_KEY or GEMINI_API_KEY');
    process.exit(1);
  }

  return filters;
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

async function getCredits(page) {
  const data = await page.evaluate(async () => {
    try {
      const res = await fetch('https://api.clay.com/v3/subscriptions/889252', {
        credentials: 'include', headers: { 'Accept': 'application/json' },
      });
      const d = await res.json();
      return d.creditBalances;
    } catch { return null; }
  });
  return data;
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

// Type into a Clay filter input field
async function fillFilterField(page, placeholder, values) {
  if (!values || values.length === 0) return false;

  // Find input by placeholder
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
    // Press Enter to select from dropdown
    await page.keyboard.press('Enter');
    await humanDelay(300, 600);
  }
  console.log(`    ${placeholder}: ${values.join(', ')}`);
  return true;
}

// Type into a number input
async function fillNumberField(page, placeholder, value) {
  if (value === null || value === undefined) return false;
  const input = await page.$(`input[placeholder="${placeholder}"]`);
  if (!input) return false;
  await input.click({ clickCount: 3 });
  await input.type(String(value), { delay: 40 });
  await humanDelay(200, 400);
  console.log(`    ${placeholder}: ${value}`);
  return true;
}

// ============================================================
// Main pipeline
// ============================================================

async function main() {
  const args = process.argv.slice(2);
  const isTest = args.includes('--test');
  const isLoginOnly = args.includes('--login-only');
  const headless = args.includes('--headless');
  const maxExport = isTest ? 5 : 50;
  const icpText = isTest || isLoginOnly
    ? 'Companies selling gaming skins, virtual items, loot boxes for games like CS2, CSGO, Dota2, Roblox, WoW, FIFA. Gaming marketplace platforms. Skin trading sites.'
    : args.filter(a => !a.startsWith('--')).join(' ');

  if (!icpText && !isLoginOnly) {
    console.log('Usage: node clay_tam_export.js "ICP description text"');
    console.log('       node clay_tam_export.js --test');
    console.log('       node clay_tam_export.js --login-only  (refresh session only)');
    process.exit(0);
  }

  console.log(`\n=== Clay TAM Export Pipeline ===`);
  console.log(`ICP: ${icpText.substring(0, 100)}...`);
  console.log(`Max export: ${maxExport} contacts`);

  // Step 1: Map ICP to Clay filters (or load pre-computed filters)
  console.log('\n[1] Mapping ICP to Clay filters...');
  let filters;
  const precomputedFilters = path.join(OUT_DIR, 'filters_input.json');
  if (fs.existsSync(precomputedFilters)) {
    filters = JSON.parse(fs.readFileSync(precomputedFilters, 'utf-8'));
    console.log('  Loaded pre-computed filters');
    fs.unlinkSync(precomputedFilters); // Clean up
  } else {
    filters = await mapIcpToFilters(icpText);
  }
  console.log('  Filters:', JSON.stringify(filters, null, 2));
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(path.join(OUT_DIR, 'filters.json'), JSON.stringify(filters, null, 2));

  // Step 2: Launch browser
  console.log('\n[2] Launching stealth browser...');
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

  // Load session and set cookie
  const session = loadSession();
  console.log(`  Session from: ${session.savedAt || 'hardcoded default'}`);
  await setSessionCookie(page, session.value);

  // Step 3: Validate session + check credits BEFORE
  console.log('\n[3] Validating session & checking credits...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3000);

  let sessionCheck = await validateSession(page);
  if (!sessionCheck.valid) {
    // Session expired — auto-refresh via login
    const newCookie = await refreshSession(browser, page);
    await setSessionCookie(page, newCookie);
    await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(2000, 3000);
    sessionCheck = await validateSession(page);
    if (!sessionCheck.valid) throw new Error('Session still invalid after re-login');
  }

  const creditsBefore = sessionCheck.credits || await getCredits(page);
  console.log(`  Session valid. Credits before: ${JSON.stringify(creditsBefore)}`);
  await screenshot(page, 'tam_01_home');

  if (isLoginOnly) {
    console.log('\n=== Login-only mode — session refreshed, exiting. ===');
    const cookies = await page.cookies('https://api.clay.com');
    const sc = cookies.find(c => c.name === 'claysession');
    if (sc) saveSession(sc.value);
    await browser.close();
    return;
  }

  // Step 4: Navigate to Find Companies
  console.log('\n[4] Opening Find Companies...');
  // Click "Find leads" card
  await page.evaluate(() => {
    const els = [...document.querySelectorAll('button, div[role="button"]')];
    const el = els.find(e => e.textContent?.includes('Find leads') && e.textContent?.includes('Find people'));
    if (el) el.click();
  });
  await humanDelay(1500, 2500);

  // Select "Companies" tab if not already selected
  const compBtn = await findByText(page, 'Companies');
  if (compBtn) {
    await page.mouse.click(compBtn.x, compBtn.y);
    await humanDelay(1500, 2500);
  }
  await screenshot(page, 'tam_02_find_companies');

  // Step 5: Apply filters
  console.log('\n[5] Applying filters...');

  if (filters.industries?.length) {
    await fillFilterField(page, 'Software development', filters.industries);
  }
  if (filters.industries_exclude?.length) {
    await fillFilterField(page, 'Advertising services', filters.industries_exclude);
  }
  if (filters.sizes?.length) {
    await fillFilterField(page, '11-50 employees', filters.sizes);
  }
  if (filters.annual_revenues?.length) {
    await fillFilterField(page, '$1M - $5M', filters.annual_revenues);
  }
  if (filters.types?.length) {
    await fillFilterField(page, 'Privately held', filters.types);
  }
  if (filters.description_keywords?.length) {
    await fillFilterField(page, 'sales, data, outbound', filters.description_keywords);
  }
  if (filters.description_keywords_exclude?.length) {
    await fillFilterField(page, 'agency, marketing', filters.description_keywords_exclude);
  }
  if (filters.minimum_member_count != null) {
    await fillNumberField(page, 'Min', filters.minimum_member_count);
  }
  if (filters.maximum_member_count != null) {
    await fillNumberField(page, 'Max', filters.maximum_member_count);
  }
  if (filters.country_names?.length) {
    // The Location section in Clay's Find Companies is below the fold in the left sidebar.
    // We need to: 1. Scroll the sidebar down  2. Click Location to expand  3. Fill countries

    // Step 1: Scroll the LEFT SIDEBAR to make Location visible
    // The sidebar is a scrollable container — find it and scroll it aggressively
    const scrollResult = await page.evaluate(() => {
      // Find the Location element first to know if we need to scroll
      const findLocation = () => {
        const allEls = [...document.querySelectorAll('div, span, button, label')];
        for (const el of allEls) {
          if (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3) {
            const text = el.textContent?.trim();
            if (text === 'Location') {
              const rect = el.getBoundingClientRect();
              if (rect.x < 400 && rect.width < 300) return { el, rect };
            }
          }
        }
        return null;
      };

      let loc = findLocation();
      if (loc && loc.rect.y < window.innerHeight) {
        return { found: true, scrolled: false, y: loc.rect.y };
      }

      // Need to scroll — find the scrollable sidebar container
      // It's the parent container of all the filter sections
      const scrollableEls = [...document.querySelectorAll('*')].filter(el => {
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return (style.overflowY === 'auto' || style.overflowY === 'scroll')
          && rect.x < 400 && rect.width > 200 && rect.height > 200;
      });

      for (const scrollEl of scrollableEls) {
        scrollEl.scrollTop = scrollEl.scrollHeight;
      }

      // Also try scrollIntoView on Location if found but off-screen
      loc = findLocation();
      if (loc) {
        loc.el.scrollIntoView({ behavior: 'instant', block: 'center' });
        return { found: true, scrolled: true, y: loc.el.getBoundingClientRect().y };
      }

      return { found: false, scrolled: true, scrollableCount: scrollableEls.length };
    });
    console.log(`    Location scroll: ${JSON.stringify(scrollResult)}`);
    await humanDelay(1000, 1500);

    // Step 2: Click Location section header to expand it
    // Clay's section headers are clickable containers with icon + text + chevron
    // We need to find the "Location" text, then click its PARENT container
    const locCoords = await page.evaluate(() => {
      const allEls = [...document.querySelectorAll('*')];
      for (const el of allEls) {
        // Find leaf text nodes containing exactly "Location"
        if (el.children.length <= 2 && el.textContent?.trim() === 'Location') {
          const rect = el.getBoundingClientRect();
          if (rect.x < 400 && rect.y > 0 && rect.y < window.innerHeight && rect.height > 10 && rect.height < 60) {
            // Click the parent (the full section header row)
            const parent = el.closest('[role="button"]') || el.parentElement?.parentElement || el.parentElement || el;
            const parentRect = parent.getBoundingClientRect();
            return {
              x: parentRect.x + parentRect.width / 2,
              y: parentRect.y + parentRect.height / 2,
              tag: el.tagName,
              parentTag: parent.tagName,
              w: parentRect.width,
              h: parentRect.height,
            };
          }
        }
      }
      return null;
    });
    console.log(`    Location coords: ${JSON.stringify(locCoords)}`);

    if (locCoords) {
      // Use mouse.click on the exact coordinates
      await page.mouse.click(locCoords.x, locCoords.y);
      await humanDelay(1500, 2000);
      console.log('    Clicked Location section');

      // Take screenshot to verify expansion
      await screenshot(page, 'tam_03b_location_expanded');
    } else {
      console.log('    WARNING: Location section not found after scroll');
    }

    // Step 3: Wait for country input to appear and dump all placeholders for debugging
    await humanDelay(500, 800);
    const allPlaceholders = await page.evaluate(() => {
      return [...document.querySelectorAll('input')].filter(i => i.offsetParent !== null)
        .map(i => ({ placeholder: i.placeholder, rect: i.getBoundingClientRect() }))
        .filter(p => p.placeholder && p.rect.x < 300);
    });
    console.log('    Sidebar inputs:', JSON.stringify(allPlaceholders.map(p => p.placeholder)));

    // Step 4: Find country input
    let countryInput = await page.$('input[placeholder*="United States"]')
      || await page.$('input[placeholder*="country"]')
      || await page.$('input[placeholder*="location"]')
      || await page.$('input[placeholder*="Country"]');

    // Broader fallback: look for any new input that appeared in the sidebar
    if (!countryInput) {
      for (const ph of allPlaceholders) {
        const p = ph.placeholder.toLowerCase();
        if (p.includes('united') || p.includes('countr') || p.includes('locat') || p.includes('region') || p.includes('geo')) {
          countryInput = await page.$(`input[placeholder="${ph.placeholder}"]`);
          if (countryInput) {
            console.log(`    Found location input via fallback: "${ph.placeholder}"`);
            break;
          }
        }
      }
    }

    // Last resort: if Location section expanded, find the first NEW input (one that wasn't there before)
    if (!countryInput) {
      console.log('    Trying last resort: looking for any input inside Location section...');
      countryInput = await page.evaluate(() => {
        // Find the Location text node, then look for inputs near it
        const allEls = [...document.querySelectorAll('*')];
        let locationEl = null;
        for (const el of allEls) {
          if (el.textContent?.trim() === 'Location' && el.children.length === 0 && el.offsetParent !== null) {
            const rect = el.getBoundingClientRect();
            if (rect.x < 300) { locationEl = el; break; }
          }
        }
        if (!locationEl) return null;

        // Find the nearest input below this element
        const locRect = locationEl.getBoundingClientRect();
        const inputs = [...document.querySelectorAll('input')].filter(i => {
          const r = i.getBoundingClientRect();
          return i.offsetParent !== null && r.x < 300 && r.y > locRect.y && r.y < locRect.y + 200;
        });
        if (inputs.length > 0) {
          const rect = inputs[0].getBoundingClientRect();
          return { x: rect.x + 10, y: rect.y + 10, placeholder: inputs[0].placeholder };
        }
        return null;
      });
      if (countryInput && countryInput.x) {
        console.log(`    Last resort: clicking input at (${countryInput.x}, ${countryInput.y}) placeholder="${countryInput.placeholder}"`);
        // Use mouse click on coordinates
        for (const country of filters.country_names) {
          await page.mouse.click(countryInput.x, countryInput.y);
          await humanDelay(200, 400);
          await page.keyboard.type(country, { delay: 25 });
          await humanDelay(600, 1000);
          await page.keyboard.press('Enter');
          await humanDelay(300, 500);
        }
        console.log(`    Location: ${filters.country_names.join(', ')}`);
        countryInput = null; // Already handled
      }
    }

    if (countryInput && countryInput.click) {
      for (const country of filters.country_names) {
        await countryInput.click();
        await humanDelay(200, 400);
        await countryInput.type(country, { delay: 25 + Math.random() * 30 });
        await humanDelay(600, 1000);
        await page.keyboard.press('Enter');
        await humanDelay(300, 500);
      }
      console.log(`    Location: ${filters.country_names.join(', ')}`);
    } else if (countryInput !== null) {
      console.log('    WARNING: Country input not found — location filter NOT applied!');
    }

    // Take a debug screenshot after location attempt
    await screenshot(page, 'tam_03a_location_debug');
  }

  await humanDelay(2000, 3000);

  // Log result count after filters to verify location filter is working
  const resultCountText = await page.evaluate(() => {
    const el = [...document.querySelectorAll('*')].find(e =>
      e.textContent?.includes(' of ') && e.textContent?.includes('results') && e.innerText?.length < 50
    );
    return el?.innerText?.trim() || 'unknown';
  });
  console.log(`  Results after filters: ${resultCountText}`);
  await screenshot(page, 'tam_03_filters_applied');

  // Step 6: Click Continue dropdown → "Save to new workbook and table"
  console.log('\n[6] Opening Continue dropdown...');

  // Find the Continue button
  const continueBtnInfo = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null);
    const btn = buttons.find(b => b.textContent?.trim().startsWith('Continue'));
    if (!btn) return null;
    const rect = btn.getBoundingClientRect();
    return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, right: rect.x + rect.width - 8 };
  });

  if (continueBtnInfo) {
    // Helper to find the dropdown option
    async function findDropdownOption() {
      return page.evaluate(() => {
        const allEls = [...document.querySelectorAll('button, div[role="menuitem"], div[role="option"], li, a')];
        for (const el of allEls) {
          const t = el.textContent?.trim().toLowerCase() || '';
          if ((t.includes('new workbook') || t.includes('new table')) && el.offsetParent !== null) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 50) {
              return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: el.textContent.trim() };
            }
          }
        }
        return null;
      });
    }

    // Try multiple approaches to get the dropdown to appear
    let option = null;
    for (let attempt = 0; attempt < 4 && !option; attempt++) {
      if (attempt > 0) {
        await page.keyboard.press('Escape');
        await humanDelay(500, 800);
      }

      if (attempt < 2) {
        // Click dropdown arrow area (right edge)
        console.log(`  Attempt ${attempt + 1}: clicking dropdown arrow...`);
        await page.mouse.click(continueBtnInfo.right, continueBtnInfo.y);
      } else {
        // Click main Continue button
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
      console.log('  Dropdown not found after retries. Will scrape preview data.');
    }
  }

  // Wait for navigation to "Enrich Companies" page
  console.log('  Waiting for enrichment page...');
  await humanDelay(5000, 8000);
  await screenshot(page, 'tam_05_after_save');

  // Extract table ID from URL query params (Clay uses ?tableId=xxx format)
  let tableId = null;
  let workbookId = null;

  function extractIdsFromUrl(url) {
    const tableMatch = url.match(/tableId=([^&]+)/);
    const wbMatch = url.match(/workbookId=([^&]+)/);
    return { tableId: tableMatch?.[1], workbookId: wbMatch?.[1] };
  }

  // Wait for URL to contain tableId
  for (let i = 0; i < 15; i++) {
    const currentUrl = page.url();
    const ids = extractIdsFromUrl(currentUrl);
    if (ids.tableId) {
      tableId = ids.tableId;
      workbookId = ids.workbookId;
      console.log(`  Table ID: ${tableId}, Workbook: ${workbookId}`);
      break;
    }
    // Also check path-based table URL
    const pathMatch = currentUrl.match(/tables\/([^/?]+)/);
    if (pathMatch) {
      tableId = pathMatch[1];
      break;
    }
    await sleep(2000);
    console.log(`  Waiting for table... (${i + 1}/15)`);
  }

  // Step 7: Handle "Enrich Companies" page — skip enrichments, click "Create table"
  console.log('\n[7] Handling enrichment page...');
  const isEnrichPage = await page.evaluate(() => {
    return document.body.textContent?.includes('Enrich Companies') ||
           document.body.textContent?.includes('Select enrichments') ||
           document.body.textContent?.includes('enrich-companies');
  });

  if (isEnrichPage) {
    console.log('  On Enrich Companies page — skipping enrichments...');
    await screenshot(page, 'tam_06_enrich_page');

    // Don't select any enrichments (saves credits). Just click "Create table"
    await humanDelay(1500, 2500);
    const createTableBtn = await findByText(page, 'Create table', false);
    if (createTableBtn) {
      console.log('  Clicking "Create table"...');
      await page.mouse.click(createTableBtn.x, createTableBtn.y);
      await humanDelay(8000, 12000);
      await screenshot(page, 'tam_07_table_created');

      // Update table ID from new URL if needed
      const newUrl = page.url();
      console.log(`  URL after create: ${newUrl}`);
      const newIds = extractIdsFromUrl(newUrl);
      if (newIds.tableId) {
        tableId = newIds.tableId;
        workbookId = newIds.workbookId;
      }
      const pathMatch = newUrl.match(/tables\/([^/?]+)/);
      if (pathMatch) tableId = pathMatch[1];
    } else {
      console.log('  "Create table" button not found');
      // List available buttons
      const btns = await page.evaluate(() =>
        [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null)
          .map(b => b.textContent?.trim().substring(0, 50)).filter(t => t)
      );
      console.log('  Buttons:', btns.join(' | '));
    }
  }

  // Step 8: Read table data via API
  console.log(`\n[8] Reading table data (${tableId})...`);

  if (tableId) {
    // Wait for table data to load fully
    console.log('  Waiting for data to populate...');
    await humanDelay(10000, 15000);

    // Reload to ensure data is loaded
    await page.reload({ waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(5000, 8000);
    await screenshot(page, 'tam_08_table_data');

    // Step 8a: Get table metadata (field ID → name mapping)
    console.log('  Fetching table metadata...');
    const tableMeta = await page.evaluate(async (tid) => {
      try {
        const res = await fetch(`https://api.clay.com/v3/tables/${tid}`, {
          credentials: 'include', headers: { 'Accept': 'application/json' },
        });
        return await res.json();
      } catch (e) { return { error: e.message }; }
    }, tableId);

    // Build field ID → name mapping
    const fieldMap = {};
    const fields = tableMeta?.table?.fields || [];
    for (const field of fields) {
      fieldMap[field.id] = field.name;
    }
    console.log(`  Fields: ${Object.values(fieldMap).join(', ')}`);

    // Step 8b: Get record count
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

    // Step 8c: Get record IDs from the view, then fetch via bulk-fetch-records (POST)
    console.log('  Fetching record IDs from view...');

    // Get the view ID from the URL
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

    // Fetch records in batches using POST with record IDs
    console.log('  Fetching records via bulk-fetch-records (POST)...');
    const allRawRecords = [];
    const batchSize = 200;

    for (let i = 0; i < recordIds.length; i += batchSize) {
      const batch = recordIds.slice(i, i + batchSize);
      const batchData = await page.evaluate(async (tid, ids) => {
        try {
          const res = await fetch(`https://api.clay.com/v3/tables/${tid}/bulk-fetch-records`, {
            method: 'POST',
            credentials: 'include',
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

    const rawRecords = allRawRecords;
    console.log(`  Raw records: ${rawRecords.length}`);

    // Step 8d: Parse records — map field IDs to names, extract values
    const companies = rawRecords.map(record => {
      const company = {};
      for (const [fieldId, cell] of Object.entries(record.cells || {})) {
        const fieldName = fieldMap[fieldId] || fieldId;
        let value = cell?.value;
        // Handle option values (e.g. industry, size)
        if (value && typeof value === 'object' && value.optionIds) {
          value = (cell?.metadata?.valueDisplay || cell?.metadata?.display || JSON.stringify(value.optionIds));
        }
        if (value !== null && value !== undefined) {
          company[fieldName] = String(value).substring(0, 1000);
        }
      }
      company._id = record.id;
      return company;
    });

    console.log(`  Parsed companies: ${companies.length}`);
    if (companies.length > 0) {
      console.log('  Columns:', Object.keys(companies[0]).join(', '));
      console.log('  Sample:', JSON.stringify(companies[0]).substring(0, 400));
    }

    // Save all data
    fs.writeFileSync(path.join(OUT_DIR, 'tam_companies.json'), JSON.stringify(companies, null, 2));
    fs.writeFileSync(path.join(OUT_DIR, 'tam_table_meta.json'), JSON.stringify({ tableMeta, fieldMap, totalRecords }, null, 2));
    console.log(`  Saved ${companies.length} companies to tam_companies.json`);
  } else {
    console.log('  No table ID — scraping preview data from search results...');

    // Navigate back to Find Companies if needed
    const onSearch = await page.evaluate(() =>
      document.body.textContent?.includes('Refine with filters') || document.body.textContent?.includes('Find Companies')
    );

    if (!onSearch) {
      console.log('  Navigating back to search results...');
      await page.goBack();
      await humanDelay(3000, 5000);
    }

    // Scrape all visible companies from the preview table
    const previewCompanies = await page.evaluate(() => {
      const companies = [];
      const table = document.querySelector('table');
      if (!table) return companies;
      const headers = [...table.querySelectorAll('th')].map(h => h.textContent?.trim());
      const rows = table.querySelectorAll('tbody tr');
      rows.forEach(row => {
        const cells = [...row.querySelectorAll('td')];
        const company = {};
        cells.forEach((cell, i) => {
          const key = headers[i] || `col${i}`;
          company[key] = cell.textContent?.trim().substring(0, 500);
        });
        if (company['Name'] || Object.values(company).some(v => v && v.length > 5)) {
          companies.push(company);
        }
      });
      return companies;
    });
    console.log(`  Scraped ${previewCompanies.length} companies from preview`);
    if (previewCompanies.length > 0) {
      console.log('  Sample:', JSON.stringify(previewCompanies[0]).substring(0, 300));
      fs.writeFileSync(path.join(OUT_DIR, 'tam_companies.json'), JSON.stringify(previewCompanies, null, 2));
    }
  }

  await screenshot(page, 'tam_09_final');

  // Step 12: Final credit check
  console.log('\n[12] Checking credits AFTER all operations...');
  const creditsAfter = await getCredits(page);
  console.log(`  Credits before: ${JSON.stringify(creditsBefore)}`);
  console.log(`  Credits after:  ${JSON.stringify(creditsAfter)}`);

  if (creditsBefore && creditsAfter) {
    const spent = (creditsBefore.basic || 0) - (creditsAfter.basic || 0);
    console.log(`\n  === CREDITS SPENT: ${spent} ===`);
    if (spent > 0) {
      console.log('  WARNING: Credits were spent!');
    } else {
      console.log('  SAFE: No credits spent.');
    }
  }

  // Save full results
  fs.writeFileSync(path.join(OUT_DIR, 'tam_results.json'), JSON.stringify({
    icp: icpText,
    filters,
    creditsBefore,
    creditsAfter,
    tableUrl: page.url(),
    tableId: tableId || null,
    timestamp: new Date().toISOString(),
  }, null, 2));

  // Save session cookie for next run (keeps it fresh)
  const endCookies = await page.cookies('https://api.clay.com');
  const endSession = endCookies.find(c => c.name === 'claysession');
  if (endSession) saveSession(endSession.value);

  console.log('\n=== Pipeline complete! ===');
  console.log(`Results saved to ${OUT_DIR}/`);

  // In non-interactive mode (--auto flag), close browser immediately
  if (args.includes('--auto')) {
    console.log('Auto mode: closing browser.');
    await browser.close();
  } else {
    console.log('Browser stays open for inspection. Press Ctrl+C to close.\n');
    await sleep(600000);
    await browser.close();
  }
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
