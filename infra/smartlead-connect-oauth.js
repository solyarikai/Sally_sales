// Connects Google Workspace mailboxes to Smartlead via Google OAuth (Smartlead Infrastructure)
// Usage: node smartlead-connect-oauth.js --domains-file crona-domains.txt [--codes-file crona-domains-backup-codes.csv]

const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

// ── Config ────────────────────────────────────────────────────────────────────

const SMARTLEAD_EMAIL    = 'services@getsally.io';
const SMARTLEAD_PASSWORD = 'SallySarrh7231';
const GOOGLE_PASSWORD    = 'SallySuper777';
const CHROME             = require('puppeteer').executablePath();
const SESSION_FILE       = path.join(__dirname, 'sl-session-dir.txt');
const API_KEY            = 'eaa086b6-b7c0-4b2f-a6e9-b183c81122d5_638f7e5';

const args = process.argv.slice(2);
const getArg = n => { const i = args.indexOf('--' + n); return i !== -1 ? args[i + 1] : null; };

const domainsFile = getArg('domains-file');
if (!domainsFile) {
  console.error('Usage: node smartlead-connect-oauth.js --domains-file domains.txt');
  process.exit(1);
}

const codesFile = getArg('codes-file') || domainsFile.replace(/\.txt$/, '') + '-backup-codes.csv';
const domains   = fs.readFileSync(domainsFile, 'utf8').split('\n').map(d => d.trim()).filter(Boolean);
const USERS     = ['petr', 'rinat'];

// ── Load backup codes ─────────────────────────────────────────────────────────

const backupCodes = {};
const usedCodes   = {};

if (fs.existsSync(codesFile)) {
  const lines = fs.readFileSync(codesFile, 'utf8').split('\n').filter(Boolean);
  for (const line of lines.slice(1)) {
    const parts = line.split(',');
    const email = parts[0].trim();
    const codes = parts.slice(1).map(c => c.trim()).filter(c => c && !c.startsWith('ERROR'));
    if (codes.length) backupCodes[email] = codes;
  }
  console.log(`Backup codes loaded for ${Object.keys(backupCodes).length} accounts`);
}

function getNextCode(email) {
  const codes = backupCodes[email] || [];
  const used  = usedCodes[email] || 0;
  if (used >= codes.length) return null;
  usedCodes[email] = used + 1;
  return codes[used];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const wait = ms => new Promise(r => setTimeout(r, ms));

function getOrCreateSessionDir() {
  let dir = '';
  try { dir = fs.readFileSync(SESSION_FILE, 'utf8').trim(); } catch (_) {}
  if (!dir || !fs.existsSync(dir)) {
    dir = path.join(require('os').tmpdir(), 'sl_session_' + Date.now());
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(SESSION_FILE, dir);
    console.log('New session dir created');
  } else {
    console.log('Reusing saved session');
  }
  return dir;
}

function ss(page, name) {
  return page.screenshot({ path: path.join(__dirname, name) }).catch(() => {});
}

// ── Launch browser ────────────────────────────────────────────────────────────

async function tryLaunch(userDataDir) {
  return puppeteer.launch({
    headless: false,
    executablePath: CHROME,
    userDataDir,
    pipe: true,
    protocolTimeout: 300000,
    args: ['--no-sandbox', '--no-first-run', '--start-maximized', '--disable-popup-blocking'],
    defaultViewport: null,
  });
}

async function launchBrowser() {
  let userDataDir = getOrCreateSessionDir();

  // Remove stale lock files
  for (const lock of ['SingletonLock', 'SingletonSocket', 'lockfile', 'DevToolsActivePort']) {
    try { fs.unlinkSync(path.join(userDataDir, lock)); } catch (_) {}
  }

  try {
    return await tryLaunch(userDataDir);
  } catch (e) {
    if (e.message && e.message.includes('already running')) {
      // Session dir is truly locked — nuke it and start fresh (OTP required once)
      console.log('Session locked, creating fresh session...');
      try { fs.rmSync(userDataDir, { recursive: true, force: true }); } catch (_) {}
      try { fs.unlinkSync(SESSION_FILE); } catch (_) {}
      userDataDir = getOrCreateSessionDir();
      return await tryLaunch(userDataDir);
    }
    throw e;
  }
}

// ── Login to Smartlead ────────────────────────────────────────────────────────

async function ensureLoggedIn(page) {
  await page.goto('https://app.smartlead.ai/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await wait(1000);

  if (!page.url().includes('/login')) {
    console.log('Session active — already logged in\n');
    return;
  }

  console.log('Logging in to Smartlead...');
  await page.waitForSelector('input[type="email"]', { timeout: 30000 });
  await page.click('input[type="email"]', { clickCount: 3 });
  await page.type('input[type="email"]', SMARTLEAD_EMAIL, { delay: 60 });
  await wait(300);
  await page.click('input[type="password"]', { clickCount: 3 });
  await page.type('input[type="password"]', SMARTLEAD_PASSWORD, { delay: 60 });
  await page.keyboard.press('Enter');
  await wait(2000);

  if (page.url().includes('/login')) {
    console.log('\n⚠ OTP required — check services@getsally.io and enter the code in the browser.');
    console.log('Waiting up to 10 minutes...\n');
    let loggedIn = false;
    for (let i = 0; i < 600 && !loggedIn; i++) {
      await wait(1000);
      try { loggedIn = !page.url().includes('/login'); } catch (_) {}
    }
    if (!loggedIn) throw new Error('OTP timeout — 10 minutes exceeded');
  }

  await wait(2000);
  console.log('✓ Logged in\n');
}

// ── Connect one email account ─────────────────────────────────────────────────

async function connectAccount(browser, page, email) {
  process.stdout.write(`${email} ... `);

  try {
    // Hard reload to clear any leftover modal state
    await page.goto('https://app.smartlead.ai/app/email-accounts', { waitUntil: 'networkidle2', timeout: 30000 });
    await wait(2000);

    // Step 1: Open "Add Account(s)" modal
    await page.waitForSelector('button', { timeout: 10000 });
    await page.evaluate(() => {
      for (const btn of document.querySelectorAll('button, [role="button"]')) {
        if (btn.textContent.includes('Add Account')) { btn.click(); return; }
      }
    });
    await wait(2500);

    // Step 2: Select "Smartlead's Infrastructure" radio
    await page.evaluate(() => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        if (node.textContent.includes("Smartlead's Infrastructure")) {
          let el = node.parentElement;
          for (let i = 0; i < 8; i++) {
            const r = el.querySelector('input[type="radio"]');
            if (r) { r.click(); return; }
            if (el.getAttribute('role') === 'radio' || el.tagName === 'LABEL') { el.click(); return; }
            el = el.parentElement;
            if (!el) break;
          }
          node.parentElement.click();
          return;
        }
      }
    });
    await wait(2000);

    // Step 3: Click "Google OAuth" provider card
    const providerClicked = await page.evaluate(() => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        if (node.textContent.trim() === 'Google OAuth') {
          let el = node.parentElement;
          for (let i = 0; i < 5; i++) {
            if (el.tagName === 'DIV' && el.children.length >= 1) { el.click(); return 'Google OAuth'; }
            el = el.parentElement;
            if (!el) break;
          }
          node.parentElement.click();
          return 'Google OAuth (text parent)';
        }
      }
      return null;
    });

    if (!providerClicked) {
      return { success: false, error: 'Google OAuth provider card not found' };
    }
    await wait(2000);

    // Step 4: Click "Connect Account" — listen for new target BEFORE clicking
    const newTargetPromise = new Promise((resolve, reject) => {
      const timer = setTimeout(
        () => reject(new Error('Google OAuth popup not found after 35s')),
        35000
      );
      const handler = async target => {
        process.stdout.write(`\n    [target] type=${target.type()} url=${target.url().substring(0, 60)}`);
        if (target.type() !== 'page') return;
        clearTimeout(timer);
        browser.off('targetcreated', handler);
        // target.page() can return null briefly with pipe:true — retry up to 5s
        let p = null;
        for (let i = 0; i < 17 && !p; i++) {
          await wait(300);
          p = await target.page().catch(() => null);
        }
        p ? resolve(p) : reject(new Error('popup page() returned null after retries'));
      };
      browser.on('targetcreated', handler);
    });

    const connectClicked = await page.evaluate(() => {
      for (const btn of document.querySelectorAll('button')) {
        if (btn.textContent.trim().toLowerCase() === 'connect account') { btn.click(); return true; }
      }
      return false;
    });

    if (!connectClicked) {
      return { success: false, error: '"Connect Account" button not found' };
    }

    let googlePage;
    try {
      googlePage = await newTargetPromise;
    } catch (e) {
      return { success: false, error: e.message };
    }

    // Bring popup to front (required for keyboard/click to work)
    await googlePage.bringToFront();

    // Wait for Google's page to load
    await googlePage.waitForFunction(
      () => window.location.hostname.includes('google.com'),
      { timeout: 20000 }
    ).catch(() => {});

    console.log(`\n    Popup URL: ${googlePage.url().substring(0, 80)}`);
    await ss(googlePage, 'sl-google-2-loaded.png');

    // Wait for email input or account picker
    await googlePage.waitForSelector('input[type="email"], [data-identifier]', {
      visible: true, timeout: 20000
    }).catch(() => {});
    await wait(1500);

    // If account picker shown — dismiss it
    const pickerItem = await googlePage.$('[data-identifier]').catch(() => null);
    if (pickerItem) {
      console.log(`\n    Account picker — dismissing`);
      const clicked = await googlePage.evaluate(() => {
        // Try known selectors for "Use another account"
        for (const sel of ['[data-authuser="-1"]', '[data-identifier=""]']) {
          const el = document.querySelector(sel);
          if (el) { el.click(); return sel; }
        }
        // Find by text
        for (const el of document.querySelectorAll('li, [role="link"], [role="button"], div')) {
          const t = (el.innerText || '').trim();
          if (t.includes('Use another') || t.includes('другой акк') || t.includes('Add account')) {
            el.click();
            return 'text:' + t.substring(0, 40);
          }
        }
        return null;
      });
      console.log(`\n    Picker action: ${clicked}`);
      await wait(2500);
      await googlePage.waitForSelector('input[type="email"]', { visible: true, timeout: 15000 }).catch(() => {});
      await wait(800);
    }

    console.log(`\n    Typing email: ${email}`);

    // Wait for email input — Google may use type="email", type="text", or name="identifier"
    const emailEl = await googlePage.waitForSelector(
      'input[type="email"], input[name="identifier"], input[type="text"]',
      { visible: true, timeout: 15000 }
    ).catch(() => null);

    if (emailEl) {
      await emailEl.click({ clickCount: 3 });
      await wait(300);
      await googlePage.keyboard.type(email, { delay: 80 });
      await wait(400);
      await googlePage.keyboard.press('Enter');
      await wait(3000);
    } else {
      console.log('\n    WARNING: email input not found');
    }

    console.log(`\n    Looking for password field...`);

    // Wait for password field
    await googlePage.waitForSelector('input[type="password"]', { visible: true, timeout: 15000 }).catch(() => {});
    await wait(800);

    const pwdEl = await googlePage.$('input[type="password"]').catch(() => null);
    console.log(`\n    Password field found: ${!!pwdEl}`);
    if (pwdEl) {
      await pwdEl.click({ clickCount: 3 });
      await wait(300);
      await googlePage.keyboard.type(GOOGLE_PASSWORD, { delay: 80 });
      await wait(400);
      await googlePage.keyboard.press('Enter');
      await wait(4000);
      console.log('\n    Password entered, URL: ' + googlePage.url().substring(0, 80));
    } else {
      console.log('\n    WARNING: password input not found');
    }

    await ss(googlePage, 'sl-google-after-password.png');

    // Handle 2FA if needed
    const url2fa = googlePage.url();
    const content2fa = await googlePage.content().catch(() => '');
    if (url2fa.includes('challenge') || url2fa.includes('2-step') ||
        content2fa.includes('2-Step') || content2fa.includes('backup') ||
        content2fa.includes('верификац') || content2fa.includes('подтвержд')) {
      console.log(`\n    2FA — using backup code`);
      await googlePage.evaluate(() => {
        for (const el of document.querySelectorAll('button, a, [role="link"], [role="button"]')) {
          if (['Use a backup code', 'backup code', 'Try another way', 'More options',
               'Другой способ', 'резервный код'].some(p => el.textContent.includes(p))) {
            el.click(); return;
          }
        }
      });
      await wait(1500);
      const code = getNextCode(email);
      if (code) {
        const codeInput = await googlePage.$('input[type="tel"], input[type="number"], input[name="totpPin"]').catch(() => null);
        if (codeInput) {
          await codeInput.click({ clickCount: 3 });
          await wait(200);
          await codeInput.type(code, { delay: 60 });
          await wait(400);
          await codeInput.press('Enter');
          await wait(2000);
          console.log(`\n    ✓ Backup code entered`);
        }
      } else {
        console.log(`\n    ⚠ No backup code available for ${email}`);
      }
    }

    // Click Allow on OAuth consent screen
    await googlePage.evaluate(() => {
      for (const btn of document.querySelectorAll('button, [role="button"]')) {
        if (['Allow', 'Continue', 'Grant access', 'Разрешить', 'Предоставить'].some(p =>
            btn.textContent.trim().startsWith(p))) {
          btn.click(); return;
        }
      }
    });
    await wait(3000);
    await googlePage.close().catch(() => {});

    // Verify via API
    await wait(2000);
    const verified = await new Promise(resolve => {
      const https = require('https');
      https.get(
        `https://server.smartlead.ai/api/v1/email-accounts?api_key=${API_KEY}&limit=10&offset=0`,
        res => {
          let d = '';
          res.on('data', c => d += c);
          res.on('end', () => {
            try {
              const arr = JSON.parse(d);
              // Check all pages would be slow — just check if count increased vs progress
              resolve(Array.isArray(arr));
            } catch (_) { resolve(false); }
          });
        }
      ).on('error', () => resolve(false));
    });

    // Navigate back and check
    await page.goto('https://app.smartlead.ai/app/email-accounts', { waitUntil: 'networkidle2', timeout: 20000 });
    await wait(1000);
    const found = await page.evaluate(e => document.body.innerText.toLowerCase().includes(e.toLowerCase()), email);

    if (found) {
      console.log('✓');
      return { success: true };
    } else {
      console.log('? (checking API...)');
      // API check
      const apiFound = await new Promise(resolve => {
        const https = require('https');
        let offset = 0;
        const checkPage = () => {
          https.get(
            `https://server.smartlead.ai/api/v1/email-accounts?api_key=${API_KEY}&limit=100&offset=${offset}`,
            res => {
              let d = '';
              res.on('data', c => d += c);
              res.on('end', () => {
                try {
                  const arr = JSON.parse(d);
                  if (!Array.isArray(arr) || arr.length === 0) { resolve(false); return; }
                  if (arr.some(a => (a.from_email || '').toLowerCase() === email.toLowerCase())) {
                    resolve(true); return;
                  }
                  if (arr.length < 100) { resolve(false); return; }
                  offset += 100;
                  checkPage();
                } catch (_) { resolve(false); }
              });
            }
          ).on('error', () => resolve(false));
        };
        checkPage();
      });
      if (apiFound) {
        console.log('✓ (API confirmed)');
        return { success: true };
      }
      console.log('✗');
      return { success: false, error: 'OAuth completed but account not found in Smartlead' };
    }

  } catch (e) {
    console.log(`FAIL: ${e.message.split('\n')[0]}`);
    return { success: false, error: e.message.split('\n')[0] };
  }
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const emails = [];
  for (const domain of domains) {
    for (const login of USERS) emails.push(`${login}@${domain}`);
  }

  const progressFile = path.join(__dirname, 'smartlead-connect-progress.json');
  let progress = { connected: [], failed: [] };
  if (fs.existsSync(progressFile)) {
    try { progress = JSON.parse(fs.readFileSync(progressFile, 'utf8')); } catch (_) {}
  }
  if (!progress.connected) progress.connected = [];
  if (!progress.failed) progress.failed = [];

  const alreadyDone = new Set(progress.connected.map(e => typeof e === 'string' ? e : e.email));
  const toConnect = emails.filter(e => !alreadyDone.has(e));

  console.log(`\nTotal: ${emails.length} | Already connected: ${alreadyDone.size} | To connect: ${toConnect.length}`);
  console.log('Launching browser...\n');

  const browser = await launchBrowser();
  const page = await browser.newPage();

  try {
    await ensureLoggedIn(page);

    for (const email of toConnect) {
      const result = await connectAccount(browser, page, email);

      if (result.success) {
        progress.connected.push(email);
        progress.failed = progress.failed.filter(f => (typeof f === 'string' ? f : f.email) !== email);
      } else {
        progress.failed = progress.failed.filter(f => (typeof f === 'string' ? f : f.email) !== email);
        progress.failed.push({ email, error: result.error });
      }

      try { fs.writeFileSync(progressFile, JSON.stringify(progress, null, 2)); } catch (_) {}
      await wait(1000);
    }

  } finally {
    console.log('\n══════════════════════════════════════════');
    console.log(`Connected: ${progress.connected.length}`);
    console.log(`Failed:    ${progress.failed.length}`);
    if (progress.failed.length) {
      progress.failed.forEach(f => console.log(`  - ${f.email || f}: ${f.error || ''}`));
    }
    console.log('\nBrowser closing...');
    await browser.close();
  }
}

main().catch(e => { console.error(e); process.exit(1); });
