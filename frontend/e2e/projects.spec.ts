import { test, expect } from '@playwright/test';

/**
 * E2E tests for /projects list page and /projects/:id detail page.
 * Verifies pages load, render project cards, and individual project
 * shows campaigns section.
 */
test.describe('Projects Pages', () => {
  test('projects list page loads and shows project cards', async ({ page }) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log(`[BROWSER ERROR] ${msg.text()}`);
    });
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`));

    // Navigate to projects page
    await page.goto('/projects');
    await expect(page).toHaveURL(/\/projects/);

    // Wait for loading to finish — either project cards or empty state
    const projectsList = page.locator('[data-testid="projects-list"]');
    const emptyState = page.locator('text=No projects yet');
    const loadingState = page.locator('[data-testid="projects-loading"]');

    // Loading state should appear briefly then disappear
    await expect(loadingState.or(projectsList).or(emptyState)).toBeVisible({ timeout: 10000 });

    // Wait for loading to finish
    await expect(loadingState).not.toBeVisible({ timeout: 15000 });

    // Should show either project cards or empty state
    await expect(projectsList.or(emptyState)).toBeVisible({ timeout: 10000 });

    if (await emptyState.isVisible()) {
      console.log('No projects found — empty state displayed correctly');
      return;
    }

    // Verify project cards are rendered
    const cards = page.locator('[data-testid="project-card"]');
    const cardCount = await cards.count();
    expect(cardCount).toBeGreaterThan(0);
    console.log(`Projects page shows ${cardCount} project cards`);

    // Verify first card has a name (not empty)
    const firstName = await cards.first().locator('h3').textContent();
    expect(firstName?.trim().length).toBeGreaterThan(0);
    console.log(`First project: "${firstName?.trim()}"`);

    // Verify "Projects" heading is visible
    const heading = page.locator('h1:has-text("Projects")');
    await expect(heading).toBeVisible();

    // Verify search input exists
    const searchInput = page.locator('input[placeholder="Search projects..."]');
    await expect(searchInput).toBeVisible();

    // Verify "New Project" button exists
    const newProjectBtn = page.locator('button:has-text("New Project")');
    await expect(newProjectBtn).toBeVisible();
  });

  test('search filters projects list', async ({ page }) => {
    await page.goto('/projects');

    const projectsList = page.locator('[data-testid="projects-list"]');
    await expect(projectsList).toBeVisible({ timeout: 15000 });

    const cards = page.locator('[data-testid="project-card"]');
    const initialCount = await cards.count();

    if (initialCount < 2) {
      test.skip(true, 'Need at least 2 projects to test search filtering');
      return;
    }

    // Get a project name to search for
    const targetName = await cards.first().locator('h3').textContent();
    if (!targetName) {
      test.skip(true, 'Could not read project name');
      return;
    }

    // Type the search query
    const searchInput = page.locator('input[placeholder="Search projects..."]');
    await searchInput.fill(targetName.trim());

    // Filtered results should show fewer or equal cards
    await expect(async () => {
      const filteredCount = await cards.count();
      expect(filteredCount).toBeLessThanOrEqual(initialCount);
      expect(filteredCount).toBeGreaterThan(0);
    }).toPass({ timeout: 5000 });

    console.log(`Search "${targetName?.trim()}" filtered ${initialCount} → ${await cards.count()} projects`);
  });

  test('clicking project card navigates to project detail', async ({ page }) => {
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`));

    await page.goto('/projects');

    const projectsList = page.locator('[data-testid="projects-list"]');
    await expect(projectsList).toBeVisible({ timeout: 15000 });

    const cards = page.locator('[data-testid="project-card"]');
    const cardCount = await cards.count();
    if (cardCount === 0) {
      test.skip(true, 'No projects to click');
      return;
    }

    // Get project name before clicking
    const projectName = (await cards.first().locator('h3').textContent())?.trim();
    console.log(`Clicking project: "${projectName}"`);

    // Click first project card
    await cards.first().click();

    // Should navigate to /projects/:id
    await expect(page).toHaveURL(/\/projects\/\d+/, { timeout: 10000 });

    // Project detail page should show the project name
    const nameHeading = page.locator('[data-testid="project-name"]');
    await expect(nameHeading).toBeVisible({ timeout: 15000 });
    const displayedName = await nameHeading.textContent();
    expect(displayedName?.trim()).toBe(projectName);
    console.log(`Project detail page loaded: "${displayedName?.trim()}"`);

    // Campaigns section should be visible
    const campaignsSection = page.locator('[data-testid="campaigns-section"]');
    await expect(campaignsSection).toBeVisible({ timeout: 10000 });
    console.log('Campaigns section visible');

    // "All Projects" back link should be visible
    const backLink = page.locator('a:has-text("All Projects")');
    await expect(backLink).toBeVisible();
  });

  test('project detail page shows campaign badges', async ({ page }) => {
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`));

    // Find a project with campaigns via API
    const projectsResp = await page.request.get('/api/contacts/projects/list-lite');
    expect(projectsResp.ok()).toBeTruthy();
    const projects = await projectsResp.json();

    const projectWithCampaigns = projects.find(
      (p: { campaign_filters: string[] }) => (p.campaign_filters || []).length > 0
    );

    if (!projectWithCampaigns) {
      test.skip(true, 'No project with campaigns found');
      return;
    }

    console.log(`Testing project "${projectWithCampaigns.name}" (id=${projectWithCampaigns.id}) with ${projectWithCampaigns.campaign_filters.length} campaigns`);

    // Navigate directly to the project detail page
    await page.goto(`/projects/${projectWithCampaigns.id}`);

    // Wait for project name to appear
    const nameHeading = page.locator('[data-testid="project-name"]');
    await expect(nameHeading).toBeVisible({ timeout: 15000 });

    // Campaigns section
    const campaignsSection = page.locator('[data-testid="campaigns-section"]');
    await expect(campaignsSection).toBeVisible({ timeout: 10000 });

    // Campaign badges should be rendered
    const badges = page.locator('[data-testid="campaign-badge"]');
    await expect(badges.first()).toBeVisible({ timeout: 10000 });

    const badgeCount = await badges.count();
    console.log(`UI shows ${badgeCount} campaign badges, API has ${projectWithCampaigns.campaign_filters.length}`);
    expect(badgeCount).toBe(projectWithCampaigns.campaign_filters.length);

    // Each badge should have a source indicator (SL, GS, or ?)
    for (let i = 0; i < Math.min(badgeCount, 5); i++) {
      const badge = badges.nth(i);
      const text = await badge.textContent();
      expect(text).toBeTruthy();
      console.log(`  Badge ${i + 1}: ${text?.trim()}`);
    }
    if (badgeCount > 5) {
      console.log(`  ... and ${badgeCount - 5} more`);
    }

    // Campaign search input should exist
    const searchInput = page.locator('input[placeholder="Search campaigns to add..."]');
    await expect(searchInput).toBeVisible();
  });

  test('project detail back link returns to projects list', async ({ page }) => {
    // Navigate to first project
    await page.goto('/projects');
    const projectsList = page.locator('[data-testid="projects-list"]');
    await expect(projectsList).toBeVisible({ timeout: 15000 });

    const cards = page.locator('[data-testid="project-card"]');
    if ((await cards.count()) === 0) {
      test.skip(true, 'No projects available');
      return;
    }

    await cards.first().click();
    await expect(page).toHaveURL(/\/projects\/\d+/, { timeout: 10000 });

    // Wait for project detail page to fully load before looking for back link
    const nameHeading = page.locator('[data-testid="project-name"]');
    await expect(nameHeading).toBeVisible({ timeout: 15000 });

    // Click "All Projects" back link
    const backLink = page.locator('a:has-text("All Projects")');
    await expect(backLink).toBeVisible({ timeout: 10000 });
    await backLink.click();

    // Should navigate back to /projects
    await expect(page).toHaveURL(/\/projects$/, { timeout: 10000 });
    await expect(projectsList).toBeVisible({ timeout: 15000 });
    console.log('Back navigation works correctly');
  });

  test('projects list API count matches UI count', async ({ page }) => {
    // Get expected count from API
    const projectsResp = await page.request.get('/api/contacts/projects/list-lite');
    expect(projectsResp.ok()).toBeTruthy();
    const apiProjects = await projectsResp.json();
    const apiCount = apiProjects.length;
    console.log(`API returns ${apiCount} projects`);

    if (apiCount === 0) {
      test.skip(true, 'No projects in API');
      return;
    }

    // Load page
    await page.goto('/projects');
    const projectsList = page.locator('[data-testid="projects-list"]');
    await expect(projectsList).toBeVisible({ timeout: 15000 });

    // Count cards
    const cards = page.locator('[data-testid="project-card"]');
    const uiCount = await cards.count();

    console.log(`UI shows ${uiCount} project cards, API has ${apiCount}`);
    expect(uiCount).toBe(apiCount);
  });

  test('projects page content is visible in dark mode', async ({ page }) => {
    // Set dark mode in localStorage before navigating
    await page.addInitScript(() => {
      localStorage.setItem('leadgen-theme', 'dark');
    });

    await page.goto('/projects');
    const projectsList = page.locator('[data-testid="projects-list"]');
    const emptyState = page.locator('text=No projects yet');
    await expect(projectsList.or(emptyState)).toBeVisible({ timeout: 15000 });

    if (await emptyState.isVisible()) {
      test.skip(true, 'No projects for dark mode test');
      return;
    }

    // Verify heading is visible (not invisible text on dark bg)
    const heading = page.locator('h1:has-text("Projects")');
    await expect(heading).toBeVisible();
    const headingBox = await heading.boundingBox();
    expect(headingBox).toBeTruthy();
    console.log(`Dark mode: heading visible at y=${headingBox?.y}`);

    // Verify project cards are visible
    const cards = page.locator('[data-testid="project-card"]');
    const firstCard = cards.first();
    await expect(firstCard).toBeVisible();
    const cardBox = await firstCard.boundingBox();
    expect(cardBox).toBeTruthy();
    console.log(`Dark mode: first card visible at y=${cardBox?.y}`);

    // Verify search input is visible
    const searchInput = page.locator('input[placeholder="Search projects..."]');
    await expect(searchInput).toBeVisible();
    console.log('Dark mode: all elements visible');
  });
});
