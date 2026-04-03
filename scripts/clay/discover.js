const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const CLAY_COOKIE = 'claysession=s%3AsydgrI74YLdGMrU8LWzQSmCv-IrJgDYg.FYCecoCtfmRICI19MVyPsTXRxlfUAfoeKSLns5ofeGw';
const WORKSPACE_ID = '889252';
const OUT_DIR = path.join(__dirname, 'discovery');

async function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

async function screenshot(page, name) {
  const fp = path.join(OUT_DIR, `${name}.png`);
  await page.screenshot({ path: fp, fullPage: false });
  console.log(`  screenshot: ${name}.png`);
}

async function saveHtml(page, name) {
  const html = await page.content();
  const fp = path.join(OUT_DIR, `${name}.html`);
  fs.writeFileSync(fp, html);
  console.log(`  html: ${name}.html`);
}

async function interceptApiCalls(page) {
  const calls = [];
  page.on('request', req => {
    if (req.url().includes('api.clay.com')) {
      calls.push({
        method: req.method(),
        url: req.url(),
        postData: req.postData()?.substring(0, 500),
      });
    }
  });
  return calls;
}

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true });

  console.log('Launching browser...');
  const browser = await puppeteer.launch({
    headless: false,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--window-size=1440,900',
    ],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();

  // Set cookies
  await page.setCookie({
    name: 'claysession',
    value: 's%3AsydgrI74YLdGMrU8LWzQSmCv-IrJgDYg.FYCecoCtfmRICI19MVyPsTXRxlfUAfoeKSLns5ofeGw',
    domain: 'api.clay.com',
    path: '/',
    httpOnly: true,
    secure: true,
    sameSite: 'None',
  });

  // Intercept all API calls to discover endpoints
  const apiCalls = await interceptApiCalls(page);

  // Step 1: Navigate to workspace home
  console.log('\n1. Loading workspace home...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, {
    waitUntil: 'networkidle2',
    timeout: 30000,
  });
  await sleep(3000);
  await screenshot(page, '01_workspace_home');
  await saveHtml(page, '01_workspace_home');

  // Step 2: Click "New Table" or "Create" button
  console.log('\n2. Looking for create table button...');
  await screenshot(page, '02_before_create');

  // Try to find and click "New" or "Create" button
  const createBtn = await page.evaluate(() => {
    const buttons = [...document.querySelectorAll('button, a, div[role="button"]')];
    const found = buttons.find(b => {
      const text = b.textContent?.toLowerCase() || '';
      return text.includes('new') || text.includes('create');
    });
    if (found) {
      found.click();
      return found.textContent?.trim();
    }
    return null;
  });
  console.log(`  Clicked: ${createBtn || 'NOT FOUND'}`);
  await sleep(2000);
  await screenshot(page, '03_after_create_click');
  await saveHtml(page, '03_after_create_click');

  // Step 3: Look for "Import from CSV" or "Spreadsheet" option
  console.log('\n3. Looking for import/spreadsheet option...');
  const importBtn = await page.evaluate(() => {
    const elements = [...document.querySelectorAll('button, a, div[role="button"], div[role="menuitem"], li, span')];
    const found = elements.find(el => {
      const text = el.textContent?.toLowerCase() || '';
      return text.includes('import') || text.includes('csv') || text.includes('spreadsheet') || text.includes('company');
    });
    if (found) {
      found.click();
      return found.textContent?.trim().substring(0, 80);
    }
    return null;
  });
  console.log(`  Clicked: ${importBtn || 'NOT FOUND'}`);
  await sleep(2000);
  await screenshot(page, '04_after_import_click');
  await saveHtml(page, '04_after_import_click');

  // Step 4: Navigate to existing INXY table to understand the UI
  console.log('\n4. Opening existing INXY table...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/tables/t_0tbheobyJd7BQgJxWNT`, {
    waitUntil: 'networkidle2',
    timeout: 30000,
  });
  await sleep(3000);
  await screenshot(page, '05_inxy_table');
  await saveHtml(page, '05_inxy_table');

  // Step 5: Try to find "Add row" or "Import" in the table view
  console.log('\n5. Looking for add row / import options in table...');
  const addRowBtn = await page.evaluate(() => {
    const elements = [...document.querySelectorAll('button, a, div[role="button"], span')];
    const results = elements
      .filter(el => {
        const text = el.textContent?.toLowerCase() || '';
        return text.includes('add') || text.includes('import') || text.includes('upload');
      })
      .map(el => ({
        tag: el.tagName,
        text: el.textContent?.trim().substring(0, 60),
        classes: el.className?.substring?.(0, 80),
      }));
    return results.slice(0, 10);
  });
  console.log('  Add/Import elements found:', JSON.stringify(addRowBtn, null, 2));

  // Step 6: Try to find "Find People" or enrichment actions
  console.log('\n6. Looking for enrichment/action buttons...');
  const enrichBtns = await page.evaluate(() => {
    const elements = [...document.querySelectorAll('button, a, div[role="button"], span')];
    return elements
      .filter(el => {
        const text = el.textContent?.toLowerCase() || '';
        return text.includes('enrich') || text.includes('find people') || text.includes('action') || text.includes('column');
      })
      .map(el => ({
        tag: el.tagName,
        text: el.textContent?.trim().substring(0, 60),
      }))
      .slice(0, 10);
  });
  console.log('  Enrichment elements:', JSON.stringify(enrichBtns, null, 2));

  // Step 7: Check the "Find People" linked table
  console.log('\n7. Opening Find People table linked to INXY...');
  // The people table linked from INXY spreadsheet
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/tables/t_0tbhfg9U7AzTVe7QhRs`, {
    waitUntil: 'networkidle2',
    timeout: 30000,
  });
  await sleep(3000);
  await screenshot(page, '06_find_people_table');
  await saveHtml(page, '06_find_people_table');

  // Step 8: Navigate to a company table to see the "Find Companies" flow
  console.log('\n8. Opening a company-type table for reference...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/tables/t_0tbhcaasK4dxeffMEKR`, {
    waitUntil: 'networkidle2',
    timeout: 30000,
  });
  await sleep(3000);
  await screenshot(page, '07_company_table');
  await saveHtml(page, '07_company_table');

  // Save all intercepted API calls
  console.log('\n9. Saving intercepted API calls...');
  const callsPath = path.join(OUT_DIR, 'api_calls.json');
  fs.writeFileSync(callsPath, JSON.stringify(apiCalls, null, 2));
  console.log(`  Saved ${apiCalls.length} API calls`);

  // Save top calls summary
  const uniqueEndpoints = [...new Set(apiCalls.map(c => `${c.method} ${c.url.replace(/\?.*/, '')}`))];
  console.log('\n  Unique API endpoints discovered:');
  uniqueEndpoints.forEach(e => console.log(`    ${e}`));

  console.log('\n\nDiscovery complete! Check scripts/clay/discovery/ for screenshots and HTML.');
  console.log('Press Ctrl+C to close the browser, or interact manually.');

  // Keep browser open for manual exploration
  await sleep(300000);
  await browser.close();
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
