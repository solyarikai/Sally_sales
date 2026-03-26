// Scout: clicks Smartlead Infrastructure → Next → screenshots step 2
const { launch } = require('./sl-base');
const path = require('path');

(async () => {
  const { browser, page } = await launch();

  await page.goto('https://app.smartlead.ai/app/email-accounts', { waitUntil: 'networkidle2', timeout: 20000 });
  await new Promise(r => setTimeout(r, 2000));

  // Click "Add Account(s)"
  await page.evaluate(() => {
    for (const btn of document.querySelectorAll('button, [role="button"]')) {
      if (btn.textContent.includes('Add Account')) { btn.click(); return; }
    }
  });
  await new Promise(r => setTimeout(r, 2000));

  // Click "Smartlead's Infrastructure" radio/card
  const infra = await page.evaluate(() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.textContent.includes("Smartlead's Infrastructure")) {
        let el = node.parentElement;
        for (let i = 0; i < 6; i++) {
          const r = el.querySelector('input[type="radio"]');
          if (r) { r.click(); return 'clicked radio'; }
          if (el.getAttribute('role') === 'radio' || el.tagName === 'LABEL') { el.click(); return 'clicked label'; }
          el = el.parentElement;
          if (!el) break;
        }
        node.parentElement.click();
        return 'clicked text parent';
      }
    }
    return null;
  });
  console.log('Infrastructure selection:', infra);
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(__dirname, 'sl-infra-sel.png') });

  // Click Next button
  const next = await page.evaluate(() => {
    for (const btn of document.querySelectorAll('button')) {
      const t = btn.textContent.trim();
      if (t === 'Next' || t === 'Continue' || t === 'Next Step') { btn.click(); return t; }
    }
    return null;
  });
  console.log('Next clicked:', next);
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(__dirname, 'sl-step2.png') });
  console.log('Screenshot: sl-step2.png');

  // Get all text content in modal
  const modalContent = await page.evaluate(() => {
    const d = document.querySelector('[role="dialog"]');
    if (!d) return document.body.innerText.substring(0, 2000);
    return d.innerText;
  });
  console.log('Step 2 content:\n', modalContent.substring(0, 1000));

  const allBtns = await page.evaluate(() =>
    [...document.querySelectorAll('button, [role="button"]')].map(el => el.textContent.trim()).filter(Boolean)
  );
  console.log('Buttons:', allBtns);

  console.log('\nBrowser stays open.');
})().catch(e => { console.error(e.message); process.exit(1); });
