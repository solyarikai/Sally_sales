import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { DataSearchPage } from '../pages/DataSearchPage';

// Mock dataSearch API
vi.mock('../api/dataSearch', () => ({
  dataSearchApi: {
    chat: vi.fn(),
    search: vi.fn(),
    feedback: vi.fn(),
    exportResults: vi.fn(),
    searchLike: vi.fn(),
    verifySearchResults: vi.fn(),
  },
  projectSearchApi: {
    chatSearch: vi.fn(),
    streamSearchJob: vi.fn(),
    cancelSearchJob: vi.fn(),
    getProjectResults: vi.fn(),
    getProjectSpending: vi.fn(),
    exportToGoogleSheet: vi.fn(),
  },
}));

// Mock contacts API (for project list)
vi.mock('../api/contacts', () => ({
  contactsApi: {
    listProjects: vi.fn().mockResolvedValue([]),
  },
}));

function renderDataSearch() {
  return render(
    <MemoryRouter>
      <DataSearchPage />
    </MemoryRouter>,
  );
}

describe('DataSearchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the page with mode toggle buttons', () => {
    renderDataSearch();
    // "Natural Language" appears in both the toggle button and the feature card
    expect(screen.getAllByText('Natural Language').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Find Similar')).toBeInTheDocument();
    expect(screen.getByText('Web Search')).toBeInTheDocument();
  });

  it('shows chat mode (Natural Language) by default', () => {
    renderDataSearch();
    expect(screen.getByText('AI-Powered Search')).toBeInTheDocument();
    expect(screen.getByText(/Find Your/)).toBeInTheDocument();
    expect(screen.getByText(/Ideal Customers/)).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText('e.g., SaaS companies in Germany with 50-200 employees...'),
    ).toBeInTheDocument();
  });

  it('shows example queries in chat mode', () => {
    renderDataSearch();
    expect(
      screen.getByText('SaaS companies in Germany with 50-200 employees'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Fintech startups in London founded after 2020'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('E-commerce companies using Shopify in the US'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Healthcare tech companies with Series A funding'),
    ).toBeInTheDocument();
  });

  it('shows feature cards in chat mode', () => {
    renderDataSearch();
    // "Natural Language" appears both as toggle button and feature card title
    expect(screen.getAllByText('Natural Language').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('Instant Results')).toBeInTheDocument();
    expect(screen.getByText('Verified Data')).toBeInTheDocument();
  });

  it('switches to Find Similar mode', async () => {
    const user = userEvent.setup();
    renderDataSearch();

    await user.click(screen.getByText('Find Similar'));

    expect(screen.getByText('Reverse Engineering Search')).toBeInTheDocument();
    // "Similar Companies" appears in both heading and button
    expect(screen.getAllByText(/Similar Companies/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Example Companies')).toBeInTheDocument();
    expect(screen.getByText('Add Another Company')).toBeInTheDocument();
  });

  it('shows reverse mode feature cards', async () => {
    const user = userEvent.setup();
    renderDataSearch();

    await user.click(screen.getByText('Find Similar'));

    expect(screen.getByText('Pattern Detection')).toBeInTheDocument();
    expect(screen.getByText('Smart Filters')).toBeInTheDocument();
    expect(screen.getByText('Similar Matches')).toBeInTheDocument();
  });

  it('switches to Web Search (project) mode', async () => {
    const user = userEvent.setup();
    renderDataSearch();

    await user.click(screen.getByText('Web Search'));

    expect(screen.getByText('AI Web Search Pipeline')).toBeInTheDocument();
    expect(screen.getByText(/Entire Web/)).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Describe the companies you're looking for..."),
    ).toBeInTheDocument();
  });

  it('shows web search example queries', async () => {
    const user = userEvent.setup();
    renderDataSearch();

    await user.click(screen.getByText('Web Search'));

    expect(
      screen.getByText('Find villa builders in Dubai and Abu Dhabi'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Family offices in Moscow managing private wealth'),
    ).toBeInTheDocument();
  });

  it('shows web search feature cards', async () => {
    const user = userEvent.setup();
    renderDataSearch();

    await user.click(screen.getByText('Web Search'));

    expect(screen.getByText('Conversational')).toBeInTheDocument();
    expect(screen.getByText('Web Crawling')).toBeInTheDocument();
    expect(screen.getByText('GPT Analysis')).toBeInTheDocument();
  });

  it('populates search input when clicking an example query in chat mode', async () => {
    const user = userEvent.setup();
    renderDataSearch();

    await user.click(
      screen.getByText('SaaS companies in Germany with 50-200 employees'),
    );

    const input = screen.getByPlaceholderText(
      'e.g., SaaS companies in Germany with 50-200 employees...',
    ) as HTMLInputElement;
    expect(input.value).toBe('SaaS companies in Germany with 50-200 employees');
  });

  it('has reverse mode company input fields', async () => {
    const user = userEvent.setup();
    renderDataSearch();

    await user.click(screen.getByText('Find Similar'));

    expect(screen.getByPlaceholderText('Company name')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Domain (e.g., acme.com)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Industry')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Location')).toBeInTheDocument();
  });

  it('can add more example companies in reverse mode', async () => {
    const user = userEvent.setup();
    renderDataSearch();

    await user.click(screen.getByText('Find Similar'));

    // Initially there's 1 company row (1 "Company name" input)
    expect(screen.getAllByPlaceholderText('Company name')).toHaveLength(1);

    await user.click(screen.getByText('Add Another Company'));

    expect(screen.getAllByPlaceholderText('Company name')).toHaveLength(2);
  });
});
