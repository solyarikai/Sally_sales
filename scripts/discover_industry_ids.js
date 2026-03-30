/**
 * Discover Apollo industry tag IDs by clicking quick filter buttons
 * and using the Industry & Keywords sidebar filter.
 */

const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());
const fs = require('fs');
const path = require('path');

const OUT_DIR = path.join(__dirname, '..', 'easystaff-global', 'data');
const IDS_FILE = path.join(OUT_DIR, 'apollo_industry_tag_ids.json');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// Industries to discover
const INDUSTRIES = [
  'computer software', 'internet', 'design', 'media production',
  'graphic design', 'animation', 'computer games', 'online media',
  'broadcast media', 'motion pictures and film', 'photography', 'music',
  'performing arts', 'entertainment', 'events services',
  'management consulting', 'staffing & recruiting', 'human resources',
  'outsourcing/offshoring', 'market research', 'translation and localization',
  'writing and editing', 'professional training & coaching', 'e-learning',
  'education management', 'public relations and communications',
  'telecommunications', 'information services', 'program development',
  'computer & network security', 'accounting', 'financial services',
  'legal services', 'architecture & planning', 'publishing', 'printing',
];

async function main() {
  if (!fs.existsSync(OUT_DIR)) fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    headless: 'new',
    executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36');

  // Login
  console.log('Logging in...');
  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await sleep(2000);
  await page.type('input[name="email"]', 'danila@getsally.io', { delay: 30 });
  await sleep(500);
  await page.type('input[name="password"]', 'UQdzDShCjAi5Nil!!', { delay: 30 });
  await page.click('button[type="submit"]');
  await sleep(8000);
  console.log('Logged in');

  // Load existing IDs
  let ids = {};
  try { ids = JSON.parse(fs.readFileSync(IDS_FILE, 'utf8')); } catch {}
  console.log(`Loaded ${Object.keys(ids).length} existing IDs`);

  // For each industry: navigate to Companies, click quick filters, or use Industry filter
  for (const industry of INDUSTRIES) {
    // Skip if already discovered
    if (Object.keys(ids).some(k => k.toLowerCase().includes(industry.split(' ')[0].toLowerCase()))) {
      console.log(`SKIP: "${industry}" (already found)`);
      continue;
    }

    console.log(`\nSearching: "${industry}"`);

    // Navigate fresh
    await page.goto('https://app.apollo.io/#/companies', { waitUntil: 'networkidle2', timeout: 30000 });
    await sleep(4000);

    // Strategy 1: Click Industry & Keywords section to expand
    await page.evaluate(() => {
      const all = document.querySelectorAll('div, span, button');
      for (const el of all) {
        if (el.textContent?.trim() === 'Industry & Keywords') {
          el.click();
          return;
        }
      }
    });
    await sleep(2000);

    // Strategy 2: Find the industry filter input/select inside the expanded section
    // Look for the specific input or select for industries
    // Apollo uses a typeahead/autocomplete — need to find and type in it

    // First, look for any "Select" or "Search" text that appeared after expanding
    const hasTypeahead = await page.evaluate((ind) => {
      // Look for elements that look like a typeahead input or its trigger
      const all = document.querySelectorAll('div, span, input');
      for (const el of all) {
        const text = el.textContent?.trim() || '';
        const placeholder = el.getAttribute('placeholder') || '';
        // Look for industry-related inputs
        if ((placeholder.toLowerCase().includes('search') || placeholder.toLowerCase().includes('type') ||
             placeholder.toLowerCase().includes('industry') || placeholder.toLowerCase().includes('select')) &&
            el.tagName === 'INPUT' && el.offsetParent !== null) {
          // Check if this input is inside or near the Industry section
          const rect = el.getBoundingClientRect();
          if (rect.y > 400 && rect.y < 800 && rect.x < 500) { // Sidebar area
            el.focus();
            el.click();
            return { found: true, placeholder, y: rect.y };
          }
        }
      }

      // Try to find a React Select component
      const selectControls = document.querySelectorAll('[class*="control"], [class*="Control"]');
      for (const sc of selectControls) {
        const rect = sc.getBoundingClientRect();
        if (rect.y > 400 && rect.y < 800 && rect.x < 500 && sc.offsetParent !== null) {
          sc.click();
          return { found: true, type: 'select-control', y: rect.y };
        }
      }

      return { found: false };
    }, industry);

    console.log('  Typeahead:', JSON.stringify(hasTypeahead));

    if (hasTypeahead.found) {
      // Type the industry name
      await page.keyboard.type(industry.substring(0, 15), { delay: 50 });
      await sleep(3000);

      // Look for dropdown options
      const selected = await page.evaluate((ind) => {
        const options = document.querySelectorAll('[class*="option"], [class*="Option"], [role="option"], [class*="menuList"] div, [class*="menu-list"] div');
        for (const opt of options) {
          if (opt.offsetParent !== null && opt.textContent?.trim().length > 3) {
            const text = opt.textContent.trim();
            if (text.toLowerCase().includes(ind.split(' ')[0].toLowerCase())) {
              opt.click();
              return text;
            }
          }
        }
        // Click first visible option as fallback
        for (const opt of options) {
          if (opt.offsetParent !== null && opt.textContent?.trim().length > 3) {
            const text = opt.textContent.trim();
            opt.click();
            return text;
          }
        }
        return null;
      }, industry);

      if (selected) {
        console.log(`  Selected: "${selected}"`);
        await sleep(3000);

        // Read URL for tag IDs
        const url = page.url();
        const matches = url.match(/organizationIndustryTagIds\[\]=([a-f0-9]+)/g);
        if (matches) {
          for (const m of matches) {
            const id = m.split('=')[1];
            ids[selected.toLowerCase()] = id;
            console.log(`  ✓ ${selected} → ${id}`);
          }
        } else {
          console.log(`  URL has no tag IDs: ${url.substring(url.indexOf('#'), url.indexOf('#') + 100)}`);
        }
      } else {
        console.log('  No options found');
      }
    }

    // Save after each discovery
    fs.writeFileSync(IDS_FILE, JSON.stringify(ids, null, 2));
    await sleep(1000);
  }

  console.log('\n=== FINAL RESULTS ===');
  console.log(`Total discovered: ${Object.keys(ids).length}`);
  for (const [name, id] of Object.entries(ids)) {
    console.log(`  ${name} → ${id}`);
  }

  await browser.close();
}

main().catch(console.error);
