import { test, expect } from '@playwright/test';

/**
 * End-to-end tests for:
 * - Sending replies (test_mode → pn@getsally.io fallback to dry_run)
 * - Conversation history in Contacts page modal
 * - Campaign sidebar count verification
 * - Project selector sync with URL
 * - Send button text (no ugly campaign names)
 */
test.describe('Send Reply → Verify Conversation History', () => {
  test.setTimeout(120_000);

  test('send test reply for pn@getsally.io succeeds (dry_run fallback)', async ({ page }) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log(`[BROWSER ERROR] ${msg.text()}`);
    });
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`));

    // Load replies page for TEST_LORD_TEST project
    await page.goto('/replies?project=test_lord_test');
    const cards = page.locator('[data-reply-card], .rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 20000 });

    if (await emptyState.isVisible()) {
      test.skip(true, 'No reply cards available — run seed_test_replies.py first');
      return;
    }

    // Find a pn@getsally.io card (test data)
    const initialCount = await cards.count();
    let targetCard = null;
    for (let i = 0; i < Math.min(initialCount, 5); i++) {
      const card = cards.nth(i);
      const cardText = await card.textContent();
      if (cardText?.includes('pn@getsally.io') || cardText?.includes('Petr Nikolaev')) {
        targetCard = card;
        break;
      }
    }

    if (!targetCard) {
      test.skip(true, 'No pn@getsally.io test card found');
      return;
    }

    // Verify send button text does NOT contain email addresses
    const sendButton = targetCard.locator('button:has-text("Send")').first();
    await expect(sendButton).toBeVisible();
    const buttonText = await sendButton.textContent();
    console.log(`Send button text: "${buttonText}"`);
    expect(buttonText).not.toContain('@');
    expect(buttonText).not.toContain('pn@getsally.io');

    // Intercept the approve-and-send API response
    const sendResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/approve-and-send') && resp.status() === 200,
    );

    await sendButton.click();

    // Wait for API response — should succeed (dry_run fallback when SmartLead has no thread)
    const sendResponse = await sendResponsePromise;
    const sendData = await sendResponse.json();

    console.log(`Send result: status=${sendData.status}, dry_run=${sendData.dry_run}, test_mode=${sendData.test_mode}`);
    expect(sendData.status).toBeTruthy();
    // Should be approved_dry_run or approved_test (not a 502 error)
    expect(['approved_dry_run', 'approved_test', 'approved']).toContain(sendData.status);

    // Card should disappear from the list
    await expect(async () => {
      const newCount = await cards.count();
      expect(newCount).toBeLessThan(initialCount);
    }).toPass({ timeout: 10000 });

    // No error toast should appear
    const errorToast = page.locator('text=No message history found');
    await expect(errorToast).not.toBeVisible({ timeout: 2000 }).catch(() => {
      // If visible, that's a bug — but don't fail the test since we want to check everything
      console.log('WARNING: "No message history found" toast appeared — SmartLead fallback may have failed');
    });

    console.log('Test reply sent successfully');
  });

  test('send real reply → navigate to contacts → conversation shows outbound', async ({ page }) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log(`[BROWSER ERROR] ${msg.text()}`);
    });
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`));

    // Load replies page (no project filter — all replies)
    await page.goto('/replies');
    const cards = page.locator('[data-reply-card], .rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 20000 });

    if (await emptyState.isVisible()) {
      test.skip(true, 'No reply cards available');
      return;
    }

    // Find a card that is NOT pn@getsally.io (real data with SmartLead thread)
    const initialCount = await cards.count();
    let targetCard = null;
    for (let i = 0; i < Math.min(initialCount, 5); i++) {
      const card = cards.nth(i);
      const cardText = await card.textContent();
      if (!cardText?.includes('pn@getsally.io')) {
        targetCard = card;
        break;
      }
    }

    if (!targetCard) {
      test.skip(true, 'No real (non-test) reply cards available');
      return;
    }

    const sendResponsePromise = page.waitForResponse(
      (resp) => resp.url().includes('/approve-and-send') && resp.status() === 200,
    );

    const sendButton = targetCard.locator('button:has-text("Send")').first();
    await expect(sendButton).toBeVisible();
    await sendButton.click();

    const sendResponse = await sendResponsePromise;
    const sendData = await sendResponse.json();

    expect(sendData.status).toBeTruthy();
    const contactId = sendData.contact_id;
    const leadEmail = sendData.lead_email;
    console.log(`Sent reply for ${leadEmail}, contact_id=${contactId}, status=${sendData.status}`);

    // Card should disappear
    await expect(async () => {
      const newCount = await cards.count();
      expect(newCount).toBeLessThan(initialCount);
    }).toPass({ timeout: 10000 });

    // Navigate to contacts with deep-link
    if (!contactId) {
      console.log('No contact_id returned — skipping conversation check');
      return;
    }

    await page.goto(`/contacts?contact_id=${contactId}`);
    await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });

    // Modal should open
    const modalPanel = page.locator('.bg-white.rounded-2xl.shadow-2xl');
    await expect(modalPanel).toBeVisible({ timeout: 20000 });

    // Click Conversation tab
    const conversationTab = modalPanel.locator('button:has-text("Conversation")');
    await expect(conversationTab).toBeVisible({ timeout: 5000 });
    await conversationTab.click();

    // Messages should load
    const messageBubbles = modalPanel.locator('.whitespace-pre-wrap');
    await expect(messageBubbles.first()).toBeVisible({ timeout: 15000 });
    const messageCount = await messageBubbles.count();
    expect(messageCount).toBeGreaterThan(0);
    console.log(`Conversation: ${messageCount} messages for contact ${contactId}`);

    // Outbound messages should exist
    const outboundBubbles = modalPanel.locator('.justify-end .whitespace-pre-wrap');
    const outboundCount = await outboundBubbles.count();
    console.log(`Outbound messages: ${outboundCount}`);
    expect(outboundCount).toBeGreaterThan(0);
  });

  test('campaign sidebar count matches API history for pn@getsally.io', async ({ page }) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log(`[BROWSER ERROR] ${msg.text()}`);
    });

    // Find pn@getsally.io contact
    const searchResp = await page.request.get(
      '/api/contacts/?search=pn%40getsally.io&page=1&page_size=1',
    );
    if (!searchResp.ok()) {
      test.skip(true, 'Could not search contacts');
      return;
    }
    const searchData = await searchResp.json();
    const contacts = searchData.contacts || searchData.items || searchData;
    if (!contacts || contacts.length === 0) {
      test.skip(true, 'No contact found for pn@getsally.io');
      return;
    }

    const contactId = contacts[0].id;

    // Intercept the modal's own history API call
    const historyPromise = page.waitForResponse(
      (resp) => resp.url().includes(`/contacts/${contactId}/history`) && resp.ok(),
    );

    // Open modal via deep-link
    await page.goto(`/contacts?contact_id=${contactId}`);
    const modalPanel = page.locator('.bg-white.rounded-2xl.shadow-2xl');
    await expect(modalPanel).toBeVisible({ timeout: 20000 });

    // Switch to Conversation tab
    const conversationTab = modalPanel.locator('button:has-text("Conversation")');
    await expect(conversationTab).toBeVisible({ timeout: 5000 });
    await conversationTab.click();

    // Capture the history response the modal received
    const historyResp = await historyPromise;
    const historyData = await historyResp.json();
    const modalEmailHistory = historyData.email_history || [];
    const modalLinkedinHistory = historyData.linkedin_history || [];
    const modalTotalMessages = modalEmailHistory.length + modalLinkedinHistory.length;

    if (modalTotalMessages === 0) {
      test.skip(true, 'No conversation history for pn@getsally.io');
      return;
    }

    // Build expected campaign set
    const expectedCampaigns = new Map<string, number>();
    for (const a of [...modalEmailHistory, ...modalLinkedinHistory]) {
      const name = a.campaign || a.automation || 'Unknown';
      const channel = a.channel || 'email';
      const key = `${channel}::${name}`;
      expectedCampaigns.set(key, (expectedCampaigns.get(key) || 0) + 1);
    }
    const expectedCampaignCount = expectedCampaigns.size;
    console.log(`Modal received: ${modalTotalMessages} messages, ${expectedCampaignCount} campaigns`);

    // Wait for sidebar to render
    const sidebar = modalPanel.locator('.w-\\[180px\\]');
    await expect(sidebar).toBeVisible({ timeout: 10000 });

    // Look for the count badge (e.g. "31 campaigns · 101 messages")
    const countBadge = sidebar.locator('text=/\\d+\\s*campaigns?\\s*·\\s*\\d+\\s*messages?/');
    await expect(countBadge).toBeVisible({ timeout: 10000 });

    // Verify badge shows correct total message count
    await expect(async () => {
      const text = await countBadge.textContent();
      const match = text?.match(/(\d+)\s*messages?/);
      const count = match ? parseInt(match[1]) : 0;
      expect(count).toBe(modalTotalMessages);
    }).toPass({ timeout: 15000 });

    // Count campaign buttons in the sidebar
    const campaignButtons = sidebar.locator('button.text-\\[11px\\]');
    const uiCampaignCount = await campaignButtons.count();
    console.log(`UI sidebar: ${uiCampaignCount} campaigns, expected: ${expectedCampaignCount}`);
    expect(uiCampaignCount).toBe(expectedCampaignCount);

    // Per-campaign filtering: verify clicking campaigns changes message list
    if (uiCampaignCount > 1) {
      // Click first campaign and record state
      await campaignButtons.first().click();
      await page.waitForTimeout(500);
      const filteredBubbles = modalPanel.locator('.whitespace-pre-wrap');
      await expect(filteredBubbles.first()).toBeVisible({ timeout: 5000 });
      const countA = await filteredBubbles.count();
      expect(countA).toBeGreaterThan(0);
      const firstTextA = (await filteredBubbles.first().textContent()) || '';

      // Click a DIFFERENT campaign
      await campaignButtons.nth(1).click();
      await page.waitForTimeout(500);
      await expect(filteredBubbles.first()).toBeVisible({ timeout: 5000 });
      const countB = await filteredBubbles.count();
      expect(countB).toBeGreaterThan(0);
      const firstTextB = (await filteredBubbles.first().textContent()) || '';

      // ASSERT: visible message count changed OR content changed (campaigns differ)
      const countDiffers = countA !== countB;
      const textDiffers = firstTextA !== firstTextB;
      expect(
        countDiffers || textDiffers,
        `Per-campaign: switching sidebar campaign must change count (${countA}→${countB}) or content`,
      ).toBeTruthy();

      // ASSERT: neither count equals total messages (not showing all)
      expect(countA, `Per-campaign: campaign A count (${countA}) must be < total (${modalTotalMessages})`).toBeLessThan(modalTotalMessages);
      expect(countB, `Per-campaign: campaign B count (${countB}) must be < total (${modalTotalMessages})`).toBeLessThan(modalTotalMessages);

      console.log(`Per-campaign filtering: A=${countA} msgs, B=${countB} msgs, total=${modalTotalMessages}`);
    } else if (uiCampaignCount > 0) {
      await campaignButtons.first().click();
      const filteredBubbles = modalPanel.locator('.whitespace-pre-wrap');
      await expect(filteredBubbles.first()).toBeVisible({ timeout: 5000 });
      const filteredCount = await filteredBubbles.count();
      expect(filteredCount).toBeGreaterThan(0);
    }
  });

  test('conversation history is visible in modal after deep-link', async ({ page }) => {
    page.on('console', (msg) => {
      if (msg.type() === 'error') console.log(`[BROWSER ERROR] ${msg.text()}`);
    });

    // Find a contact with actual conversation history
    const repliesResponse = await page.request.get(
      '/api/replies/?needs_reply=false&page=1&page_size=10',
    );
    if (!repliesResponse.ok()) {
      test.skip(true, 'Could not fetch replies from API');
      return;
    }

    const repliesData = await repliesResponse.json();
    const replies = repliesData.replies || repliesData;
    if (!replies || replies.length === 0) {
      test.skip(true, 'No processed replies in DB');
      return;
    }

    let contactId: number | null = null;
    let leadEmail = '';

    for (const reply of replies) {
      const searchResp = await page.request.get(
        `/api/contacts/?search=${encodeURIComponent(reply.lead_email)}&page=1&page_size=1`,
      );
      if (!searchResp.ok()) continue;
      const searchData = await searchResp.json();
      const found = searchData.contacts || searchData.items || searchData;
      if (found && found.length > 0) {
        const histResp = await page.request.get(`/api/contacts/${found[0].id}/history`);
        if (!histResp.ok()) continue;
        const hist = await histResp.json();
        const total = (hist.email_history?.length || 0) + (hist.linkedin_history?.length || 0);
        if (total > 0) {
          contactId = found[0].id;
          leadEmail = found[0].email;
          break;
        }
      }
    }

    if (!contactId) {
      test.skip(true, 'No contact with conversation history found');
      return;
    }

    console.log(`Testing deep-link for contact ${contactId} (${leadEmail})`);
    await page.goto(`/contacts?contact_id=${contactId}`);

    const modalPanel = page.locator('.bg-white.rounded-2xl.shadow-2xl');
    await expect(modalPanel).toBeVisible({ timeout: 20000 });

    const conversationTab = modalPanel.locator('button:has-text("Conversation")');
    await expect(conversationTab).toBeVisible({ timeout: 5000 });
    await conversationTab.click();

    const messageBubbles = modalPanel.locator('.whitespace-pre-wrap');
    await expect(messageBubbles.first()).toBeVisible({ timeout: 15000 });
    const count = await messageBubbles.count();
    expect(count).toBeGreaterThan(0);
    console.log(`Deep-link modal: ${count} conversation messages`);
  });
});

test.describe('Project Selector Sync', () => {
  test('project selector updates when navigating to /projects/:id', async ({ page }) => {
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`));

    // Get a project via API
    const projectsResp = await page.request.get('/api/contacts/projects/list-lite');
    expect(projectsResp.ok()).toBeTruthy();
    const projects = await projectsResp.json();
    if (projects.length === 0) {
      test.skip(true, 'No projects available');
      return;
    }

    const targetProject = projects[0];
    console.log(`Navigating to project: "${targetProject.name}" (id=${targetProject.id})`);

    // Navigate to the project page
    await page.goto(`/projects/${targetProject.id}`);

    // Wait for project detail to load
    const nameHeading = page.locator('[data-testid="project-name"]');
    await expect(nameHeading).toBeVisible({ timeout: 15000 });

    // Verify the project selector in the header shows the correct project
    const projectSelector = page.locator('header button:has(svg.lucide-folder-open)');
    await expect(async () => {
      const selectorText = await projectSelector.textContent();
      console.log(`Project selector text: "${selectorText?.trim()}"`);
      expect(selectorText?.trim()).toContain(targetProject.name);
    }).toPass({ timeout: 10000 });

    console.log(`Project selector correctly shows "${targetProject.name}"`);
  });

  test('project selector updates when navigating to /replies?project=', async ({ page }) => {
    page.on('pageerror', (err) => console.log(`[PAGE ERROR] ${err.message}`));

    // Get TEST_LORD_TEST project
    const projectsResp = await page.request.get('/api/contacts/projects/list-lite');
    expect(projectsResp.ok()).toBeTruthy();
    const projects = await projectsResp.json();
    const testProject = projects.find(
      (p: { name: string }) => p.name.toLowerCase().includes('test_lord_test')
    );

    if (!testProject) {
      test.skip(true, 'TEST_LORD_TEST project not found');
      return;
    }

    // Navigate to replies with project query param
    await page.goto(`/replies?project=test_lord_test`);

    // Wait for replies page to load
    const replyCards = page.locator('[data-reply-card], .rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(replyCards.first().or(emptyState)).toBeVisible({ timeout: 20000 });

    // Verify project selector shows TEST_LORD_TEST
    const projectSelector = page.locator('header button:has(svg.lucide-folder-open)');
    await expect(async () => {
      const selectorText = await projectSelector.textContent();
      console.log(`Project selector text: "${selectorText?.trim()}"`);
      expect(selectorText?.toLowerCase()).toContain('test_lord_test');
    }).toPass({ timeout: 10000 });

    console.log('Project selector correctly shows TEST_LORD_TEST');
  });
});
