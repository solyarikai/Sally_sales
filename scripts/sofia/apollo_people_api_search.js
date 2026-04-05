/**
 * Apollo People Search — Internal API via Browser Session
 *
 * Uses Apollo's internal API (POST /api/v1/mixed_people/search) from within
 * a Puppeteer browser session. No DOM scraping — structured JSON responses.
 *
 * Usage:
 *   node apollo_people_api_search.js \
 *     --domains "hubspot.com,goat.agency" \
 *     --titles "CEO,Founder,CTO" \
 *     --seniorities "founder,c_suite,vp,director" \
 *     --max-pages 5 \
 *     --profile /tmp/apollo_profile \
 *     --output /tmp/people.json
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function ts() { return new Date().toISOString().replace('T', ' ').substring(0, 19); }

async function login(page) {
  console.log(`[${ts()}] LOGIN: Starting...`);
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'domcontentloaded', timeout: 30000 });
  await sleep(3000);

  const url = page.url();
  if (url.includes('/people') || url.includes('/home') || url.includes('/companies') || url.includes('/sequences')) {
    console.log(`[${ts()}] LOGIN: Already logged in`);
    return;
  }

  async function typeReact(selector, value) {
    await page.click(selector, { clickCount: 3 });
    await sleep(200);
    await page.evaluate((sel, val) => {
      const el = document.querySelector(sel);
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(el, val);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }, selector, value);
    await sleep(300);
  }

  await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  await typeReact('input[name="email"]', APOLLO_EMAIL);
  await typeReact('input[name="password"]', APOLLO_PASS);
  await page.click('button[type="submit"]');
  console.log(`[${ts()}] LOGIN: Submitted, waiting...`);
  await sleep(5000);

  for (let i = 0; i < 30; i++) {
    const u = page.url();
    if (u.includes('/people') || u.includes('/home') || u.includes('/companies') || u.includes('/sequences')) {
      console.log(`[${ts()}] LOGIN: Success`);
      return;
    }
    await sleep(2000);
  }
  throw new Error(`Login failed (stuck at: ${page.url()})`);
}

async function apiSearchPeople(page, params) {
  return page.evaluate(async (searchParams) => {
    try {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfMeta ? csrfMeta.content : '';

      const res = await fetch('https://app.apollo.io/api/v1/mixed_people/search', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Csrf-Token': csrfToken,
        },
        credentials: 'include',
        body: JSON.stringify(searchParams),
      });

      if (!res.ok) {
        return { error: `HTTP ${res.status}`, status: res.status };
      }
      return await res.json();
    } catch (e) {
      return { error: e.message };
    }
  }, params);
}

async function searchPeople(page, domains, titles, seniorities, maxPages) {
  const allPeople = [];
  let pageNum = 1;
  let totalEntries = null;

  while (pageNum <= maxPages) {
    const params = {
      organization_domains: domains,
      person_titles: titles,
      person_seniorities: seniorities,
      sort_by_field: '[none]',
      sort_ascending: false,
      page: pageNum,
      per_page: 25,
      display_mode: 'explorer_mode',
      context: 'people-index-page',
      show_suggestions: false,
      num_fetch_result: 1,
      finder_version: 2,
      cacheKey: Date.now(),
    };

    const result = await apiSearchPeople(page, params);

    if (result.error) {
      console.log(`    p${pageNum}: ERROR ${result.error}`);
      if (result.status === 422 || result.status === 429) break;
      await sleep(5000);
      pageNum++;
      continue;
    }

    const people = result.people || result.contacts || [];
    totalEntries = result.pagination?.total_entries || totalEntries;

    if (people.length === 0) break;

    for (const p of people) {
      const org = p.organization || {};
      allPeople.push({
        name: p.name || '',
        first_name: p.first_name || '',
        last_name: p.last_name || '',
        title: p.title || '',
        company: org.name || p.organization_name || '',
        domain: org.primary_domain || org.website_url || '',
        linkedin_url: p.linkedin_url || '',
        location: [p.city, p.state, p.country].filter(Boolean).join(', '),
        email: p.email || '',
        employees: org.estimated_num_employees || '',
      });
    }

    if (pageNum === 1 && totalEntries) {
      console.log(`    Total: ${totalEntries} (fetching up to ${maxPages} pages)`);
    }

    pageNum++;
    await sleep(1000 + Math.random() * 2000);
  }

  return allPeople;
}

// ================================================================
//  MAIN
// ================================================================

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.length === 0) {
    console.log('Usage: node apollo_people_api_search.js --domains "d1,d2" --titles "CEO,CTO" [options]');
    console.log('  --domains      Comma-separated company domains');
    console.log('  --titles       Comma-separated job titles');
    console.log('  --seniorities  Comma-separated seniorities (default: founder,c_suite,vp,director)');
    console.log('  --max-pages    Max pages per search (default: 5)');
    console.log('  --profile      Puppeteer profile dir (saved session)');
    console.log('  --output       Output JSON file');
    process.exit(0);
  }

  const getArg = (name) => {
    const idx = args.indexOf(name);
    return idx >= 0 ? args[idx + 1] : null;
  };

  const domainsStr = getArg('--domains');
  const titlesStr = getArg('--titles');
  const senioritiesStr = getArg('--seniorities') || 'founder,c_suite,vp,director,owner,head,partner';
  const maxPages = parseInt(getArg('--max-pages') || '5');
  const profileDir = getArg('--profile');
  const outputFile = getArg('--output') || '/tmp/apollo_people.json';

  if (!domainsStr) {
    console.error('ERROR: --domains is required');
    process.exit(1);
  }

  const domains = domainsStr.split(',').map(d => d.trim()).filter(Boolean);
  const titles = titlesStr ? titlesStr.split(',').map(t => t.trim()).filter(Boolean) : [];
  const seniorities = senioritiesStr.split(',').map(s => s.trim()).filter(Boolean);

  const launchOpts = {
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  };
  if (profileDir) {
    launchOpts.userDataDir = profileDir;
  } else {
    launchOpts.executablePath = process.env.CHROME_PATH || '/usr/bin/google-chrome';
  }

  const browser = await puppeteer.launch(launchOpts);
  const page = await browser.newPage();

  try {
    await login(page);

    // Navigate to people page to establish session context + CSRF token
    await page.goto('https://app.apollo.io/#/people', { waitUntil: 'domcontentloaded', timeout: 60000 });
    await sleep(8000);

    // Verify CSRF token exists
    const csrfOk = await page.evaluate(() => {
      const meta = document.querySelector('meta[name="csrf-token"]');
      return meta ? meta.content.substring(0, 10) + '...' : 'NOT FOUND';
    });
    console.log(`[${ts()}] CSRF: ${csrfOk}`);

    const people = await searchPeople(page, domains, titles, seniorities, maxPages);

    console.log(`  Result: ${people.length} people`);
    fs.writeFileSync(outputFile, JSON.stringify(people, null, 2));
    console.log(`  Saved: ${outputFile}`);
  } catch (e) {
    console.error(`FATAL: ${e.message}`);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

main();
