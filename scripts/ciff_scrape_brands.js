const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900'],
    defaultViewport: { width: 1440, height: 900 },
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
  });

  try {
    const page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36');

    console.error('Navigating to CIFF brands page...');
    await page.goto('https://ciff.dk/our-brands', { waitUntil: 'networkidle2', timeout: 60000 });
    await sleep(3000);

    // Scroll down to load all brands (lazy loading)
    let previousHeight = 0;
    let scrollAttempts = 0;
    while (scrollAttempts < 50) {
      const currentHeight = await page.evaluate(() => document.body.scrollHeight);
      if (currentHeight === previousHeight) {
        // Try one more scroll to be sure
        await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
        await sleep(2000);
        const finalHeight = await page.evaluate(() => document.body.scrollHeight);
        if (finalHeight === currentHeight) break;
      }
      previousHeight = currentHeight;
      await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
      await sleep(1500);
      scrollAttempts++;
    }
    console.error(`Scrolled ${scrollAttempts} times`);

    // Scroll back to top
    await page.evaluate(() => window.scrollTo(0, 0));
    await sleep(1000);

    // Extract brand names - try multiple selectors
    const brands = await page.evaluate(() => {
      const results = [];

      // Strategy 1: Look for links/text in brand grid/list containers
      const allLinks = document.querySelectorAll('a');
      const brandLinks = [];
      for (const link of allLinks) {
        const href = link.getAttribute('href') || '';
        const text = (link.textContent || '').trim();
        // Brand links typically point to /brand/ or /our-brands/ paths
        if (href.includes('/brand') || href.includes('/our-brands/')) {
          if (text && text.length > 0 && text.length < 100) {
            brandLinks.push({ text, href });
          }
        }
      }

      if (brandLinks.length > 0) {
        for (const b of brandLinks) {
          if (b.text && !results.includes(b.text)) results.push(b.text);
        }
      }

      // Strategy 2: Look for elements in grid/list layout that look like brand names
      if (results.length < 10) {
        // Try common patterns
        const selectors = [
          '[class*="brand"] a',
          '[class*="Brand"] a',
          '[class*="grid"] a',
          '[class*="list"] li a',
          '[class*="exhibitor"] a',
          'article a',
          'main a',
        ];
        for (const sel of selectors) {
          const els = document.querySelectorAll(sel);
          for (const el of els) {
            const text = (el.textContent || '').trim();
            if (text && text.length > 1 && text.length < 80 && !results.includes(text)) {
              results.push(text);
            }
          }
        }
      }

      // Strategy 3: Dump all visible text blocks that look like brand names
      if (results.length < 10) {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        const texts = [];
        while (walker.nextNode()) {
          const t = walker.currentNode.textContent.trim();
          if (t && t.length > 1 && t.length < 60) texts.push(t);
        }
        // Return raw texts for analysis
        return { brands: results, fallbackTexts: texts.slice(0, 500) };
      }

      return { brands: results, fallbackTexts: [] };
    });

    // Also try to intercept any API calls for brand data
    const pageContent = await page.content();
    const nextDataMatch = pageContent.match(/<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/);
    let nextData = null;
    if (nextDataMatch) {
      try {
        nextData = JSON.parse(nextDataMatch[1]);
      } catch (e) {}
    }

    const output = {
      brandsFound: brands.brands.length,
      brands: brands.brands,
      fallbackTexts: brands.fallbackTexts,
      hasNextData: !!nextData,
    };

    // If we got __NEXT_DATA__, extract brand info from it
    if (nextData) {
      const extractBrands = (obj, depth = 0) => {
        if (depth > 10) return [];
        const found = [];
        if (Array.isArray(obj)) {
          for (const item of obj) {
            if (typeof item === 'object' && item !== null) {
              if (item.name || item.title || item.brandName) {
                found.push(item.name || item.title || item.brandName);
              }
              found.push(...extractBrands(item, depth + 1));
            }
          }
        } else if (typeof obj === 'object' && obj !== null) {
          for (const [key, val] of Object.entries(obj)) {
            if (key === 'brands' || key === 'exhibitors' || key === 'items' || key === 'data') {
              found.push(...extractBrands(val, depth + 1));
            } else if (typeof val === 'object') {
              found.push(...extractBrands(val, depth + 1));
            }
          }
        }
        return found;
      };
      output.nextDataBrands = [...new Set(extractBrands(nextData))];
    }

    console.log(JSON.stringify(output, null, 2));
  } catch (err) {
    console.error('Error:', err.message);
    console.log(JSON.stringify({ error: err.message }));
  } finally {
    await browser.close();
  }
})();
