import { test, expect } from '@playwright/test';
import path from 'path';
import fs from 'fs';

const SCREENSHOTS = path.join(__dirname, '..', 'screenshots', 'query-dashboard');

// Ensure screenshots directory exists
fs.mkdirSync(SCREENSHOTS, { recursive: true });

const ss = (name: string) => path.join(SCREENSHOTS, `${name}.png`);

/**
 * E2E tests for /dashboard/queries — Query Dashboard page.
 * Tests against live backend with Deliryo project (id=18),
 * segment=family_office, geo=moscow_fo.
 */
test.describe('Query Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log(`[BROWSER ERROR] ${msg.text()}`);
    });
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`));
  });

  test('page loads and shows query data for Deliryo project', async ({ page }) => {
    // Set project in localStorage before navigating
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    await page.goto('/dashboard/queries?project_id=18');
    await expect(page).toHaveURL(/\/dashboard\/queries/);

    // Wait for either the grid or loading to finish
    const grid = page.locator('.ag-theme-alpine');
    await expect(grid).toBeVisible({ timeout: 15000 });

    // Wait for data to load — look for "queries" counter in command bar
    const queriesCount = page.locator('text=/\\d+.*queries/');
    await expect(queriesCount).toBeVisible({ timeout: 15000 });

    await page.screenshot({ path: ss('01-page-loaded') });

    // Verify "Query Dashboard" title
    const title = page.locator('h1:has-text("Query Dashboard")');
    await expect(title).toBeVisible();

    // Verify search input exists
    const searchInput = page.locator('input[placeholder="Search query text..."]');
    await expect(searchInput).toBeVisible();

    console.log('Query Dashboard loaded successfully');
  });

  test('summary metrics bar shows aggregate data', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    await page.goto('/dashboard/queries?project_id=18');

    // Wait for summary to load
    const queriesMetric = page.locator('text=Queries').first();
    await expect(queriesMetric).toBeVisible({ timeout: 15000 });

    // Verify key metrics are visible
    await expect(page.locator('text=Done').first()).toBeVisible();
    await expect(page.locator('text=Domains').first()).toBeVisible();
    await expect(page.locator('text=Targets').first()).toBeVisible();
    await expect(page.locator('text=Saturation').first()).toBeVisible();

    await page.screenshot({ path: ss('02-summary-metrics') });
    console.log('Summary metrics bar visible');
  });

  test('filter by family_office segment and moscow_fo geo via URL', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    // Navigate with pre-applied filters
    await page.goto('/dashboard/queries?project_id=18&segment=family_office&geo=moscow_fo');

    // Wait for grid to load
    const grid = page.locator('.ag-theme-alpine');
    await expect(grid).toBeVisible({ timeout: 15000 });

    // Wait for data rows to appear
    await page.waitForTimeout(2000);

    await page.screenshot({ path: ss('03-family-office-russia-filtered'), fullPage: true });

    // Verify URL still has the filters
    const url = page.url();
    expect(url).toContain('segment=family_office');
    expect(url).toContain('geo=moscow_fo');

    console.log(`Filtered page URL: ${url}`);

    // Check that the query count reflects filtered data
    const queriesCount = page.locator('text=/\\d+.*queries/');
    await expect(queriesCount).toBeVisible({ timeout: 10000 });
    const countText = await queriesCount.textContent();
    console.log(`Filtered results: ${countText}`);
  });

  test('saturation panel opens and shows segment/geo breakdown', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    await page.goto('/dashboard/queries?project_id=18');

    // Wait for summary metrics
    await expect(page.locator('text=Saturation').first()).toBeVisible({ timeout: 15000 });

    // Click "Saturation breakdown" toggle
    const toggleBtn = page.locator('button:has-text("Saturation breakdown")');
    await expect(toggleBtn).toBeVisible({ timeout: 10000 });
    await toggleBtn.click();

    // Wait for breakdown tables to appear
    await page.waitForTimeout(1000);

    // Verify "By Segment" and "By Geo" headers
    const bySegment = page.locator('text=By Segment');
    const byGeo = page.locator('text=By Geo');
    await expect(bySegment).toBeVisible({ timeout: 5000 });
    await expect(byGeo).toBeVisible({ timeout: 5000 });

    await page.screenshot({ path: ss('04-saturation-panel-open'), fullPage: true });

    console.log('Saturation panel opened with breakdown tables');
  });

  test('clicking segment row in saturation panel applies segment filter', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    await page.goto('/dashboard/queries?project_id=18');

    // Open saturation panel
    const toggleBtn = page.locator('button:has-text("Saturation breakdown")');
    await expect(toggleBtn).toBeVisible({ timeout: 15000 });
    await toggleBtn.click();
    await page.waitForTimeout(1000);

    // Click the first segment row in the By Segment table
    const segmentRows = page.locator('text=By Segment').locator('..').locator('table tbody tr');
    const rowCount = await segmentRows.count();
    if (rowCount > 0) {
      const firstRow = segmentRows.first();
      const segmentName = await firstRow.locator('td').first().textContent();
      console.log(`Clicking segment: "${segmentName}"`);
      await firstRow.click();

      // URL should now have segment filter
      await page.waitForTimeout(500);
      const url = page.url();
      expect(url).toContain('segment=');
      console.log(`URL after segment click: ${url}`);

      await page.screenshot({ path: ss('05-segment-filter-applied') });
    } else {
      console.log('No segment rows to click');
    }
  });

  test('URL state is preserved on page reload', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    const targetUrl = '/dashboard/queries?project_id=18&segment=family_office&geo=moscow_fo&sort_by=targets_found&sort_order=desc';
    await page.goto(targetUrl);

    // Wait for grid to load
    const grid = page.locator('.ag-theme-alpine');
    await expect(grid).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    // Get the current URL
    const urlBefore = page.url();
    expect(urlBefore).toContain('segment=family_office');
    expect(urlBefore).toContain('geo=moscow_fo');

    // Reload the page
    await page.reload();

    // Wait for grid to load again
    await expect(grid).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    // Verify URL still has the same filters
    const urlAfter = page.url();
    expect(urlAfter).toContain('segment=family_office');
    expect(urlAfter).toContain('geo=moscow_fo');

    await page.screenshot({ path: ss('06-url-preserved-after-reload') });
    console.log('URL state preserved after reload');
  });

  test('clicking domains count navigates to CRM contacts page', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    await page.goto('/dashboard/queries?project_id=18&segment=family_office');

    // Wait for grid
    const grid = page.locator('.ag-theme-alpine');
    await expect(grid).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    await page.screenshot({ path: ss('07-before-domains-click') });

    // Find a clickable domains number (blue, non-zero)
    const domainLinks = page.locator('button[title="View contacts from these domains"]');
    const linkCount = await domainLinks.count();
    console.log(`Found ${linkCount} clickable domain links`);

    if (linkCount > 0) {
      const firstLink = domainLinks.first();
      const value = await firstLink.textContent();
      console.log(`Clicking domains count: ${value}`);

      await firstLink.click();

      // Should navigate to /contacts with filters
      await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });
      const contactsUrl = page.url();
      expect(contactsUrl).toContain('segment=family_office');
      console.log(`Navigated to: ${contactsUrl}`);

      await page.waitForTimeout(2000);
      await page.screenshot({ path: ss('08-contacts-from-domains-click') });
    } else {
      console.log('No clickable domain links found (all queries have 0 domains)');
    }
  });

  test('clicking targets count navigates to CRM contacts page', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    await page.goto('/dashboard/queries?project_id=18');

    // Wait for grid
    const grid = page.locator('.ag-theme-alpine');
    await expect(grid).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    // Find a clickable targets number (green, non-zero)
    const targetLinks = page.locator('button[title="View target contacts"]');
    const linkCount = await targetLinks.count();
    console.log(`Found ${linkCount} clickable target links`);

    if (linkCount > 0) {
      const firstLink = targetLinks.first();
      const value = await firstLink.textContent();
      console.log(`Clicking targets count: ${value}`);

      await firstLink.click();

      // Should navigate to /contacts
      await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });
      const contactsUrl = page.url();
      console.log(`Navigated to CRM: ${contactsUrl}`);

      await page.waitForTimeout(2000);
      await page.screenshot({ path: ss('09-contacts-from-targets-click') });
    } else {
      console.log('No clickable target links found (all queries have 0 targets)');
    }
  });

  test('pagination controls work', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    await page.goto('/dashboard/queries?project_id=18');

    // Wait for grid
    const grid = page.locator('.ag-theme-alpine');
    await expect(grid).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    // Check pagination info is visible
    const pageInfo = page.locator('text=/Page \\d+ of \\d+/');
    await expect(pageInfo).toBeVisible({ timeout: 10000 });
    const pageText = await pageInfo.textContent();
    console.log(`Pagination: ${pageText}`);

    // If multi-page, test next button
    const match = pageText?.match(/Page (\d+) of (\d+)/);
    if (match && parseInt(match[2]) > 1) {
      // Click next page
      const nextBtn = page.locator('button').filter({ has: page.locator('svg.lucide-chevron-right') }).first();
      await nextBtn.click();
      await page.waitForTimeout(1500);

      // Page should now be 2
      const newPageInfo = page.locator('text=/Page 2 of/');
      await expect(newPageInfo).toBeVisible({ timeout: 5000 });
      console.log('Navigated to page 2');

      // URL should have page=2
      expect(page.url()).toContain('page=2');

      await page.screenshot({ path: ss('10-pagination-page-2') });
    } else {
      console.log('Only one page of results — pagination not testable');
    }
  });

  test('search filters queries by text', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    await page.goto('/dashboard/queries?project_id=18');

    // Wait for grid
    const grid = page.locator('.ag-theme-alpine');
    await expect(grid).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    // Get initial count
    const countBefore = page.locator('text=/\\d+.*queries/');
    const textBefore = await countBefore.textContent();
    console.log(`Before search: ${textBefore}`);

    // Type a search query
    const searchInput = page.locator('input[placeholder="Search query text..."]');
    await searchInput.fill('family office');

    // Wait for debounce + API response
    await page.waitForTimeout(1000);

    // Get new count
    const textAfter = await countBefore.textContent();
    console.log(`After search "family office": ${textAfter}`);

    // URL should have q=family+office
    expect(page.url()).toContain('q=family');

    await page.screenshot({ path: ss('11-search-family-office') });
  });

  test('clear filters button resets all filters', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    // Start with filters applied
    await page.goto('/dashboard/queries?project_id=18&segment=family_office&geo=moscow_fo&q=office');

    const grid = page.locator('.ag-theme-alpine');
    await expect(grid).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(2000);

    // Find "Clear filters" button
    const clearBtn = page.locator('button:has-text("Clear filters")');
    await expect(clearBtn).toBeVisible({ timeout: 5000 });
    await clearBtn.click();

    await page.waitForTimeout(1000);

    // URL should no longer have segment/geo/q params
    const url = page.url();
    expect(url).not.toContain('segment=');
    expect(url).not.toContain('geo=');
    expect(url).not.toContain('q=');

    await page.screenshot({ path: ss('12-filters-cleared') });
    console.log('All filters cleared');
  });

  test('FULL SCENARIO: Deliryo family_office Russia deep analysis', async ({ page }) => {
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      store.state = store.state || {};
      store.state.currentProject = { id: 18, name: 'Deliryo' };
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    // Step 1: Load with family_office + moscow_fo filters
    console.log('--- Step 1: Loading filtered dashboard ---');
    await page.goto('/dashboard/queries?project_id=18&segment=family_office&geo=moscow_fo');
    const grid = page.locator('.ag-theme-alpine');
    await expect(grid).toBeVisible({ timeout: 15000 });
    await page.waitForTimeout(3000);

    // Read query count and summary
    const countText = await page.locator('text=/\\d+.*queries/').textContent();
    console.log(`Filtered queries count: ${countText}`);

    await page.screenshot({ path: ss('FULL-01-dashboard-filtered'), fullPage: true });

    // Step 2: Open saturation panel for breakdown
    console.log('--- Step 2: Opening saturation panel ---');
    const toggleBtn = page.locator('button:has-text("Saturation breakdown")');
    if (await toggleBtn.isVisible()) {
      await toggleBtn.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: ss('FULL-02-saturation-panel'), fullPage: true });
    }

    // Step 3: Sort by targets_found desc to see most productive queries
    console.log('--- Step 3: Sorting by targets found ---');
    const targetsHeader = page.locator('.ag-header-cell:has-text("Targets")').first();
    if (await targetsHeader.isVisible()) {
      await targetsHeader.click();
      await page.waitForTimeout(1500);
      await targetsHeader.click(); // Click again for desc
      await page.waitForTimeout(1500);
    }
    await page.screenshot({ path: ss('FULL-03-sorted-by-targets'), fullPage: true });

    // Step 4: Click through to contacts
    console.log('--- Step 4: Click-through to CRM contacts ---');
    const targetLinks = page.locator('button[title="View target contacts"]');
    const linkCount = await targetLinks.count();
    if (linkCount > 0) {
      await targetLinks.first().click();
      await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });
      await page.waitForTimeout(3000);
      await page.screenshot({ path: ss('FULL-04-contacts-from-query'), fullPage: true });

      const contactsUrl = page.url();
      console.log(`CRM contacts URL: ${contactsUrl}`);
      expect(contactsUrl).toContain('segment=family_office');
    } else {
      console.log('No target links to click through');
      // Try domain links instead
      const domainLinks = page.locator('button[title="View contacts from these domains"]');
      if (await domainLinks.count() > 0) {
        await domainLinks.first().click();
        await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });
        await page.waitForTimeout(3000);
        await page.screenshot({ path: ss('FULL-04-contacts-from-domains'), fullPage: true });
      }
    }

    console.log('--- Full scenario complete ---');
  });

  test('no-project state shows prompt to select project', async ({ page }) => {
    // Clear any stored project
    await page.addInitScript(() => {
      const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
      if (store.state) store.state.currentProject = null;
      localStorage.setItem('leadgen-storage', JSON.stringify(store));
    });

    await page.goto('/dashboard/queries');
    await page.waitForTimeout(2000);

    const selectPrompt = page.locator('text=Select a project');
    await expect(selectPrompt).toBeVisible({ timeout: 10000 });

    await page.screenshot({ path: ss('13-no-project-selected') });
    console.log('No-project state shows prompt');
  });
});
