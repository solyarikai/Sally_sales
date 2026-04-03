import { test, expect } from '@playwright/test';

const PROD_URL = 'http://46.62.210.24';

test('Production auth check + page load', async ({ page }) => {
  // Set HTTP basic auth credentials
  await page.context().setHTTPCredentials({
    username: 'ilovesally',
    password: 'BdaP31NNXX4ZCyvU',
  });

  await page.goto(PROD_URL + '/contacts');
  await page.waitForSelector('.ag-body-viewport', { timeout: 20000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: 'screenshot_auth_check.png', fullPage: true });

  // Verify page loaded (not a 401 page)
  const title = await page.title();
  console.log('Page title:', title);
  expect(title).not.toContain('401');
});
