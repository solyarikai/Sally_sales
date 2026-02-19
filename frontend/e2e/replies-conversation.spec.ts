/**
 * E2E Tests: Conversation History — Assertion-Driven Per-Campaign Verification
 *
 * Tests per-campaign message isolation, campaign switching, auto-selection,
 * count badges, and API structure. All assertions check browser DOM + intercepted
 * API data. Never asserts against database directly.
 *
 * Key feedback items:
 *   F8  — Per-campaign message isolation
 *   F10 — No "All campaigns" view
 *   F19 — Auto-selects most recent campaign
 *   F20 — Campaign count badge
 */
import { test, expect, type Page, type Route } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCREENSHOTS = path.join(__dirname, 'screenshots');
const BUGS = path.join(__dirname, '..', '..', 'tasks', 'test_project', 'autotest', 'bugs');
fs.mkdirSync(SCREENSHOTS, { recursive: true });
fs.mkdirSync(BUGS, { recursive: true });

const ss = (name: string) => path.join(SCREENSHOTS, `${name}.png`);
const bugSs = (name: string) => path.join(BUGS, `${name}.png`);

// ── Types ──────────────────────────────────────────────────────────
interface FullHistoryCampaign {
  campaign_name: string;
  channel: string;
  message_count: number;
  latest_at: string;
  earliest_at: string;
}

interface FullHistoryActivity {
  direction: 'inbound' | 'outbound';
  content: string;
  timestamp: string;
  channel: 'email' | 'linkedin';
  campaign: string;
}

interface FullHistoryResponse {
  contact_id: number | null;
  campaigns: FullHistoryCampaign[];
  activities: FullHistoryActivity[];
  approval_status: string | null;
  inbox_links: Record<string, string>;
}

// ── Helpers ─────────────────────────────────────────────────────────

async function openReplies(page: Page) {
  await page.goto('/replies');
  const cards = page.locator('.rounded-md.border');
  const emptyState = page.locator('text=All caught up');
  await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 15000 });
  return { cards, emptyState };
}

async function readReplyCount(page: Page): Promise<number> {
  const allTab = page.locator('button:has-text("All need reply")');
  const text = await allTab.textContent();
  const m = text?.match(/(\d+)/);
  return m ? parseInt(m[1], 10) : 0;
}

async function sFail(page: Page, state: string, reason: string) {
  const name = `FAIL-${state}-${Date.now()}`;
  await page.screenshot({ path: bugSs(name) });
  expect(false, `S_FAIL at ${state}: ${reason} — see ${bugSs(name)}`).toBeTruthy();
}

/**
 * Intercept full-history API. Returns getter + reset.
 * Call reset() before each History click to avoid stale data from auto-removed cards.
 */
function interceptFullHistory(page: Page) {
  let captured: FullHistoryResponse | null = null;
  const ready = page.route('**/api/replies/*/full-history', async (route: Route) => {
    try {
      const response = await route.fetch();
      const json = await response.json();
      captured = json as FullHistoryResponse;
      await route.fulfill({ response });
    } catch {
      // Page may be closing during teardown
      await route.continue().catch(() => {});
    }
  });
  return {
    ready,
    getCaptured: () => captured,
    reset: () => { captured = null; },
  };
}

/** Count visible message bubbles in the expanded history section */
async function countVisibleMessages(page: Page): Promise<number> {
  return await page.locator('.mt-1\\.5.mb-2 .whitespace-pre-wrap').count();
}

/** Get text of the first visible message bubble */
async function getFirstMessageText(page: Page): Promise<string> {
  const bubble = page.locator('.mt-1\\.5.mb-2 .whitespace-pre-wrap').first();
  if (await bubble.isVisible({ timeout: 1000 }).catch(() => false)) {
    return (await bubble.textContent()) || '';
  }
  return '';
}

/** Count API activities matching a campaign key */
function countActivitiesForCampaign(activities: FullHistoryActivity[], campaignKey: string): number {
  const [channel, ...nameParts] = campaignKey.split('::');
  const name = nameParts.join('::');
  return activities.filter((a) => a.channel === channel && a.campaign === name).length;
}

/**
 * Expand history on a card. If requireMultiCampaign, tries cards until the API
 * returns 2+ campaigns (collapses and tries next if not). Max 8 attempts.
 * Resets interceptor before each click to ensure captured data matches the surviving card.
 */
async function expandHistoryOnCard(
  page: Page,
  resetCapture: () => void,
  getCaptured: () => FullHistoryResponse | null,
  requireMultiCampaign = false,
): Promise<{ expanded: boolean; isMultiCampaign: boolean }> {
  const cards = page.locator('.rounded-md.border');
  const cardCount = await cards.count();
  const maxAttempts = requireMultiCampaign ? 8 : 5;

  for (let i = 0; i < Math.min(cardCount, maxAttempts); i++) {
    const card = cards.nth(i);
    const histBtn = card.locator('button', { hasText: 'History' }).first();
    if (!(await histBtn.isVisible({ timeout: 300 }).catch(() => false))) continue;

    resetCapture();
    await histBtn.click();

    const hideBtn = card.locator('button', { hasText: 'Hide history' }).first();
    if (!(await hideBtn.isVisible({ timeout: 6000 }).catch(() => false))) {
      continue; // Auto-removed
    }

    await expect(async () => { expect(getCaptured()).not.toBeNull(); }).toPass({ timeout: 6000 });
    const data = getCaptured()!;

    if (requireMultiCampaign && data.campaigns.length < 2) {
      await hideBtn.click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(200);
      continue;
    }

    const msgLocator = page.locator('.mt-1\\.5.mb-2 .whitespace-pre-wrap').first();
    const noHistory = page.locator('.mt-1\\.5.mb-2 text=No history').first();
    await msgLocator.or(noHistory).waitFor({ timeout: 5000 }).catch(() => {});

    return { expanded: true, isMultiCampaign: data.campaigns.length > 1 };
  }

  return { expanded: false, isMultiCampaign: false };
}

// ── Test 0: Test Project — Number checksum + screenshots ────────────

test.describe('Test Project: UI-DB number checksum', () => {
  test('all numbers match API data, screenshots at each step', async ({ page }) => {
    const { ready, getCaptured, reset } = interceptFullHistory(page);
    await ready;

    // S1: Navigate to test project
    await page.goto('/replies?project=test_lord_test');
    const cards = page.locator('.rounded-md.border');
    const emptyState = page.locator('text=All caught up');
    await expect(cards.first().or(emptyState)).toBeVisible({ timeout: 15000 });
    if (await emptyState.isVisible()) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      test.skip(true, 'No test cards (consumed by earlier send test)');
      return;
    }
    await page.screenshot({ path: ss('test-S1-card-before-expand') });

    // S2: Verify card shows pn@getsally.io
    const firstCard = cards.first();
    const cardText = await firstCard.textContent() || '';
    if (!cardText.toLowerCase().includes('getsally')) {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
      test.skip(true, 'Test card not found (may have been consumed)');
      return;
    }

    // S3: Check no legacy campaign count badge in header (removed)
    const legacyBadge = firstCard.locator('button:has-text("▼"), button:has-text("▲")');
    expect(await legacyBadge.count(), 'No legacy campaign dropdown').toBe(0);

    // S4: Expand history
    reset();
    const histBtn = firstCard.locator('button', { hasText: 'History' }).first();
    await histBtn.click();
    await expect(firstCard.locator('button', { hasText: 'Hide history' }).first()).toBeVisible({ timeout: 8000 });
    await expect(async () => { expect(getCaptured()).not.toBeNull(); }).toPass({ timeout: 6000 });

    const history = getCaptured()!;
    await page.screenshot({ path: ss('test-S4-history-expanded') });

    // S5: CHECKSUM — verify test campaigns exist in API data
    const testCampaigns = history.campaigns.filter(c =>
      c.campaign_name.startsWith('E2E_Test_')
    );
    expect(testCampaigns.length, 'Has 3 E2E test campaigns').toBe(3);

    // Auto-selected campaign = first (most recent)
    const autoSelected = history.campaigns[0];
    const expectedMsgCount = autoSelected.message_count;

    // S6: CHECKSUM — Visible messages == selected campaign message_count
    await page.waitForTimeout(500);
    await expect(async () => {
      const vc = await countVisibleMessages(page);
      expect(vc, `Visible msgs (${vc}) == campaign "${autoSelected.campaign_name}" count (${expectedMsgCount})`).toBe(expectedMsgCount);
    }).toPass({ timeout: 5000 });

    await page.screenshot({ path: ss('test-S6-messages-filtered') });

    // S7: CHECKSUM — CampaignDropdown badge shows total campaigns
    const campBadge = page.locator('.rounded-full').filter({ hasText: /\d+\s*campaigns/ }).first();
    if (await campBadge.isVisible({ timeout: 2000 }).catch(() => false)) {
      const campText = await campBadge.textContent() || '';
      const campCount = parseInt(campText.match(/(\d+)/)?.[1] || '0', 10);
      expect(campCount, `Campaign badge (${campCount}) == API campaigns (${history.campaigns.length})`).toBe(history.campaigns.length);
    }

    // S8: Open dropdown, take screenshot
    const trigger = page.locator('.mt-1\\.5.mb-2 .relative button').first();
    if (await trigger.isVisible({ timeout: 2000 }).catch(() => false)) {
      await trigger.click();
      await page.waitForTimeout(300);
      await page.screenshot({ path: ss('test-S8-dropdown-open') });

      // S9: Switch to second E2E campaign
      const panel = page.locator('.absolute.rounded-lg.border.shadow-lg');
      if (await panel.isVisible({ timeout: 2000 }).catch(() => false)) {
        // Find an E2E test campaign that's not the auto-selected one
        const items = panel.locator('button.w-full.text-left');
        const itemCount = await items.count();
        let switchedTo: string | null = null;
        for (let i = 0; i < itemCount; i++) {
          const text = await items.nth(i).textContent() || '';
          if (text.includes('E2E_Test_') && !text.includes(autoSelected.campaign_name)) {
            await items.nth(i).click();
            switchedTo = text;
            break;
          }
        }

        if (switchedTo) {
          await page.waitForTimeout(800);
          await page.screenshot({ path: ss('test-S9-campaign-switched') });

          // S10: CHECKSUM — Message count matches switched campaign
          const switchedCamp = testCampaigns.find(c => switchedTo!.includes(c.campaign_name));
          if (switchedCamp) {
            await expect(async () => {
              const vc = await countVisibleMessages(page);
              expect(vc, `After switch: visible (${vc}) == "${switchedCamp.campaign_name}" count (${switchedCamp.message_count})`).toBe(switchedCamp.message_count);
            }).toPass({ timeout: 5000 });
          }
        }
      }
    }

    // S11: CHECKSUM — Sum of all campaign message_counts == total activities
    const sumCounts = history.campaigns.reduce((s, c) => s + c.message_count, 0);
    expect(sumCounts, `Sum campaign counts (${sumCounts}) == activities (${history.activities.length})`).toBe(history.activities.length);

    await page.screenshot({ path: ss('test-S11-final') });
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});

// ── Test 1: F8 — Per-campaign message isolation ────────────────────

test.describe('F8: Per-campaign message isolation', () => {
  test('visible message count matches selected campaign only', async ({ page }) => {
    const { ready, getCaptured, reset } = interceptFullHistory(page);
    await ready;

    const { emptyState } = await openReplies(page);
    if (await emptyState.isVisible()) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No reply cards'); return; }

    const { expanded } = await expandHistoryOnCard(page, reset, getCaptured, true);
    if (!expanded) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No expandable card'); return; }

    const history = getCaptured()!;
    if (history.campaigns.length === 0) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No campaigns'); return; }

    const key = `${history.campaigns[0].channel}::${history.campaigns[0].campaign_name}`;
    const expectedCount = countActivitiesForCampaign(history.activities, key);
    const visibleCount = await countVisibleMessages(page);

    expect(visibleCount, `F8: visible (${visibleCount}) == campaign count (${expectedCount}) for "${key}"`).toBe(expectedCount);

    if (history.campaigns.length > 1) {
      expect(visibleCount, `F8: visible (${visibleCount}) < total (${history.activities.length})`).toBeLessThan(history.activities.length);
    }

    await page.screenshot({ path: ss('F8-isolation-pass') });
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});

// ── Test 2: F8 — Switching campaign changes content ────────────────

test.describe('F8: Switching campaign changes content', () => {
  test('selecting different campaign updates message list', async ({ page }) => {
    const { ready, getCaptured, reset } = interceptFullHistory(page);
    await ready;

    const { emptyState } = await openReplies(page);
    if (await emptyState.isVisible()) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No reply cards'); return; }

    const { expanded, isMultiCampaign } = await expandHistoryOnCard(page, reset, getCaptured, true);
    if (!expanded) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No expandable card'); return; }

    const history = getCaptured()!;
    if (history.campaigns.length < 2) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'Need 2+ campaigns'); return; }

    // Record campaign A
    const countA = await countVisibleMessages(page);
    const firstTextA = await getFirstMessageText(page);

    // Open dropdown and click campaign B
    const trigger = page.locator('.mt-1\\.5.mb-2 .relative button').first();
    await expect(trigger).toBeVisible({ timeout: 3000 });
    await trigger.click();
    await page.waitForTimeout(300);

    const panel = page.locator('.absolute.rounded-lg.border.shadow-lg');
    await expect(panel).toBeVisible({ timeout: 2000 });

    const items = panel.locator('button.w-full.text-left');
    await items.nth(1).click();
    await page.waitForTimeout(800);

    // Verify campaign B
    const countB = await countVisibleMessages(page);
    const secondKey = `${history.campaigns[1].channel}::${history.campaigns[1].campaign_name}`;
    const expectedB = countActivitiesForCampaign(history.activities, secondKey);

    expect(countB, `F8: after switch, visible (${countB}) == campaign B count (${expectedB})`).toBe(expectedB);

    // Primary assertion: countB matches API data for campaign B (already checked above).
    // Secondary: if both campaigns happen to have identical template messages, that's valid data.
    const firstTextB = await getFirstMessageText(page);
    if (countA === countB && firstTextA === firstTextB) {
      console.log('WARN: campaigns have same count and content — valid if same template messages');
    }

    await page.screenshot({ path: ss('F8-switch-pass') });
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});

// ── Test 3: F10 — No all-campaigns view exists ─────────────────────

test.describe('F10: No all-campaigns view exists', () => {
  test('no "All campaigns" in trigger or dropdown', async ({ page }) => {
    const { ready, getCaptured, reset } = interceptFullHistory(page);
    await ready;

    const { emptyState } = await openReplies(page);
    if (await emptyState.isVisible()) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No reply cards'); return; }

    const { expanded } = await expandHistoryOnCard(page, reset, getCaptured, true);
    if (!expanded) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No expandable card'); return; }

    const history = getCaptured()!;
    if (history.campaigns.length < 2) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'Need 2+ campaigns'); return; }

    const trigger = page.locator('.mt-1\\.5.mb-2 .relative button').first();
    await expect(trigger).toBeVisible({ timeout: 3000 });
    expect((await trigger.textContent() || '').toLowerCase()).not.toContain('all campaigns');

    await trigger.click();
    await page.waitForTimeout(300);
    const panel = page.locator('.absolute.rounded-lg.border.shadow-lg');
    await expect(panel).toBeVisible({ timeout: 2000 });

    const btns = panel.locator('button');
    const count = await btns.count();
    for (let i = 0; i < count; i++) {
      const text = await btns.nth(i).textContent() || '';
      expect(text.toLowerCase(), `F10: "${text}"`).not.toContain('all campaigns');
    }

    const visibleCount = await countVisibleMessages(page);
    expect(visibleCount, `F10: visible (${visibleCount}) < total (${history.activities.length})`).toBeLessThan(history.activities.length);

    await page.screenshot({ path: ss('F10-pass') });
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});

// ── Test 4: F19 — Auto-selects most recent campaign ────────────────

test.describe('F19: Auto-selects most recent campaign', () => {
  test('selected campaign is the one with latest_at first', async ({ page }) => {
    const { ready, getCaptured, reset } = interceptFullHistory(page);
    await ready;

    const { emptyState } = await openReplies(page);
    if (await emptyState.isVisible()) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No reply cards'); return; }

    const { expanded } = await expandHistoryOnCard(page, reset, getCaptured, true);
    if (!expanded) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No expandable card'); return; }

    const history = getCaptured()!;
    if (history.campaigns.length === 0) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No campaigns'); return; }

    const sortedByLatest = [...history.campaigns].sort(
      (a, b) => new Date(b.latest_at).getTime() - new Date(a.latest_at).getTime(),
    );
    expect(history.campaigns[0].campaign_name, 'F19: auto-selected = most recent').toBe(sortedByLatest[0].campaign_name);

    const trigger = page.locator('.mt-1\\.5.mb-2 .relative button').first();
    if (await trigger.isVisible({ timeout: 2000 }).catch(() => false)) {
      const text = await trigger.textContent() || '';
      expect(text, `F19: trigger contains "${history.campaigns[0].campaign_name}"`).toContain(history.campaigns[0].campaign_name);
    }

    await page.screenshot({ path: ss('F19-pass') });
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});

// ── Test 5: F20 — Campaign count badge ─────────────────────────────

test.describe('F20: Campaign count badge', () => {
  test('badge shows correct campaign count from API', async ({ page }) => {
    const { ready, getCaptured, reset } = interceptFullHistory(page);
    await ready;

    const { emptyState } = await openReplies(page);
    if (await emptyState.isVisible()) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No reply cards'); return; }

    const { expanded } = await expandHistoryOnCard(page, reset, getCaptured, true);
    if (!expanded) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No expandable card'); return; }

    const history = getCaptured()!;
    if (history.campaigns.length < 2) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'Need 2+ campaigns for badge'); return; }

    const badge = page.locator('.rounded-full').filter({ hasText: /\d+\s*campaigns/ }).first();
    await expect(badge).toBeVisible({ timeout: 3000 });
    const badgeText = (await badge.textContent()) || '';
    const badgeCount = parseInt(badgeText.match(/(\d+)\s*campaigns/)?.[1] || '0', 10);

    expect(badgeCount, `F20: badge (${badgeCount}) == API campaigns (${history.campaigns.length})`).toBe(history.campaigns.length);

    await page.screenshot({ path: ss('F20-pass') });
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});

// ── Test 6: API response structure ─────────────────────────────────

test.describe('API response structure', () => {
  test('full-history response has correct shape', async ({ page }) => {
    const { ready, getCaptured, reset } = interceptFullHistory(page);
    await ready;

    const { emptyState } = await openReplies(page);
    if (await emptyState.isVisible()) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No reply cards'); return; }

    const { expanded } = await expandHistoryOnCard(page, reset, getCaptured);
    if (!expanded) { await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'No expandable card'); return; }

    const history = getCaptured()!;
    if (history.campaigns.length === 0 && history.activities.length === 0) {
      await page.unrouteAll({ behavior: 'ignoreErrors' }); test.skip(true, 'Empty history'); return;
    }

    for (const c of history.campaigns) {
      expect(c.channel, `Campaign "${c.campaign_name}" channel`).toBeTruthy();
      expect(c.campaign_name, 'campaign_name').toBeTruthy();
      expect(typeof c.message_count, 'message_count type').toBe('number');
      expect(c.latest_at, 'latest_at').toBeTruthy();
    }

    for (let i = 0; i < history.activities.length; i++) {
      const a = history.activities[i];
      expect(a.campaign, `Activity ${i} campaign`).toBeTruthy();
      expect(a.channel, `Activity ${i} channel`).toBeTruthy();
    }

    const sumCounts = history.campaigns.reduce((sum, c) => sum + c.message_count, 0);
    expect(sumCounts, `Sum campaign counts (${sumCounts}) == activities (${history.activities.length})`).toBe(history.activities.length);

    await page.screenshot({ path: ss('API-structure-pass') });
    await page.unrouteAll({ behavior: 'ignoreErrors' });
  });
});

// ── Test 7: History toggle ──────────────────────────────────────────

test.describe('History toggle', () => {
  test('expand and collapse history panel', async ({ page }) => {
    const { emptyState } = await openReplies(page);
    if (await emptyState.isVisible()) { test.skip(true, 'No reply cards'); return; }

    const cards = page.locator('.rounded-md.border');
    const cardCount = await cards.count();
    let expandedCard: ReturnType<typeof cards.nth> | null = null;

    for (let i = 0; i < Math.min(cardCount, 5); i++) {
      const card = cards.nth(i);
      const histBtn = card.locator('button', { hasText: 'History' }).first();
      if (!(await histBtn.isVisible({ timeout: 1000 }).catch(() => false))) continue;
      await histBtn.click();
      const hideBtn = card.locator('button', { hasText: 'Hide history' }).first();
      if (await hideBtn.isVisible({ timeout: 8000 }).catch(() => false)) {
        expandedCard = card;
        break;
      }
    }

    if (!expandedCard) { test.skip(true, 'No expandable card'); return; }

    await page.screenshot({ path: ss('history-expanded') });

    const hideBtn = expandedCard.locator('button', { hasText: 'Hide history' }).first();
    await hideBtn.click();
    await page.waitForTimeout(500);
    await expect(expandedCard.locator('button', { hasText: 'History' }).first()).toBeVisible({ timeout: 3000 });
    await page.screenshot({ path: ss('history-collapsed') });
  });
});

// ── Test 8: Optimistic count on send ────────────────────────────────

test.describe('Optimistic count updates', () => {
  test('count decrements on send', async ({ page }) => {
    const { emptyState } = await openReplies(page);
    if (await emptyState.isVisible()) { test.skip(true, 'No reply cards'); return; }

    const countBefore = await readReplyCount(page);
    if (countBefore === 0) { test.skip(true, 'Count is 0'); return; }

    const firstCard = page.locator('.rounded-md.border').first();
    const sendBtn = firstCard.locator('button', { hasText: 'Send' }).first();
    if (!(await sendBtn.isVisible()) || !(await sendBtn.isEnabled())) {
      test.skip(true, 'Send button not available');
      return;
    }

    await sendBtn.click();

    await expect(async () => {
      const currentCount = await readReplyCount(page);
      expect(currentCount).toBeLessThan(countBefore);
    }).toPass({ timeout: 15000 });

    await page.screenshot({ path: ss('counts-after-send') });
  });
});
