/**
 * Apollo Universal Search — Puppeteer Scraper
 *
 * Universal search script that accepts parameters via command line.
 * Works for ANY location and keywords, not hardcoded to UAE.
 *
 * Usage:
 *   node scripts/apollo_universal_search.js --location "Poland" --keywords "PHP,Laravel,WordPress"
 *   node scripts/apollo_universal_search.js --location "Romania" --keywords "software house" --max-pages 50
 *   node scripts/apollo_universal_search.js --location "Poland" --sizes "11,50" --sizes "51,200"
 *   node scripts/apollo_universal_search.js --config /path/to/config.json
 *
 * Output: JSON file with companies array
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

// ================================================================
//  PARSE COMMAND LINE ARGS
// ================================================================

function parseArgs() {
  const args = process.argv.slice(2);
  const config = {
    locations: [],
    keywords: [],
    sizes: ['11,50', '51,200'],
    maxPages: 50,
    outputDir: path.join(__dirname, '..', 'gathering-data'),
    outputFile: null,
    configFile: null,
    resume: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const next = args[i + 1];

    if (arg === '--location' && next) {
      config.locations.push(next);
      i++;
    } else if (arg === '--keywords' && next) {
      config.keywords.push(...next.split(',').map(k => k.trim()));
      i++;
    } else if (arg === '--sizes' && next) {
      if (config.sizes.length === 2 && config.sizes[0] === '11,50') {
        config.sizes = []; // Reset default
      }
      config.sizes.push(next);
      i++;
    } else if (arg === '--max-pages' && next) {
      config.maxPages = parseInt(next) || 50;
      i++;
    } else if (arg === '--output-dir' && next) {
      config.outputDir = next;
      i++;
    } else if (arg === '--output-file' && next) {
      config.outputFile = next;
      i++;
    } else if (arg === '--config' && next) {
      config.configFile = next;
      i++;
    } else if (arg === '--resume') {
      config.resume = true;
    }
  }

  // Load from config file if provided
  if (config.configFile && fs.existsSync(config.configFile)) {
    const fileConfig = JSON.parse(fs.readFileSync(config.configFile, 'utf8'));
    if (fileConfig.locations) config.locations = fileConfig.locations;
    if (fileConfig.keywords) config.keywords = fileConfig.keywords;
    if (fileConfig.sizes) config.sizes = fileConfig.sizes;
    if (fileConfig.maxPages) config.maxPages = fileConfig.maxPages;
  }

  // Validate
  if (config.locations.length === 0) {
    console.error('ERROR: At least one --location is required');
    process.exit(1);
  }

  // Generate output filename based on params
  if (!config.outputFile) {
    const locSlug = config.locations[0].toLowerCase().replace(/[^a-z0-9]+/g, '_');
    const kwSlug = config.keywords.length > 0
      ? config.keywords[0].toLowerCase().replace(/[^a-z0-9]+/g, '_').substring(0, 20)
      : 'all';
    config.outputFile = `${locSlug}_${kwSlug}_companies.json`;
  }

  return config;
}

// ================================================================
//  URL BUILDER
// ================================================================

function buildUrl(params) {
  const parts = [];

  for (const loc of params.locations) {
    parts.push(`organizationLocations[]=${encodeURIComponent(loc)}`);
  }

  for (const size of params.sizes) {
    parts.push(`organizationNumEmployeesRanges[]=${encodeURIComponent(size)}`);
  }

  if (params.keyword) {
    parts.push(`qKeywords=${encodeURIComponent(params.keyword)}`);
  }

  if (params.industryTagId) {
    parts.push(`organizationIndustryTagIds[]=${params.industryTagId}`);
  }

  parts.push('sortAscending=false');
  parts.push('sortByField=recommendations_score');

  if (params.page) {
    parts.push(`page=${params.page}`);
  }

  return 'https://app.apollo.io/#/companies?' + parts.join('&');
}

// ================================================================
//  LOGIN
// ================================================================

async function login(page) {
  console.log(`[${ts()}] LOGIN: Starting...`);
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);

  const url = page.url();
  if (url.includes('/people') || url.includes('/home') || url.includes('/companies') || url.includes('/sequences')) {
    console.log(`[${ts()}] LOGIN: Already logged in`);
    return;
  }

  await page.waitForSelector('input[name="email"]', { timeout: 10000 });
  await page.type('input[name="email"]', APOLLO_EMAIL, { delay: 30 });
  await sleep(500);
  await page.type('input[name="password"]', APOLLO_PASS, { delay: 30 });
  await sleep(500);
  await page.click('button[type="submit"]');
  await sleep(5000);

  // Verify login - wait up to 60 seconds (same as working script)
  for (let i = 0; i < 30; i++) {
    const u = page.url();
    if (u.includes('/people') || u.includes('/home') || u.includes('/companies') || u.includes('/sequences')) {
      console.log(`[${ts()}] LOGIN: Success`);
      return;
    }
    await sleep(2000);
  }

  throw new Error('Login failed - stuck at: ' + page.url());
}

// ================================================================
//  DOM SCRAPER
// ================================================================

async function scrapePage(page) {
  return page.evaluate(() => {
    const companies = [];
    const seen = new Set();

    // Find company links
    const links = document.querySelectorAll('a[href*="/companies/"], a[data-to*="/companies/"], a[href*="/organizations/"], a[data-to*="/organizations/"]');

    for (const link of links) {
      const name = link.textContent?.trim() || '';
      if (!name || name.length < 2 || seen.has(name.toLowerCase())) continue;
      seen.add(name.toLowerCase());

      const href = link.getAttribute('href') || link.getAttribute('data-to') || '';
      const idMatch = href.match(/(?:companies|organizations)\/([a-f0-9]+)/);
      const id = idMatch ? idMatch[1] : '';

      // Get row for additional data
      const row = link.closest('[role="row"], tr') || link.parentElement?.parentElement;
      let employees = null;
      let linkedinUrl = '';
      let domain = '';

      if (row) {
        // Find employee count
        const cells = row.querySelectorAll('[role="gridcell"], td, div');
        for (const cell of cells) {
          const text = cell.textContent?.trim() || '';
          if (/^\d{1,6}$/.test(text)) {
            const num = parseInt(text);
            if (num > 0 && num < 100000) {
              employees = num;
              break;
            }
          }
        }

        // Find LinkedIn URL
        const linkedinLink = row.querySelector('a[href*="linkedin.com/company"]');
        if (linkedinLink) {
          linkedinUrl = linkedinLink.getAttribute('href') || '';
        }

        // Find domain/website
        const websiteLink = row.querySelector('a[href*="://"][target="_blank"]:not([href*="linkedin.com"]):not([href*="apollo.io"])');
        if (websiteLink) {
          try {
            const url = new URL(websiteLink.getAttribute('href'));
            domain = url.hostname.replace('www.', '');
          } catch (e) {}
        }
      }

      companies.push({ id, name, employees, linkedin_url: linkedinUrl, domain });
    }

    return companies;
  });
}

// ================================================================
//  PAGINATION
// ================================================================

async function getTotalPages(page) {
  await sleep(2000);
  return page.evaluate(() => {
    // Look for pagination text like "1 of 100" or "Page 1 of 50"
    const pageTexts = document.body.innerText.match(/(?:page\s+)?\d+\s+of\s+(\d+)/i);
    if (pageTexts) return parseInt(pageTexts[1]);

    // Look for pagination buttons
    const buttons = document.querySelectorAll('[data-page], .pagination button, nav button');
    let max = 1;
    for (const btn of buttons) {
      const num = parseInt(btn.textContent);
      if (num > max) max = num;
    }
    return max;
  });
}

async function goToNextPage(page, currentPage) {
  // Try clicking next button
  const nextClicked = await page.evaluate(() => {
    const nextBtn = document.querySelector('button[aria-label="Next"], [data-next], .pagination-next, button:has(svg[data-icon="chevron-right"])');
    if (nextBtn && !nextBtn.disabled) {
      nextBtn.click();
      return true;
    }
    return false;
  });

  if (nextClicked) {
    await sleep(3000);
    return true;
  }

  // Fallback: modify URL
  const url = page.url();
  const newUrl = url.includes('page=')
    ? url.replace(/page=\d+/, `page=${currentPage + 1}`)
    : url + `&page=${currentPage + 1}`;
  await page.goto(newUrl, { waitUntil: 'networkidle2' });
  await sleep(2000);
  return true;
}

// ================================================================
//  MAIN SEARCH
// ================================================================

async function runSearch(config) {
  const outputPath = path.join(config.outputDir, config.outputFile);
  const progressPath = outputPath.replace('.json', '_progress.json');

  // Create output dir
  if (!fs.existsSync(config.outputDir)) {
    fs.mkdirSync(config.outputDir, { recursive: true });
  }

  // Load existing results if resuming
  let allCompanies = [];
  let completedSearches = new Set();

  if (config.resume && fs.existsSync(progressPath)) {
    const progress = JSON.parse(fs.readFileSync(progressPath, 'utf8'));
    completedSearches = new Set(progress.completedSearches || []);
    if (fs.existsSync(outputPath)) {
      allCompanies = JSON.parse(fs.readFileSync(outputPath, 'utf8'));
    }
    console.log(`[${ts()}] RESUME: Loaded ${allCompanies.length} companies, ${completedSearches.size} completed searches`);
  }

  // Generate search configs
  const searches = [];

  if (config.keywords.length === 0) {
    // No keywords - just search by location + size
    for (const size of config.sizes) {
      searches.push({
        id: `loc_${size}`,
        keyword: null,
        sizes: [size],
      });
    }
  } else {
    // Search each keyword × size combination
    for (const keyword of config.keywords) {
      for (const size of config.sizes) {
        searches.push({
          id: `${keyword}_${size}`,
          keyword,
          sizes: [size],
        });
      }
    }
  }

  console.log(`[${ts()}] CONFIG: ${config.locations.join(', ')} | Keywords: ${config.keywords.join(', ') || 'none'} | Sizes: ${config.sizes.join(', ')}`);
  console.log(`[${ts()}] SEARCHES: ${searches.length} total, ${searches.length - completedSearches.size} remaining`);

  // Launch browser
  // Use system Chromium in Docker, or default in local env
  const executablePath = process.env.PUPPETEER_EXECUTABLE_PATH || undefined;

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--disable-software-rasterizer',
    ],
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  try {
    await login(page);

    const seenDomains = new Set(allCompanies.map(c => c.domain).filter(Boolean));
    const seenNames = new Set(allCompanies.map(c => c.name.toLowerCase()));

    for (const search of searches) {
      if (completedSearches.has(search.id)) {
        console.log(`[${ts()}] SKIP: ${search.id} (already done)`);
        continue;
      }

      console.log(`[${ts()}] SEARCH: ${search.id}`);

      const url = buildUrl({
        locations: config.locations,
        sizes: search.sizes,
        keyword: search.keyword,
      });

      await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });
      await sleep(3000);

      const totalPages = await getTotalPages(page);
      const pagesToScrape = Math.min(totalPages, config.maxPages);
      console.log(`[${ts()}]   Pages: ${pagesToScrape} of ${totalPages}`);

      let searchCompanies = 0;

      for (let p = 1; p <= pagesToScrape; p++) {
        const pageCompanies = await scrapePage(page);

        for (const company of pageCompanies) {
          // Dedupe by domain or name
          if (company.domain && seenDomains.has(company.domain)) continue;
          if (seenNames.has(company.name.toLowerCase())) continue;

          if (company.domain) seenDomains.add(company.domain);
          seenNames.add(company.name.toLowerCase());

          company._source = search.id;
          company._scraped_at = new Date().toISOString();
          allCompanies.push(company);
          searchCompanies++;
        }

        if (p < pagesToScrape) {
          await goToNextPage(page, p);
        }

        // Progress log every 10 pages
        if (p % 10 === 0) {
          console.log(`[${ts()}]   Page ${p}/${pagesToScrape}, +${searchCompanies} companies (total: ${allCompanies.length})`);
        }
      }

      console.log(`[${ts()}]   Done: +${searchCompanies} companies`);

      // Mark search as complete and save
      completedSearches.add(search.id);
      fs.writeFileSync(outputPath, JSON.stringify(allCompanies, null, 2));
      fs.writeFileSync(progressPath, JSON.stringify({
        completedSearches: Array.from(completedSearches),
        totalCompanies: allCompanies.length,
        lastUpdated: new Date().toISOString(),
      }, null, 2));

      // Rate limit between searches
      await sleep(2000);
    }

    console.log(`[${ts()}] COMPLETE: ${allCompanies.length} total companies`);
    console.log(`[${ts()}] Output: ${outputPath}`);

  } finally {
    await browser.close();
  }

  return allCompanies;
}

// ================================================================
//  ENTRY POINT
// ================================================================

const config = parseArgs();
runSearch(config)
  .then(companies => {
    console.log(JSON.stringify({ success: true, count: companies.length }));
    process.exit(0);
  })
  .catch(err => {
    console.error(`[${ts()}] ERROR: ${err.message}`);
    console.log(JSON.stringify({ success: false, error: err.message }));
    process.exit(1);
  });
