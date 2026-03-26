const { launch } = require('./sl-base');
const path = require('path');

(async () => {
  const { browser, page } = await launch();

  await page.goto('https://app.smartlead.ai/app/email-accounts', { waitUntil: 'networkidle2', timeout: 20000 });
  await new Promise(r => setTimeout(r, 2000));

  // Open modal
  await page.evaluate(() => {
    for (const btn of document.querySelectorAll('button')) { if (btn.textContent.includes('Add Account')) { btn.click(); return; } }
  });
  await new Promise(r => setTimeout(r, 2000));

  // Select Smartlead's Infrastructure
  await page.evaluate(() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.textContent.includes("Smartlead's Infrastructure")) {
        let el = node.parentElement;
        for (let i = 0; i < 8; i++) {
          const r = el.querySelector('input[type="radio"]');
          if (r) { r.click(); return; }
          el = el.parentElement; if (!el) break;
        }
        node.parentElement.click(); return;
      }
    }
  });
  await new Promise(r => setTimeout(r, 1500));

  // Click Google OAuth
  const clicked = await page.evaluate(() => {
    for (const el of document.querySelectorAll('div, button')) {
      if (el.textContent.trim() === 'Google OAuth' && el.children.length < 6) { el.click(); return el.textContent.trim(); }
    }
    return null;
  });
  console.log('Clicked:', clicked);
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(__dirname, 'sl-google-oauth-step.png') });
  console.log('Screenshot: sl-google-oauth-step.png');

  const content = await page.evaluate(() => {
    const d = document.querySelector('[role="dialog"]');
    return d ? d.innerText : '';
  });
  console.log('Step content:\n', content);

  const inputs = await page.evaluate(() =>
    [...document.querySelectorAll('input')].map(i => ({ type: i.type, placeholder: i.placeholder, name: i.name }))
  );
  console.log('Inputs:', JSON.stringify(inputs));

  const btns = await page.evaluate(() =>
    [...document.querySelectorAll('button')].map(b => b.textContent.trim()).filter(Boolean)
  );
  console.log('Buttons:', btns);

  console.log('\nBrowser stays open.');
})().catch(e => { console.error(e.message); process.exit(1); });
