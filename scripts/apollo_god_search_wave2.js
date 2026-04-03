/**
 * Apollo Wave 2 — More industry tags + larger companies + more cities
 *
 * Targets:
 * - Strategy E: Founder/C-suite at 201-1000 emp companies (larger agencies)
 * - Strategy F: MORE keywords not covered in Strategy A
 *
 * Usage:
 *   node scripts/apollo_god_search_wave2.js --strategy E
 *   node scripts/apollo_god_search_wave2.js --strategy F
 *   node scripts/apollo_god_search_wave2.js --resume
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const OUT_DIR = path.join(__dirname, '..', 'easystaff-global', 'data');
const RESULTS_FILE = path.join(OUT_DIR, 'uae_wave2_companies.json');
const PEOPLE_FILE = path.join(OUT_DIR, 'uae_wave2_people.json');
const PROGRESS_FILE = path.join(OUT_DIR, 'uae_wave2_progress.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const UAE_CITIES = [
  'Dubai, United Arab Emirates',
  'Abu Dhabi, United Arab Emirates',
  'Sharjah, United Arab Emirates',
  'Ajman, United Arab Emirates',
  'Ras Al Khaimah, United Arab Emirates',
  'Al Ain, United Arab Emirates',
  'Fujairah, United Arab Emirates',
];

// Strategy E: Larger companies (201-1000) with founder/c_suite
const SENIORITIES_E = ['founder', 'c_suite', 'owner', 'vp', 'director'];
const SIZE_RANGES_E = ['201,500', '501,1000'];

// Strategy F: Keywords NOT covered in waves A/D
const KEYWORDS_F = [
  // Agency types not yet searched
  'boutique agency', 'full service agency', '360 agency',
  'experiential agency', 'activation agency', 'BTL agency',
  'shopper marketing', 'trade marketing',

  // Specific tech
  'Shopify agency', 'WordPress agency', 'HubSpot partner',
  'Salesforce partner', 'SAP partner', 'Oracle partner',
  'React developer', 'Node.js developer', 'Python developer',
  'Flutter developer', 'AWS partner', 'Azure partner',

  // Dubai-specific
  'free zone company', 'DMCC company', 'DIFC company',
  'DIC company', 'DMC company', 'JAFZA company',
  'media city', 'internet city', 'knowledge village',

  // More services
  'animation company', 'rendering studio', 'CGI company',
  'drone services', 'aerial photography',
  'AR company', 'VR company', 'mixed reality',
  'chatbot company', 'AI company', 'ML company',
  'data company', 'analytics company',

  // Underserved segments
  'localization company', 'translation company',
  'QA company', 'testing company',
  'hosting company', 'domain registrar',
  'payment gateway', 'fintech company',
  'edtech company', 'healthtech company',
  'proptech company', 'legaltech company',
  'regtech company', 'insurtech company',
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

function generateSearchConfigs(strategy, cityFilter) {
  const configs = [];
  const cities = cityFilter
    ? UAE_CITIES.filter(c => c.toLowerCase().includes(cityFilter.toLowerCase()))
    : UAE_CITIES;

  if (strategy === 'E' || strategy === 'all') {
    for (const city of cities) {
      for (const size of SIZE_RANGES_E) {
        for (const sen of SENIORITIES_E) {
          configs.push({
            id: `E_${city.split(',')[0]}_${sen}_${size}`,
            strategy: 'E',
            label: `[E] ${sen} at ${size} emp in ${city.split(',')[0]}`,
            url: buildSearchUrl({ locations: [city], seniorities: [sen], sizeRanges: [size] }),
          });
        }
      }
    }
  }

  if (strategy === 'F' || strategy === 'all') {
    for (const city of cities) {
      for (const kw of KEYWORDS_F) {
        configs.push({
          id: `F_${city.split(',')[0]}_${kw}`,
          strategy: 'F',
          label: `[F] "${kw}" in ${city.split(',')[0]}`,
          url: buildSearchUrl({ locations: [city], keyword: kw }),
        });
      }
    }
  }

  return configs;
}

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

async function main() {
  const args = process.argv.slice(2);
  const strategyArg = args.includes('--strategy') ? args[args.indexOf('--strategy') + 1] : 'all';
  const maxPages = args.includes('--max-pages') ? parseInt(args[args.indexOf('--max-pages') + 1]) : 10;
  const resume = args.includes('--resume');

  const configs = generateSearchConfigs(strategyArg);
  let progress = {};
  if (resume && fs.existsSync(PROGRESS_FILE)) progress = JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8'));

  let allCompanies = resume && fs.existsSync(RESULTS_FILE) ? JSON.parse(fs.readFileSync(RESULTS_FILE, 'utf8')) : [];
  let allPeople = resume && fs.existsSync(PEOPLE_FILE) ? JSON.parse(fs.readFileSync(PEOPLE_FILE, 'utf8')) : [];

  const remaining = configs.filter(c => !progress[c.id]);
  console.log(`=== APOLLO WAVE 2 ===`);
  console.log(`Strategy: ${strategyArg}, Configs: ${configs.length}, Remaining: ${remaining.length}`);
  console.log(`Companies so far: ${allCompanies.length}`);

  if (remaining.length === 0) { console.log('All done!'); return; }

  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

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
                city: p.city || org.city || '', country: p.country || org.country || '',
                linkedin_url: org.linkedin_url || '', founded_year: org.founded_year,
              });
            }
            allPeople.push({
              name: `${p.first_name || ''} ${p.last_name || ''}`.trim(),
              title: p.title || '', email: p.email || '',
              linkedin_url: p.linkedin_url || '', seniority: p.seniority || '',
              organization: { name: org.name, website_url: domain, estimated_num_employees: org.estimated_num_employees },
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
        for (let p = 0; p < maxPages; p++) {
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
          if (!allCompanies.find(c => c.domain === org.domain || c.id === org.id)) allCompanies.push(org);
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

  fs.writeFileSync(RESULTS_FILE, JSON.stringify(allCompanies, null, 2));
  fs.writeFileSync(PEOPLE_FILE, JSON.stringify(allPeople, null, 2));
  console.log(`\n=== DONE === Companies: ${allCompanies.length}, People: ${allPeople.length}`);
}

main().catch(e => { console.error('FATAL:', e); process.exit(1); });
