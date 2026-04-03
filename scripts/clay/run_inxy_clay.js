/**
 * Clay automation for Inxy gaming skin companies
 * - Puppeteer stealth anti-detection
 * - Real mouse clicks (not el.click()) for React compatibility
 * - Random human-like delays
 * - Exact Chrome UA from request.txt
 */
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
const fs = require('fs');
const path = require('path');

puppeteer.use(StealthPlugin());

const WORKSPACE_ID = '889252';
const OUT_DIR = path.join(__dirname, 'discovery');
const CSV_PATH = path.join(__dirname, 'inxy_gaming_companies.csv');
const DOMAINS_FILE = '/tmp/inxy_targets.txt';
const USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36';

function humanDelay(minMs = 800, maxMs = 2500) {
  const ms = minMs + Math.random() * (maxMs - minMs);
  return new Promise(r => setTimeout(r, ms));
}
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function screenshot(page, name) {
  fs.mkdirSync(OUT_DIR, { recursive: true });
  await page.screenshot({ path: path.join(OUT_DIR, `${name}.png`), fullPage: false });
  console.log(`  [img] ${name}.png`);
}

async function saveHtml(page, name) {
  fs.writeFileSync(path.join(OUT_DIR, `${name}.html`), await page.content());
  console.log(`  [html] ${name}.html`);
}

function generateCSV() {
  const domains = fs.readFileSync(DOMAINS_FILE, 'utf-8')
    .split('\n').map(d => d.trim()).filter(Boolean);
  fs.writeFileSync(CSV_PATH, ['Website', ...domains].join('\n'));
  console.log(`CSV: ${domains.length} companies`);
  return domains.length;
}

// Find element by text and return its bounding box for real mouse click
async function findByText(page, text, exactMatch = true) {
  return page.evaluate((text, exactMatch) => {
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    while (walk.nextNode()) {
      const node = walk.currentNode;
      const match = exactMatch
        ? node.textContent.trim() === text
        : node.textContent.trim().includes(text);
      if (match) {
        const el = node.parentElement;
        if (el && el.offsetParent !== null) {
          const rect = el.getBoundingClientRect();
          return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, text: el.textContent.trim().substring(0, 60) };
        }
      }
    }
    return null;
  }, text, exactMatch);
}

// Real mouse click on element found by text
async function realClickText(page, text, exactMatch = true) {
  const pos = await findByText(page, text, exactMatch);
  if (pos) {
    await page.mouse.click(pos.x, pos.y);
    return pos.text;
  }
  return null;
}

// Find button by text and return position
async function findButton(page, text) {
  return page.evaluate((text) => {
    const buttons = [...document.querySelectorAll('button')];
    const btn = buttons.find(b => {
      const t = b.textContent?.trim();
      return t === text || t?.toLowerCase() === text.toLowerCase();
    });
    if (btn) {
      const rect = btn.getBoundingClientRect();
      return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, disabled: btn.disabled, text: btn.textContent.trim() };
    }
    return null;
  }, text);
}

// Real mouse click on a button
async function realClickButton(page, text) {
  const btn = await findButton(page, text);
  if (btn && !btn.disabled) {
    await page.mouse.click(btn.x, btn.y);
    return `clicked: ${btn.text}`;
  }
  return btn ? `disabled: ${btn.text}` : null;
}

async function waitForText(page, text, timeout = 20000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const found = await page.evaluate(t => document.body?.textContent?.includes(t), text);
    if (found) return true;
    await sleep(400);
  }
  return false;
}

async function waitForButtonEnabled(page, text, timeout = 10000) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    const btn = await findButton(page, text);
    if (btn && !btn.disabled) return true;
    await sleep(300);
  }
  return false;
}

async function listButtons(page) {
  return page.evaluate(() => {
    return [...document.querySelectorAll('button')]
      .filter(b => b.offsetParent !== null)
      .map(b => ({ text: b.textContent?.trim().substring(0, 60), disabled: b.disabled }));
  });
}

async function main() {
  const count = generateCSV();

  console.log('\nLaunching stealth browser...');
  const browser = await puppeteer.launch({
    headless: false,
    args: [
      '--no-sandbox', '--disable-setuid-sandbox',
      '--window-size=1440,900',
      '--disable-blink-features=AutomationControlled',
    ],
    defaultViewport: { width: 1440, height: 900 },
  });

  const page = await browser.newPage();
  await page.setUserAgent(USER_AGENT);
  await page.evaluateOnNewDocument(() => {
    Object.defineProperty(navigator, 'webdriver', { get: () => false });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
  });

  await page.setCookie({
    name: 'claysession',
    value: 's%3AsydgrI74YLdGMrU8LWzQSmCv-IrJgDYg.FYCecoCtfmRICI19MVyPsTXRxlfUAfoeKSLns5ofeGw',
    domain: 'api.clay.com', path: '/', httpOnly: true, secure: true, sameSite: 'None',
  });

  const apiCalls = [];
  page.on('request', req => {
    if (req.url().includes('api.clay.com') && req.method() === 'POST') {
      apiCalls.push({ url: req.url(), data: req.postData()?.substring(0, 800) });
    }
  });

  // ====== STEP 1: Workspace home ======
  console.log('\n[1] Navigate to workspace...');
  await page.goto(`https://app.clay.com/workspaces/${WORKSPACE_ID}/home`, { waitUntil: 'networkidle2', timeout: 30000 });
  await humanDelay(2000, 3500);

  // ====== STEP 2: Import data → Import CSV ======
  console.log('\n[2] Import data → Import CSV...');
  let r = await realClickText(page, 'Import data', false);
  console.log(`  Import data: ${r || 'FAIL'}`);
  await humanDelay(1000, 1800);

  r = await realClickText(page, 'Import CSV');
  console.log(`  Import CSV: ${r || 'FAIL'}`);
  await humanDelay(1500, 2500);
  await screenshot(page, 'r_02_csv_dialog');

  // ====== STEP 3: Upload CSV ======
  console.log('\n[3] Upload CSV...');
  const fileInput = await page.$('input[type="file"]');
  if (!fileInput) { console.error('  No file input!'); return; }
  await humanDelay(400, 800);
  await fileInput.uploadFile(CSV_PATH);
  console.log(`  Uploaded ${count} companies`);

  await waitForText(page, '100% completed', 30000);
  console.log('  Upload finalized');
  await humanDelay(1000, 2000);
  await screenshot(page, 'r_03_uploaded');

  // ====== STEP 4: Continue (after upload) ======
  console.log('\n[4] Continue (post-upload)...');
  await humanDelay(600, 1200);
  r = await realClickButton(page, 'Continue');
  console.log(`  ${r || 'FAIL'}`);
  await humanDelay(2000, 3500);
  await screenshot(page, 'r_04_step2');

  // ====== STEP 5: Delimiter screen ======
  console.log('\n[5] Delimiter screen...');
  if (await page.evaluate(() => document.body?.textContent?.includes('Delimiter'))) {
    console.log('  Found delimiter screen');
    await humanDelay(800, 1500);
    r = await realClickButton(page, 'Continue');
    console.log(`  ${r || 'FAIL'}`);
    await humanDelay(2000, 3500);
  }
  await screenshot(page, 'r_05_destination');

  // ====== STEP 6: New blank table selection ======
  console.log('\n[6] New blank table...');
  if (await page.evaluate(() => document.body?.textContent?.includes('New blank table'))) {
    // Save HTML for analysis
    await saveHtml(page, 'r_06_destination');

    // Find the "New blank table" card and click it with real mouse
    console.log('  Clicking "New blank table" card...');

    // Get the card's bounding box - it's a div containing the text "New blank table"
    const cardPos = await page.evaluate(() => {
      // Find the container div that has "New blank table" text
      const allDivs = [...document.querySelectorAll('div')];
      // Find the card - it should be a clickable container with both icon and text
      for (const div of allDivs) {
        if (div.textContent?.trim() === 'New blank table' && div.children.length >= 1) {
          // This is likely the text span, go up to the card container
          let card = div.parentElement;
          // Go up until we find a reasonable card-size element
          while (card && card.getBoundingClientRect().width < 100) {
            card = card.parentElement;
          }
          if (card) {
            const rect = card.getBoundingClientRect();
            return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, w: rect.width, h: rect.height };
          }
        }
      }
      return null;
    });

    if (cardPos) {
      console.log(`  Card found at (${cardPos.x.toFixed(0)}, ${cardPos.y.toFixed(0)}) ${cardPos.w.toFixed(0)}x${cardPos.h.toFixed(0)}`);
      // Real mouse click on the card center
      await page.mouse.click(cardPos.x, cardPos.y);
      await humanDelay(500, 1000);
    } else {
      console.log('  Card not found via parent, trying direct text click...');
      await realClickText(page, 'New blank table');
      await humanDelay(500, 1000);
    }

    // Check if Continue is now enabled
    const continueBtn = await findButton(page, 'Continue');
    console.log(`  Continue button disabled: ${continueBtn?.disabled}`);

    if (continueBtn?.disabled) {
      console.log('  Continue still disabled! Trying alternative approaches...');

      // Try clicking the card icon area too
      if (cardPos) {
        // Click multiple positions on the card
        for (const offset of [
          { dx: 0, dy: -20 },   // near icon
          { dx: -30, dy: 0 },   // left side
          { dx: 30, dy: 0 },    // right side
          { dx: 0, dy: 20 },    // bottom
        ]) {
          await page.mouse.click(cardPos.x + offset.dx, cardPos.y + offset.dy);
          await sleep(500);
          const btn = await findButton(page, 'Continue');
          if (!btn?.disabled) {
            console.log(`  Continue enabled after clicking offset (${offset.dx}, ${offset.dy})`);
            break;
          }
        }
      }

      // If still disabled, try keyboard tab + enter
      const stillDisabled = await findButton(page, 'Continue');
      if (stillDisabled?.disabled) {
        console.log('  Trying keyboard selection...');
        await page.keyboard.press('Tab');
        await sleep(300);
        await page.keyboard.press('Enter');
        await sleep(500);

        const btn2 = await findButton(page, 'Continue');
        console.log(`  After keyboard: disabled=${btn2?.disabled}`);
      }
    }

    await screenshot(page, 'r_06_after_card_click');

    // The button might be "Continue" or "Complete import"
    await humanDelay(800, 1500);
    for (const label of ['Complete import', 'Continue']) {
      const enabled = await waitForButtonEnabled(page, label, 3000);
      if (enabled) {
        console.log(`  "${label}" is enabled!`);
        await humanDelay(500, 1000);
        r = await realClickButton(page, label);
        console.log(`  ${r || 'FAIL'}`);
        break;
      }
    }
    await humanDelay(5000, 8000);
  }
  await screenshot(page, 'r_06_result');

  // ====== STEP 7: Column mapping / final ======
  console.log('\n[7] Final step...');
  const btns = await listButtons(page);
  console.log(`  Buttons: ${btns.filter(b => !b.disabled).map(b => b.text.substring(0, 30)).join(' | ')}`);

  for (const label of ['Complete import', 'Import', 'Create table', 'Done', 'Finish', 'Continue']) {
    r = await realClickButton(page, label);
    if (r && !r.startsWith('disabled')) {
      console.log(`  ${r}`);
      break;
    }
  }
  await humanDelay(5000, 8000);
  await screenshot(page, 'r_07_final');

  const finalUrl = page.url();
  console.log(`  URL: ${finalUrl}`);

  const tableMatch = finalUrl.match(/tables\/([^/?]+)/);
  if (tableMatch) {
    console.log(`\n  TABLE CREATED: ${tableMatch[1]}`);
  }

  fs.writeFileSync(path.join(OUT_DIR, 'run_api_calls.json'), JSON.stringify(apiCalls, null, 2));
  console.log(`\n  ${apiCalls.length} API calls saved`);

  console.log('\n=== Browser open. Press Ctrl+C to close. ===');
  await sleep(600000);
  await browser.close();
}

main().catch(err => {
  console.error('Error:', err.message);
  process.exit(1);
});
