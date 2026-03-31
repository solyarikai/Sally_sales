/**
 * Apollo People Search — Internal API via Browser Session
 *
 * Searches Apollo People by domains + titles + seniorities using the internal
 * API (app.apollo.io/api/v1/mixed_people/search) from within a browser session.
 * FREE — no API credits spent.
 *
 * Key advantage over apollo_scraper.js:
 *   - Uses internal API instead of UI grid scraping (more reliable)
 *   - Stealth plugin + session cookies (avoids CAPTCHA)
 *   - Structured JSON response (not fragile DOM selectors)
 *
 * Usage:
 *   # Search by domains file (one domain per line)
 *   node scripts/apollo_people_search.js --domains-file /tmp/domains.txt --output /tmp/people.json
 *
 *   # Search by inline domains
 *   node scripts/apollo_people_search.js --domains "modash.io,captiv8.io,lefty.io" --output /tmp/people.json
 *
 *   # With custom titles and seniorities
 *   node scripts/apollo_people_search.js --domains-file /tmp/domains.txt \
 *     --titles "CTO,CEO,Founder,VP Engineering" \
 *     --seniorities "c_suite,vp,director,founder" \
 *     --output /tmp/people.json
 *
 *   # Batch size control (domains per API call, default 10)
 *   node scripts/apollo_people_search.js --domains-file /tmp/domains.txt --batch-size 15
 *
 *   # Max pages per batch (default 5, max results = batch_size * per_page * max_pages)
 *   node scripts/apollo_people_search.js --domains-file /tmp/domains.txt --max-pages 10
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const SESSION_FILE = path.join(__dirname, 'data', 'apollo_session.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function ts() { return new Date().toISOString().replace('T', ' ').substring(0, 19); }

// ── Parse args ────────────────────────────────────────────────────────────────
function parseArgs() {
  const args = process.argv.slice(2);
  const get = (flag) => {
    const idx = args.indexOf(flag);
    return idx >= 0 && args[idx + 1] ? args[idx + 1] : null;
  };

  const domainsFile = get('--domains-file');
  const domainsInline = get('--domains');
  const output = get('--output') || path.join(__dirname, 'data', 'apollo_people_search.json');
  const batchSize = parseInt(get('--batch-size') || '10');
  const maxPages = parseInt(get('--max-pages') || '5');
  const perPage = parseInt(get('--per-page') || '25');

  // Titles
  const titlesArg = get('--titles');
  const titles = titlesArg ? titlesArg.split(',').map(t => t.trim()) : [
    'CTO', 'VP Engineering', 'VP of Engineering', 'Head of Engineering',
    'Head of Product', 'Chief Product Officer', 'VP Product',
    'Director of Engineering', 'Director of Product',
    'Co-Founder', 'Founder', 'CEO', 'COO',
  ];

  // Seniorities
  const senArg = get('--seniorities');
  const seniorities = senArg ? senArg.split(',').map(s => s.trim()) : [
    'c_suite', 'vp', 'director', 'owner', 'founder',
  ];

  // Load domains
  let domains = [];
  if (domainsFile) {
    if (!fs.existsSync(domainsFile)) {
      console.error(`ERROR: domains file not found: ${domainsFile}`);
      process.exit(1);
    }
    domains = fs.readFileSync(domainsFile, 'utf8')
      .split('\n').map(d => d.trim().toLowerCase()).filter(d => d && d.includes('.'));
  } else if (domainsInline) {
    domains = domainsInline.split(',').map(d => d.trim().toLowerCase()).filter(d => d);
  }

  if (domains.length === 0) {
    console.log('Usage: node apollo_people_search.js --domains "modash.io,captiv8.io" --output /tmp/out.json');
    console.log('   or: node apollo_people_search.js --domains-file /tmp/domains.txt');
    process.exit(1);
  }

  return { domains, titles, seniorities, output, batchSize, maxPages, perPage };
}

// ── Login with session reuse ──────────────────────────────────────────────────
async function login(page) {
  console.log(`[${ts()}] Logging into Apollo...`);

  // Try saved cookies first
  if (fs.existsSync(SESSION_FILE)) {
    try {
      const cookies = JSON.parse(fs.readFileSync(SESSION_FILE, 'utf8'));
      await page.setCookie(...cookies);
      console.log(`[${ts()}] Loaded saved cookies`);
    } catch (e) {
      console.log(`[${ts()}] Failed to load cookies: ${e.message}`);
    }
  }

  await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  const url = page.url();
  if (url.includes('/people') || url.includes('/home') || url.includes('/companies') || url.includes('/sequences')) {
    console.log(`[${ts()}] Already logged in (cookies valid)`);
    return;
  }

  // Need to login
  console.log(`[${ts()}] Cookies expired, entering credentials...`);
  try {
    await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  } catch (e) {
    // Maybe CAPTCHA or other blocker
    const dataDir = path.join(__dirname, 'data');
    if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
    await page.screenshot({ path: path.join(dataDir, 'apollo_login_blocked.png'), fullPage: true });
    const html = await page.content();
    fs.writeFileSync(path.join(dataDir, 'apollo_login_blocked.html'), html.substring(0, 50000));
    console.log(`[${ts()}] Login form not found — saved screenshot to data/apollo_login_blocked.png`);
    throw new Error('Login blocked (CAPTCHA or page change). Check data/apollo_login_blocked.png');
  }

  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 50 });
  await sleep(500);
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 50 });
  await sleep(500);
  await page.click('button[type="submit"]');
  await sleep(5000);

  for (let i = 0; i < 30; i++) {
    const u = page.url();
    if (u.includes('/people') || u.includes('/home') || u.includes('/companies') || u.includes('/sequences')) {
      console.log(`[${ts()}] Login successful`);
      // Save cookies for next time
      const cookies = await page.cookies();
      const dataDir = path.join(__dirname, 'data');
      if (!fs.existsSync(dataDir)) fs.mkdirSync(dataDir, { recursive: true });
      fs.writeFileSync(SESSION_FILE, JSON.stringify(cookies, null, 2));
      return;
    }
    await sleep(2000);
  }

  await page.screenshot({ path: path.join(__dirname, 'data', 'apollo_login_failed.png'), fullPage: true });
  throw new Error('Login failed — stuck at: ' + page.url());
}

// ── Internal API call ─────────────────────────────────────────────────────────
async function searchPeopleAPI(page, params) {
  return page.evaluate(async (searchParams) => {
    try {
      const csrfMeta = document.querySelector('meta[name="csrf-token"]');
      const csrfToken = csrfMeta ? csrfMeta.content : '';
      const res = await fetch('https://app.apollo.io/api/v1/mixed_people/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Csrf-Token': csrfToken },
        credentials: 'include',
        body: JSON.stringify(searchParams),
      });
      if (!res.ok) return { error: `HTTP ${res.status}`, status: res.status };
      return await res.json();
    } catch (e) {
      return { error: e.message };
    }
  }, params);
}

// ── Main ──────────────────────────────────────────────────────────────────────
(async () => {
  const config = parseArgs();
  const { domains, titles, seniorities, output, batchSize, maxPages, perPage } = config;

  console.log(`[${ts()}] Apollo People Search (Internal API)`);
  console.log(`  Domains: ${domains.length}`);
  console.log(`  Titles: ${titles.length} (${titles.slice(0, 5).join(', ')}...)`);
  console.log(`  Seniorities: ${seniorities.join(', ')}`);
  console.log(`  Batch size: ${batchSize} domains per API call`);
  console.log(`  Max pages per batch: ${maxPages}`);
  console.log(`  Output: ${output}`);

  const browser = await puppeteer.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage',
           '--disable-gpu', '--disable-blink-features=AutomationControlled'],
    defaultViewport: { width: 1440, height: 900 },
  });
  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36');

  try {
    await login(page);

    // Navigate to people page (needed for CSRF token)
    await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(2000);

    const allPeople = [];
    const batches = [];
    for (let i = 0; i < domains.length; i += batchSize) {
      batches.push(domains.slice(i, i + batchSize));
    }

    console.log(`\n[${ts()}] Starting search: ${batches.length} batches`);

    let consecutiveErrors = 0;

    for (let bi = 0; bi < batches.length; bi++) {
      const batchDomains = batches[bi];
      let batchPeople = 0;

      for (let pageNum = 1; pageNum <= maxPages; pageNum++) {
        const params = {
          organization_domains: batchDomains,
          person_titles: titles,
          person_seniorities: seniorities,
          page: pageNum,
          per_page: perPage,
          display_mode: 'explorer_mode',
          context: 'people-index-page',
          finder_version: 2,
        };

        const result = await searchPeopleAPI(page, params);

        if (result.error) {
          console.log(`  Batch ${bi + 1}/${batches.length} p${pageNum}: ERROR ${result.error}`);
          consecutiveErrors++;
          if (result.status === 429) {
            console.log(`  Rate limited — waiting 60s...`);
            await sleep(60000);
            continue;
          }
          if (result.status === 401 || result.status === 403) {
            console.log(`  Session expired — re-logging in...`);
            await login(page);
            await page.goto('https://app.apollo.io/#/people', { waitUntil: 'networkidle2', timeout: 30000 });
            await sleep(2000);
            continue;
          }
          if (consecutiveErrors >= 5) {
            console.log(`  Too many consecutive errors — stopping`);
            break;
          }
          await sleep(3000);
          continue;
        }

        consecutiveErrors = 0;
        const people = result.people || [];
        const accounts = result.accounts || [];
        const totalEntries = result.pagination?.total_entries || 0;

        // Build org lookup
        const orgMap = {};
        for (const acc of accounts) {
          const orgId = acc.organization_id || acc.id;
          if (orgId) orgMap[orgId] = acc;
        }

        for (const p of people) {
          const orgId = p.organization_id || (p.organization || {}).id;
          const acc = orgMap[orgId] || {};
          const org = p.organization || {};

          let email = p.email || '';
          if (email.includes('not_unlocked')) email = '';

          allPeople.push({
            name: p.name || '',
            first_name: p.first_name || '',
            last_name: p.last_name || '',
            title: p.title || '',
            email: email,
            linkedin_url: p.linkedin_url || '',
            city: p.city || '',
            state: p.state || '',
            country: p.country || '',
            company_name: acc.name || org.name || p.organization_name || '',
            domain: (acc.primary_domain || org.primary_domain || acc.domain || org.domain || '').toLowerCase(),
            company_linkedin: acc.linkedin_url || org.linkedin_url || '',
            employees: acc.estimated_num_employees || org.estimated_num_employees || null,
            industry: (acc.industries || []).join(', ') || org.industry || '',
          });
        }

        batchPeople += people.length;

        if (people.length === 0 || people.length < perPage) break;
        if (pageNum >= (result.pagination?.total_pages || Infinity)) break;

        await sleep(800 + Math.random() * 500);
      }

      const total = allPeople.length;
      process.stdout.write(`  Batch ${bi + 1}/${batches.length}: ${batchDomains.length} domains -> ${batchPeople} people (total: ${total})\n`);

      // Save progress after each batch
      const outDir = path.dirname(output);
      if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
      fs.writeFileSync(output, JSON.stringify(allPeople, null, 2));

      if (consecutiveErrors >= 5) break;

      // Delay between batches
      await sleep(1500 + Math.random() * 1000);
    }

    // Dedup
    const seen = new Set();
    const unique = allPeople.filter(p => {
      const key = p.linkedin_url || `${p.name}__${p.domain}`.toLowerCase();
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    // Save final
    fs.writeFileSync(output, JSON.stringify(unique, null, 2));

    // Stats
    const withEmail = unique.filter(p => p.email).length;
    const withLi = unique.filter(p => p.linkedin_url).length;
    const companies = new Set(unique.map(p => p.domain).filter(Boolean)).size;

    console.log(`\n[${ts()}] DONE: ${unique.length} unique people from ${companies} companies`);
    console.log(`  With email: ${withEmail}, With LinkedIn: ${withLi}`);
    console.log(`  Output: ${output}`);

  } catch (e) {
    console.error(`[${ts()}] FATAL: ${e.message}`);
    try {
      await page.screenshot({ path: path.join(__dirname, 'data', 'apollo_people_search_error.png'), fullPage: true });
    } catch (_) {}
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
