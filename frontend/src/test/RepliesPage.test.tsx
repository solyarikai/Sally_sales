import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { RepliesPage } from '../pages/RepliesPage';
import type {
  ProcessedReply,
  ProcessedReplyStats,
  ConversationMessage,
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
  category: 'interested',
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
  ...overrides,
});

const makeStats = (overrides?: Partial<ProcessedReplyStats>): ProcessedReplyStats => ({
  total: 25,
  by_category: { interested: 10, meeting_request: 5, not_interested: 3, question: 7 },
  by_status: { pending: 15, approved: 8, dismissed: 2 },
  today: 4,
  this_week: 18,
  sent_to_slack: 20,
  pending: 15,
  approved: 8,
  dismissed: 2,
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

// ============ Mock repliesApi ============

const mockGetReplies = vi.fn();
const mockGetReplyStats = vi.fn();
const mockApproveAndSendReply = vi.fn();
const mockDismissReply = vi.fn();
const mockGetConversation = vi.fn();

vi.mock('../api/replies', async () => {
  const actual = await vi.importActual('../api/replies');
  return {
    ...actual,
    repliesApi: {
      getReplies: (...args: unknown[]) => mockGetReplies(...args),
      getReplyStats: (...args: unknown[]) => mockGetReplyStats(...args),
      approveAndSendReply: (...args: unknown[]) => mockApproveAndSendReply(...args),
      dismissReply: (...args: unknown[]) => mockDismissReply(...args),
      getConversation: (...args: unknown[]) => mockGetConversation(...args),
    },
  };
});

// Mock store
vi.mock('../store/appStore', () => ({
  useAppStore: () => ({
    currentProject: null,
  }),
}));

// Mock react-hot-toast
const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();

vi.mock('react-hot-toast', () => ({
  default: {
    success: (...args: unknown[]) => mockToastSuccess(...args),
    error: (...args: unknown[]) => mockToastError(...args),
  },
  Toaster: () => null,
}));

// ============ Helpers ============

function renderRepliesPage() {
  return render(
    <MemoryRouter initialEntries={['/replies']}>
      <Routes>
        <Route path="/replies" element={<RepliesPage />} />
      </Routes>
    </MemoryRouter>
  );
}

// ============ Tests ============

describe('RepliesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: return some replies and stats
    mockGetReplies.mockResolvedValue({
      replies: [makeReply(1), makeReply(2), makeReply(3)],
      total: 3,
      page: 1,
      page_size: 50,
    });
    mockGetReplyStats.mockResolvedValue(makeStats());
    mockGetConversation.mockResolvedValue({ messages: [], contact_id: null });
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
      const interestedBadges = screen.getAllByText(/Interested/);
      expect(interestedBadges.length).toBeGreaterThanOrEqual(1);
      // Subject
      expect(screen.getByText(/Subject 1/)).toBeInTheDocument();
    });

    it('shows stats bar (Total, Pending, Today)', async () => {
      renderRepliesPage();
      await waitFor(() => {
        expect(screen.getByText('Total')).toBeInTheDocument();
        // "Pending" appears in both stats badge and dropdown — use getAllByText
        const pendingElements = screen.getAllByText('Pending');
        expect(pendingElements.length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText('Today')).toBeInTheDocument();
      });
    });

    it('shows empty state when no replies', async () => {
      mockGetReplies.mockResolvedValue({ replies: [], total: 0, page: 1, page_size: 50 });
      renderRepliesPage();
      await waitFor(() => {
        expect(screen.getByText('No replies found')).toBeInTheDocument();
      });
    });
  });

  // ============ Filters ============

  describe('Filters', () => {
    it('"Needs Reply" button toggles and re-fetches', async () => {
      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('Needs Reply')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Needs Reply'));

      await waitFor(() => {
        // getReplies should be called again with needs_reply: true
        const lastCall = mockGetReplies.mock.calls[mockGetReplies.mock.calls.length - 1][0];
        expect(lastCall.needs_reply).toBe(true);
      });
    });

    it('"Moderation" button sets approval_status=pending', async () => {
      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('Moderation')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Moderation'));

      await waitFor(() => {
        const lastCall = mockGetReplies.mock.calls[mockGetReplies.mock.calls.length - 1][0];
        expect(lastCall.approval_status).toBe('pending');
      });
    });

    it('category dropdown filters by category', async () => {
      const user = userEvent.setup();
      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByDisplayValue('All Categories')).toBeInTheDocument();
      });

      await user.selectOptions(screen.getByDisplayValue('All Categories'), 'interested');

      await waitFor(() => {
        const lastCall = mockGetReplies.mock.calls[mockGetReplies.mock.calls.length - 1][0];
        expect(lastCall.category).toBe('interested');
      });
    });
  });

  // ============ Approve & Send ============

  describe('Approve & Send', () => {
    it('click OK button → dry_run=true → toast "Approved (dry run)"', async () => {
      const user = userEvent.setup();
      mockApproveAndSendReply.mockResolvedValue({
        status: 'approved_dry_run',
        dry_run: true,
        reply_id: 1,
        message: 'SmartLead send skipped (DEBUG)',
      });

      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      // Click the OK button on the first reply card
      const okButtons = screen.getAllByTitle('Approve & send');
      await user.click(okButtons[0]);

      await waitFor(() => {
        expect(mockApproveAndSendReply).toHaveBeenCalledWith(1);
        expect(mockToastSuccess).toHaveBeenCalledWith('Approved (dry run)');
      });
    });

    it('click OK button → dry_run=false → toast "Reply sent!"', async () => {
      const user = userEvent.setup();
      mockApproveAndSendReply.mockResolvedValue({
        status: 'approved',
        dry_run: false,
        reply_id: 1,
        lead_email: 'lead-1@example.com',
      });

      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      const okButtons = screen.getAllByTitle('Approve & send');
      await user.click(okButtons[0]);

      await waitFor(() => {
        expect(mockApproveAndSendReply).toHaveBeenCalledWith(1);
        expect(mockToastSuccess).toHaveBeenCalledWith('Reply sent!');
      });
    });

    it('API error → toast.error with detail', async () => {
      const user = userEvent.setup();
      mockApproveAndSendReply.mockRejectedValue({
        response: { data: { detail: 'Reply already approved' } },
      });

      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      const okButtons = screen.getAllByTitle('Approve & send');
      await user.click(okButtons[0]);

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Reply already approved');
      });
    });
  });

  // ============ Dismiss ============

  describe('Dismiss', () => {
    it('click skip button → calls dismissReply → toast "Reply skipped"', async () => {
      const user = userEvent.setup();
      mockDismissReply.mockResolvedValue({
        success: true,
        reply_id: 1,
        approval_status: 'dismissed',
      });

      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      const skipButtons = screen.getAllByTitle('Skip');
      await user.click(skipButtons[0]);

      await waitFor(() => {
        expect(mockDismissReply).toHaveBeenCalledWith(1);
        expect(mockToastSuccess).toHaveBeenCalledWith('Reply skipped');
      });
    });

    it('shows "Skipped" badge for dismissed replies', async () => {
      mockGetReplies.mockResolvedValue({
        replies: [makeReply(1, { approval_status: 'dismissed' })],
        total: 1,
        page: 1,
        page_size: 50,
      });

      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('Skipped')).toBeInTheDocument();
      });
    });
  });

  // ============ Detail Panel & Conversation ============

  describe('Detail Panel & Conversation', () => {
    it('click reply card → opens detail panel → calls getConversation', async () => {
      const user = userEvent.setup();
      mockGetConversation.mockResolvedValue({
        messages: makeConversation(2),
        contact_id: 42,
      });

      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      // Click on the reply card (the lead name text)
      await user.click(screen.getByText('First1 Last1'));

      await waitFor(() => {
        expect(screen.getByText('Reply Details')).toBeInTheDocument();
        expect(mockGetConversation).toHaveBeenCalledWith(1);
      });
    });

    it('shows inbound (blue) and outbound (gray) message bubbles', async () => {
      const user = userEvent.setup();
      mockGetConversation.mockResolvedValue({
        messages: [
          { direction: 'outbound', channel: 'email', subject: null, body: 'Hey there!', activity_at: '2026-02-10T10:00:00Z', source: 'smartlead', activity_type: 'email_sent', extra_data: null },
          { direction: 'inbound', channel: 'email', subject: null, body: 'I am interested!', activity_at: '2026-02-10T11:00:00Z', source: 'smartlead', activity_type: 'email_replied', extra_data: null },
        ],
        contact_id: 42,
      });

      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      await user.click(screen.getByText('First1 Last1'));

      await waitFor(() => {
        expect(screen.getByText('Hey there!')).toBeInTheDocument();
        expect(screen.getByText('I am interested!')).toBeInTheDocument();
      });

      // Check visual distinction: inbound has blue background, outbound has neutral
      const inboundBubble = screen.getByText('I am interested!').closest('div[class*="bg-blue"]');
      expect(inboundBubble).toBeTruthy();

      const outboundBubble = screen.getByText('Hey there!').closest('div[class*="bg-neutral"]');
      expect(outboundBubble).toBeTruthy();
    });

    it('shows "No conversation history" when empty', async () => {
      const user = userEvent.setup();
      mockGetConversation.mockResolvedValue({ messages: [], contact_id: null });

      renderRepliesPage();

      await waitFor(() => {
        expect(screen.getByText('First1 Last1')).toBeInTheDocument();
      });

      await user.click(screen.getByText('First1 Last1'));

      await waitFor(() => {
        expect(screen.getByText('No conversation history found')).toBeInTheDocument();
      });
    });
  });
});
