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

  // Step B: Type company domains into the "Companies" field (placeholder: "amazon.com, microsoft.com")
  // This is the most important filter — targets specific gaming companies
  if (filters.company_domains?.length) {
    console.log(`  Typing ${filters.company_domains.length} company domains...`);

    // "Companies" section is near the bottom of the sidebar — scroll down to it
    await page.evaluate(() => {
      const sidebar = document.querySelector('[class*="sidebar"]')
        || document.querySelector('[class*="filter"]')?.closest('div[style*="overflow"]')
        || document.querySelector('div[class*="scroll"]');
      // Try to find and scroll the sidebar container
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

    // Click "Companies" section to expand it (exact text, not "Company attributes")
    const compSection = await findByText(page, 'Companies', true);
    if (compSection) {
      await page.mouse.click(compSection.x, compSection.y);
      await humanDelay(1200, 1800);
    } else {
      // Fallback: try finding it with icon prefix
      const compAlt = await findByText(page, 'Companies', false);
      if (compAlt) {
        await page.mouse.click(compAlt.x, compAlt.y);
        await humanDelay(1200, 1800);
      }
    }

    // Find the domain input (placeholder contains "amazon.com" or similar)
    // Use evaluate to get coordinates — more reliable than ElementHandle.click()
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
        console.log(`    Exclude country input: "${excludeInput.placeholder}"`);
        for (const country of filters.countries_exclude) {
          await page.mouse.click(excludeInput.x, excludeInput.y);
          await humanDelay(200, 400);
          await page.keyboard.type(country, { delay: 25 + Math.random() * 30 });
          await humanDelay(600, 1000);
          await page.keyboard.press('Enter');
          await humanDelay(300, 500);
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
            await humanDelay(600, 1000);
            await page.keyboard.press('Enter');
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

  // Load domains — from external file if provided, else from known sources
  let allDomains;
  if (externalDomainsFile && fs.existsSync(externalDomainsFile)) {
    const lines = fs.readFileSync(externalDomainsFile, 'utf-8').split('\n');
    allDomains = lines.map(l => l.trim().toLowerCase().replace(/^www\./, '')).filter(d => d && d.includes('.'));
    console.log(`  External domains file: ${externalDomainsFile} (${allDomains.length} domains)`);
  } else if (customSchools || customCountries) {
    // Filter-based search: no domains needed
    allDomains = [];
    console.log(`  Filter-based search (no domains). Schools: ${customSchools?.length || 0}, Countries: ${customCountries?.length || 0}`);
  } else {
    allDomains = loadKnownDomains();
    console.log(`  Known gaming ICP domains: ${allDomains.length}`);
  }
  GAMING_ICP_FILTERS.company_domains = allDomains;

  // Build search configs
  // Clay limit is ~500 domains per search and 5000 people per table.
  // If we have >500 domains, split into batches.
  let searches;
  const DOMAIN_BATCH_SIZE = 200; // Conservative batch size for UI input

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

  if (allDomains.length === 0) {
    // No domains — filter-based search (schools + countries + titles)
    searches = [{ label: 'filter_based', filters: GAMING_ICP_FILTERS }];
    console.log('\n[2] Running filter-based search (no domains)...');
  } else if (allDomains.length > DOMAIN_BATCH_SIZE) {
    // Split domains into batches
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
