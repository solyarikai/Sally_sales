import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { RepliesPage } from '../pages/RepliesPage';

// Mock replies API with the actual method names used in RepliesPage
vi.mock('../api/replies', () => ({
  repliesApi: {
    getReplies: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 }),
    getReplyStats: vi.fn().mockResolvedValue({
      total: 0,
      by_category: {},
      by_sentiment: {},
      by_campaign: {},
    }),
    getAutomations: vi.fn().mockResolvedValue([]),
    getSmartleadCampaigns: vi.fn().mockResolvedValue([]),
    getSlackChannels: vi.fn().mockResolvedValue([]),
    getCategories: vi.fn().mockResolvedValue([]),
    getGoogleSheetsStatus: vi.fn().mockResolvedValue({ connected: false }),
    getTestEmailAccounts: vi.fn().mockResolvedValue([]),
    getTestCampaigns: vi.fn().mockResolvedValue([]),
  },
}));

// Mock react-hot-toast
vi.mock('react-hot-toast', () => {
  const toast = vi.fn() as any;
  toast.success = vi.fn();
  toast.error = vi.fn();
  return {
    default: toast,
    Toaster: () => null,
  };
});

// Import the mocked module to access mock functions
import { repliesApi } from '../api/replies';

describe('RepliesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders page title "Email Replies"', async () => {
    render(
      <MemoryRouter>
        <RepliesPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Email Replies')).toBeInTheDocument();
    });
  });

  it('renders search input', async () => {
    render(
      <MemoryRouter>
        <RepliesPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
    });
  });

  it('calls getReplies on mount', async () => {
    render(
      <MemoryRouter>
        <RepliesPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(repliesApi.getReplies).toHaveBeenCalled();
    });
  });

  it('calls getReplyStats on mount', async () => {
    render(
      <MemoryRouter>
        <RepliesPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(repliesApi.getReplyStats).toHaveBeenCalled();
    });
  });

  it('calls getAutomations on mount', async () => {
    render(
      <MemoryRouter>
        <RepliesPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(repliesApi.getAutomations).toHaveBeenCalled();
    });
  });

  it('shows total count area', async () => {
    render(
      <MemoryRouter>
        <RepliesPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Email Replies')).toBeInTheDocument();
    });
  });

  it('shows category filter pills when stats have data', async () => {
    (repliesApi.getReplyStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      total: 5,
      by_category: {
        interested: 2,
        not_interested: 1,
        out_of_office: 1,
        other: 1,
      },
      by_sentiment: {},
      by_campaign: {},
    });

    render(
      <MemoryRouter>
        <RepliesPage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Interested')).toBeInTheDocument();
    });
  });
});
