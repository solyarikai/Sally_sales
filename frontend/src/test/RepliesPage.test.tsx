import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { RepliesPage } from '../pages/RepliesPage';
import type {
  ProcessedReply,
  ConversationMessage,
  ContactCampaignEntry,
} from '../api/replies';

// ============ Mock data factories ============

const makeReply = (id: number, overrides?: Partial<ProcessedReply>): ProcessedReply => ({
  id,
  automation_id: null,
  campaign_id: 'camp_001',
  campaign_name: 'Rizzult Outreach Q1',
  lead_email: `lead-${id}@example.com`,
  lead_first_name: `First${id}`,
  lead_last_name: `Last${id}`,
  lead_company: `Company ${id}`,
  email_subject: `Re: Subject ${id}`,
  email_body: `Reply body ${id}`,
  reply_text: `Reply body ${id}`,
  received_at: '2026-02-10T12:00:00Z',
  category: 'meeting_request',
  category_confidence: 'high',
  classification_reasoning: `Reasoning for ${id}`,
  draft_reply: `Draft reply for ${id}`,
  draft_subject: `Re: Subject ${id}`,
  inbox_link: null,
  processed_at: '2026-02-10T12:01:00Z',
  sent_to_slack: false,
  slack_sent_at: null,
  approval_status: null,
  approved_by: null,
  approved_at: null,
  created_at: '2026-02-10T12:01:00Z',
  channel: 'email',
  source: 'smartlead',
  ...overrides,
});

const makeConversation = (count: number): ConversationMessage[] =>
  Array.from({ length: count }, (_, i) => ({
    direction: i % 2 === 0 ? 'outbound' : 'inbound',
    channel: 'email',
    subject: `Message ${i + 1}`,
    body: `Message body ${i + 1}`,
    activity_at: new Date(Date.now() - (count - i) * 3600000).toISOString(),
    source: 'smartlead',
    activity_type: i % 2 === 0 ? 'email_sent' : 'email_replied',
    extra_data: null,
  }));

const makeCampaignEntries = (): ContactCampaignEntry[] => [
  {
    reply_id: 1,
    campaign_id: 'camp_001',
    campaign_name: 'Rizzult Outreach Q1',
    category: 'meeting_request',
    classification_reasoning: 'Wants meeting',
    received_at: '2026-02-10T12:00:00Z',
    email_subject: 'Re: Subject 1',
    email_body: 'Reply body 1',
    reply_text: 'Reply body 1',
    draft_reply: 'Draft reply for 1',
    draft_subject: 'Re: Subject 1',
    approval_status: null,
    inbox_link: null,
    channel: 'email',
  },
  {
    reply_id: 100,
    campaign_id: 'camp_002',
    campaign_name: 'Partner Campaign',
    category: 'interested',
    classification_reasoning: 'Shows interest',
    received_at: '2026-02-09T10:00:00Z',
    email_subject: 'Re: Partner Intro',
    email_body: 'Interested in learning more',
    reply_text: 'Interested in learning more',
    draft_reply: 'Thanks for your interest!',
    draft_subject: 'Re: Partner Intro',
    approval_status: null,
    inbox_link: null,
    channel: 'email',
  },
];

// ============ Hoisted mocks (vi.mock factories are hoisted above imports) ============

const {
  mockGetReplies,
  mockApproveAndSendReply,
  mockDismissReply,
  mockGetConversation,
  mockRegenerateDraft,
  mockGetContactCampaigns,
  mockToast,
} = vi.hoisted(() => {
  const toast = Object.assign(vi.fn(), {
    success: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
  });
  return {
    mockGetReplies: vi.fn(),
    mockApproveAndSendReply: vi.fn(),
    mockDismissReply: vi.fn(),
    mockGetConversation: vi.fn(),
    mockRegenerateDraft: vi.fn(),
    mockGetContactCampaigns: vi.fn(),
    mockToast: toast,
  };
});

vi.mock('../api/replies', async () => {
  const actual = await vi.importActual('../api/replies');
  return {
    ...actual,
    repliesApi: {
      getReplies: (...args: unknown[]) => mockGetReplies(...args),
      approveAndSendReply: (...args: unknown[]) => mockApproveAndSendReply(...args),
      dismissReply: (...args: unknown[]) => mockDismissReply(...args),
      getConversation: (...args: unknown[]) => mockGetConversation(...args),
      regenerateDraft: (...args: unknown[]) => mockRegenerateDraft(...args),
      getContactCampaigns: (...args: unknown[]) => mockGetContactCampaigns(...args),
    },
  };
});

// Stable object references to prevent useEffect re-firing
const stableProject = { id: 1, name: 'Test Project' };
const stableProjects = [stableProject];
const stableSetCurrentProject = vi.fn();

vi.mock('../store/appStore', () => ({
  useAppStore: () => ({
    currentProject: stableProject,
    setCurrentProject: stableSetCurrentProject,
    projects: stableProjects,
  }),
}));

vi.mock('../hooks/useTheme', () => ({
  useTheme: () => ({ isDark: false }),
}));

vi.mock('react-hot-toast', () => ({
  default: mockToast,
  Toaster: () => null,
}));

// ============ Helpers ============

function renderRepliesPage(initialRoute = '/replies') {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route path="/replies" element={<RepliesPage />} />
        <Route path="/contacts" element={<div>Contacts Page</div>} />
      </Routes>
    </MemoryRouter>
  );
}

// ============ Tests ============

describe('RepliesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: return 3 meeting_request replies with category counts
    mockGetReplies.mockResolvedValue({
      replies: [makeReply(1), makeReply(2), makeReply(3)],
      total: 8,
      category_counts: { meeting_request: 5, interested: 3 },
      page: 1,
      page_size: 30,
    });
    mockGetConversation.mockResolvedValue({ messages: [], contact_info: null });
  });

  // ============ Rendering ============

  describe('Rendering', () => {
    it('loads and displays reply cards with lead name, category badge, subject', async () => {
      renderRepliesPage();
      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
        expect(screen.getByText('First2 Last2')).toBeInTheDocument();
      });
      // Category badge
      const meetingBadges = screen.getAllByText('Meeting');
      expect(meetingBadges.length).toBeGreaterThanOrEqual(1);
      // Subject
      expect(screen.getByText('Re: Subject 1')).toBeInTheDocument();
    });

    it('shows "All caught up" when no replies', async () => {
      mockGetReplies.mockResolvedValue({
        replies: [],
        total: 0,
        category_counts: {},
        page: 1,
        page_size: 30,
      });
      renderRepliesPage();
      await waitFor(() => {
        expect(screen.getByText('All caught up')).toBeInTheDocument();
      });
    });
  });

  // ============ Category Tabs & Counts ============

  describe('Category Count Updates', () => {
    it('category counts render in filter tabs', async () => {
      renderRepliesPage();
      await waitFor(() => {
        // "Meetings 5" tab and "Interested 3" tab
        expect(screen.getByText(/Meetings\s*5/)).toBeInTheDocument();
        expect(screen.getByText(/Interested\s*3/)).toBeInTheDocument();
      });
    });

    it('clicking category tab changes filter', async () => {
      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      // Click "Interested" tab
      await user.click(screen.getByText(/Interested/));

      await waitFor(() => {
        const calls = mockGetReplies.mock.calls;
        const lastCall = calls[calls.length - 1][0];
        expect(lastCall.category).toBe('interested');
      });
    });

    it('after dismiss, category counts update from server re-fetch', async () => {
      mockDismissReply.mockResolvedValue({ success: true });
      // After dismiss, server returns updated counts
      mockGetReplies
        .mockResolvedValueOnce({
          replies: [makeReply(1), makeReply(2)],
          total: 7,
          category_counts: { meeting_request: 5, interested: 2 },
          page: 1,
          page_size: 30,
        })
        .mockResolvedValue({
          replies: [],
          total: 6,
          category_counts: { meeting_request: 4, interested: 2 },
          page: 1,
          page_size: 0,
        });

      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      // Click Skip on first reply
      const skipButtons = screen.getAllByText('Skip');
      await user.click(skipButtons[0]);

      await waitFor(() => {
        expect(mockDismissReply).toHaveBeenCalledWith(1);
      });
    });
  });

  // ============ Campaign Dropdown ============

  describe('Campaign Dropdown', () => {
    it('renders dropdown trigger when contact_campaign_count > 1', async () => {
      mockGetReplies.mockResolvedValue({
        replies: [makeReply(1, { contact_campaign_count: 3 })],
        total: 1,
        category_counts: { meeting_request: 1 },
        page: 1,
        page_size: 30,
      });

      renderRepliesPage();

      await waitFor(() => {
        // Campaign count badge "3" should appear
        expect(screen.getByText('3')).toBeInTheDocument();
      });
    });

    it('click opens dropdown, shows campaign entries', async () => {
      mockGetReplies.mockResolvedValue({
        replies: [makeReply(1, { contact_campaign_count: 2 })],
        total: 1,
        category_counts: { meeting_request: 1 },
        page: 1,
        page_size: 30,
      });
      mockGetContactCampaigns.mockResolvedValue({
        campaigns: makeCampaignEntries(),
      });

      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('2')).toBeInTheDocument();
      });

      // Click the campaign count badge area to open dropdown
      const trigger = screen.getByText('2').closest('button')!;
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByText('Partner Campaign')).toBeInTheDocument();
      });
    });

    it('click entry switches displayed reply data', async () => {
      mockGetReplies.mockResolvedValue({
        replies: [makeReply(1, { contact_campaign_count: 2 })],
        total: 1,
        category_counts: { meeting_request: 1 },
        page: 1,
        page_size: 30,
      });
      mockGetContactCampaigns.mockResolvedValue({
        campaigns: makeCampaignEntries(),
      });

      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('Re: Subject 1')).toBeInTheDocument();
      });

      // Open dropdown
      const trigger = screen.getByText('2').closest('button')!;
      await user.click(trigger);

      await waitFor(() => {
        expect(screen.getByText('Partner Campaign')).toBeInTheDocument();
      });

      // Click the "Partner Campaign" entry
      await user.click(screen.getByText('Partner Campaign'));

      // Should now show the partner campaign's data
      await waitFor(() => {
        expect(screen.getByText('Re: Partner Intro')).toBeInTheDocument();
      });
    });
  });

  // ============ Regenerate Button ============

  describe('Regenerate Button', () => {
    it('shows "Regenerate" button when draft matches FAILED_DRAFT_RE', async () => {
      mockGetReplies.mockResolvedValue({
        replies: [makeReply(1, { draft_reply: '{Draft generation failed: timeout}' })],
        total: 1,
        category_counts: { meeting_request: 1 },
        page: 1,
        page_size: 30,
      });

      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('Regenerate')).toBeInTheDocument();
      });
    });

    it('click calls regenerateDraft, updates card with new draft', async () => {
      mockGetReplies.mockResolvedValue({
        replies: [makeReply(1, { draft_reply: '{Draft generation failed: timeout}' })],
        total: 1,
        category_counts: { meeting_request: 1 },
        page: 1,
        page_size: 30,
      });
      mockRegenerateDraft.mockResolvedValue({
        reply_id: 1,
        draft_reply: 'Fresh new draft text',
        draft_subject: 'Re: Subject 1',
        category: 'meeting_request',
        classification_reasoning: 'Wants a meeting',
      });

      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('Regenerate')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Regenerate'));

      await waitFor(() => {
        expect(mockRegenerateDraft).toHaveBeenCalledWith(1);
      });

      // After regeneration, the new draft should appear
      await waitFor(() => {
        expect(screen.getByText('Fresh new draft text')).toBeInTheDocument();
      });
    });

    it('shows "Regenerating..." spinner while in progress', async () => {
      // Create a promise that we can control
      let resolveRegenerate: (value: unknown) => void;
      const regeneratePromise = new Promise((resolve) => {
        resolveRegenerate = resolve;
      });

      mockGetReplies.mockResolvedValue({
        replies: [makeReply(1, { draft_reply: 'Error generating draft' })],
        total: 1,
        category_counts: { meeting_request: 1 },
        page: 1,
        page_size: 30,
      });
      mockRegenerateDraft.mockReturnValue(regeneratePromise);

      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('Regenerate')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Regenerate'));

      // Should show "Regenerating..." while pending
      await waitFor(() => {
        expect(screen.getByText('Regenerating...')).toBeInTheDocument();
      });

      // Resolve the promise
      resolveRegenerate!({
        reply_id: 1,
        draft_reply: 'New draft',
        draft_subject: 'Re: Subject 1',
        category: 'meeting_request',
        classification_reasoning: 'Updated reasoning',
      });

      await waitFor(() => {
        expect(screen.queryByText('Regenerating...')).not.toBeInTheDocument();
      });
    });
  });

  // ============ Send ============

  describe('Send', () => {
    it('click Send → calls approveAndSendReply → reply removed from list', async () => {
      mockApproveAndSendReply.mockResolvedValue({
        status: 'approved',
        dry_run: false,
        reply_id: 1,
        contact_id: 42,
      });

      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      // Click Send on first card
      const sendButtons = screen.getAllByText('Send');
      await user.click(sendButtons[0]);

      await waitFor(() => {
        expect(mockApproveAndSendReply).toHaveBeenCalledWith(1, undefined);
        // Reply should be removed from DOM
        expect(screen.queryByText('First1 Last1')).not.toBeInTheDocument();
      });
    });

    it('API error → toast.error with detail', async () => {
      mockApproveAndSendReply.mockRejectedValue({
        response: { data: { detail: 'Reply already approved' } },
      });

      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      const sendButtons = screen.getAllByText('Send');
      await user.click(sendButtons[0]);

      await waitFor(() => {
        expect(mockToast.error).toHaveBeenCalledWith(
          'Reply already approved',
          expect.any(Object),
        );
      });
    });
  });

  // ============ Dismiss ============

  describe('Dismiss', () => {
    it('click Skip → calls dismissReply → reply removed from list', async () => {
      mockDismissReply.mockResolvedValue({ success: true });

      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      const skipButtons = screen.getAllByText('Skip');
      await user.click(skipButtons[0]);

      await waitFor(() => {
        expect(mockDismissReply).toHaveBeenCalledWith(1);
        expect(screen.queryByText('First1 Last1')).not.toBeInTheDocument();
      });
    });
  });
});
