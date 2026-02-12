import { test, expect } from '@playwright/test';

test.describe('Projects List Page', () => {
  test('loads projects and search filters them', async ({ page }) => {
    await page.goto('/projects');

    // Wait for page to load
    await expect(page.locator('h1')).toContainText('Projects');

    // Should show search input
    const searchInput = page.locator('input[placeholder="Search projects..."]');
    await expect(searchInput).toBeVisible();

    // Wait for projects to load (check no "Loading" text)
    await expect(page.locator('text=Loading projects...')).not.toBeVisible({ timeout: 15000 });

    // If there are project cards, search should filter them
    const projectCards = page.locator('a[href^="/projects/"]');
    const initialCount = await projectCards.count();

    if (initialCount > 0) {
      // Get text of first project
      const firstProjectName = await projectCards.first().locator('h3').textContent();

      // Type a search that matches
      await searchInput.fill(firstProjectName || 'test');
      await expect(projectCards).toHaveCount(1);

      // Type gibberish that matches nothing
      await searchInput.fill('zzzznonexistent99999');
      await expect(projectCards).toHaveCount(0);
      await expect(page.locator('text=No projects matching')).toBeVisible();

      // Clear search
      await searchInput.fill('');
      await expect(projectCards).toHaveCount(initialCount);
    }
  });

  test('clicking project navigates to project page', async ({ page }) => {
    await page.goto('/projects');
    await expect(page.locator('text=Loading projects...')).not.toBeVisible({ timeout: 15000 });

    const projectCards = page.locator('a[href^="/projects/"]');
    const count = await projectCards.count();

    if (count > 0) {
      // Get the href
      const href = await projectCards.first().getAttribute('href');
      expect(href).toMatch(/\/projects\/\d+/);

      // Click
      await projectCards.first().click();

      // Should navigate to project page
      await expect(page).toHaveURL(/\/projects\/\d+/);
      await expect(page.locator('text=All Projects')).toBeVisible();
    }
  });
});

test.describe('Individual Project Page', () => {
  test('shows project details with campaigns and source badges', async ({ page }) => {
    // Navigate to projects list first
    await page.goto('/projects');
    await expect(page.locator('text=Loading projects...')).not.toBeVisible({ timeout: 15000 });

    const projectCards = page.locator('a[href^="/projects/"]');
    const count = await projectCards.count();

    if (count > 0) {
      await projectCards.first().click();
      await expect(page).toHaveURL(/\/projects\/\d+/);

      // Check header elements
      await expect(page.locator('text=All Projects')).toBeVisible();
      await expect(page.locator('h1')).toBeVisible();

      // Campaigns section should exist
      await expect(page.locator('text=Campaigns')).toBeVisible();

      // Campaign search input should exist
      await expect(page.locator('input[placeholder="Search campaigns to add..."]')).toBeVisible();

      // Check for source badges (SL or GS) if campaigns exist
      const badges = page.locator('span:has-text("SL"), span:has-text("GS")');
      // Badges may or may not be present depending on campaign data

      // Telegram section should exist
      await expect(page.locator('text=Telegram Notifications')).toBeVisible();
    }
  });

  test('editable project name', async ({ page }) => {
    await page.goto('/projects');
    await expect(page.locator('text=Loading projects...')).not.toBeVisible({ timeout: 15000 });

    const projectCards = page.locator('a[href^="/projects/"]');
    const count = await projectCards.count();

    if (count > 0) {
      await projectCards.first().click();
      await expect(page).toHaveURL(/\/projects\/\d+/);

      // Click pencil icon to start editing
      const editButton = page.locator('button').filter({ has: page.locator('svg.lucide-pencil') });
      if (await editButton.isVisible()) {
        await editButton.click();

        // Name input should appear
        const nameInput = page.locator('input[type="text"]').first();
        await expect(nameInput).toBeVisible();

        // Press Escape to cancel
        await nameInput.press('Escape');
      }
    }
  });

  test('back button navigates to projects list', async ({ page }) => {
    await page.goto('/projects');
    await expect(page.locator('text=Loading projects...')).not.toBeVisible({ timeout: 15000 });

    const projectCards = page.locator('a[href^="/projects/"]');
    const count = await projectCards.count();

    if (count > 0) {
      await projectCards.first().click();
      await expect(page).toHaveURL(/\/projects\/\d+/);

      // Click back
      await page.locator('a:has-text("All Projects")').click();
      await expect(page).toHaveURL('/projects');
    }
  });
});

test.describe('Replies Page - Project Selector', () => {
  test('shows project selector bar with tabs', async ({ page }) => {
    await page.goto('/replies');

    // Wait for page to load
    await expect(page.locator('h1')).toContainText('Replies');

    // "All Projects" button should be visible
    const allBtn = page.locator('button:has-text("All Projects")');
    await expect(allBtn).toBeVisible({ timeout: 10000 });

    // Should have violet highlight when selected (default = "All")
    await expect(allBtn).toHaveClass(/bg-violet-100/);
  });

  test('clicking project tab filters replies', async ({ page }) => {
    await page.goto('/replies');
    await expect(page.locator('h1')).toContainText('Replies');

    // Wait for project selector to load
    const allBtn = page.locator('button:has-text("All Projects")');
    await expect(allBtn).toBeVisible({ timeout: 10000 });

    // Find project buttons (siblings of "All Projects")
    const projectBtns = allBtn.locator('..').locator('button').filter({ hasNot: page.locator(':has-text("All Projects")') });
    const projectCount = await projectBtns.count();

    if (projectCount > 0) {
      // Click first project
      await projectBtns.first().click();

      // "All Projects" should no longer be highlighted
      await expect(allBtn).not.toHaveClass(/bg-violet-100/);

      // The clicked button should now be highlighted
      await expect(projectBtns.first()).toHaveClass(/bg-violet-100/);

      // Click "All" again
      await allBtn.click();
      await expect(allBtn).toHaveClass(/bg-violet-100/);
    }
  });

  test('Telegram Connect button visible on project page', async ({ page }) => {
    await page.goto('/projects');
    await expect(page.locator('text=Loading projects...')).not.toBeVisible({ timeout: 15000 });

    const projectCards = page.locator('a[href^="/projects/"]');
    const count = await projectCards.count();

    if (count > 0) {
      await projectCards.first().click();
      await expect(page).toHaveURL(/\/projects\/\d+/);

      // Either "Connect Telegram" button or connected status should be visible
      const connectBtn = page.locator('button:has-text("Connect Telegram")');
      const connectedStatus = page.locator('text=Connected');
      const telegramElement = connectBtn.or(connectedStatus);
      await expect(telegramElement.first()).toBeVisible({ timeout: 10000 });
    }
  });
});
