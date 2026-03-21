/**
 * Apollo City Scraper — Universal script for any city
 *
 * Searches Apollo People tab with seniority + keyword strategies.
 * Saves ALL filters as actual arrays (not summaries) for pipeline DB.
 *
 * Usage:
 *   node scripts/apollo_city_scraper.js --city "New York" --country "United States" --state "New York"
 *   node scripts/apollo_city_scraper.js --city "Riyadh" --country "Saudi Arabia"
 *   node scripts/apollo_city_scraper.js --city "London" --country "United Kingdom" --state "England"
 *   node scripts/apollo_city_scraper.js --resume
 *   node scripts/apollo_city_scraper.js --max-pages 10
 *   node scripts/apollo_city_scraper.js --strategy seniority   # seniority only
 *   node scripts/apollo_city_scraper.js --strategy keywords    # keywords only
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ================================================================
//  CONFIGURATION
// ================================================================

const SENIORITIES = ['founder', 'c_suite', 'owner', 'vp', 'director', 'manager'];
const SIZE_RANGES = ['1,10', '11,20', '21,50', '51,100', '101,200', '201,500'];

const KEYWORDS = [
  // Digital agencies
  'marketing agency', 'digital agency', 'creative agency', 'advertising agency',
  'design agency', 'branding agency', 'PR agency', 'social media agency',
  'SEO agency', 'content agency', 'web design', 'web development',
  'UX agency', 'UI design', 'product design',
  // Tech services
  'software development', 'IT services', 'app development', 'mobile development',
  'cloud consulting', 'DevOps', 'cybersecurity', 'data analytics',
  'AI consulting', 'machine learning', 'SaaS', 'tech startup',
  // Creative/media
  'video production', 'film production', 'animation studio', 'production house',
  'photography studio', 'motion graphics', 'post production', 'game studio',
  'podcast production', 'content creation',
  // Professional services
  'digital marketing', 'performance marketing', 'growth agency',
  'influencer agency', 'e-commerce', 'media agency',
  'communications agency', 'event production', 'innovation lab',
  'digital transformation', 'technology company', 'digital solutions',
  'fintech', 'edtech', 'healthtech', 'proptech',
  // Broader
  'software house', 'development studio', 'creative studio',
  'tech solutions', 'managed services', 'IT consulting',
  'boutique agency', 'full service agency',
];

const EXCLUDE_KEYWORDS = [
  'restaurant', 'café', 'cafe', 'catering', 'food', 'bakery',
  'hotel', 'hospitality', 'resort', 'spa', 'salon',
  'construction', 'contracting', 'building', 'real estate', 'property',
  'trading', 'import', 'export', 'wholesale', 'retail',
  'shipping', 'freight', 'cargo', 'logistics',
  'oil', 'gas', 'petroleum', 'mining', 'steel',
  'medical', 'hospital', 'clinic', 'pharmacy',
  'school', 'university', 'nursery',
  'laundry', 'cleaning', 'plumbing',
  'car', 'auto', 'garage', 'vehicle',
  'furniture', 'textile', 'jewelry',
  'travel', 'tourism', 'airline',
  'bank', 'insurance', 'exchange',
  'government', 'ministry', 'municipality',
  'church', 'mosque', 'temple',
];

// ================================================================
//  ARGS PARSING
// ================================================================

const args = process.argv.slice(2);
function getArg(name, defaultVal) {
  const idx = args.indexOf(`--${name}`);
  return idx !== -1 && idx + 1 < args.length ? args[idx + 1] : defaultVal;
}

const CITY = getArg('city', 'New York');
const COUNTRY = getArg('country', 'United States');
const STATE = getArg('state', '');
const MAX_PAGES = parseInt(getArg('max-pages', '10'));
const STRATEGY = getArg('strategy', 'all'); // seniority, keywords, all
const RESUME = args.includes('--resume');

const LOCATION = STATE ? `${CITY}, ${STATE}, ${COUNTRY}` : `${CITY}, ${COUNTRY}`;
const SLUG = CITY.toLowerCase().replace(/\s+/g, '_');
const OUT_DIR = path.join(__dirname, '..', 'gathering-data', SLUG);

// Create output dir
if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

const RESULTS_FILE = path.join(OUT_DIR, `${SLUG}_companies.json`);
const PEOPLE_FILE = path.join(OUT_DIR, `${SLUG}_people.json`);
const PROGRESS_FILE = path.join(OUT_DIR, `${SLUG}_progress.json`);
const META_FILE = path.join(OUT_DIR, `${SLUG}_meta.json`);

// ================================================================
//  URL BUILDER
// ================================================================

function buildSearchUrl(params) {
  const base = 'https://app.apollo.io/#/people?';
  const parts = [];
  for (const loc of (params.locations || [])) {
    parts.push(`personLocations[]=${encodeURIComponent(loc)}`);
  }
  if (params.keyword) {
    parts.push(`qOrganizationName=${encodeURIComponent(params.keyword)}`);
  }
  for (const sen of (params.seniorities || [])) {
    parts.push(`personSeniorities[]=${encodeURIComponent(sen)}`);
  }
  for (const range of (params.sizeRanges || [])) {
    parts.push(`organizationNumEmployeesRanges[]=${encodeURIComponent(range)}`);
  }
  return base + parts.join('&');
}

// ================================================================
//  SEARCH CONFIGS
// ================================================================

function generateConfigs() {
  const configs = [];

  if (STRATEGY === 'seniority' || STRATEGY === 'all') {
    for (const size of SIZE_RANGES) {
      for (const sen of SENIORITIES) {
        configs.push({
          id: `S_${SLUG}_${sen}_${size}`,
          strategy: 'seniority',
          label: `[S] ${sen} at ${size} emp in ${CITY}`,
          url: buildSearchUrl({ locations: [LOCATION], seniorities: [sen], sizeRanges: [size] }),
        });
      }
    }
  }

  if (STRATEGY === 'keywords' || STRATEGY === 'all') {
    for (const kw of KEYWORDS) {
      configs.push({
        id: `K_${SLUG}_${kw}`,
        strategy: 'keywords',
        label: `[K] "${kw}" in ${CITY}`,
        url: buildSearchUrl({ locations: [LOCATION], keyword: kw }),
      });
    }
  }

  return configs;
}

// ================================================================
//  LOGIN
// ================================================================

async function login(page) {
  console.log('[LOGIN] Logging into Apollo...');
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);
  if (page.url().includes('/people') || page.url().includes('/home')) {
    console.log('  Already logged in');
    return;
  }
  await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 30 });
  await sleep(500);
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 30 });
  await sleep(500);
  const buttons = await page.$$('button[type="submit"]');
  for (const btn of buttons) {
    const text = await page.evaluate(el => el.textContent, btn);
    if (text.includes('Log In')) { await btn.click(); break; }
  }
  await sleep(3000);
  if (page.url().includes('/login')) throw new Error('Login failed');
  console.log('  Login successful');
}

// ================================================================
//  MAIN
// ================================================================

async function main() {
  const configs = generateConfigs();
  let progress = {};
  if (RESUME && fs.existsSync(PROGRESS_FILE)) progress = JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8'));

  let allCompanies = RESUME && fs.existsSync(RESULTS_FILE) ? JSON.parse(fs.readFileSync(RESULTS_FILE, 'utf8')) : [];
  let allPeople = RESUME && fs.existsSync(PEOPLE_FILE) ? JSON.parse(fs.readFileSync(PEOPLE_FILE, 'utf8')) : [];

  const remaining = configs.filter(c => !progress[c.id]);

  console.log(`=== APOLLO CITY SCRAPER: ${CITY}, ${COUNTRY} ===`);
  console.log(`Location: ${LOCATION}`);
  console.log(`Strategy: ${STRATEGY}`);
  console.log(`Max pages: ${MAX_PAGES}`);
  console.log(`Configs: ${configs.length} total, ${remaining.length} remaining`);
  console.log(`Companies so far: ${allCompanies.length}`);
  console.log(`Output: ${OUT_DIR}`);

  // Save metadata (actual filters for pipeline DB)
  const meta = {
    city: CITY, country: COUNTRY, state: STATE,
    location: LOCATION, strategy: STRATEGY,
    max_pages: MAX_PAGES,
    seniorities: SENIORITIES,
    size_ranges: SIZE_RANGES,
    keywords: KEYWORDS,  // ACTUAL ARRAY — not a summary!
    exclude_keywords: EXCLUDE_KEYWORDS,
    total_configs: configs.length,
    started_at: new Date().toISOString(),
  };
  fs.writeFileSync(META_FILE, JSON.stringify(meta, null, 2));

  if (remaining.length === 0) { console.log('All done!'); return; }

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  // API response interception
  const interceptedOrgs = new Map();
  page.on('response', async (response) => {
    try {
      const url = response.url();
      if (url.includes('/mixed_people/search') || url.includes('/people/search')) {
        const data = await response.json();
        for (const p of (data.people || [])) {
          if (p.organization) {
            const org = p.organization;
            const domain = org.primary_domain || org.website_url || '';
            if (domain) {
              interceptedOrgs.set(org.id || domain, {
                id: org.id, name: org.name, domain,
                industry: org.industry || '', keywords: org.keywords || [],
                employees: org.estimated_num_employees,
                city: p.city || org.city || '', state: p.state || org.state || '',
                country: p.country || org.country || '',
                linkedin_url: org.linkedin_url || '',
                short_description: org.short_description || '',
                founded_year: org.founded_year,
              });
            }
            allPeople.push({
              name: `${p.first_name || ''} ${p.last_name || ''}`.trim(),
              first_name: p.first_name, last_name: p.last_name,
              title: p.title || '', email: p.email || '',
              email_status: p.email_status || '',
              linkedin_url: p.linkedin_url || '',
              city: p.city || '', country: p.country || '',
              seniority: p.seniority || '',
              organization: {
                name: org.name, website_url: domain,
                estimated_num_employees: org.estimated_num_employees,
                industries: org.industries || [], keywords: org.keywords || [],
              },
            });
          }
        }
      }
    } catch (e) {}
  });

  try {
    await login(page);

    for (let i = 0; i < remaining.length; i++) {
      const config = remaining[i];
      console.log(`\n[${i+1}/${remaining.length}] ${config.label}`);

      try {
        await page.goto(config.url, { waitUntil: 'networkidle2', timeout: 30000 });
        await sleep(3000);

        let emptyPages = 0;
        for (let p = 0; p < MAX_PAGES; p++) {
          const before = interceptedOrgs.size;
          await sleep(2000);
          const after = interceptedOrgs.size;
          const newCount = after - before;
          console.log(`  ${config.label} p${p+1}: ${newCount} people (${newCount > 0 ? 'API' : 'DOM'})`);
          if (newCount === 0) { emptyPages++; if (emptyPages >= 2) break; } else emptyPages = 0;
          try {
            const nextBtn = await page.$('button[aria-label="right-arrow"]');
            if (!nextBtn) break;
            if (await page.evaluate(el => el.disabled, nextBtn)) break;
            await nextBtn.click();
            await sleep(2000 + Math.random() * 1000);
          } catch (e) { break; }
        }

        for (const [key, org] of interceptedOrgs) {
          if (!allCompanies.find(c => c.domain === org.domain || c.id === org.id)) {
            allCompanies.push(org);
          }
        }
      } catch (e) { console.log(`  ERROR: ${e.message}`); }

      progress[config.id] = { done: true, timestamp: new Date().toISOString() };

      if ((i+1) % 5 === 0 || i === remaining.length - 1) {
        fs.writeFileSync(RESULTS_FILE, JSON.stringify(allCompanies, null, 2));
        fs.writeFileSync(PEOPLE_FILE, JSON.stringify(allPeople, null, 2));
        fs.writeFileSync(PROGRESS_FILE, JSON.stringify(progress, null, 2));
        console.log(`  [SAVED] ${allCompanies.length} companies, ${allPeople.length} people`);
      }

      await sleep(1000 + Math.random() * 2000);
    }
  } finally { await browser.close(); }

  // Final save
  fs.writeFileSync(RESULTS_FILE, JSON.stringify(allCompanies, null, 2));
  fs.writeFileSync(PEOPLE_FILE, JSON.stringify(allPeople, null, 2));
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify(progress, null, 2));

  // Update meta
  meta.completed_at = new Date().toISOString();
  meta.total_companies = allCompanies.length;
  meta.total_people = allPeople.length;
  fs.writeFileSync(META_FILE, JSON.stringify(meta, null, 2));

  console.log(`\n=== DONE: ${CITY} ===`);
  console.log(`Companies: ${allCompanies.length}`);
  console.log(`People: ${allPeople.length}`);
  console.log(`Output: ${OUT_DIR}`);
}

main().catch(e => { console.error('FATAL:', e); process.exit(1); });
