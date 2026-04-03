import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { CampaignColumnFilter } from '../components/filters/CampaignColumnFilter';
import { ContactsFilterContext, type ContactsFilterState } from '../components/filters/ContactsFilterContext';
import type { ContactStats } from '../api/contacts';

const mockStats: ContactStats = {
  total: 820,
  by_status: { touched: 800, warm: 20 },
  by_segment: {},
  by_source: {},
  by_project: {},
};

const mockCampaigns: Array<{ name: string; source: string }> = [
  { name: 'Inxy - AI Agents', source: 'smartlead' },
  { name: 'Alpha Outreach', source: 'smartlead' },
  { name: 'Beta LinkedIn Flow', source: 'getsales' },
];

function createMockContext(overrides: Partial<ContactsFilterState> = {}): ContactsFilterState {
  return {
    campaignFilters: [],
    setCampaignFilters: vi.fn(),
    toggleCampaign: vi.fn(),
    statusFilters: [],
    setStatusFilters: vi.fn(),
    toggleStatus: vi.fn(),
    campaigns: mockCampaigns,
    stats: mockStats,
    resetPage: vi.fn(),
    ...overrides,
  };
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CampaignFilter = CampaignColumnFilter as any;

function renderFilter(ctx: ContactsFilterState) {
  return render(
    <ContactsFilterContext.Provider value={ctx}>
      <CampaignFilter />
    </ContactsFilterContext.Provider>
  );
}

describe('CampaignColumnFilter', () => {
  it('renders CAMPAIGN header text', () => {
    const ctx = createMockContext();
    renderFilter(ctx);

    expect(screen.getByText('CAMPAIGN')).toBeInTheDocument();
  });

  it('renders search input with placeholder "Search campaigns..."', () => {
    const ctx = createMockContext();
    renderFilter(ctx);

    expect(screen.getByPlaceholderText('Search campaigns...')).toBeInTheDocument();
  });

  it('shows all campaigns grouped by channel (Email section, LinkedIn section)', () => {
    const ctx = createMockContext();
    renderFilter(ctx);

    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('LinkedIn')).toBeInTheDocument();
  });

  it('shows campaign names', () => {
    const ctx = createMockContext();
    renderFilter(ctx);

    expect(screen.getByText('Inxy - AI Agents')).toBeInTheDocument();
    expect(screen.getByText('Alpha Outreach')).toBeInTheDocument();
    expect(screen.getByText('Beta LinkedIn Flow')).toBeInTheDocument();
  });

  it('toggles a campaign on click (calls toggleCampaign with campaign name)', async () => {
    const user = userEvent.setup();
    const toggleCampaign = vi.fn();
    const ctx = createMockContext({ toggleCampaign });
    renderFilter(ctx);

    await user.click(screen.getByText('Inxy - AI Agents'));

    expect(toggleCampaign).toHaveBeenCalledWith('Inxy - AI Agents');
  });

  it('calls resetPage on selection', async () => {
    const user = userEvent.setup();
    const resetPage = vi.fn();
    const ctx = createMockContext({ resetPage });
    renderFilter(ctx);

    await user.click(screen.getByText('Alpha Outreach'));

    expect(resetPage).toHaveBeenCalled();
  });

  it('deselects campaign on second click (calls toggleCampaign again)', async () => {
    const user = userEvent.setup();
    const toggleCampaign = vi.fn();
    const ctx = createMockContext({ campaignFilters: ['Inxy - AI Agents'], toggleCampaign });
    renderFilter(ctx);

    // When selected, the name appears in both the chip and the list; click the list button
    const matches = screen.getAllByText('Inxy - AI Agents');
    // The second match is the campaign button in the list
    await user.click(matches[1]);

    expect(toggleCampaign).toHaveBeenCalledWith('Inxy - AI Agents');
  });

  it('shows selected campaign chip when campaignFilters includes a campaign', () => {
    const ctx = createMockContext({ campaignFilters: ['Alpha Outreach'] });
    renderFilter(ctx);

    // The selected name appears in the chip AND in the list
    const alphaElements = screen.getAllByText('Alpha Outreach');
    expect(alphaElements.length).toBeGreaterThanOrEqual(2);
  });

  it('clears all selections via the "Clear all" button', async () => {
    const user = userEvent.setup();
    const setCampaignFilters = vi.fn();
    const resetPage = vi.fn();
    const ctx = createMockContext({ campaignFilters: ['Inxy - AI Agents'], setCampaignFilters, resetPage });
    renderFilter(ctx);

    // The "Clear all (1)" button should be visible
    await user.click(screen.getByText('Clear all (1)'));

    expect(setCampaignFilters).toHaveBeenCalledWith([]);
    expect(resetPage).toHaveBeenCalled();
  });

  it('filters campaigns by search query', async () => {
    const user = userEvent.setup();
    const ctx = createMockContext();
    renderFilter(ctx);

    const searchInput = screen.getByPlaceholderText('Search campaigns...');
    await user.type(searchInput, 'Alpha');

    // HighlightMatch splits text across elements, so use a matcher that checks textContent
    expect(screen.getByText((_content, el) =>
      el?.tagName === 'SPAN' && el.textContent === 'Alpha Outreach'
    )).toBeInTheDocument();
    // Filtered-out campaigns should not appear
    expect(screen.queryByText('Inxy - AI Agents')).not.toBeInTheDocument();
    expect(screen.queryByText('Beta LinkedIn Flow')).not.toBeInTheDocument();
  });

  it('shows "No campaigns match" when search returns empty', async () => {
    const user = userEvent.setup();
    const ctx = createMockContext();
    renderFilter(ctx);

    const searchInput = screen.getByPlaceholderText('Search campaigns...');
    await user.type(searchInput, 'zzzznonexistent');

    expect(screen.getByText('No campaigns match')).toBeInTheDocument();
  });
});
