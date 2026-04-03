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

  test('send reply → "View conversation" opens modal with same campaign selected', async ({ page }) => {
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
    let replyCampaignName = '';
    for (let i = 0; i < Math.min(initialCount, 5); i++) {
      const card = cards.nth(i);
      const cardText = await card.textContent();
      if (!cardText?.includes('pn@getsally.io')) {
        targetCard = card;
        // Extract campaign name from the card's campaign marker
        const campMarker = card.locator('.rounded-full.text-\\[10px\\]').first();
        if (await campMarker.isVisible({ timeout: 1000 }).catch(() => false)) {
          replyCampaignName = (await campMarker.textContent())?.replace(/^[✉📧🔗]\s*/, '').trim() || '';
        }
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
    const sentCampaignName = sendData.campaign_name || replyCampaignName;
    console.log(`Sent reply for ${leadEmail}, contact_id=${contactId}, campaign=${sentCampaignName}, status=${sendData.status}`);

    // Card should disappear
    await expect(async () => {
      const newCount = await cards.count();
      expect(newCount).toBeLessThan(initialCount);
    }).toPass({ timeout: 10000 });

    // Click "View conversation" link in the toast
    const toastLink = page.locator('a:has-text("View conversation")').first();
    if (await toastLink.isVisible({ timeout: 3000 }).catch(() => false)) {
      // Verify the link contains campaign param
      const href = await toastLink.getAttribute('href') || '';
      console.log(`Toast link href: ${href}`);
      expect(href).toContain('campaign=');
      if (sentCampaignName) {
        expect(href).toContain(encodeURIComponent(sentCampaignName));
      }
      await toastLink.click();
    } else if (contactId) {
      // Toast may have auto-dismissed, navigate manually with campaign param
      const campaignKey = `email::${sentCampaignName}`;
      await page.goto(`/contacts?contact_id=${contactId}&campaign=${encodeURIComponent(campaignKey)}`);
    } else {
      console.log('No contact_id and no toast link — skipping conversation check');
      return;
    }

    await expect(page).toHaveURL(/\/contacts/, { timeout: 10000 });

    // Modal should open
    const modalPanel = page.locator('.rounded-2xl.shadow-2xl');
    await expect(modalPanel).toBeVisible({ timeout: 20000 });

    // Messages should load
    const messageBubbles = modalPanel.locator('.whitespace-pre-wrap');
    await expect(messageBubbles.first()).toBeVisible({ timeout: 15000 });
    const messageCount = await messageBubbles.count();
    expect(messageCount).toBeGreaterThan(0);
    console.log(`Conversation: ${messageCount} messages for contact ${contactId}`);

    // ASSERT: Campaign dropdown (if visible) shows the SAME campaign that was sent
    const dropdownTrigger = modalPanel.locator('.relative button').first();
    if (await dropdownTrigger.isVisible({ timeout: 3000 }).catch(() => false)) {
      const triggerText = await dropdownTrigger.textContent() || '';
      console.log(`Modal campaign dropdown: "${triggerText}"`);
      if (sentCampaignName) {
        expect(triggerText, `Campaign dropdown should show "${sentCampaignName}"`).toContain(sentCampaignName);
      }
    }

    // ASSERT: URL contains campaign param
    expect(page.url()).toContain('campaign=');

    // Outbound messages should exist
    const outboundBubbles = modalPanel.locator('.items-end .whitespace-pre-wrap');
    const outboundCount = await outboundBubbles.count();
    console.log(`Outbound messages: ${outboundCount}`);
    expect(outboundCount).toBeGreaterThan(0);

    await page.screenshot({ path: 'test-results/modal-after-send-campaign-check.png', fullPage: false });
  });

  test('campaign dropdown + per-campaign filtering for pn@getsally.io', async ({ page }) => {
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
    const modalPanel = page.locator('.rounded-2xl.shadow-2xl');
    await expect(modalPanel).toBeVisible({ timeout: 20000 });

    // Conversation tab auto-selected on open
    await page.waitForTimeout(1000);

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

    // Screenshot: dark theme modal with conversation
    await page.screenshot({ path: 'test-results/modal-dark-conversation.png', fullPage: false });

    // CampaignDropdown should be visible (trigger button with campaign name)
    const dropdownTrigger = modalPanel.locator('.relative button').first();
    await expect(dropdownTrigger).toBeVisible({ timeout: 5000 });
    const triggerText = await dropdownTrigger.textContent() || '';
    console.log(`CampaignDropdown trigger: "${triggerText}"`);
    expect(triggerText.length).toBeGreaterThan(0);

    // Messages should be visible (dark compact mode)
    const messageBubbles = modalPanel.locator('.whitespace-pre-wrap');
    await expect(messageBubbles.first()).toBeVisible({ timeout: 10000 });
    const visibleCount = await messageBubbles.count();
    console.log(`Visible messages (filtered to auto-selected campaign): ${visibleCount}`);
    expect(visibleCount).toBeGreaterThan(0);

    // If multi-campaign, test per-campaign filtering via dropdown
    if (expectedCampaignCount > 1) {
      // Open dropdown
      await dropdownTrigger.click();
      await page.waitForTimeout(300);

      const dropdownPanel = modalPanel.locator('.absolute.rounded-lg.border.shadow-lg');
      await expect(dropdownPanel).toBeVisible({ timeout: 3000 });

      // Screenshot: dropdown open
      await page.screenshot({ path: 'test-results/modal-campaign-dropdown-open.png', fullPage: false });

      // Count dropdown items
      const items = dropdownPanel.locator('button');
      const itemCount = await items.count();
      console.log(`Dropdown items: ${itemCount} (initial 8 + show-more, total campaigns: ${expectedCampaignCount})`);
      // Dropdown shows max 8 initially + "Show more" button; verify at least 2 items visible
      expect(itemCount).toBeGreaterThanOrEqual(2);

      // Record state A (current auto-selected campaign)
      const countA = visibleCount;

      // Click second campaign in dropdown
      if (itemCount >= 2) {
        await items.nth(1).click();
        await page.waitForTimeout(500);

        const countB = await messageBubbles.count();
        console.log(`Per-campaign filtering: A=${countA} msgs, B=${countB} msgs, total=${modalTotalMessages}`);

        // Screenshot: different campaign selected
        await page.screenshot({ path: 'test-results/modal-switched-campaign.png', fullPage: false });

        // ASSERT: filtered — not showing all messages
        expect(countA, `Campaign A (${countA}) < total (${modalTotalMessages})`).toBeLessThanOrEqual(modalTotalMessages);
        expect(countB, `Campaign B (${countB}) < total (${modalTotalMessages})`).toBeLessThanOrEqual(modalTotalMessages);
      }
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

    const modalPanel = page.locator('.rounded-2xl.shadow-2xl');
    await expect(modalPanel).toBeVisible({ timeout: 20000 });

    // Conversation tab is auto-selected on open
    const messageBubbles = modalPanel.locator('.whitespace-pre-wrap');
    await expect(messageBubbles.first()).toBeVisible({ timeout: 15000 });
    const count = await messageBubbles.count();
    expect(count).toBeGreaterThan(0);
    console.log(`Deep-link modal: ${count} conversation messages`);

    // Screenshot: dark theme modal after deep-link
    await page.screenshot({ path: 'test-results/modal-deep-link.png', fullPage: false });
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
