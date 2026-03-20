/**
 * Apollo Person Lookup — Find LinkedIn URLs by name + company
 *
 * Takes CSV with name + company columns, searches Apollo People tab,
 * extracts LinkedIn URLs. FREE (Puppeteer scraping, no API credits).
 *
 * Usage:
 *   node scripts/apollo_person_lookup.js --file contacts.csv --name-col "name" --company-col "company"
 *   node scripts/apollo_person_lookup.js --file contacts.csv --output enriched.csv --headless
 *
 * Output: CSV with original columns + linkedin_url
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';

const OUT_DIR = path.join(__dirname, 'exports');
const SESSION_FILE = path.join(__dirname, 'apollo_session.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function humanDelay(min = 300, max = 800) {
  return sleep(min + Math.random() * (max - min));
}
function ts() { return new Date().toISOString().replace('T', ' ').substring(0, 19); }

// ================================================================
//  CSV PARSING
// ================================================================

function parseCSV(content) {
  const lines = content.split('\n').filter(l => l.trim());
  if (lines.length === 0) return [];

  // Detect delimiter
  const firstLine = lines[0];
  const delimiter = firstLine.includes('\t') ? '\t' :
                    firstLine.includes(';') ? ';' : ',';

  const headers = lines[0].split(delimiter).map(h => h.trim().replace(/^["']|["']$/g, ''));
  const rows = [];

  for (let i = 1; i < lines.length; i++) {
    const values = lines[i].split(delimiter).map(v => v.trim().replace(/^["']|["']$/g, ''));
    const row = {};
    headers.forEach((h, idx) => {
      row[h] = values[idx] || '';
    });
    rows.push(row);
  }

  return rows;
}

function writeCSV(rows, filePath) {
  if (rows.length === 0) return;
  const headers = Object.keys(rows[0]);
  const lines = [headers.join(',')];
  for (const row of rows) {
    const values = headers.map(h => {
      const v = row[h] || '';
      return v.includes(',') || v.includes('"') ? `"${v.replace(/"/g, '""')}"` : v;
    });
    lines.push(values.join(','));
  }
  fs.writeFileSync(filePath, lines.join('\n'));
}

// ================================================================
//  SESSION MANAGEMENT
// ================================================================

function loadSession() {
  try {
    if (fs.existsSync(SESSION_FILE)) {
      return JSON.parse(fs.readFileSync(SESSION_FILE, 'utf-8'));
    }
  } catch {}
  return null;
}

function saveSession(cookies) {
  fs.writeFileSync(SESSION_FILE, JSON.stringify(cookies, null, 2));
  console.log(`[${ts()}] Session saved`);
}

// ================================================================
//  APOLLO LOGIN
// ================================================================

async function loginToApollo(page) {
  console.log(`[${ts()}] Logging in to Apollo...`);

  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 60000 });
  await humanDelay(2000, 3000);

  // Check if already logged in
  if (page.url().includes('/people') || page.url().includes('/home')) {
    console.log(`[${ts()}] Already logged in`);
    return true;
  }

  // Fill email
  const emailInput = await page.$('input[name="email"]');
  if (emailInput) {
    await emailInput.click();
    await humanDelay(200, 400);
    await emailInput.type(APOLLO_EMAIL, { delay: 30 + Math.random() * 50 });
    await humanDelay(500, 1000);
  }

  // Fill password
  const passInput = await page.$('input[name="password"]');
  if (passInput) {
    await passInput.click();
    await humanDelay(200, 400);
    await passInput.type(APOLLO_PASS, { delay: 30 + Math.random() * 50 });
    await humanDelay(500, 1000);
  }

  // Click login button
  const loginBtn = await page.$('button[type="submit"]');
  if (loginBtn) {
    await loginBtn.click();
    await humanDelay(3000, 5000);
  }

  // Wait for redirect
  for (let i = 0; i < 30; i++) {
    await sleep(1000);
    if (page.url().includes('/people') || page.url().includes('/home') || page.url().includes('/companies')) {
      console.log(`[${ts()}] Login successful`);
      const cookies = await page.cookies();
      saveSession(cookies);
      return true;
    }
  }

  console.log(`[${ts()}] Login may have failed, current URL: ${page.url()}`);
  return false;
}

// ================================================================
//  PERSON SEARCH
// ================================================================

async function searchPerson(page, name, company, debug = false) {
  const searchQuery = `${name} ${company}`.trim();
  console.log(`[${ts()}] Searching: "${searchQuery}"`);

  // Go to People search page with query
  const searchUrl = `https://app.apollo.io/#/people?qKeywords=${encodeURIComponent(searchQuery)}&sortByField=recommendations_score&sortAscending=false`;

  await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 15000 });
  await sleep(2000);  // Fixed wait for React to render

  // Debug screenshot
  if (debug) {
    const screenshotPath = path.join(OUT_DIR, `debug_${Date.now()}.png`);
    await page.screenshot({ path: screenshotPath, fullPage: false });
    console.log(`[${ts()}]   Debug screenshot: ${screenshotPath}`);
  }

  // Extract first result's LinkedIn URL - improved selectors for Apollo UI
  const result = await page.evaluate((targetName, targetCompany) => {
    const debug = [];

    // Apollo uses various table structures - try multiple selectors
    const tableSelectors = [
      'table tbody tr',
      '[class*="zp_RFed0"]',  // Apollo specific class
      '[class*="TableRow"]',
      '[data-cy*="row"]',
      'div[class*="zp_"] > div[class*="zp_"]',  // nested divs
    ];

    let rows = [];
    for (const sel of tableSelectors) {
      const found = document.querySelectorAll(sel);
      if (found.length > 0) {
        rows = found;
        debug.push(`Found ${found.length} rows with selector: ${sel}`);
        break;
      }
    }

    if (rows.length === 0) {
      // Try to find any content that looks like person cards
      rows = document.querySelectorAll('div[class*="person"], div[class*="contact"], article');
      debug.push(`Fallback: found ${rows.length} person-like elements`);
    }

    debug.push(`Total rows to check: ${rows.length}`);

    for (const row of rows) {
      const rowText = row.textContent?.toLowerCase() || '';
      const nameLower = targetName.toLowerCase();
      const companyLower = targetCompany.toLowerCase();

      // Check if this row matches our search
      const nameMatch = nameLower.split(' ').some(part => part.length > 2 && rowText.includes(part));
      const companyMatch = companyLower.split(' ').filter(w => w.length > 2).some(part => rowText.includes(part));

      if (nameMatch || companyMatch) {
        debug.push(`Potential match: ${rowText.substring(0, 100)}`);

        // Look for LinkedIn link in various places
        const linkedinSelectors = [
          'a[href*="linkedin.com/in/"]',
          'a[href*="linkedin.com"]',
          '[class*="linkedin"] a',
          'a[title*="LinkedIn"]',
        ];

        for (const sel of linkedinSelectors) {
          const linkedinLink = row.querySelector(sel);
          if (linkedinLink?.href) {
            return {
              linkedin_url: linkedinLink.href,
              matched_text: rowText.substring(0, 200).trim(),
              debug: debug
            };
          }
        }

        // Try to find person profile link (to visit and get LinkedIn from there)
        const personLink = row.querySelector('a[href*="/people/"], a[href*="contact"]');
        if (personLink?.href) {
          return {
            apollo_url: personLink.href,
            matched_text: rowText.substring(0, 200).trim(),
            debug: debug
          };
        }
      }
    }

    // Fallback: get first LinkedIn link on page
    const firstLinkedin = document.querySelector('a[href*="linkedin.com/in/"]');
    if (firstLinkedin) {
      return {
        linkedin_url: firstLinkedin.href,
        matched_text: 'first_result_fallback',
        debug: debug
      };
    }

    // Return debug info even if no match
    return { debug: debug, no_results: true }

  }, name, company);

  // Log debug info
  if (result?.debug) {
    for (const d of result.debug) {
      console.log(`[${ts()}]   Debug: ${d}`);
    }
  }

  if (result?.linkedin_url) {
    console.log(`[${ts()}]   Found LinkedIn: ${result.linkedin_url}`);
    return result.linkedin_url;
  } else if (result?.apollo_url) {
    // Need to visit Apollo profile to get LinkedIn
    console.log(`[${ts()}]   Found Apollo profile, extracting LinkedIn...`);
    await page.goto(result.apollo_url, { waitUntil: 'networkidle2', timeout: 30000 });
    await humanDelay(1500, 2500);

    const linkedinUrl = await page.evaluate(() => {
      const link = document.querySelector('a[href*="linkedin.com/in/"]');
      return link?.href || null;
    });

    if (linkedinUrl) {
      console.log(`[${ts()}]   Found LinkedIn: ${linkedinUrl}`);
      return linkedinUrl;
    }
  }

  console.log(`[${ts()}]   No LinkedIn found`);
  return null;
}

// ================================================================
//  MAIN
// ================================================================

async function main() {
  const args = process.argv.slice(2);

  // Parse arguments
  const getArg = (flag) => {
    const idx = args.indexOf(flag);
    return idx >= 0 && args[idx + 1] ? args[idx + 1] : null;
  };
  const hasFlag = (flag) => args.includes(flag);

  const inputFile = getArg('--file');
  const nameCol = getArg('--name-col') || 'name';
  const companyCol = getArg('--company-col') || 'company';
  const outputFile = getArg('--output');
  const headless = hasFlag('--headless');
  const debug = hasFlag('--debug');
  const limit = parseInt(getArg('--limit')) || 0;

  if (!inputFile) {
    console.log('Usage: node apollo_person_lookup.js --file contacts.csv [options]');
    console.log('Options:');
    console.log('  --name-col NAME      Column name for person name (default: "name")');
    console.log('  --company-col NAME   Column name for company (default: "company")');
    console.log('  --output FILE        Output CSV file (default: input_enriched.csv)');
    console.log('  --headless           Run headless (no browser window)');
    console.log('  --limit N            Process only first N rows');
    process.exit(1);
  }

  if (!fs.existsSync(inputFile)) {
    console.error(`File not found: ${inputFile}`);
    process.exit(1);
  }

  // Parse input CSV
  const content = fs.readFileSync(inputFile, 'utf-8');
  let rows = parseCSV(content);
  console.log(`[${ts()}] Loaded ${rows.length} rows from ${inputFile}`);
  console.log(`[${ts()}] Columns: ${Object.keys(rows[0] || {}).join(', ')}`);

  // Filter rows that need enrichment (have company, no email)
  const toEnrich = rows.filter(r => {
    const hasName = r[nameCol]?.trim();
    const hasCompany = r[companyCol]?.trim() && r[companyCol] !== '-';
    const hasEmail = r.email?.trim();
    return hasName && hasCompany && !hasEmail;
  });

  console.log(`[${ts()}] Rows to enrich: ${toEnrich.length} (have name+company, no email)`);

  if (toEnrich.length === 0) {
    console.log('Nothing to enrich!');
    process.exit(0);
  }

  // Apply limit
  const processRows = limit > 0 ? toEnrich.slice(0, limit) : toEnrich;
  console.log(`[${ts()}] Will process: ${processRows.length} rows`);

  // Launch browser
  fs.mkdirSync(OUT_DIR, { recursive: true });

  console.log(`[${ts()}] Launching browser (headless: ${headless})...`);
  const browser = await puppeteer.launch({
    headless: headless ? 'new' : false,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--window-size=1440,900',
      '--disable-blink-features=AutomationControlled',
    ],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

  // Load session if exists
  const session = loadSession();
  if (session) {
    await page.setCookie(...session);
    console.log(`[${ts()}] Session loaded`);
  }

  // Login
  const loggedIn = await loginToApollo(page);
  if (!loggedIn) {
    console.error('Failed to login to Apollo');
    await browser.close();
    process.exit(1);
  }

  // Process each row
  let found = 0;
  let notFound = 0;
  const results = [];

  for (let i = 0; i < processRows.length; i++) {
    const row = processRows[i];
    const name = row[nameCol]?.trim() || '';
    const company = row[companyCol]?.trim() || '';

    console.log(`\n[${ts()}] [${i + 1}/${processRows.length}] ${name} @ ${company}`);

    try {
      const linkedinUrl = await searchPerson(page, name, company, debug);

      if (linkedinUrl) {
        row.linkedin_url = linkedinUrl;
        found++;
      } else {
        row.linkedin_url = '';
        notFound++;
      }

      results.push(row);

      // Brief delay between searches
      await humanDelay(500, 1000);

      // Save progress every 10 rows
      if ((i + 1) % 10 === 0) {
        const progressFile = outputFile || inputFile.replace('.csv', '_enriched.csv');
        writeCSV(results, progressFile);
        console.log(`[${ts()}] Progress saved: ${results.length} rows`);
      }

    } catch (err) {
      console.error(`[${ts()}] Error: ${err.message}`);
      row.linkedin_url = '';
      row.error = err.message;
      results.push(row);
    }
  }

  // Save final results
  const finalOutput = outputFile || inputFile.replace('.csv', '_enriched.csv');
  writeCSV(results, finalOutput);

  console.log(`\n[${ts()}] === DONE ===`);
  console.log(`[${ts()}] Found LinkedIn: ${found}`);
  console.log(`[${ts()}] Not found: ${notFound}`);
  console.log(`[${ts()}] Output: ${finalOutput}`);

  await browser.close();
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
