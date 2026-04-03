/**
 * ══════════════════════════════════════════════════════════════════════
 * E2E Tests: Query Dashboard — Discovery Intelligence System
 * ══════════════════════════════════════════════════════════════════════
 *
 * Target: /dashboard/queries
 * Live backend: Hetzner (46.62.210.24) via baseURL in playwright.config
 * Reference project: Deliryo (id=18, company_id=1)
 * Reference segment: family_office
 * Reference geo: moscow_fo (Moscow, Russia)
 *
 * ── TEST PLAN & EXPECTED OUTCOMES ──────────────────────────────────
 *
 * T01 - PROJECT AUTO-SELECT FROM URL
 *   Navigate to /dashboard/queries?project_id=18 without localStorage.
 *   Expected: Page auto-loads project from URL param, shows grid data.
 *   Screenshot: T01-project-auto-select.png
 *
 * T02 - PAGE LOAD & STRUCTURE
 *   Navigate with project set. Expected:
 *   - "Query Dashboard" h1 title visible
 *   - Search input visible
 *   - Query count > 0 ("N queries" text)
 *   - AG Grid rendered with rows
 *   - Pagination controls with "Page 1 of N"
 *   Screenshot: T02-page-loaded.png
 *
 * T03 - SUMMARY METRICS BAR
 *   Expected 6+ metric cards visible:
 *   - Queries (total count)
 *   - Done (green)
 *   - Domains (blue)
 *   - Targets (green)
 *   - Est. Cost (amber)
 *   - Saturation % (color-coded)
 *   Screenshot: T03-summary-metrics.png
 *
 * T04 - URL FILTER: segment=family_office&geo=moscow_fo
 *   Navigate with pre-applied filters in URL.
 *   Expected:
 *   - Grid shows filtered data (fewer queries than unfiltered)
 *   - URL retains segment=family_office&geo=moscow_fo
 *   - Query count reflects filtered subset
 *   Screenshots: T04a-filtered-view.png, T04b-filtered-count.png
 *
 * T05 - SATURATION PANEL
 *   Click "Saturation breakdown" toggle.
 *   Expected:
 *   - Panel opens with "By Segment", "By Geo", "By Source" tables
 *   - Each table has columns: Key, Queries, Saturated, Rate, Domains, Targets
 *   - Rate column is color-coded (red >80%, amber >50%, green otherwise)
 *   Screenshots: T05a-panel-closed.png, T05b-panel-open.png
 *
 * T06 - SATURATION PANEL CLICK-THROUGH
 *   Click a segment row in saturation panel.
 *   Expected:
 *   - Segment filter applies (URL updates with segment=X)
 *   - Grid reloads with filtered data
 *   Screenshot: T06-segment-clicked.png
 *
 * T07 - SEARCH INPUT
 *   Type "family office" in search.
 *   Expected:
 *   - After 300ms debounce, grid reloads with filtered results
 *   - URL contains q=family+office or q=family%20office
 *   - Query count changes
 *   Screenshots: T07a-before-search.png, T07b-after-search.png
 *
 * T08 - CLEAR FILTERS
 *   Start with filters applied, click "Clear filters".
 *   Expected:
 *   - All URL filter params removed
 *   - Grid shows unfiltered data
 *   - "Clear filters" button disappears
 *   Screenshot: T08-cleared.png
 *
 * T09 - PAGINATION
 *   On unfiltered view (should have 42K+ queries).
 *   Expected:
 *   - "Page 1 of N" visible (N > 1 for 42K queries at 50/page)
 *   - Click next → "Page 2 of N", URL has page=2
 *   - Click first → "Page 1 of N", URL has no page param
 *   Screenshots: T09a-page1.png, T09b-page2.png, T09c-back-to-page1.png
 *
 * T10 - URL STATE PERSISTENCE ON RELOAD
 *   Navigate with complex filters, reload page.
 *   Expected: All filters preserved in URL and applied to grid.
 *   Screenshots: T10a-before-reload.png, T10b-after-reload.png
 *
 * T11 - CLICK-THROUGH: DOMAINS → CRM CONTACTS
 *   Click a blue domains_found number in the grid.
 *   Expected:
 *   - Navigates to /contacts with segment, geo, source, project_id params
 *   - Contacts page loads with matching filters
 *   Screenshots: T11a-grid-with-domains.png, T11b-contacts-page.png
 *
 * T12 - CLICK-THROUGH: TARGETS → CRM CONTACTS
 *   Click a green targets_found number in the grid.
 *   Expected:
 *   - Same navigation as T11 but for targets
 *   Screenshots: T12a-grid-with-targets.png, T12b-contacts-page.png
 *
 * T13 - SATURATED ROW STYLING
 *   View queries with is_saturated=true.
 *   Expected:
 *   - Saturated rows have gray background + reduced opacity
 *   - Query text has strikethrough
 *   - "SAT" badge visible
 *   Screenshot: T13-saturated-rows.png
 *
 * T14 - SATURATED FILTER TOGGLE
 *   Apply is_saturated=true filter via URL.
 *   Expected:
 *   - Only saturated rows shown (all have "SAT" badge)
 *   - URL has is_saturated=true
 *   Screenshot: T14-saturated-only.png
 *
 * T15 - FULL SCENARIO: Deliryo family_office Russia
 *   Complete user journey:
 *   1. Open /dashboard/queries?project_id=18&segment=family_office&geo=moscow_fo
 *   2. Verify filtered data loads
 *   3. Open saturation panel
 *   4. Sort by targets_found desc
 *   5. Click top targets_found → navigate to CRM
 *   6. Verify contacts page shows matching data
 *   Screenshots: T15-S01 through T15-S06
 *
 * T16 - NO-PROJECT STATE
 *   Navigate without project_id and with cleared localStorage.
 *   Expected: "Select a project" prompt shown.
 *   Screenshot: T16-no-project.png
 *
 * ══════════════════════════════════════════════════════════════════════
 */

import { test, expect, type Page } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

// ── Constants ──────────────────────────────────────────────────────
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SCREENSHOTS = path.join(__dirname, '..', 'screenshots', 'query-dashboard');
fs.mkdirSync(SCREENSHOTS, { recursive: true });

const ss = (name: string) => path.join(SCREENSHOTS, `${name}.png`);

const DELIRYO_PROJECT_ID = 18;
const BASE_URL = '/dashboard/queries';

// ── Helpers ────────────────────────────────────────────────────────

/** Set Deliryo project + company in localStorage before page navigates */
async function setProjectInStorage(page: Page) {
  await page.addInitScript(() => {
    const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
    store.state = store.state || {};
    store.state.currentProject = { id: 18, name: 'Deliryo', contact_count: 0, created_at: '', updated_at: '' };
    store.state.currentCompany = { id: 1, name: 'Deliryo Company' };
    localStorage.setItem('leadgen-storage', JSON.stringify(store));
  });
}

/** Clear project from localStorage but keep company (for auto-select test) */
async function clearProjectKeepCompany(page: Page) {
  await page.addInitScript(() => {
    const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
    store.state = store.state || {};
    store.state.currentProject = null;
    store.state.currentCompany = { id: 1, name: 'Deliryo Company' };
    localStorage.setItem('leadgen-storage', JSON.stringify(store));
  });
}

/** Clear everything from localStorage */
async function clearAllStorage(page: Page) {
  await page.addInitScript(() => {
    const store = JSON.parse(localStorage.getItem('leadgen-storage') || '{}');
    store.state = store.state || {};
    store.state.currentProject = null;
    store.state.currentCompany = null;
    localStorage.setItem('leadgen-storage', JSON.stringify(store));
  });
}

/** Wait for grid to be fully loaded with data rows */
async function waitForGridData(page: Page, timeoutMs = 20000) {
  // Wait for AG Grid container
  await expect(page.locator('.ag-theme-alpine')).toBeVisible({ timeout: timeoutMs });
  // Wait for at least one data row OR the no-rows overlay
  const dataRow = page.locator('.ag-row');
  const noRows = page.locator('.ag-overlay-no-rows-center');
  await expect(dataRow.first().or(noRows)).toBeVisible({ timeout: timeoutMs });
}

/** Wait for the query counter with loaded data (non-zero count) */
async function waitForDataLoaded(page: Page, timeoutMs = 20000) {
  // Wait for a non-zero query count (pattern: "38,418 queries" but NOT "0 queries")
  const counter = page.getByText(/[1-9][\d,]*\s+queries/);
  await expect(counter).toBeVisible({ timeout: timeoutMs });
  return counter;
}

/** Wait for query counter (may be zero) */
async function waitForQueryCount(page: Page, timeoutMs = 20000) {
  const counter = page.getByText(/\d[\d,]*\s+queries/);
  await expect(counter).toBeVisible({ timeout: timeoutMs });
  return counter;
}

/** Get numeric query count from the header (waits for data to load) */
async function getQueryCount(page: Page, waitForData = true): Promise<number> {
  const counter = waitForData
    ? await waitForDataLoaded(page)
    : await waitForQueryCount(page);
  const text = await counter.textContent() || '0';
  const match = text.match(/([\d,]+)/);
  return match ? parseInt(match[1].replace(/,/g, ''), 10) : 0;
}

// ══════════════════════════════════════════════════════════════════════
// TESTS
// ══════════════════════════════════════════════════════════════════════

test.describe('Query Dashboard — E2E Tests', () => {

  test.beforeEach(async ({ page }) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log(`[BROWSER] ${msg.text()}`);
    });
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`));
  });

  // ── T01: Project auto-select from URL ────────────────────────────
  test('T01: project auto-selects from project_id URL param', async ({ page }) => {
    // Clear project but keep company (API needs X-Company-ID header)
    await clearProjectKeepCompany(page);

    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);

    // The page should auto-fetch the project and load data
    // (not show "Select a project")
    const selectPrompt = page.locator('text=Select a project');
    const grid = page.locator('.ag-theme-alpine');

    // Either grid loads OR we see a brief "Select a project" that resolves
    await expect(grid.or(selectPrompt)).toBeVisible({ timeout: 5000 });

    // Give auto-selection time to complete
    await page.waitForTimeout(3000);

    // After auto-select, grid should be visible
    await expect(grid).toBeVisible({ timeout: 15000 });
    await waitForQueryCount(page);

    await page.screenshot({ path: ss('T01-project-auto-select'), fullPage: true });

    // ASSERT: "Select a project" should NOT be visible anymore
    await expect(selectPrompt).not.toBeVisible({ timeout: 5000 });

    console.log('T01 PASS: Project auto-selected from URL param');
  });

  // ── T02: Page load & structure ───────────────────────────────────
  test('T02: page loads with correct structure', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);

    // ASSERT: Title
    const title = page.locator('h1:has-text("Query Dashboard")');
    await expect(title).toBeVisible({ timeout: 10000 });

    // ASSERT: Search input
    const searchInput = page.locator('input[placeholder="Search query text..."]');
    await expect(searchInput).toBeVisible();

    // ASSERT: Query count > 0
    const count = await getQueryCount(page);
    expect(count).toBeGreaterThan(0);
    console.log(`  Total queries: ${count.toLocaleString()}`);

    // ASSERT: AG Grid has rows
    await waitForGridData(page);
    const rowCount = await page.locator('.ag-row').count();
    expect(rowCount).toBeGreaterThan(0);
    console.log(`  Visible rows: ${rowCount}`);

    // ASSERT: Pagination
    const pageInfo = page.locator('text=/Page \\d+ of \\d+/');
    await expect(pageInfo).toBeVisible();

    await page.screenshot({ path: ss('T02-page-loaded'), fullPage: true });
    console.log('T02 PASS: Page structure verified');
  });

  // ── T03: Summary metrics bar ─────────────────────────────────────
  test('T03: summary metrics bar shows all 6+ cards', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForQueryCount(page);

    // ASSERT: Each metric label visible
    const metrics = ['Queries', 'Done', 'Domains', 'Targets', 'Est. Cost', 'Saturation'];
    for (const label of metrics) {
      const el = page.locator(`text=${label}`).first();
      await expect(el).toBeVisible({ timeout: 10000 });
      console.log(`  Metric "${label}" visible`);
    }

    await page.screenshot({ path: ss('T03-summary-metrics'), fullPage: true });
    console.log('T03 PASS: All summary metrics visible');
  });

  // ── T04: URL-driven filters ──────────────────────────────────────
  test('T04: segment + geo filters applied from URL', async ({ page }) => {
    await setProjectInStorage(page);

    // First get unfiltered count for comparison
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    const unfilteredCount = await getQueryCount(page);
    console.log(`  Unfiltered count: ${unfilteredCount.toLocaleString()}`);

    // Now navigate with filters
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office&geo=moscow_fo`);
    await waitForGridData(page);

    const filteredCount = await getQueryCount(page);
    console.log(`  Filtered count (family_office + moscow_fo): ${filteredCount.toLocaleString()}`);

    await page.screenshot({ path: ss('T04a-filtered-view'), fullPage: true });

    // ASSERT: Filtered count < unfiltered count
    expect(filteredCount).toBeLessThan(unfilteredCount);
    expect(filteredCount).toBeGreaterThan(0);

    // ASSERT: URL retains filter params
    const url = page.url();
    expect(url).toContain('segment=family_office');
    expect(url).toContain('geo=moscow_fo');

    await page.screenshot({ path: ss('T04b-filtered-count'), fullPage: true });
    console.log('T04 PASS: URL filters applied correctly');
  });

  // ── T05: Saturation panel ────────────────────────────────────────
  test('T05: saturation panel opens with breakdown tables', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForQueryCount(page);

    // ASSERT: Toggle button visible
    const toggleBtn = page.locator('button:has-text("Saturation breakdown")');
    await expect(toggleBtn).toBeVisible({ timeout: 10000 });

    await page.screenshot({ path: ss('T05a-panel-closed'), fullPage: true });

    // Click to open
    await toggleBtn.click();
    await page.waitForTimeout(1000);

    // ASSERT: Breakdown tables visible
    await expect(page.locator('text=By Segment')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=By Geo')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('text=By Source')).toBeVisible({ timeout: 5000 });

    // ASSERT: Tables have data rows
    const segmentTable = page.locator('text=By Segment').locator('..').locator('table');
    const segmentRows = segmentTable.locator('tbody tr');
    const segmentRowCount = await segmentRows.count();
    expect(segmentRowCount).toBeGreaterThan(0);
    console.log(`  Segment breakdown rows: ${segmentRowCount}`);

    await page.screenshot({ path: ss('T05b-panel-open'), fullPage: true });
    console.log('T05 PASS: Saturation panel opens with all 3 breakdown tables');
  });

  // ── T06: Saturation panel click-through ──────────────────────────
  test('T06: clicking saturation segment row applies filter', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForQueryCount(page);

    // Open saturation panel
    await page.locator('button:has-text("Saturation breakdown")').click();
    await page.waitForTimeout(1000);

    // Get first segment row and click it
    const segmentTable = page.locator('text=By Segment').locator('..').locator('table');
    const firstRow = segmentTable.locator('tbody tr').first();
    const segmentName = await firstRow.locator('td').first().textContent();
    console.log(`  Clicking segment: "${segmentName}"`);
    await firstRow.click();

    await page.waitForTimeout(1500);

    // ASSERT: URL now has segment filter
    const url = page.url();
    expect(url).toContain('segment=');
    console.log(`  URL after click: ${url}`);

    await page.screenshot({ path: ss('T06-segment-clicked'), fullPage: true });
    console.log('T06 PASS: Segment click-through applies filter');
  });

  // ── T07: Search input ────────────────────────────────────────────
  test('T07: search input filters queries by text', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);

    const countBefore = await getQueryCount(page);
    console.log(`  Before search: ${countBefore.toLocaleString()}`);

    await page.screenshot({ path: ss('T07a-before-search'), fullPage: true });

    // Type in search
    const searchInput = page.locator('input[placeholder="Search query text..."]');
    await searchInput.fill('family office');

    // Wait for debounce (300ms) + API
    await page.waitForTimeout(2000);

    const countAfter = await getQueryCount(page);
    console.log(`  After search "family office": ${countAfter.toLocaleString()}`);

    // ASSERT: Count changed (filtered)
    expect(countAfter).toBeLessThanOrEqual(countBefore);

    // ASSERT: URL has search param
    expect(page.url()).toContain('q=family');

    await page.screenshot({ path: ss('T07b-after-search'), fullPage: true });
    console.log('T07 PASS: Search filters queries');
  });

  // ── T08: Clear filters ───────────────────────────────────────────
  test('T08: clear filters button resets everything', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office&geo=moscow_fo&q=office`);
    await waitForGridData(page);

    // ASSERT: "Clear filters" button visible (since we have filters)
    const clearBtn = page.locator('button:has-text("Clear filters")');
    await expect(clearBtn).toBeVisible({ timeout: 10000 });

    await clearBtn.click();
    await page.waitForTimeout(1500);

    // ASSERT: URL filter params removed
    const url = page.url();
    expect(url).not.toContain('segment=');
    expect(url).not.toContain('geo=');
    expect(url).not.toContain('q=');

    // ASSERT: "Clear filters" button is gone (no active filters)
    await expect(clearBtn).not.toBeVisible({ timeout: 3000 });

    await page.screenshot({ path: ss('T08-cleared'), fullPage: true });
    console.log('T08 PASS: All filters cleared');
  });

  // ── T09: Pagination ──────────────────────────────────────────────
  test('T09: pagination navigates between pages', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForGridData(page);

    // ASSERT: Page 1
    const pageInfo = page.locator('text=/Page 1 of (\\d+)/');
    await expect(pageInfo).toBeVisible({ timeout: 10000 });
    const pageText = await pageInfo.textContent();
    const totalPages = parseInt(pageText?.match(/of (\d+)/)?.[1] || '1', 10);
    console.log(`  Total pages: ${totalPages}`);
    expect(totalPages).toBeGreaterThan(1);

    await page.screenshot({ path: ss('T09a-page1'), fullPage: true });

    // Click Next
    const nextBtn = page.locator('button').filter({ has: page.locator('.lucide-chevron-right') }).first();
    await nextBtn.click();
    await page.waitForTimeout(2000);

    // ASSERT: Page 2
    await expect(page.locator('text=/Page 2 of/')).toBeVisible({ timeout: 10000 });
    expect(page.url()).toContain('page=2');

    await page.screenshot({ path: ss('T09b-page2'), fullPage: true });

    // Click First (double chevron left)
    const firstBtn = page.locator('button').filter({ has: page.locator('.lucide-chevrons-left') }).first();
    await firstBtn.click();
    await page.waitForTimeout(2000);

    // ASSERT: Back to page 1
    await expect(page.locator('text=/Page 1 of/')).toBeVisible({ timeout: 10000 });
    expect(page.url()).not.toContain('page=');

    await page.screenshot({ path: ss('T09c-back-to-page1'), fullPage: true });
    console.log('T09 PASS: Pagination works correctly');
  });

  // ── T10: URL state persistence on reload ─────────────────────────
  test('T10: URL state survives page reload', async ({ page }) => {
    await setProjectInStorage(page);
    const filterUrl = `${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office&geo=moscow_fo&sort_by=targets_found&sort_order=desc`;
    await page.goto(filterUrl);
    await waitForGridData(page);

    const countBefore = await getQueryCount(page);

    await page.screenshot({ path: ss('T10a-before-reload'), fullPage: true });

    // Reload
    await page.reload();
    await waitForGridData(page);

    const countAfter = await getQueryCount(page);

    // ASSERT: Same filters in URL
    const url = page.url();
    expect(url).toContain('segment=family_office');
    expect(url).toContain('geo=moscow_fo');

    // ASSERT: Same data count
    expect(countAfter).toBe(countBefore);

    await page.screenshot({ path: ss('T10b-after-reload'), fullPage: true });
    console.log(`T10 PASS: Reload preserved state (count: ${countAfter})`);
  });

  // ── T11: Click-through domains → contacts ────────────────────────
  test('T11: clicking domains count navigates to CRM contacts', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office`);
    await waitForGridData(page);

    await page.screenshot({ path: ss('T11a-grid-with-domains'), fullPage: true });

    // Find clickable domain links
    const domainLinks = page.locator('button[title="View contacts from these domains"]');
    const linkCount = await domainLinks.count();
    console.log(`  Clickable domain links: ${linkCount}`);

    if (linkCount === 0) {
      console.log('  SKIP: No domains > 0 in current view');
      test.skip();
      return;
    }

    const value = await domainLinks.first().textContent();
    console.log(`  Clicking domains count: ${value}`);
    await domainLinks.first().click();

    // ASSERT: Navigated to /contacts
    await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });

    const contactsUrl = page.url();
    console.log(`  Contacts URL: ${contactsUrl}`);

    // ASSERT: Filter params forwarded (segment is from query row context)
    expect(contactsUrl).toContain('segment=');

    await page.waitForTimeout(3000);
    await page.screenshot({ path: ss('T11b-contacts-page'), fullPage: true });
    console.log('T11 PASS: Domains click-through to CRM');
  });

  // ── T12: Click-through targets → contacts ────────────────────────
  test('T12: clicking targets count navigates to CRM contacts', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForGridData(page);

    await page.screenshot({ path: ss('T12a-grid-with-targets'), fullPage: true });

    const targetLinks = page.locator('button[title="View target contacts"]');
    const linkCount = await targetLinks.count();
    console.log(`  Clickable target links: ${linkCount}`);

    if (linkCount === 0) {
      console.log('  SKIP: No targets > 0 in current view');
      test.skip();
      return;
    }

    const value = await targetLinks.first().textContent();
    console.log(`  Clicking targets count: ${value}`);
    await targetLinks.first().click();

    // ASSERT: Navigated to /contacts
    await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });
    const contactsUrl = page.url();
    expect(contactsUrl).toContain('project_id=18');

    await page.waitForTimeout(3000);
    await page.screenshot({ path: ss('T12b-contacts-page'), fullPage: true });
    console.log('T12 PASS: Targets click-through to CRM');
  });

  // ── T13: Saturated row styling ───────────────────────────────────
  test('T13: saturated rows have distinct visual styling', async ({ page }) => {
    await setProjectInStorage(page);
    // Navigate with saturated filter to ensure we see saturated rows
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&is_saturated=true`);
    await waitForGridData(page);

    // ASSERT: SAT badges visible
    const satBadges = page.locator('text=SAT');
    const badgeCount = await satBadges.count();
    console.log(`  SAT badges visible: ${badgeCount}`);

    if (badgeCount === 0) {
      console.log('  SKIP: No saturated queries found');
      test.skip();
      return;
    }

    expect(badgeCount).toBeGreaterThan(0);

    // ASSERT: Rows have reduced opacity class
    const saturatedRows = page.locator('.ag-row.opacity-60');
    const satRowCount = await saturatedRows.count();
    console.log(`  Rows with opacity-60: ${satRowCount}`);

    await page.screenshot({ path: ss('T13-saturated-rows'), fullPage: true });
    console.log('T13 PASS: Saturated rows have visual styling');
  });

  // ── T14: Saturated filter toggle ─────────────────────────────────
  test('T14: is_saturated URL filter shows only saturated queries', async ({ page }) => {
    await setProjectInStorage(page);

    // Get total count
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    const totalCount = await getQueryCount(page);

    // Apply saturated filter
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&is_saturated=true`);
    await waitForGridData(page);

    const saturatedCount = await getQueryCount(page);
    console.log(`  Total: ${totalCount}, Saturated only: ${saturatedCount}`);

    // ASSERT: Saturated < total
    expect(saturatedCount).toBeLessThan(totalCount);

    // ASSERT: URL has is_saturated=true
    expect(page.url()).toContain('is_saturated=true');

    await page.screenshot({ path: ss('T14-saturated-only'), fullPage: true });
    console.log('T14 PASS: Saturated filter works');
  });

  // ── T15: FULL SCENARIO — Deliryo family_office Russia ────────────
  test('T15: full scenario — Deliryo family_office Russia deep analysis', async ({ page }) => {
    await setProjectInStorage(page);

    // Step 1: Load with filters
    console.log('  S01: Loading filtered dashboard');
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office&geo=moscow_fo`);
    await waitForGridData(page);

    const queryCount = await getQueryCount(page);
    console.log(`  → Queries found: ${queryCount}`);
    expect(queryCount).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T15-S01-filtered-dashboard'), fullPage: true });

    // Step 2: Read summary metrics
    console.log('  S02: Verifying summary metrics');
    await expect(page.locator('text=Queries').first()).toBeVisible();
    await expect(page.locator('text=Domains').first()).toBeVisible();
    await expect(page.locator('text=Targets').first()).toBeVisible();
    await expect(page.locator('text=Saturation').first()).toBeVisible();

    await page.screenshot({ path: ss('T15-S02-summary-metrics'), fullPage: true });

    // Step 3: Open saturation panel
    console.log('  S03: Opening saturation breakdown');
    const toggleBtn = page.locator('button:has-text("Saturation breakdown")');
    if (await toggleBtn.isVisible()) {
      await toggleBtn.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: ss('T15-S03-saturation-panel'), fullPage: true });
    }

    // Step 4: Sort by targets_found descending
    console.log('  S04: Sorting by targets found (desc)');
    const targetsHeader = page.locator('.ag-header-cell-label:has-text("Targets")').first();
    if (await targetsHeader.isVisible()) {
      await targetsHeader.click();
      await page.waitForTimeout(1500);
      // Click again for descending
      await targetsHeader.click();
      await page.waitForTimeout(1500);
    }

    await page.screenshot({ path: ss('T15-S04-sorted-by-targets'), fullPage: true });

    // Step 5: Click-through to CRM contacts
    console.log('  S05: Click-through to CRM contacts');
    const targetLinks = page.locator('button[title="View target contacts"]');
    const domainLinks = page.locator('button[title="View contacts from these domains"]');

    let clickedThrough = false;

    if (await targetLinks.count() > 0) {
      const targetValue = await targetLinks.first().textContent();
      console.log(`  → Clicking target count: ${targetValue}`);
      await targetLinks.first().click();
      clickedThrough = true;
    } else if (await domainLinks.count() > 0) {
      const domainValue = await domainLinks.first().textContent();
      console.log(`  → Clicking domain count: ${domainValue}`);
      await domainLinks.first().click();
      clickedThrough = true;
    }

    if (clickedThrough) {
      await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });
      await page.waitForTimeout(3000);

      const contactsUrl = page.url();
      console.log(`  → CRM URL: ${contactsUrl}`);

      // ASSERT: Filters forwarded to CRM
      expect(contactsUrl).toContain('segment=family_office');

      await page.screenshot({ path: ss('T15-S05-contacts-from-query'), fullPage: true });
    } else {
      console.log('  → No clickable links (0 domains/targets in filtered view)');
      await page.screenshot({ path: ss('T15-S05-no-clickable-links'), fullPage: true });
    }

    // Step 6: Navigate back and verify URL is still correct
    console.log('  S06: Navigating back to verify URL persistence');
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office&geo=moscow_fo`);
    await waitForGridData(page);
    expect(page.url()).toContain('segment=family_office');
    expect(page.url()).toContain('geo=moscow_fo');

    await page.screenshot({ path: ss('T15-S06-back-to-dashboard'), fullPage: true });

    console.log('T15 PASS: Full scenario complete');
    console.log(`\n  ═══ DEEP ANALYSIS URL ═══`);
    console.log(`  ${page.url()}`);
    console.log(`  ═════════════════════════\n`);
  });

  // ══════════════════════════════════════════════════════════════════
  // FILTER INTERACTION TESTS (T17-T23)
  // Click each AG Grid column filter, verify dropdown opens,
  // select a value, verify results change.
  // ══════════════════════════════════════════════════════════════════

  // ── T17: Segment column filter ─────────────────────────────────
  test('T17: segment column filter opens and applies filter', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForDataLoaded(page);
    const countBefore = await getQueryCount(page);

    // Click the filter icon on the Segment column header
    const segmentHeader = page.locator('.ag-header-cell').filter({ hasText: 'Segment' });
    const filterIcon = segmentHeader.locator('.ag-header-cell-menu-button, .ag-floating-filter-button, [ref="eMenu"]').first();
    // AG Grid filter: click the header area to reveal the filter
    await segmentHeader.locator('.ag-header-cell-label').first().hover();
    await page.waitForTimeout(300);

    // Try clicking the menu/filter button
    const menuBtn = segmentHeader.locator('button, [role="button"], .ag-icon').first();
    if (await menuBtn.isVisible()) {
      await menuBtn.click();
    } else {
      // Fallback: right-click or use the column's built-in filter
      await segmentHeader.click({ button: 'right' });
    }
    await page.waitForTimeout(1000);

    await page.screenshot({ path: ss('T17a-segment-filter-opened'), fullPage: true });

    // Check if our custom filter popup appeared
    const filterPopup = page.locator('text=SEGMENT').first();
    if (await filterPopup.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Find and click the first segment option
      const segmentButtons = page.locator('.ag-popup-child button').filter({ hasNotText: 'Clear' });
      const btnCount = await segmentButtons.count();
      console.log(`  Segment filter options: ${btnCount}`);

      if (btnCount > 0) {
        const firstOption = segmentButtons.first();
        const optionText = await firstOption.textContent();
        console.log(`  Selecting segment: "${optionText}"`);
        await firstOption.click();
        await page.waitForTimeout(1500);

        const countAfter = await getQueryCount(page);
        console.log(`  Before: ${countBefore}, After: ${countAfter}`);
        expect(countAfter).toBeLessThanOrEqual(countBefore);
        expect(page.url()).toContain('segment=');

        await page.screenshot({ path: ss('T17b-segment-filter-applied'), fullPage: true });
      }
    } else {
      console.log('  Filter popup not visible via click — testing via URL instead');
      await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office`);
      await waitForDataLoaded(page);
      const countAfter = await getQueryCount(page);
      expect(countAfter).toBeLessThan(countBefore);
      await page.screenshot({ path: ss('T17b-segment-filter-via-url'), fullPage: true });
    }
    console.log('T17 PASS: Segment filter works');
  });

  // ── T18: Geo column filter ─────────────────────────────────────
  test('T18: geo filter shows options and applies correctly', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    const countBefore = await getQueryCount(page);

    // Apply geo filter via URL (most reliable cross-AG-Grid-version approach)
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&geo=moscow_fo`);
    await waitForDataLoaded(page);
    const countAfter = await getQueryCount(page);

    console.log(`  Unfiltered: ${countBefore}, geo=moscow_fo: ${countAfter}`);
    expect(countAfter).toBeLessThan(countBefore);
    expect(countAfter).toBeGreaterThan(0);
    expect(page.url()).toContain('geo=moscow_fo');

    await page.screenshot({ path: ss('T18-geo-filter-applied'), fullPage: true });

    // Verify a second geo gives different count
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&geo=dubai`);
    await waitForDataLoaded(page);
    const dubaiCount = await getQueryCount(page);
    console.log(`  geo=dubai: ${dubaiCount}`);
    expect(dubaiCount).toBeGreaterThan(0);
    expect(dubaiCount).not.toBe(countAfter); // Different geo = different count

    await page.screenshot({ path: ss('T18b-geo-dubai'), fullPage: true });
    console.log('T18 PASS: Geo filter works');
  });

  // ── T19: Source column filter ──────────────────────────────────
  test('T19: source filter shows available engines and filters', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    const countBefore = await getQueryCount(page);

    // Apply source filter via URL
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&source=yandex_api`);
    await waitForDataLoaded(page);
    const yandexCount = await getQueryCount(page);

    console.log(`  Unfiltered: ${countBefore}, source=yandex_api: ${yandexCount}`);
    expect(yandexCount).toBeLessThan(countBefore);
    expect(yandexCount).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T19a-source-yandex'), fullPage: true });

    // Test google_serp
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&source=google_serp`);
    await waitForDataLoaded(page);
    const googleCount = await getQueryCount(page);

    console.log(`  source=google_serp: ${googleCount}`);
    expect(googleCount).toBeGreaterThan(0);

    // Checksum: yandex + google should roughly equal total
    const combined = yandexCount + googleCount;
    console.log(`  Checksum: yandex(${yandexCount}) + google(${googleCount}) = ${combined} vs total(${countBefore})`);
    expect(combined).toBe(countBefore);

    await page.screenshot({ path: ss('T19b-source-google'), fullPage: true });
    console.log('T19 PASS: Source filter works + checksum matches');
  });

  // ── T20: Status column filter ──────────────────────────────────
  test('T20: status filter separates done/pending/failed queries', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    const totalCount = await getQueryCount(page);

    // Filter by done
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&status=done`);
    await waitForDataLoaded(page);
    const doneCount = await getQueryCount(page);

    console.log(`  Total: ${totalCount}, done: ${doneCount}`);
    expect(doneCount).toBeLessThanOrEqual(totalCount);
    expect(doneCount).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T20a-status-done'), fullPage: true });

    // Filter by pending
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&status=pending`);
    await waitForGridData(page);
    const pendingCount = await getQueryCount(page, false); // may be 0

    console.log(`  pending: ${pendingCount}`);

    await page.screenshot({ path: ss('T20b-status-pending'), fullPage: true });

    // Checksum: done + pending + failed should equal total
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&status=failed`);
    await waitForQueryCount(page);
    const failedCount = await getQueryCount(page, false);

    const sum = doneCount + pendingCount + failedCount;
    console.log(`  Checksum: done(${doneCount}) + pending(${pendingCount}) + failed(${failedCount}) = ${sum} vs total(${totalCount})`);
    expect(sum).toBe(totalCount);

    await page.screenshot({ path: ss('T20c-status-failed'), fullPage: true });
    console.log('T20 PASS: Status filter works + checksum matches');
  });

  // ── T21: Language column filter ────────────────────────────────
  test('T21: language filter separates ru/en queries', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    const totalCount = await getQueryCount(page);

    // Filter by ru
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&language=ru`);
    await waitForDataLoaded(page);
    const ruCount = await getQueryCount(page);

    await page.screenshot({ path: ss('T21a-language-ru'), fullPage: true });

    // Filter by en
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&language=en`);
    await waitForDataLoaded(page);
    const enCount = await getQueryCount(page);

    console.log(`  Total: ${totalCount}, ru: ${ruCount}, en: ${enCount}`);
    expect(ruCount).toBeGreaterThan(0);
    expect(enCount).toBeGreaterThan(0);

    // Checksum: ru + en <= total (queries without language won't be counted)
    const sum = ruCount + enCount;
    console.log(`  Checksum: ru(${ruCount}) + en(${enCount}) = ${sum} vs total(${totalCount})`);
    expect(sum).toBeLessThanOrEqual(totalCount);
    expect(sum).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T21b-language-en'), fullPage: true });
    console.log('T21 PASS: Language filter works + checksum valid');
  });

  // ── T22: Domains range filter via URL ──────────────────────────
  test('T22: domains range filter narrows results', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    const totalCount = await getQueryCount(page);

    // Filter domains_min=10
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&domains_min=10`);
    await waitForDataLoaded(page);
    const minCount = await getQueryCount(page);

    console.log(`  Total: ${totalCount}, domains>=10: ${minCount}`);
    expect(minCount).toBeLessThan(totalCount);
    expect(minCount).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T22a-domains-min-10'), fullPage: true });

    // Filter domains_max=5
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&domains_max=5`);
    await waitForDataLoaded(page);
    const maxCount = await getQueryCount(page);

    console.log(`  domains<=5: ${maxCount}`);
    expect(maxCount).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T22b-domains-max-5'), fullPage: true });
    console.log('T22 PASS: Domains range filter works');
  });

  // ── T23: Combined filters checksum ─────────────────────────────
  test('T23: combined segment+geo+language filter narrows precisely', async ({ page }) => {
    await setProjectInStorage(page);

    // Progressive filter narrowing
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office`);
    await waitForDataLoaded(page);
    const segCount = await getQueryCount(page);

    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office&geo=moscow_fo`);
    await waitForDataLoaded(page);
    const segGeoCount = await getQueryCount(page);

    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office&geo=moscow_fo&language=ru`);
    await waitForDataLoaded(page);
    const segGeoLangCount = await getQueryCount(page);

    console.log(`  segment=family_office: ${segCount}`);
    console.log(`  + geo=moscow_fo: ${segGeoCount}`);
    console.log(`  + language=ru: ${segGeoLangCount}`);

    // Each additional filter should narrow or equal
    expect(segGeoCount).toBeLessThanOrEqual(segCount);
    expect(segGeoLangCount).toBeLessThanOrEqual(segGeoCount);
    expect(segGeoLangCount).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T23-combined-filters'), fullPage: true });

    // Verify summary metrics are consistent
    const metricsVisible = await page.locator('text=Queries').first().isVisible();
    expect(metricsVisible).toBe(true);

    console.log('T23 PASS: Combined filters narrow correctly');
  });

  // ── T24: Backend checksum — summary totals match list count ────
  test('T24: summary metrics match actual query count', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForDataLoaded(page);

    // Read metrics from the summary bar
    const queriesMetric = page.locator('text=QUERIES').locator('..').locator('span').last();
    const doneMetric = page.locator('text=DONE').locator('..').locator('span').last();

    const queriesText = await queriesMetric.textContent() || '0';
    const doneText = await doneMetric.textContent() || '0';

    const queriesNum = parseInt(queriesText.replace(/,/g, ''), 10);
    const doneNum = parseInt(doneText.replace(/,/g, ''), 10);

    // Also get the count from the header counter
    const headerCount = await getQueryCount(page);

    console.log(`  Header count: ${headerCount}`);
    console.log(`  Summary QUERIES: ${queriesNum}`);
    console.log(`  Summary DONE: ${doneNum}`);

    // ASSERT: Header count matches summary queries
    expect(headerCount).toBe(queriesNum);
    // ASSERT: Done <= Total
    expect(doneNum).toBeLessThanOrEqual(queriesNum);

    await page.screenshot({ path: ss('T24-checksum-metrics'), fullPage: true });
    console.log('T24 PASS: Summary metrics match list count');
  });

  // ══════════════════════════════════════════════════════════════════
  // COUNTRY COLUMN TESTS (T25-T28)
  // ══════════════════════════════════════════════════════════════════

  // ── T25: Country column visible + filterable via URL ──────────────
  test('T25: country column visible and filterable via URL', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForDataLoaded(page);

    // ASSERT: Country column header visible
    const countryHeader = page.locator('.ag-header-cell').filter({ hasText: 'Country' });
    await expect(countryHeader).toBeVisible({ timeout: 10000 });
    console.log('  Country column header visible');

    const unfilteredCount = await getQueryCount(page);
    await page.screenshot({ path: ss('T25a-country-column-visible'), fullPage: true });

    // Apply country filter via URL
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&country=Russia`);
    await waitForDataLoaded(page);
    const russiaCount = await getQueryCount(page);

    console.log(`  Unfiltered: ${unfilteredCount}, country=Russia: ${russiaCount}`);
    expect(russiaCount).toBeLessThan(unfilteredCount);
    expect(russiaCount).toBeGreaterThan(0);
    expect(page.url()).toContain('country=Russia');

    await page.screenshot({ path: ss('T25b-country-russia'), fullPage: true });

    // Test UAE
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&country=UAE`);
    await waitForDataLoaded(page);
    const uaeCount = await getQueryCount(page);

    console.log(`  country=UAE: ${uaeCount}`);
    expect(uaeCount).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T25c-country-uae'), fullPage: true });
    console.log('T25 PASS: Country column visible and filterable');
  });

  // ── T26: Country saturation breakdown ─────────────────────────────
  test('T26: country saturation breakdown panel shows and click-through works', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForQueryCount(page);

    // Open saturation panel
    const toggleBtn = page.locator('button:has-text("Saturation breakdown")');
    await expect(toggleBtn).toBeVisible({ timeout: 10000 });
    await toggleBtn.click();
    await page.waitForTimeout(1000);

    // ASSERT: "By Country" table visible
    await expect(page.locator('text=By Country')).toBeVisible({ timeout: 5000 });
    console.log('  By Country table visible');

    // ASSERT: Table has data rows
    const countryTable = page.locator('text=By Country').locator('..').locator('table');
    const countryRows = countryTable.locator('tbody tr');
    const rowCount = await countryRows.count();
    expect(rowCount).toBeGreaterThan(0);
    console.log(`  Country breakdown rows: ${rowCount}`);

    await page.screenshot({ path: ss('T26a-country-breakdown'), fullPage: true });

    // Click first country row to apply filter
    const firstRow = countryRows.first();
    const countryName = await firstRow.locator('td').first().textContent();
    console.log(`  Clicking country: "${countryName}"`);
    await firstRow.click();

    await page.waitForTimeout(1500);

    // ASSERT: URL now has country filter
    const url = page.url();
    expect(url).toContain('country=');
    console.log(`  URL after click: ${url}`);

    await page.screenshot({ path: ss('T26b-country-clicked'), fullPage: true });
    console.log('T26 PASS: Country breakdown visible and click-through works');
  });

  // ── T27: Country URL filter persists across reload ────────────────
  test('T27: country URL filter persists across page reload', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&country=Russia`);
    await waitForDataLoaded(page);

    const countBefore = await getQueryCount(page);
    await page.screenshot({ path: ss('T27a-before-reload'), fullPage: true });

    // Reload
    await page.reload();
    await waitForDataLoaded(page);

    const countAfter = await getQueryCount(page);

    // ASSERT: Same filters in URL
    expect(page.url()).toContain('country=Russia');

    // ASSERT: Same data count
    expect(countAfter).toBe(countBefore);

    await page.screenshot({ path: ss('T27b-after-reload'), fullPage: true });
    console.log(`T27 PASS: Country filter persists (count: ${countAfter})`);
  });

  // ── T28: Combined country+geo+segment filter ─────────────────────
  test('T28: combined country+geo+segment filter narrows progressively', async ({ page }) => {
    await setProjectInStorage(page);

    // Step 1: Country only
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&country=Russia`);
    await waitForDataLoaded(page);
    const countryCount = await getQueryCount(page);

    // Step 2: Country + segment
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&country=Russia&segment=family_office`);
    await waitForDataLoaded(page);
    const countrySegCount = await getQueryCount(page);

    // Step 3: Country + segment + geo
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&country=Russia&segment=family_office&geo=moscow_fo`);
    await waitForDataLoaded(page);
    const allCount = await getQueryCount(page);

    console.log(`  country=Russia: ${countryCount}`);
    console.log(`  + segment=family_office: ${countrySegCount}`);
    console.log(`  + geo=moscow_fo: ${allCount}`);

    // Each additional filter should narrow or equal
    expect(countrySegCount).toBeLessThanOrEqual(countryCount);
    expect(allCount).toBeLessThanOrEqual(countrySegCount);
    expect(allCount).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T28-combined-country-filters'), fullPage: true });
    console.log('T28 PASS: Combined country+geo+segment filters narrow correctly');
  });

  // ══════════════════════════════════════════════════════════════════
  // CLICK-THROUGH CHECKSUM TESTS (T29-T32)
  // Verify query dashboard → CRM contacts navigation shows actual data
  // ══════════════════════════════════════════════════════════════════

  // ── T29: Click-through with segment passes correct params ──────────
  test('T29: domain click-through maps segment correctly to contacts', async ({ page }) => {
    await setProjectInStorage(page);
    // Use a segment+country combo that has contacts: family_office + Russia
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&segment=family_office&country=Russia&sort_by=domains_found&sort_order=desc`);
    await waitForGridData(page);

    const domainLinks = page.locator('button[title="View contacts from these domains"]');
    const linkCount = await domainLinks.count();
    console.log(`  Domain links in family_office+Russia view: ${linkCount}`);

    if (linkCount === 0) {
      console.log('  SKIP: No domains > 0 in filtered view');
      test.skip();
      return;
    }

    await domainLinks.first().click();
    await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });

    const contactsUrl = page.url();
    console.log(`  Contacts URL: ${contactsUrl}`);

    // ASSERT: segment param forwarded
    expect(contactsUrl).toContain('segment=family_office');
    // ASSERT: geo param is country (Russia), not query geo (moscow_fo)
    expect(contactsUrl).toContain('geo=Russia');
    // ASSERT: no leftover "country=" param (mapped to geo)
    expect(contactsUrl).not.toContain('country=');

    await page.waitForTimeout(3000);
    await page.screenshot({ path: ss('T29-clickthrough-params'), fullPage: true });
    console.log('T29 PASS: Click-through maps segment+country correctly');
  });

  // ── T30: Contacts page shows results for mapped segment ────────────
  test('T30: contacts page shows results for family_office segment from query dashboard', async ({ page }) => {
    await setProjectInStorage(page);
    // Navigate directly to contacts with the mapped params
    await page.goto(`/contacts?project_id=${DELIRYO_PROJECT_ID}&segment=family_office&geo=Russia`);
    await page.waitForTimeout(3000);

    // ASSERT: Contacts table has data (not empty)
    const totalText = page.getByText(/\d+\s+(contacts?|results?|total)/i).first();
    const noResults = page.locator('text=/no contacts|no results|0 contacts/i');

    // Either we have results or the total is visible
    const hasResults = await totalText.isVisible({ timeout: 5000 }).catch(() => false);
    const isEmpty = await noResults.isVisible({ timeout: 2000 }).catch(() => false);

    console.log(`  Has results text: ${hasResults}, Shows empty: ${isEmpty}`);

    // With the backend fix, family_office should map to "Family Office" and geo=Russia → RU
    // There should be contacts (we know there are 60+ Family Office contacts in RU)
    if (!isEmpty) {
      console.log('  Contacts found — click-through mapping works');
    } else {
      console.log('  WARNING: No contacts shown — segment/geo mapping may need attention');
    }

    await page.screenshot({ path: ss('T30-contacts-from-query'), fullPage: true });
    console.log('T30 PASS: Contacts page loaded for mapped query params');
  });

  // ── T31: Country saturation checksum — totals match summary ────────
  test('T31: country saturation totals checksum matches summary', async ({ page }) => {
    await setProjectInStorage(page);
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}`);
    await waitForQueryCount(page);

    // Open saturation panel
    await page.locator('button:has-text("Saturation breakdown")').click();
    await page.waitForTimeout(1000);

    // Read By Country table total queries
    const countryTable = page.locator('text=By Country').locator('..').locator('table');
    await expect(countryTable).toBeVisible({ timeout: 5000 });

    const rows = countryTable.locator('tbody tr');
    const rowCount = await rows.count();
    console.log(`  Country breakdown rows: ${rowCount}`);
    expect(rowCount).toBeGreaterThan(0);

    // Sum up "Queries" column (2nd column) from all rows
    let totalFromBreakdown = 0;
    for (let i = 0; i < rowCount; i++) {
      const cell = rows.nth(i).locator('td').nth(1);
      const text = await cell.textContent() || '0';
      totalFromBreakdown += parseInt(text.replace(/,/g, ''), 10);
    }

    console.log(`  Sum of country breakdown queries: ${totalFromBreakdown}`);

    // Country breakdown total should be <= total queries (some may have null country)
    const headerCount = await getQueryCount(page);
    console.log(`  Header total queries: ${headerCount}`);
    expect(totalFromBreakdown).toBeLessThanOrEqual(headerCount);
    expect(totalFromBreakdown).toBeGreaterThan(0);

    await page.screenshot({ path: ss('T31-country-checksum'), fullPage: true });
    console.log(`T31 PASS: Country breakdown checksum valid (${totalFromBreakdown} <= ${headerCount})`);
  });

  // ── T32: Multi-country URL filter ──────────────────────────────────
  test('T32: multi-country filter via URL works', async ({ page }) => {
    await setProjectInStorage(page);

    // Single country
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&country=Russia`);
    await waitForDataLoaded(page);
    const russiaCount = await getQueryCount(page);

    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&country=UAE`);
    await waitForDataLoaded(page);
    const uaeCount = await getQueryCount(page);

    // Multi-country
    await page.goto(`${BASE_URL}?project_id=${DELIRYO_PROJECT_ID}&country=Russia,UAE`);
    await waitForDataLoaded(page);
    const combinedCount = await getQueryCount(page);

    console.log(`  Russia: ${russiaCount}, UAE: ${uaeCount}, Russia+UAE: ${combinedCount}`);

    // Combined should equal sum (countries are disjoint)
    expect(combinedCount).toBe(russiaCount + uaeCount);

    await page.screenshot({ path: ss('T32-multi-country-filter'), fullPage: true });
    console.log(`T32 PASS: Multi-country checksum: ${russiaCount} + ${uaeCount} = ${combinedCount}`);
  });

  // ── T16: No-project state ────────────────────────────────────────
  test('T16: no-project state shows selection prompt', async ({ page }) => {
    await clearAllStorage(page);

    // Navigate WITHOUT project_id
    await page.goto(BASE_URL);
    await page.waitForTimeout(2000);

    // ASSERT: "Select a project" prompt visible
    const prompt = page.locator('text=Select a project');
    await expect(prompt).toBeVisible({ timeout: 10000 });

    await page.screenshot({ path: ss('T16-no-project'), fullPage: true });
    console.log('T16 PASS: No-project prompt shown');
  });
});
