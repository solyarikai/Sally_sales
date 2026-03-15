/**
 * SmartLead Campaign Leads Export (READONLY)
 *
 * Logs into SmartLead UI via Puppeteer, navigates to each campaign's analytics page,
 * and extracts total leads count. No modifications are made.
 *
 * Usage: node scripts/smartlead_export.js
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

// ============================================================
// Config
// ============================================================

const SMARTLEAD_EMAIL = 'services@getsally.io';
const SMARTLEAD_PASSWORD = 'SallySarrh7231';

// EasyStaff RU campaign IDs
const CAMPAIGN_IDS = [
  2979187,
  2871770,
  2662913,
  2414515,
  2414910,
  2478789,
  2144678,
];

const OUT_DIR = path.join(__dirname, 'smartlead_exports');

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function screenshot(page, name) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  const filePath = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: filePath, fullPage: false });
  console.log(`  [screenshot] ${name}.png`);
}

// ============================================================
// Login
// ============================================================

async function login(page) {
  // SmartLead is a SPA — try multiple login URLs
  const loginUrls = [
    'https://app.smartlead.ai/app/signin',
    'https://app.smartlead.ai/app/login',
    'https://app.smartlead.ai/app/sign-in',
    'https://app.smartlead.ai/',
  ];

  let foundInputs = false;

  for (const url of loginUrls) {
    console.log(`\n[LOGIN] Trying ${url}...`);
    try {
      await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    } catch {
      console.log('  Navigation timeout, continuing...');
    }

    // Wait for SPA to render
    await sleep(5000);

    // Dump current URL and page state
    const currentUrl = page.url();
    console.log(`  Current URL: ${currentUrl}`);

    // Check if already logged in
    if (currentUrl.includes('/email-campaigns') || currentUrl.includes('/dashboard') || currentUrl.includes('/home')) {
      console.log('  Already logged in!');
      await screenshot(page, '01_already_logged_in');
      return true;
    }

    // Check for inputs (SPA may have rendered them)
    const inputInfo = await page.evaluate(() => {
      return [...document.querySelectorAll('input')].map(i => ({
        type: i.type, name: i.name, placeholder: i.placeholder, id: i.id,
        visible: i.offsetParent !== null,
        ariaLabel: i.getAttribute('aria-label'),
        className: (i.className || '').substring(0, 100),
      }));
    });
    console.log(`  Found ${inputInfo.length} inputs:`, JSON.stringify(inputInfo));

    // Check page text
    const pageText = await page.evaluate(() => document.body?.innerText?.substring(0, 500) || '');
    console.log(`  Page text: ${pageText.substring(0, 200)}`);

    await screenshot(page, `01_login_attempt_${loginUrls.indexOf(url)}`);

    if (inputInfo.length >= 2) {
      foundInputs = true;
      break;
    }

    // Also try waiting longer for SPA to load
    if (inputInfo.length === 0) {
      console.log('  No inputs yet, waiting 5 more seconds for SPA...');
      await sleep(5000);

      const inputInfo2 = await page.evaluate(() => {
        return [...document.querySelectorAll('input')].map(i => ({
          type: i.type, name: i.name, placeholder: i.placeholder, id: i.id,
          visible: i.offsetParent !== null,
        }));
      });
      console.log(`  After wait: ${inputInfo2.length} inputs:`, JSON.stringify(inputInfo2));
      if (inputInfo2.length >= 2) {
        foundInputs = true;
        break;
      }
    }
  }

  if (!foundInputs) {
    // Last resort: try to find ANY form elements including shadow DOM
    console.log('\n  Trying to find form elements in all frames/shadow DOM...');
    const frames = page.frames();
    console.log(`  Frames: ${frames.length}`);
    for (const frame of frames) {
      const frameInputs = await frame.evaluate(() => {
        return [...document.querySelectorAll('input')].map(i => ({
          type: i.type, name: i.name, placeholder: i.placeholder,
        }));
      }).catch(() => []);
      if (frameInputs.length > 0) {
        console.log(`  Frame ${frame.url().substring(0, 100)}: ${JSON.stringify(frameInputs)}`);
      }
    }

    console.error('\n  FATAL: Could not find login form on any URL');
    return false;
  }

  // Fill email
  console.log('  Filling email...');
  let emailInput = await page.$('input[type="email"]');
  if (!emailInput) emailInput = await page.$('input[name="email"]');
  if (!emailInput) emailInput = await page.$('input[placeholder*="email" i]');
  if (!emailInput) {
    // Get all visible text/email inputs
    const allInputs = await page.$$('input');
    for (const inp of allInputs) {
      const t = await inp.evaluate(el => el.type);
      if (t === 'text' || t === 'email' || t === '') {
        emailInput = inp;
        break;
      }
    }
  }

  if (!emailInput) {
    console.error('  Could not find email input!');
    return false;
  }

  await emailInput.click({ clickCount: 3 });
  await sleep(200);
  await emailInput.type(SMARTLEAD_EMAIL, { delay: 50 });
  await sleep(500);

  // Fill password
  console.log('  Filling password...');
  const passwordInput = await page.$('input[type="password"]');
  if (!passwordInput) {
    console.error('  Could not find password input!');
    return false;
  }
  await passwordInput.click({ clickCount: 3 });
  await sleep(200);
  await passwordInput.type(SMARTLEAD_PASSWORD, { delay: 50 });
  await sleep(500);

  await screenshot(page, '02_credentials_filled');

  // Click login button
  console.log('  Clicking sign in button...');
  const loginBtn = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('button, input[type="submit"], a[role="button"]')];
    const btn = buttons.find(b => {
      const text = (b.textContent?.trim() || b.value || '').toLowerCase();
      return (text.includes('sign in') || text.includes('login') || text.includes('log in') || text === 'submit')
        && b.offsetParent !== null;
    });
    if (btn) {
      const rect = btn.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: btn.textContent?.trim() };
    }
    return null;
  });

  if (loginBtn) {
    console.log(`  Found button: "${loginBtn.text}"`);
    await page.mouse.click(loginBtn.x, loginBtn.y);
  } else {
    console.log('  No button found, pressing Enter...');
    await page.keyboard.press('Enter');
  }

  // Wait for login to complete
  console.log('  Waiting for login...');
  try {
    await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 30000 });
  } catch {
    await sleep(5000);
  }

  await sleep(5000);
  await screenshot(page, '03_after_login');

  const afterUrl = page.url();
  console.log(`  URL after login: ${afterUrl}`);

  // Check for error messages
  const errorText = await page.evaluate(() => {
    const alerts = document.querySelectorAll('[role="alert"], .error, .alert, [class*="error"], [class*="Error"]');
    return [...alerts].map(a => a.textContent?.trim()).filter(Boolean).join('; ');
  });
  if (errorText) {
    console.log(`  Page alerts: ${errorText}`);
  }

  // Check if we got past login
  const pageText = await page.evaluate(() => document.body?.innerText?.substring(0, 500) || '');
  console.log(`  Page text after login: ${pageText.substring(0, 200)}`);

  if (afterUrl.includes('/email-campaigns') || afterUrl.includes('/dashboard') || afterUrl.includes('/home') || afterUrl.includes('/app/')) {
    console.log('  Login successful!');
    return true;
  }

  console.error('  Login may have failed');
  return true; // Continue anyway, let campaign pages determine if logged in
}

// ============================================================
// Extract campaign data from analytics page
// ============================================================

async function extractCampaignData(page, campaignId) {
  const analyticsUrl = `https://app.smartlead.ai/app/email-campaigns-v2/${campaignId}/analytics`;
  console.log(`\n  Navigating to campaign ${campaignId}...`);
  console.log(`  URL: ${analyticsUrl}`);

  try {
    await page.goto(analyticsUrl, {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
  } catch (err) {
    console.log(`  Navigation timeout, continuing anyway...`);
  }

  await sleep(4000);

  // Extract campaign name from page
  const campaignName = await page.evaluate(() => {
    // Try common selectors for campaign name/title
    // SmartLead typically shows campaign name in a heading or breadcrumb
    const candidates = [
      ...document.querySelectorAll('h1, h2, h3, [class*="campaign-name"], [class*="campaignName"]'),
    ];
    for (const el of candidates) {
      const text = el.textContent?.trim();
      if (text && text.length > 3 && text.length < 200 && !text.includes('Analytics') && !text.includes('Campaign')) {
        return text;
      }
    }
    // Try breadcrumb
    const breadcrumbs = document.querySelectorAll('[class*="breadcrumb"] a, [class*="breadcrumb"] span, nav a');
    for (const el of breadcrumbs) {
      const text = el.textContent?.trim();
      if (text && text.length > 5 && !text.includes('Campaigns') && !text.includes('Home')) {
        return text;
      }
    }
    return null;
  });

  // Take screenshot for debugging
  await screenshot(page, `campaign_${campaignId}`);

  // Try to extract stats from the analytics page
  // SmartLead analytics pages typically show: Total Leads, Sent, Opened, Replied, etc.
  const stats = await page.evaluate(() => {
    const result = {};
    const body = document.body.innerText;

    // Method 1: Look for stat cards/boxes with numbers
    const statElements = document.querySelectorAll('[class*="stat"], [class*="metric"], [class*="card"], [class*="kpi"]');
    for (const el of statElements) {
      const text = el.textContent?.trim();
      if (!text) continue;

      // Parse "Total Leads\n1234" or "Sent\n567" style
      const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
      for (let i = 0; i < lines.length - 1; i++) {
        const label = lines[i].toLowerCase();
        const value = lines[i + 1].replace(/,/g, '');
        if (/^\d+$/.test(value) && (
          label.includes('total') || label.includes('leads') || label.includes('sent') ||
          label.includes('opened') || label.includes('replied') || label.includes('bounced') ||
          label.includes('clicked') || label.includes('unsubscribed')
        )) {
          result[label] = parseInt(value);
        }
      }
    }

    // Method 2: Scan all text for patterns like "Total Leads: 1234" or similar
    const textContent = document.body.innerText;
    const patterns = [
      /total\s*leads?\s*[:\s]*(\d[\d,]*)/i,
      /leads?\s*uploaded?\s*[:\s]*(\d[\d,]*)/i,
      /total\s*[:\s]*(\d[\d,]*)/i,
      /sent\s*[:\s]*(\d[\d,]*)/i,
      /contacted\s*[:\s]*(\d[\d,]*)/i,
    ];
    for (const pat of patterns) {
      const m = textContent.match(pat);
      if (m) {
        const key = pat.source.split('\\s')[0].replace(/\\/g, '');
        result[`_regex_${key}`] = parseInt(m[1].replace(/,/g, ''));
      }
    }

    // Method 3: Get ALL visible numbers with their context
    const allNumbers = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const text = node.textContent?.trim();
      if (!text) continue;
      // Look for standalone numbers
      if (/^\d[\d,]*$/.test(text) && parseInt(text.replace(/,/g, '')) > 0) {
        const parent = node.parentElement;
        if (parent?.offsetParent !== null) {
          // Get the context — previous sibling text, parent text, etc.
          const prevText = parent.previousElementSibling?.textContent?.trim() || '';
          const parentTag = parent.tagName;
          const parentClass = parent.className?.substring?.(0, 100) || '';
          allNumbers.push({
            value: parseInt(text.replace(/,/g, '')),
            context: prevText.substring(0, 50),
            parentTag,
            parentClass: parentClass.substring(0, 100),
          });
        }
      }
    }
    result._numbers = allNumbers.slice(0, 30);

    // Method 4: Get page text excerpt for manual parsing
    result._pageText = textContent.substring(0, 3000);

    return result;
  });

  // Also try to intercept API responses that contain campaign data
  // SmartLead fetches campaign analytics via API calls
  const apiData = await page.evaluate(async (cid) => {
    // Try fetching campaign overview data directly from SmartLead's internal API
    const urls = [
      `/api/v1/campaigns/${cid}/analytics`,
      `/api/campaigns/${cid}/analytics`,
      `/api/v1/campaigns/${cid}`,
    ];
    for (const url of urls) {
      try {
        const res = await fetch(url, { credentials: 'include' });
        if (res.ok) {
          return { url, data: await res.json() };
        }
      } catch {}
    }
    return null;
  }, campaignId);

  return {
    campaign_id: campaignId,
    campaign_name: campaignName,
    stats,
    apiData,
  };
}

// ============================================================
// Alternative: intercept network requests for analytics data
// ============================================================

async function extractViaNetworkIntercept(page, campaignId) {
  const analyticsUrl = `https://app.smartlead.ai/app/email-campaigns-v2/${campaignId}/analytics`;

  // Collect API responses
  const apiResponses = [];

  const responseHandler = async (response) => {
    const url = response.url();
    if (url.includes('/campaign') || url.includes('/analytic') || url.includes('/leads') || url.includes('/stats')) {
      try {
        const contentType = response.headers()['content-type'] || '';
        if (contentType.includes('json')) {
          const body = await response.json().catch(() => null);
          if (body) {
            apiResponses.push({
              url: url.substring(0, 200),
              status: response.status(),
              data: JSON.stringify(body).substring(0, 2000),
            });
          }
        }
      } catch {}
    }
  };

  page.on('response', responseHandler);

  try {
    await page.goto(analyticsUrl, { waitUntil: 'networkidle2', timeout: 30000 });
  } catch {
    // timeout is ok
  }
  await sleep(5000);

  page.off('response', responseHandler);

  return apiResponses;
}

// ============================================================
// Main
// ============================================================

async function main() {
  console.log('=== SmartLead Campaign Export (READONLY) ===');
  console.log(`Campaigns to check: ${CAMPAIGN_IDS.join(', ')}`);
  console.log(`Output: ${OUT_DIR}/\n`);

  fs.mkdirSync(OUT_DIR, { recursive: true });

  const browser = await puppeteer.launch({
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--window-size=1920,1080',
      '--disable-blink-features=AutomationControlled',
      '--disable-dev-shm-usage',
      '--disable-gpu',
    ],
    defaultViewport: { width: 1920, height: 1080 },
  });

  const results = [];

  try {
    const page = await browser.newPage();
    await page.setUserAgent(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    );

    // Login
    const loggedIn = await login(page);
    if (!loggedIn) {
      console.error('\nFATAL: Could not log in to SmartLead');
      await browser.close();
      process.exit(1);
    }

    // Navigate to campaigns list first
    console.log('\n[CAMPAIGNS] Navigating to campaigns list...');
    await page.goto('https://app.smartlead.ai/app/email-campaigns', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });
    await sleep(3000);
    await screenshot(page, '04_campaigns_list');

    // For each campaign, go to analytics and extract data
    for (const campaignId of CAMPAIGN_IDS) {
      console.log(`\n${'='.repeat(60)}`);
      console.log(`Processing campaign ${campaignId}...`);
      console.log(`${'='.repeat(60)}`);

      // Try network intercept approach first
      const networkData = await extractViaNetworkIntercept(page, campaignId);

      // Also extract from DOM
      const domData = await extractCampaignData(page, campaignId);

      const result = {
        ...domData,
        networkResponses: networkData,
      };
      results.push(result);

      // Be polite — don't hammer the server
      await sleep(2000);
    }

    // Summary
    console.log('\n\n' + '='.repeat(60));
    console.log('SUMMARY — SmartLead EasyStaff RU Campaign Leads');
    console.log('='.repeat(60));

    let totalLeads = 0;
    for (const r of results) {
      const name = r.campaign_name || 'Unknown';

      // Try to find total leads from various sources
      let leads = null;

      // Check stats
      if (r.stats) {
        for (const [key, val] of Object.entries(r.stats)) {
          if (typeof val === 'number' && (key.includes('total') || key.includes('lead'))) {
            leads = val;
            break;
          }
        }
      }

      // Check network responses for lead counts
      if (leads === null && r.networkResponses) {
        for (const resp of r.networkResponses) {
          try {
            const data = JSON.parse(resp.data);
            if (data.total_leads !== undefined) leads = data.total_leads;
            else if (data.leads_count !== undefined) leads = data.leads_count;
            else if (data.total !== undefined && typeof data.total === 'number') leads = data.total;
          } catch {}
        }
      }

      if (leads !== null) totalLeads += leads;
      console.log(`  Campaign ${r.campaign_id}: ${leads !== null ? leads : '???'} leads  (${name})`);
    }

    console.log(`\n  TOTAL: ${totalLeads > 0 ? totalLeads : 'Could not determine'}`);
    console.log(`  CRM count (30-day): 916`);
    if (totalLeads > 0) {
      console.log(`  Difference: ${totalLeads - 916}`);
    }

    // Save all results
    fs.writeFileSync(
      path.join(OUT_DIR, 'results.json'),
      JSON.stringify(results, null, 2)
    );
    console.log(`\nResults saved to ${OUT_DIR}/results.json`);

  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error('FATAL:', err.message);
  console.error(err.stack);
  process.exit(1);
});
