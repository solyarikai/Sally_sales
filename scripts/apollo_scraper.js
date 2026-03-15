/**
 * Apollo.io Contact Scraper — Headless Puppeteer
 *
 * Scrapes Apollo search results without spending credits.
 * Reads full contact details from the UI (name, title, company, domain, location).
 *
 * Usage:
 *   node scripts/apollo_scraper.js --url "https://app.apollo.io/#/people?..." --max-pages 50 --output /scripts/data/apollo_uae_pk.json
 *   node scripts/apollo_scraper.js --help
 *
 * Login: uses credentials from tasks/apollo/index.md
 * Runs headless on Hetzner (google-chrome installed).
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const OUT_DIR = path.join(__dirname, 'data');
const SESSION_FILE = path.join(OUT_DIR, 'apollo_session.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function login(page) {
  console.log('[1] Logging into Apollo...');
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  // Check if already logged in
  if (page.url().includes('/people') || page.url().includes('/home')) {
    console.log('  Already logged in');
    return;
  }

  // Fill email
  await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 30 });
  await sleep(500);

  // Fill password
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 30 });
  await sleep(500);

  // Click login button
  await page.click('button[type="submit"]');
  await sleep(5000);

  // Wait for redirect
  for (let i = 0; i < 30; i++) {
    if (page.url().includes('/people') || page.url().includes('/home') || page.url().includes('/sequences')) {
      console.log('  Login successful');
      return;
    }
    await sleep(2000);
  }
  throw new Error('Login failed — stuck at: ' + page.url());
}

async function scrapeCurrentPage(page) {
  return page.evaluate(() => {
    const rows = [];
    // Apollo renders a table of contacts
    const tableRows = document.querySelectorAll('tr[class*="zp_"]');
    for (const row of tableRows) {
      const cells = row.querySelectorAll('td');
      if (cells.length < 3) continue;

      // Extract text from each cell
      const nameEl = cells[0]?.querySelector('a[href*="/people/"]') || cells[0];
      const name = nameEl?.textContent?.trim() || '';

      const titleEl = cells[1] || cells[2];
      const title = titleEl?.textContent?.trim() || '';

      const companyEl = cells[2]?.querySelector('a') || cells[3]?.querySelector('a');
      const company = companyEl?.textContent?.trim() || '';

      // Try to find more details
      const locationEl = cells[4] || cells[5];
      const location = locationEl?.textContent?.trim() || '';

      const linkedinEl = row.querySelector('a[href*="linkedin.com"]');
      const linkedin = linkedinEl?.href || '';

      if (name && name.length > 1) {
        rows.push({ name, title, company, location, linkedin });
      }
    }
    return rows;
  });
}

async function getPageInfo(page) {
  return page.evaluate(() => {
    // Find total count and current page
    const countEl = document.querySelector('[class*="zp_"] span[class*="total"]') ||
                   document.querySelector('.zp_xL8JC'); // total contacts count
    const totalText = countEl?.textContent || '';
    const total = parseInt(totalText.replace(/[^0-9]/g, '')) || 0;

    // Find pagination
    const paginationEls = document.querySelectorAll('button[class*="pagination"], [class*="page_number"]');
    let currentPage = 1;
    for (const el of paginationEls) {
      if (el.getAttribute('aria-current') === 'page' || el.classList.contains('active')) {
        currentPage = parseInt(el.textContent) || 1;
        break;
      }
    }

    return { total, currentPage };
  });
}

async function clickNextPage(page) {
  const clicked = await page.evaluate(() => {
    // Find "next" button in pagination
    const buttons = document.querySelectorAll('button, a');
    for (const btn of buttons) {
      const text = btn.textContent.trim().toLowerCase();
      const ariaLabel = (btn.getAttribute('aria-label') || '').toLowerCase();
      if (text === '›' || text === 'next' || ariaLabel.includes('next')) {
        if (!btn.disabled) {
          btn.click();
          return true;
        }
      }
    }
    // Try clicking the chevron/arrow icon for next page
    const nextIcons = document.querySelectorAll('[class*="right"], [class*="next"], [class*="chevron"]');
    for (const icon of nextIcons) {
      const parent = icon.closest('button') || icon.closest('a');
      if (parent && !parent.disabled) {
        parent.click();
        return true;
      }
    }
    return false;
  });
  return clicked;
}

async function main() {
  const args = process.argv.slice(2);
  const urlIdx = args.indexOf('--url');
  const maxPagesIdx = args.indexOf('--max-pages');
  const outputIdx = args.indexOf('--output');

  const searchUrl = urlIdx >= 0 ? args[urlIdx + 1] : null;
  const maxPages = maxPagesIdx >= 0 ? parseInt(args[maxPagesIdx + 1]) : 100;
  const outputFile = outputIdx >= 0 ? args[outputIdx + 1] : path.join(OUT_DIR, 'apollo_contacts.json');

  if (!searchUrl) {
    console.log('Usage: node apollo_scraper.js --url "https://app.apollo.io/#/people?..." [--max-pages 50] [--output file.json]');
    console.log('\nSet up your search filters in Apollo UI, then copy the URL.');
    process.exit(1);
  }

  console.log(`Apollo Scraper — max ${maxPages} pages`);
  console.log(`URL: ${searchUrl.substring(0, 80)}...`);
  console.log(`Output: ${outputFile}`);

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900',
           '--disable-blink-features=AutomationControlled', '--disable-dev-shm-usage',
           '--disable-gpu'],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36');

  try {
    await login(page);

    // Navigate to search URL
    console.log('\n[2] Loading search results...');
    await page.goto(searchUrl, { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(3000);

    const allContacts = [];
    let pageNum = 1;

    while (pageNum <= maxPages) {
      await sleep(2000 + Math.random() * 1000); // Human-like delay

      const rows = await scrapeCurrentPage(page);
      console.log(`  Page ${pageNum}: ${rows.length} contacts`);

      if (rows.length === 0) {
        console.log('  No more contacts — stopping');
        break;
      }

      allContacts.push(...rows);

      // Save after each page
      fs.writeFileSync(outputFile, JSON.stringify(allContacts, null, 2));

      // Try next page
      const hasNext = await clickNextPage(page);
      if (!hasNext) {
        console.log('  No next page button — stopping');
        break;
      }

      pageNum++;
      await sleep(2000 + Math.random() * 2000);
    }

    console.log(`\n[3] Done: ${allContacts.length} contacts scraped across ${pageNum} pages`);
    console.log(`Saved to: ${outputFile}`);

  } catch (err) {
    console.error('Error:', err.message);
    await page.screenshot({ path: path.join(OUT_DIR, 'apollo_error.png') });
  } finally {
    await browser.close();
  }
}

main().catch(console.error);
