// Scout: maps out the Add Account flow in Smartlead
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
  await page.screenshot({ path: path.join(__dirname, 'sl-modal1.png') });
  console.log('Screenshot: sl-modal1.png');

  // Log all elements with text
  const items = await page.evaluate(() =>
    [...document.querySelectorAll('[role="dialog"] *')].map(el => ({
      tag: el.tagName,
      text: el.textContent.trim().substring(0, 80),
      cls: el.className.substring(0, 40),
    })).filter(i => i.text.length > 2 && i.text.length < 80)
  );
  console.log('Modal items:');
  [...new Set(items.map(i => i.text))].forEach(t => console.log(' ', t));

  // Browser stays open — DO NOT close
  console.log('\nBrowser stays open. Press Ctrl+C when done.');
})().catch(e => { console.error(e.message); process.exit(1); });
