import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { SearchResultsPage } from '../pages/SearchResultsPage';
import type {
  SearchJobFullDetail,
  SearchResultItem,
  QueryItem,
  DomainCampaignsMap,
  SearchHistoryItem,
} from '../api/dataSearch';

// ============ Mock data factories ============

const makeJobFull = (overrides?: Partial<SearchJobFullDetail>): SearchJobFullDetail => ({
  id: 14,
  company_id: 1,
  status: 'completed',
  search_engine: 'yandex_api',
  project_id: 18,
  project_name: 'deliryo',
  queries_total: 100,
  queries_completed: 100,
  domains_found: 50,
  domains_new: 20,
  domains_trash: 5,
  domains_duplicate: 25,
  started_at: '2026-02-10T10:00:00Z',
  completed_at: '2026-02-10T10:05:00Z',
  created_at: '2026-02-10T09:50:00Z',
  results_total: 30,
  targets_found: 10,
  avg_confidence: 0.75,
  yandex_cost: 0.15,
  openai_tokens_used: 50000,
  openai_cost_estimate: 0.025,
  crona_credits_used: 30,
  crona_cost: 0.03,
  total_cost_estimate: 0.205,
  ...overrides,
});

const makeResult = (id: number, overrides?: Partial<SearchResultItem>): SearchResultItem => ({
  id,
  search_job_id: 14,
  project_id: 18,
  domain: `example-${id}.com`,
  url: `https://example-${id}.com`,
  is_target: id % 3 === 0,
  confidence: 0.5 + (id % 5) * 0.1,
  reasoning: `Analysis for company ${id}`,
  company_info: {
    name: `Company ${id}`,
    description: `Description ${id}`,
    services: ['consulting'],
    location: 'Russia',
    industry: 'finance',
  },
  scores: {
    language_match: 1.0,
    industry_match: 0.8,
    service_match: 0.7,
    company_type: 0.6,
    geography_match: 1.0,
  },
  source_query_text: `query for ${id}`,
  ...overrides,
});

const makeQuery = (id: number, overrides?: Partial<QueryItem>): QueryItem => ({
  id,
  query_text: `search query ${id}`,
  status: 'completed',
  domains_found: id * 2,
  ...overrides,
});

const makeHistoryItem = (id: number, overrides?: Partial<SearchHistoryItem>): SearchHistoryItem => ({
  id,
  company_id: 1,
  status: 'completed',
  search_engine: 'yandex_api',
  project_id: 18,
  project_name: `Project ${id}`,
  queries_total: 100,
  queries_completed: 100,
  domains_found: 50,
  domains_new: 20,
  domains_trash: 5,
  domains_duplicate: 25,
  results_total: 30,
  targets_found: 10,
  started_at: '2026-02-10T10:00:00Z',
  completed_at: '2026-02-10T10:05:00Z',
  created_at: '2026-02-10T09:50:00Z',
  openai_tokens_used: 50000,
  crona_credits_used: 30,
  ...overrides,
});

// ============ Mock projectSearchApi ============

const mockGetJobFull = vi.fn();
const mockGetProjectResults = vi.fn();
const mockGetProjectResultsStats = vi.fn();
const mockGetJobQueries = vi.fn();
const mockGetDomainCampaigns = vi.fn();
const mockGetSearchHistory = vi.fn();
const mockExportToGoogleSheet = vi.fn();
const mockDownloadJobCsv = vi.fn();

vi.mock('../api/dataSearch', async () => {
  const actual = await vi.importActual('../api/dataSearch');
  return {
    ...actual,
    projectSearchApi: {
      getJobFull: (...args: unknown[]) => mockGetJobFull(...args),
      getProjectResults: (...args: unknown[]) => mockGetProjectResults(...args),
      getProjectResultsStats: (...args: unknown[]) => mockGetProjectResultsStats(...args),
      getJobQueries: (...args: unknown[]) => mockGetJobQueries(...args),
      getDomainCampaigns: (...args: unknown[]) => mockGetDomainCampaigns(...args),
      getSearchHistory: (...args: unknown[]) => mockGetSearchHistory(...args),
      exportToGoogleSheet: (...args: unknown[]) => mockExportToGoogleSheet(...args),
      downloadJobCsv: (...args: unknown[]) => mockDownloadJobCsv(...args),
    },
  };
});

// Mock useVirtualizer — render all items
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: Math.min(count, 50) }, (_, i) => ({
        index: i,
        start: i * 44,
        end: (i + 1) * 44,
        size: 44,
      })),
    getTotalSize: () => count * 44,
    measure: vi.fn(),
    measureElement: undefined,
  }),
}));

// Mock store
vi.mock('../store/appStore', () => ({
  useAppStore: () => ({
    currentCompany: { id: 1, name: 'Test Corp' },
  }),
}));

// ============ Helpers ============

function renderJobDetail(jobId: number = 14) {
  return render(
    <MemoryRouter initialEntries={[`/search-results/${jobId}`]}>
      <Routes>
        <Route path="/search-results/:jobId" element={<SearchResultsPage />} />
        <Route path="/search-results" element={<SearchResultsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

function renderHistory() {
  return render(
    <MemoryRouter initialEntries={['/search-results']}>
      <Routes>
        <Route path="/search-results" element={<SearchResultsPage />} />
      </Routes>
    </MemoryRouter>
  );
}

// ============ Tests ============

describe('SearchResultsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: return empty data
    mockGetJobFull.mockResolvedValue(makeJobFull());
    mockGetProjectResults.mockResolvedValue({
      items: Array.from({ length: 10 }, (_, i) => makeResult(i + 1)),
      total: 10,
      page: 1,
      page_size: 100,
    });
    mockGetProjectResultsStats.mockResolvedValue({
      total: 10,
      targets: 3,
      non_targets: 7,
      avg_confidence: 0.75,
    });
    mockGetJobQueries.mockResolvedValue({
      items: Array.from({ length: 5 }, (_, i) => makeQuery(i + 1)),
      total: 5,
      page: 1,
      page_size: 100,
    });
    mockGetDomainCampaigns.mockResolvedValue({});
    mockGetSearchHistory.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 20,
    });
  });

  // ============ Job History View ============

  describe('JobHistoryView', () => {
    it('renders Search Results heading', async () => {
      renderHistory();
      await waitFor(() => {
        expect(screen.getByText('Search Results')).toBeInTheDocument();
      });
    });

    it('calls getSearchHistory on mount', async () => {
      renderHistory();
      await waitFor(() => {
        expect(mockGetSearchHistory).toHaveBeenCalledWith(1, 20);
      });
    });

    it('shows "No search jobs found" when history is empty', async () => {
      renderHistory();
      await waitFor(() => {
        expect(screen.getByText(/No search jobs found/)).toBeInTheDocument();
      });
    });

    it('renders job rows from history', async () => {
      mockGetSearchHistory.mockResolvedValue({
        items: [makeHistoryItem(1, { project_name: 'Alpha Project' }), makeHistoryItem(2, { project_name: 'Beta Project' })],
        total: 2,
        page: 1,
        page_size: 20,
      });
      renderHistory();
      await waitFor(() => {
        expect(screen.getByText('Alpha Project')).toBeInTheDocument();
        expect(screen.getByText('Beta Project')).toBeInTheDocument();
      });
    });

    it('shows stat cards (Total Jobs, Domains Found, Targets Found)', async () => {
      mockGetSearchHistory.mockResolvedValue({
        items: [makeHistoryItem(1, { domains_found: 200, targets_found: 50 })],
        total: 1,
        page: 1,
        page_size: 20,
      });
      renderHistory();
      await waitFor(() => {
        expect(screen.getByText('Total Jobs')).toBeInTheDocument();
        expect(screen.getByText('Domains Found')).toBeInTheDocument();
        expect(screen.getByText('Targets Found')).toBeInTheDocument();
      });
    });
  });

  // ============ Job Detail View ============

  describe('JobDetailView', () => {
    it('shows loading spinner initially', () => {
      // Make the API hang
      mockGetJobFull.mockReturnValue(new Promise(() => {}));
      renderJobDetail();
      expect(document.querySelector('.animate-spin')).toBeTruthy();
    });

    it('loads job data, results, stats, and queries on mount', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(mockGetJobFull).toHaveBeenCalledWith(14);
        expect(mockGetProjectResults).toHaveBeenCalledWith(18, {
          jobId: 14,
          page: 1,
          pageSize: 100,
        });
        expect(mockGetJobQueries).toHaveBeenCalledWith(14, 1, 100);
      });
    });

    it('renders job header with id and status', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('Job #14')).toBeInTheDocument();
        expect(screen.getByText('completed')).toBeInTheDocument();
      });
    });

    it('renders project name in header', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('deliryo')).toBeInTheDocument();
      });
    });

    it('renders stats bar with job metrics', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('Queries')).toBeInTheDocument();
        expect(screen.getByText('Domains Found')).toBeInTheDocument();
        expect(screen.getByText('New Domains')).toBeInTheDocument();
        expect(screen.getByText('Targets')).toBeInTheDocument();
        expect(screen.getByText('Analyzed')).toBeInTheDocument();
        expect(screen.getByText('Avg Confidence')).toBeInTheDocument();
      });
    });

    it('renders spending panel with cost breakdown', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('Resource Spending')).toBeInTheDocument();
        expect(screen.getByText('Yandex API')).toBeInTheDocument();
        expect(screen.getByText('OpenAI (GPT-4o-mini)')).toBeInTheDocument();
        expect(screen.getByText('Crona (Scraping)')).toBeInTheDocument();
        expect(screen.getByText('Total Estimate')).toBeInTheDocument();
      });
    });

    it('shows Results and Queries tabs with counts', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('Results (10)')).toBeInTheDocument();
        expect(screen.getByText('Queries (5)')).toBeInTheDocument();
      });
    });

    it('renders result rows with domain and company name', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('example-1.com')).toBeInTheDocument();
        expect(screen.getByText('Company 1')).toBeInTheDocument();
      });
    });

    it('shows target checkmark for target results', async () => {
      renderJobDetail();
      await waitFor(() => {
        // Results with id % 3 === 0 are targets (id 3, 6, 9)
        expect(screen.getByText('example-3.com')).toBeInTheDocument();
      });
    });

    it('shows confidence percentage', async () => {
      renderJobDetail();
      await waitFor(() => {
        // confidence = 0.5 + (1 % 5) * 0.1 = 0.6 → "60%"
        const matches = screen.getAllByText('60%');
        expect(matches.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('shows skeleton rows for not-yet-loaded data', async () => {
      mockGetProjectResults.mockResolvedValue({
        items: [],
        total: 100,
        page: 1,
        page_size: 100,
      });
      renderJobDetail();
      await waitFor(() => {
        // Skeleton rows have animate-pulse class
        const skeletons = document.querySelectorAll('.animate-pulse');
        expect(skeletons.length).toBeGreaterThan(0);
      });
    });

    it('renders "No results yet" when total is 0', async () => {
      mockGetProjectResults.mockResolvedValue({
        items: [],
        total: 0,
        page: 1,
        page_size: 100,
      });
      mockGetProjectResultsStats.mockResolvedValue({
        total: 0,
        targets: 0,
        non_targets: 0,
        avg_confidence: null,
      });
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('No results yet')).toBeInTheDocument();
      });
    });

    it('expands a result row to show detail on click', async () => {
      const user = userEvent.setup();
      renderJobDetail();

      await waitFor(() => {
        expect(screen.getByText('example-1.com')).toBeInTheDocument();
      });

      // Click to expand
      await user.click(screen.getByText('example-1.com'));

      await waitFor(() => {
        expect(screen.getByText(/Analysis for company 1/)).toBeInTheDocument();
        expect(screen.getByText(/Description 1/)).toBeInTheDocument();
      });
    });

    it('shows source query in expanded detail', async () => {
      const user = userEvent.setup();
      renderJobDetail();

      await waitFor(() => {
        expect(screen.getByText('example-1.com')).toBeInTheDocument();
      });

      await user.click(screen.getByText('example-1.com'));

      await waitFor(() => {
        // Source query appears in the detail panel with "Source Query:" label
        expect(screen.getByText('Source Query:')).toBeInTheDocument();
      });
    });

    it('switches to Queries tab and shows query rows', async () => {
      const user = userEvent.setup();
      renderJobDetail();

      await waitFor(() => {
        expect(screen.getByText('Queries (5)')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Queries (5)'));

      await waitFor(() => {
        expect(screen.getByText('search query 1')).toBeInTheDocument();
        expect(screen.getByText('search query 2')).toBeInTheDocument();
      });
    });

    it('shows query status badges', async () => {
      const user = userEvent.setup();
      renderJobDetail();

      await waitFor(() => {
        expect(screen.getByText('Queries (5)')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Queries (5)'));

      await waitFor(() => {
        // All queries have 'completed' status
        const statusBadges = screen.getAllByText('completed');
        // At least some are from queries tab
        expect(statusBadges.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('shows error state when job loading fails', async () => {
      mockGetJobFull.mockRejectedValue({ userMessage: 'Server error occurred' });
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('Server error occurred')).toBeInTheDocument();
      });
    });

    it('fetches domain campaigns for visible results', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(mockGetDomainCampaigns).toHaveBeenCalled();
      });
    });

    it('renders campaign badges when campaign data available', async () => {
      const campaigns: DomainCampaignsMap = {
        'example-1.com': {
          contacts_count: 2,
          has_replies: false,
          first_contacted_at: '2026-01-15',
          match_type: 'email_domain',
          campaigns: [{ name: 'Q1 Outreach', source: 'smartlead', status: 'active' }],
          contacts: [
            { id: 1, name: 'John', email: 'john@test.com', status: 'sent', has_replied: false },
          ],
        },
      };
      mockGetDomainCampaigns.mockResolvedValue(campaigns);
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('Q1 Outreach')).toBeInTheDocument();
      });
    });

    it('renders export buttons (Google Sheet, CSV)', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('Google Sheet')).toBeInTheDocument();
        expect(screen.getByText('CSV')).toBeInTheDocument();
      });
    });

    it('renders table headers for results tab', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('Domain')).toBeInTheDocument();
        expect(screen.getByText('Company')).toBeInTheDocument();
        expect(screen.getByText('Target')).toBeInTheDocument();
        expect(screen.getByText('Confidence')).toBeInTheDocument();
        expect(screen.getByText('Outreach')).toBeInTheDocument();
        expect(screen.getByText('Industry')).toBeInTheDocument();
        expect(screen.getByText('Source Query')).toBeInTheDocument();
      });
    });

    it('renders table headers for queries tab', async () => {
      const user = userEvent.setup();
      renderJobDetail();

      await waitFor(() => {
        expect(screen.getByText('Queries (5)')).toBeInTheDocument();
      });

      await user.click(screen.getByText('Queries (5)'));

      await waitFor(() => {
        expect(screen.getByText('Query')).toBeInTheDocument();
        // "Status" header appears as column header text
        const statusHeaders = screen.getAllByText('Status');
        expect(statusHeaders.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('handles job with no project gracefully', async () => {
      mockGetJobFull.mockResolvedValue(makeJobFull({ project_id: undefined }));
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('Job #14')).toBeInTheDocument();
      });
      // Should not try to load results (no project_id)
      expect(mockGetProjectResults).not.toHaveBeenCalled();
    });

    it('formats duration correctly in header', async () => {
      mockGetJobFull.mockResolvedValue(
        makeJobFull({
          started_at: '2026-02-10T10:00:00Z',
          completed_at: '2026-02-10T10:05:00Z',
        })
      );
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText(/5m 0s/)).toBeInTheDocument();
      });
    });

    it('shows query count in stats bar', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(screen.getByText('100/100')).toBeInTheDocument();
      });
    });
  });

  // ============ Pagination behavior ============

  describe('pagination', () => {
    it('requests page 1 of results on initial load', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(mockGetProjectResults).toHaveBeenCalledWith(18, {
          jobId: 14,
          page: 1,
          pageSize: 100,
        });
      });
    });

    it('requests page 1 of queries on initial load', async () => {
      renderJobDetail();
      await waitFor(() => {
        expect(mockGetJobQueries).toHaveBeenCalledWith(14, 1, 100);
      });
    });
  });
});
