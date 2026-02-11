import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ContactDetailModal } from '../components/ContactDetailModal';
import type { Contact } from '../api/contacts';

// ── Mock data ────────────────────────────────────────────────────────

const mockContact: Contact = {
  id: 74301,
  email: 'pn@getsally.io',
  first_name: 'Peter',
  last_name: 'Nikolaev',
  company_name: 'GetSally',
  job_title: 'CEO',
  source: 'smartlead',
  status: 'replied',
  has_replied: true,
  smartlead_id: 'sl-12345',
  getsales_id: 'gs-67890',
  created_at: '2025-01-15T10:00:00Z',
  updated_at: '2025-01-20T14:00:00Z',
  campaigns: [
    { id: '100', name: 'tg-bot outreach', source: 'smartlead' },
    { id: '200', name: 'Sally intro', source: 'smartlead' },
  ],
};

const mockHistoryResponse = {
  contact_id: 74301,
  email_history: [
    {
      id: 1,
      type: 'email_sent',
      direction: 'outbound',
      subject: 'Intro to GetSally',
      body: 'Hi Peter, wanted to reach out...',
      snippet: 'Hi Peter, wanted to reach out...',
      channel: 'email',
      source: 'smartlead',
      campaign: 'tg-bot outreach',
      timestamp: '2025-01-16T10:16:00Z',
    },
    {
      id: 2,
      type: 'email_reply',
      direction: 'inbound',
      subject: 'Re: Intro to GetSally',
      body: 'Thanks, sounds interesting!',
      snippet: 'Thanks, sounds interesting!',
      channel: 'email',
      source: 'smartlead',
      campaign: 'tg-bot outreach',
      timestamp: '2025-01-16T10:21:00Z',
    },
    {
      id: 3,
      type: 'email_sent',
      direction: 'outbound',
      subject: 'Sally follow up',
      body: 'Following up on our conversation',
      snippet: 'Following up on our conversation',
      channel: 'email',
      source: 'smartlead',
      campaign: 'Sally intro',
      timestamp: '2025-01-17T09:00:00Z',
    },
  ],
  linkedin_history: [
    {
      id: 1001,
      type: 'linkedin_message',
      direction: 'outbound',
      body: 'Hey Peter, connecting on LI',
      snippet: 'Hey Peter, connecting on LI',
      channel: 'linkedin',
      source: 'getsales',
      automation: 'LI connect flow',
      timestamp: '2025-01-15T08:00:00Z',
    },
  ],
  summary: {
    total_activities: 4,
    email_count: 3,
    linkedin_count: 1,
    has_email_history: true,
    has_linkedin_history: true,
    smartlead_id: 'sl-12345',
    getsales_id: 'gs-67890',
  },
};

const mockContactList: Contact[] = [
  mockContact,
  {
    ...mockContact,
    id: 74302,
    email: 'jane@example.com',
    first_name: 'Jane',
    last_name: 'Doe',
  },
  {
    ...mockContact,
    id: 74303,
    email: 'bob@example.com',
    first_name: 'Bob',
    last_name: 'Smith',
  },
];

// ── Mocks ──────────────────────────────────────────────────────────

vi.mock('../api/contacts', () => ({
  contactsApi: {
    generateReply: vi.fn().mockResolvedValue({
      has_reply: true,
      cached: false,
      category: 'interested',
      draft_subject: 'Re: Intro',
      draft_body: 'Thanks for your interest! Let me share more details.',
      channel: 'email',
      reply_text: 'Thanks, sounds interesting!',
    }),
  },
}));

// Mock global fetch for history + projects
function setupFetchMock() {
  const fetchMock = vi.fn((url: string) => {
    if (typeof url === 'string' && url.includes('/history')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(mockHistoryResponse),
      });
    }
    if (typeof url === 'string' && url.includes('/projects/list')) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([{ id: 1, name: 'Test Project' }]),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

// ── Tests ──────────────────────────────────────────────────────────

describe('ContactDetailModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupFetchMock();
  });

  // Test 1: Renders conversation with campaign sidebar
  it('renders conversation tab with campaign sidebar listing campaigns', async () => {
    render(
      <ContactDetailModal
        contact={mockContact}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    // Switch to conversation tab
    const conversationTab = screen.getByText('Conversation');
    await userEvent.click(conversationTab);

    // Wait for history to load — sidebar should show "All" button and campaign names
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument();
    });

    // Campaign names appear in sidebar as truncated buttons
    await waitFor(() => {
      // Use getAllByText since campaign names appear in sidebar + conversation dividers
      const tgBotMatches = screen.getAllByText('tg-bot outreach');
      expect(tgBotMatches.length).toBeGreaterThanOrEqual(1);

      const sallyMatches = screen.getAllByText('Sally intro');
      expect(sallyMatches.length).toBeGreaterThanOrEqual(1);
    });
  });

  // Test 2: Campaign filtering
  it('filters messages when a campaign is selected in sidebar', async () => {
    render(
      <ContactDetailModal
        contact={mockContact}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    // Switch to conversation tab
    await userEvent.click(screen.getByText('Conversation'));

    // Wait for messages to render
    await waitFor(() => {
      expect(screen.getByText('Hi Peter, wanted to reach out...')).toBeInTheDocument();
    });

    // Initially all messages visible
    expect(screen.getByText('Following up on our conversation')).toBeInTheDocument();

    // Click "Sally intro" in the sidebar - get the truncated button version
    const sallyButtons = screen.getAllByText('Sally intro');
    // The sidebar button is the one inside a button with truncate class
    const sidebarButton = sallyButtons.find(el => el.closest('button'));
    expect(sidebarButton).toBeTruthy();
    await userEvent.click(sidebarButton!.closest('button')!);

    // Should show Sally intro messages, not tg-bot ones
    await waitFor(() => {
      expect(screen.getByText('Following up on our conversation')).toBeInTheDocument();
      expect(screen.queryByText('Hi Peter, wanted to reach out...')).not.toBeInTheDocument();
    });
  });

  // Test 3: Channel indicators
  it('shows email and LinkedIn channel sections in sidebar', async () => {
    render(
      <ContactDetailModal
        contact={mockContact}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await userEvent.click(screen.getByText('Conversation'));

    // Wait for history to load
    await waitFor(() => {
      expect(screen.getByText('All')).toBeInTheDocument();
    });

    // The sidebar has uppercase "EMAIL" and "LINKEDIN" section headers
    // but rendered as text "Email" and "LinkedIn" with uppercase CSS
    // Use getAllByText since "Email" appears in sidebar header AND compose area
    await waitFor(() => {
      const emailMatches = screen.getAllByText('Email');
      expect(emailMatches.length).toBeGreaterThanOrEqual(1);
    });

    // LinkedIn section should be present (we have LI history)
    await waitFor(() => {
      const linkedinMatches = screen.getAllByText('LinkedIn');
      expect(linkedinMatches.length).toBeGreaterThanOrEqual(1);
    });

    // LinkedIn automation campaign should be listed
    await waitFor(() => {
      const liFlowMatches = screen.getAllByText('LI connect flow');
      expect(liFlowMatches.length).toBeGreaterThanOrEqual(1);
    });
  });

  // Test 4: Reply mode with AI draft
  it('loads AI draft in reply mode and populates textarea', async () => {
    const { contactsApi } = await import('../api/contacts');

    render(
      <ContactDetailModal
        contact={mockContact}
        isOpen={true}
        onClose={vi.fn()}
        replyMode={true}
        contactList={mockContactList}
        currentIndex={0}
        onNavigate={vi.fn()}
        onMarkProcessed={vi.fn()}
      />
    );

    // Wait for AI draft to load into textarea
    await waitFor(() => {
      expect(contactsApi.generateReply).toHaveBeenCalledWith(74301);
    });

    await waitFor(() => {
      const textarea = screen.getByPlaceholderText('Write your reply...');
      expect(textarea).toHaveValue('Thanks for your interest! Let me share more details.');
    });
  });

  // Test 5: Navigation between contacts
  it('navigates between contacts using keyboard arrows', async () => {
    const onNavigate = vi.fn();

    render(
      <ContactDetailModal
        contact={mockContact}
        isOpen={true}
        onClose={vi.fn()}
        replyMode={true}
        contactList={mockContactList}
        currentIndex={1}
        onNavigate={onNavigate}
        onMarkProcessed={vi.fn()}
      />
    );

    // Should show counter
    expect(screen.getByText('2/3')).toBeInTheDocument();

    // Simulate keyboard navigation
    await userEvent.keyboard('{ArrowRight}');
    expect(onNavigate).toHaveBeenCalledWith(2);
  });

  // Test 6: Draft save and auto-advance
  it('saves draft and calls onMarkProcessed', async () => {
    const onMarkProcessed = vi.fn();
    const onNavigate = vi.fn();

    render(
      <ContactDetailModal
        contact={mockContact}
        isOpen={true}
        onClose={vi.fn()}
        replyMode={true}
        contactList={mockContactList}
        currentIndex={0}
        onNavigate={onNavigate}
        onMarkProcessed={onMarkProcessed}
      />
    );

    // Wait for AI draft to populate
    await waitFor(() => {
      const textarea = screen.getByPlaceholderText('Write your reply...');
      expect(textarea).toHaveValue('Thanks for your interest! Let me share more details.');
    });

    // Click Save & Next button
    const saveButton = screen.getByText('Save & Next');
    await userEvent.click(saveButton);

    // onMarkProcessed should be called after save
    await waitFor(() => {
      expect(onMarkProcessed).toHaveBeenCalledWith(74301);
    });
  });

  // Test 7: Skip contact
  it('skips contact and advances to next', async () => {
    const onMarkProcessed = vi.fn();
    const onNavigate = vi.fn();

    render(
      <ContactDetailModal
        contact={mockContact}
        isOpen={true}
        onClose={vi.fn()}
        replyMode={true}
        contactList={mockContactList}
        currentIndex={0}
        onNavigate={onNavigate}
        onMarkProcessed={onMarkProcessed}
      />
    );

    // Wait for the component to render fully
    await waitFor(() => {
      expect(screen.getByText('Peter Nikolaev')).toBeInTheDocument();
    });

    // Click Skip button — use getAllByText since "Skip" text might appear multiple times
    const skipButtons = screen.getAllByText('Skip');
    const skipButton = skipButtons.find(el => el.closest('button'));
    expect(skipButton).toBeTruthy();
    await userEvent.click(skipButton!.closest('button')!);

    expect(onMarkProcessed).toHaveBeenCalledWith(74301);
    expect(onNavigate).toHaveBeenCalledWith(1);
  });
});
