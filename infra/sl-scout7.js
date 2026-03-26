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

  // Select Smartlead's Infrastructure radio
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

  // Click Google OAuth text node parent
  const clicked = await page.evaluate(() => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.textContent.trim() === 'Google OAuth') {
        let el = node.parentElement;
        for (let i = 0; i < 5; i++) {
          if (el.tagName === 'DIV' && el.children.length >= 1) { el.click(); return 'clicked div'; }
          el = el.parentElement; if (!el) break;
        }
        node.parentElement.click(); return 'clicked text parent';
      }
    }
    return null;
  });
  console.log('Google OAuth click:', clicked);

  // Wait and capture what happens
  await new Promise(r => setTimeout(r, 3000));
  await page.screenshot({ path: path.join(__dirname, 'sl-after-google-oauth.png') });
  console.log('Screenshot: sl-after-google-oauth.png');

  // Log everything in the dialog
  const dialogHtml = await page.evaluate(() => {
    const d = document.querySelector('[role="dialog"]');
    return d ? d.innerHTML.substring(0, 3000) : 'NO DIALOG';
  });
  console.log('Dialog HTML:\n', dialogHtml);

  const inputs = await page.evaluate(() =>
    [...document.querySelectorAll('input')].map(i => ({
      type: i.type, placeholder: i.placeholder, name: i.name, id: i.id, value: i.value
    }))
  );
  console.log('All inputs:', JSON.stringify(inputs, null, 2));

  // Check for new tabs/pages opened
  const pages = await browser.pages();
  console.log('Open pages:', pages.length, pages.map(p => p.url()));

  console.log('\nBrowser stays open — check the window!');
})().catch(e => { console.error(e.message); process.exit(1); });
