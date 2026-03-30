const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
    ignoreDefaultArgs: ['--enable-automation'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });

  await page.goto('https://app.apollo.io/#/login', { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 2000));
  await page.type('input[name="email"]', 'danila@getsally.io', { delay: 50 });
  await page.type('input[name="password"]', 'UQdzDShCjAi5Nil!!', { delay: 50 });
  await page.click('button[type="submit"]');
  await new Promise(r => setTimeout(r, 5000));
  console.log('Login: ' + page.url());

  // Companies tab Miami
  const url = 'https://app.apollo.io/#/companies?organizationLocations[]=Miami%2C+Florida%2C+United+States&organizationNumEmployeesRanges[]=1%2C50&qKeywords=digital+agency';
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
  await new Promise(r => setTimeout(r, 10000));
  await page.screenshot({ path: '/tmp/apollo_direct_test.png' });

  const text = await page.evaluate(() => document.body.innerText.substring(0, 400));
  const hasCF = text.includes('Verification') || text.includes('Cloudflare');
  console.log('Cloudflare: ' + hasCF);
  console.log('Text: ' + text.substring(0, 200));
  await browser.close();
})();
