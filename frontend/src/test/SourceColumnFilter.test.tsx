import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { StatusColumnFilter } from '../components/filters/StatusColumnFilter';
import { ContactsFilterContext, type ContactsFilterState } from '../components/filters/ContactsFilterContext';
import type { ContactStats } from '../api/contacts';

const mockStats: ContactStats = {
  total: 19116,
  by_status: { touched: 9100, warm: 10016 },
  by_segment: {},
  by_source: { smartlead: 9100, getsales: 10016 },
  by_project: {},
};

function createMockContext(overrides: Partial<ContactsFilterState> = {}): ContactsFilterState {
  return {
    campaignFilters: [],
    setCampaignFilters: vi.fn(),
    toggleCampaign: vi.fn(),
    statusFilters: [],
    setStatusFilters: vi.fn(),
    toggleStatus: vi.fn(),
    campaigns: [],
    stats: mockStats,
    resetPage: vi.fn(),
    ...overrides,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const StatusFilter = StatusColumnFilter as any;

function renderFilter(ctx: ContactsFilterState) {
  return render(
    <ContactsFilterContext.Provider value={ctx}>
      <StatusFilter />
    </ContactsFilterContext.Provider>
  );
}

describe('StatusColumnFilter', () => {
  it('renders status options', () => {
    const ctx = createMockContext();
    renderFilter(ctx);

    expect(screen.getByText('Touched')).toBeInTheDocument();
    expect(screen.getByText('Warm')).toBeInTheDocument();
    expect(screen.getByText('Replied')).toBeInTheDocument();
  });

  it('shows STATUS header text', () => {
    const ctx = createMockContext();
    renderFilter(ctx);

    expect(screen.getByText('STATUS')).toBeInTheDocument();
  });

  it('shows formatted counts from stats.by_status', () => {
    const ctx = createMockContext();
    renderFilter(ctx);

    // touched: 9100 -> "9.1K"
    expect(screen.getByText('9.1K')).toBeInTheDocument();
    // warm: 10016 -> "10K" (10.0 -> trailing .0 stripped)
    expect(screen.getByText('10K')).toBeInTheDocument();
  });

  it('calls toggleStatus on click', async () => {
    const user = userEvent.setup();
    const toggleStatus = vi.fn();
    const ctx = createMockContext({ toggleStatus });
    renderFilter(ctx);

    await user.click(screen.getByText('Touched'));

    expect(toggleStatus).toHaveBeenCalledWith('touched');
  });

  it('calls resetPage on each click', async () => {
    const user = userEvent.setup();
    const resetPage = vi.fn();
    const ctx = createMockContext({ resetPage });
    renderFilter(ctx);

    await user.click(screen.getByText('Warm'));

    expect(resetPage).toHaveBeenCalledTimes(1);
  });

  it('shows Clear button when statusFilters is not empty', () => {
    const ctx = createMockContext({ statusFilters: ['touched'] });
    renderFilter(ctx);

    expect(screen.getByText('Clear (1)')).toBeInTheDocument();
  });

  it('hides Clear button when statusFilters is empty', () => {
    const ctx = createMockContext({ statusFilters: [] });
    renderFilter(ctx);

    expect(screen.queryByText(/Clear/)).not.toBeInTheDocument();
  });

  it('clears filters and resets page when Clear clicked', async () => {
    const user = userEvent.setup();
    const setStatusFilters = vi.fn();
    const resetPage = vi.fn();
    const ctx = createMockContext({
      statusFilters: ['touched', 'warm'],
      setStatusFilters,
      resetPage,
    });
    renderFilter(ctx);

    await user.click(screen.getByText('Clear (2)'));

    expect(setStatusFilters).toHaveBeenCalledWith([]);
    expect(resetPage).toHaveBeenCalledTimes(1);
  });
});
