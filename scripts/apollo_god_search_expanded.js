/**
 * Apollo God-Mode UAE Search — EXPANDED
 *
 * Builds on top of the original apollo_god_search.js.
 * Searches NEW seniority levels + industry-specific keywords not covered before.
 *
 * Strategy C: VP/Director/Manager seniority × company size (same as B but different seniorities)
 * Strategy D: Industry-specific keywords × city (more targeted than Strategy A's generic terms)
 *
 * Usage:
 *   node scripts/apollo_god_search_expanded.js                    # run all
 *   node scripts/apollo_god_search_expanded.js --strategy C       # vp/director seniority only
 *   node scripts/apollo_god_search_expanded.js --strategy D       # industry keywords only
 *   node scripts/apollo_god_search_expanded.js --resume           # resume from progress
 *   node scripts/apollo_god_search_expanded.js --max-pages 10     # default 10
 *   node scripts/apollo_god_search_expanded.js --city Dubai       # single city
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const APOLLO_EMAIL = 'danila@getsally.io';
const APOLLO_PASS = 'UQdzDShCjAi5Nil!!';
const OUT_DIR = path.join(__dirname, '..', 'easystaff-global', 'data');
const RESULTS_FILE = path.join(OUT_DIR, 'uae_expanded_companies.json');
const PEOPLE_FILE = path.join(OUT_DIR, 'uae_expanded_people.json');
const PROGRESS_FILE = path.join(OUT_DIR, 'uae_expanded_progress.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ================================================================
//  EXPANDED SEARCH CONFIGURATIONS
// ================================================================

const UAE_CITIES = [
  'Dubai, United Arab Emirates',
  'Abu Dhabi, United Arab Emirates',
  'Sharjah, United Arab Emirates',
  'Ajman, United Arab Emirates',
  'Ras Al Khaimah, United Arab Emirates',
];

// Strategy C: VP/Director/Manager — NOT searched before (original only did founder/c_suite/owner)
const SENIORITIES_EXPANDED = ['vp', 'director', 'manager'];
const SIZE_RANGES = ['1,10', '11,20', '21,50', '51,100', '101,200', '201,500'];

// Strategy D: Industry-targeted keywords — more specific than Strategy A
const INDUSTRY_KEYWORDS = [
  // Digital services (not covered by Strategy A)
  'digital transformation agency', 'growth hacking', 'conversion optimization',
  'programmatic advertising', 'media buying agency', 'affiliate marketing',
  'influencer marketing agency', 'employer branding',
  'talent acquisition firm', 'executive search', 'headhunting',

  // Tech services
  'cloud services', 'managed services', 'IT managed services',
  'SaaS company', 'software as a service', 'platform development',
  'API development', 'blockchain development', 'Web3',
  'IoT solutions', 'machine learning', 'computer vision',

  // Creative
  'creative services', 'brand strategy', 'naming agency',
  'packaging design', 'industrial design', 'UX research',
  'user experience', 'service design', 'design thinking',
  'motion design', 'visual effects', 'post production house',

  // Consulting & professional
  'technology consulting', 'digital consulting', 'innovation consulting',
  'change management', 'process automation', 'RPA',
  'business intelligence', 'data engineering', 'analytics company',
  'compliance consulting', 'risk management consulting',
  'sustainability consulting', 'ESG consulting',

  // Industry-specific tech
  'real estate technology', 'construction tech', 'logistics technology',
  'supply chain tech', 'retail technology', 'food tech',
  'travel technology', 'hospitality technology',
  'education technology', 'learning management',

  // Staffing & HR (core ICP for EasyStaff)
  'staffing solutions', 'workforce management', 'payroll services',
  'PEO', 'employer of record', 'EOR',
  'contract staffing', 'temporary staffing', 'RPO',
  'HR technology', 'HRIS', 'workforce analytics',
];

// Same exclusion list as original
const EXCLUDE_KEYWORDS = [
  'restaurant', 'café', 'cafe', 'catering', 'food', 'bakery', 'kitchen',
  'hotel', 'hospitality', 'resort', 'spa', 'salon', 'beauty',
  'construction', 'contracting', 'building', 'real estate', 'property',
  'trading', 'import', 'export', 'wholesale', 'retail', 'supermarket',
  'shipping', 'freight', 'cargo', 'logistics', 'warehouse',
  'oil', 'gas', 'petroleum', 'mining', 'steel', 'metals',
  'medical', 'hospital', 'clinic', 'pharmacy', 'dental',
  'school', 'university', 'nursery', 'kindergarten',
  'laundry', 'cleaning', 'maintenance', 'plumbing', 'electrical',
  'car', 'auto', 'garage', 'vehicle', 'transport',
  'furniture', 'textile', 'garment', 'fabric',
  'jewelry', 'gold', 'diamond', 'watch',
  'travel', 'tourism', 'airline', 'cruise',
  'bank', 'insurance', 'exchange',
  'government', 'ministry', 'municipality', 'police', 'military',
  'church', 'mosque', 'temple',
];

// ================================================================
//  URL BUILDER (same as original)
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
//  GENERATE EXPANDED CONFIGS
// ================================================================

function generateSearchConfigs(strategy, cityFilter) {
  const configs = [];
  const cities = cityFilter
    ? UAE_CITIES.filter(c => c.toLowerCase().includes(cityFilter.toLowerCase()))
    : UAE_CITIES;

  if (strategy === 'C' || strategy === 'all') {
    // Strategy C: expanded seniority × size × city
    for (const city of cities) {
      for (const size of SIZE_RANGES) {
        for (const sen of SENIORITIES_EXPANDED) {
          configs.push({
            id: `C_${city.split(',')[0]}_${sen}_${size}`,
            strategy: 'C',
            label: `[C] ${sen} at ${size} emp in ${city.split(',')[0]}`,
            url: buildSearchUrl({
              locations: [city],
              seniorities: [sen],
              sizeRanges: [size],
            }),
          });
        }
      }
    }
  }

  if (strategy === 'D' || strategy === 'all') {
    // Strategy D: industry keywords × city
    for (const city of cities) {
      for (const kw of INDUSTRY_KEYWORDS) {
        configs.push({
          id: `D_${city.split(',')[0]}_${kw}`,
          strategy: 'D',
          label: `[D] "${kw}" in ${city.split(',')[0]}`,
          url: buildSearchUrl({
            locations: [city],
            keyword: kw,
          }),
        });
      }
    }
  }

  return configs;
}

// ================================================================
//  LOGIN (same as original)
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
    if (text.includes('Log In')) {
      await btn.click();
      break;
    }
  }

  await sleep(3000);
  if (page.url().includes('/login')) {
    throw new Error('Login failed — check credentials or 2FA');
  }
  console.log('  Login successful');
}

// ================================================================
//  SCRAPE PAGE (DOM-based, same as original)
// ================================================================

async function scrapePeoplePage(page) {
  const people = await page.evaluate(() => {
    const rows = document.querySelectorAll('tr[class*="zp_"]');
    return Array.from(rows).map(row => {
      const nameEl = row.querySelector('a[href*="/contacts/"]');
      const titleEl = row.querySelector('span[class*="zp_"]');
      const companyEl = row.querySelector('a[href*="/companies/"]');
      const locationEl = row.querySelectorAll('span[class*="zp_"]');

      const name = nameEl?.textContent?.trim() || '';
      const title = titleEl?.textContent?.trim() || '';
      const company = companyEl?.textContent?.trim() || '';

      // Extract domain from company link if available
      const companyLink = companyEl?.getAttribute('href') || '';

      return { name, title, company, companyLink };
    }).filter(p => p.name);
  });
  return people;
}

// ================================================================
//  MAIN
// ================================================================

async function main() {
  const args = process.argv.slice(2);
  const strategyArg = args.includes('--strategy') ? args[args.indexOf('--strategy') + 1] : 'all';
  const maxPages = args.includes('--max-pages') ? parseInt(args[args.indexOf('--max-pages') + 1]) : 10;
  const resume = args.includes('--resume');
  const cityFilter = args.includes('--city') ? args[args.indexOf('--city') + 1] : null;

  const configs = generateSearchConfigs(strategyArg, cityFilter);

  // Load progress
  let progress = {};
  if (resume && fs.existsSync(PROGRESS_FILE)) {
    progress = JSON.parse(fs.readFileSync(PROGRESS_FILE, 'utf8'));
  }

  // Load existing results
  let allCompanies = [];
  let allPeople = [];
  if (resume && fs.existsSync(RESULTS_FILE)) {
    allCompanies = JSON.parse(fs.readFileSync(RESULTS_FILE, 'utf8'));
  }
  if (resume && fs.existsSync(PEOPLE_FILE)) {
    allPeople = JSON.parse(fs.readFileSync(PEOPLE_FILE, 'utf8'));
  }

  const remaining = configs.filter(c => !progress[c.id]);

  console.log(`=== APOLLO EXPANDED UAE SEARCH ===`);
  console.log(`Strategy: ${strategyArg}`);
  console.log(`Cities: ${cityFilter || 'all (5 UAE cities)'}`);
  console.log(`Max pages per search: ${maxPages}`);
  console.log(`Total search configs: ${configs.length}`);
  console.log(`  Strategy C (vp/director/manager): ${configs.filter(c => c.strategy === 'C').length}`);
  console.log(`  Strategy D (industry keywords): ${configs.filter(c => c.strategy === 'D').length}`);
  console.log(`Remaining searches: ${remaining.length} (${configs.length - remaining.length} already done)`);
  console.log(`Companies collected so far: ${allCompanies.length}`);
  console.log(`People collected so far: ${allPeople.length}`);

  if (remaining.length === 0) {
    console.log('All searches already done!');
    return;
  }

  // Launch browser
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });

  // Intercept API responses for structured data
  const interceptedOrgs = new Map();
  page.on('response', async (response) => {
    try {
      const url = response.url();
      if (url.includes('/mixed_people/search') || url.includes('/people/search')) {
        const data = await response.json();
        const people = data.people || [];
        for (const p of people) {
          if (p.organization) {
            const org = p.organization;
            const domain = org.primary_domain || org.website_url || '';
            if (domain) {
              interceptedOrgs.set(org.id || domain, {
                id: org.id,
                name: org.name,
                domain: domain,
                industry: org.industry || '',
                keywords: org.keywords || [],
                employees: org.estimated_num_employees,
                city: p.city || org.city || '',
                state: p.state || org.state || '',
                country: p.country || org.country || '',
                linkedin_url: org.linkedin_url || '',
                short_description: org.short_description || '',
                founded_year: org.founded_year,
              });
            }
            // Also collect the person
            allPeople.push({
              id: p.id,
              name: `${p.first_name || ''} ${p.last_name || ''}`.trim(),
              first_name: p.first_name,
              last_name: p.last_name,
              title: p.title || '',
              email: p.email || '',
              email_status: p.email_status || '',
              linkedin_url: p.linkedin_url || '',
              city: p.city || '',
              country: p.country || '',
              seniority: p.seniority || '',
              organization: {
                id: org.id,
                name: org.name,
                website_url: org.primary_domain || org.website_url || '',
                estimated_num_employees: org.estimated_num_employees,
                industries: org.industries || [],
                keywords: org.keywords || [],
              },
            });
          }
        }
      }
    } catch (e) {
      // Ignore parse errors on non-JSON responses
    }
  });

  try {
    await login(page);

    for (let i = 0; i < remaining.length; i++) {
      const config = remaining[i];
      console.log(`\n[${i + 1}/${remaining.length}] ${config.label}`);

      try {
        await page.goto(config.url, { waitUntil: 'networkidle2', timeout: 30000 });
        await sleep(3000);

        let pageNum = 0;
        let emptyPages = 0;

        for (let p = 0; p < maxPages; p++) {
          pageNum++;
          const beforeCount = interceptedOrgs.size;

          // Try DOM scraping as fallback
          const domPeople = await scrapePeoplePage(page);

          const afterCount = interceptedOrgs.size;
          const newFromApi = afterCount - beforeCount;
          const source = newFromApi > 0 ? 'API' : 'DOM';
          console.log(`  ${config.label} p${pageNum}: ${Math.max(newFromApi, domPeople.length)} people (${source})`);

          if (domPeople.length === 0 && newFromApi === 0) {
            emptyPages++;
            if (emptyPages >= 2) break; // Two consecutive empty pages = done
          } else {
            emptyPages = 0;
          }

          // Navigate to next page
          try {
            const nextBtn = await page.$('button[aria-label="right-arrow"]');
            if (!nextBtn) break;
            const isDisabled = await page.evaluate(el => el.disabled, nextBtn);
            if (isDisabled) break;
            await nextBtn.click();
            await sleep(2000 + Math.random() * 1000);
          } catch (e) {
            break;
          }
        }

        // Merge intercepted orgs into companies
        for (const [key, org] of interceptedOrgs) {
          if (!allCompanies.find(c => c.domain === org.domain || c.id === org.id)) {
            allCompanies.push(org);
          }
        }

      } catch (e) {
        console.log(`  ERROR: ${e.message}`);
      }

      // Mark done and save progress
      progress[config.id] = { done: true, timestamp: new Date().toISOString() };

      // Save every 5 configs
      if ((i + 1) % 5 === 0 || i === remaining.length - 1) {
        fs.writeFileSync(RESULTS_FILE.replace('.json', '_expanded.json'), JSON.stringify(allCompanies, null, 2));
        fs.writeFileSync(PEOPLE_FILE.replace('.json', '_expanded.json'), JSON.stringify(allPeople, null, 2));
        fs.writeFileSync(PROGRESS_FILE, JSON.stringify(progress, null, 2));
        console.log(`  [SAVED] ${allCompanies.length} companies, ${allPeople.length} people`);
      }

      // Rate limiting
      await sleep(1000 + Math.random() * 2000);
    }

  } finally {
    await browser.close();
  }

  // Final save
  const expandedFile = RESULTS_FILE.replace('.json', '_expanded.json');
  fs.writeFileSync(expandedFile, JSON.stringify(allCompanies, null, 2));
  fs.writeFileSync(PEOPLE_FILE.replace('.json', '_expanded.json'), JSON.stringify(allPeople, null, 2));
  fs.writeFileSync(PROGRESS_FILE, JSON.stringify(progress, null, 2));

  console.log(`\n=== DONE ===`);
  console.log(`Companies: ${allCompanies.length}`);
  console.log(`People: ${allPeople.length}`);
  console.log(`Saved to: ${expandedFile}`);
}

main().catch(e => {
  console.error('FATAL:', e);
  process.exit(1);
});
