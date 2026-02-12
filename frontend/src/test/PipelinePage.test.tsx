import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { PipelinePage } from '../pages/PipelinePage';

// Mock pipeline API
const mockListDiscoveredCompanies = vi.fn();
const mockGetStats = vi.fn();
const mockGetDiscoveredCompany = vi.fn();
const mockExtractContacts = vi.fn();
const mockEnrichApollo = vi.fn();
const mockUpdateStatus = vi.fn();
const mockExportCsv = vi.fn();
const mockPromoteToCrm = vi.fn();

vi.mock('../api/pipeline', () => ({
  pipelineApi: {
    listDiscoveredCompanies: (...args: unknown[]) => mockListDiscoveredCompanies(...args),
    getStats: (...args: unknown[]) => mockGetStats(...args),
    getDiscoveredCompany: (...args: unknown[]) => mockGetDiscoveredCompany(...args),
    extractContacts: (...args: unknown[]) => mockExtractContacts(...args),
    enrichApollo: (...args: unknown[]) => mockEnrichApollo(...args),
    updateStatus: (...args: unknown[]) => mockUpdateStatus(...args),
    exportCsv: (...args: unknown[]) => mockExportCsv(...args),
    promoteToCrm: (...args: unknown[]) => mockPromoteToCrm(...args),
  },
}));

// Mock contacts API (for project list)
const mockListProjects = vi.fn();

vi.mock('../api/contacts', () => ({
  contactsApi: {
    listProjects: (...args: unknown[]) => mockListProjects(...args),
  },
}));

// Store mock with switchable currentCompany
let mockCurrentCompany: any = { id: 1, name: 'Test Company' };

vi.mock('../store/appStore', () => ({
  useAppStore: () => ({
    currentCompany: mockCurrentCompany,
  }),
}));

const mockCompanies = [
  {
    id: 1,
    company_id: 1,
    domain: 'example.com',
    name: 'Example Corp',
    url: 'https://example.com',
    is_target: true,
    confidence: 0.85,
    status: 'analyzed',
    contacts_count: 3,
    apollo_people_count: 2,
    company_info: { name: 'Example Corp', industry: 'SaaS' },
  },
  {
    id: 2,
    company_id: 1,
    domain: 'test.io',
    name: 'Test Inc',
    is_target: false,
    confidence: 0.4,
    status: 'new',
    contacts_count: 0,
    apollo_people_count: 0,
    company_info: { name: 'Test Inc' },
  },
];

const mockStats = {
  total_discovered: 100,
  targets: 25,
  contacts_extracted: 50,
  enriched: 15,
  exported: 10,
};

function renderPipeline() {
  return render(
    <MemoryRouter>
      <PipelinePage />
    </MemoryRouter>,
  );
}

describe('PipelinePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCurrentCompany = { id: 1, name: 'Test Company' };
    mockListDiscoveredCompanies.mockResolvedValue({
      items: mockCompanies,
      total: 2,
    });
    mockGetStats.mockResolvedValue(mockStats);
    mockListProjects.mockResolvedValue([
      { id: 1, name: 'Project Alpha' },
    ]);
  });

  it('renders page title and subtitle', async () => {
    renderPipeline();
    await waitFor(() => {
      expect(screen.getByText('Pipeline')).toBeInTheDocument();
    });
    expect(
      screen.getByText('Manage discovered companies through the outreach pipeline'),
    ).toBeInTheDocument();
  });

  it('renders stats cards after loading', async () => {
    renderPipeline();
    await waitFor(() => {
      expect(screen.getByText('Discovered')).toBeInTheDocument();
    });
    expect(screen.getByText('100')).toBeInTheDocument();
    expect(screen.getByText('Targets')).toBeInTheDocument();
    expect(screen.getByText('25')).toBeInTheDocument();
    expect(screen.getByText('Contacts Extracted')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    // "Enriched" appears in both stats card label and status dropdown option
    expect(screen.getAllByText('Enriched').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getAllByText('Exported').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  it('renders company rows in the table', async () => {
    renderPipeline();
    await waitFor(() => {
      expect(screen.getByText('example.com')).toBeInTheDocument();
    });
    expect(screen.getByText('test.io')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
    expect(screen.getByText('40%')).toBeInTheDocument();
  });

  it('renders filter controls', async () => {
    renderPipeline();
    await waitFor(() => {
      expect(screen.getByText('All Projects')).toBeInTheDocument();
    });
    expect(screen.getByText('All Statuses')).toBeInTheDocument();
    expect(screen.getByText('Targets only')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Search domain or name...')).toBeInTheDocument();
  });

  it('shows project options in dropdown', async () => {
    renderPipeline();
    await waitFor(() => {
      expect(screen.getByText('Project Alpha')).toBeInTheDocument();
    });
  });

  it('shows bulk action toolbar when row checkbox is clicked', async () => {
    renderPipeline();

    await waitFor(() => {
      expect(screen.getByText('example.com')).toBeInTheDocument();
    });

    // Use fireEvent.click directly on checkbox (more reliable than userEvent for checkbox in table)
    const checkboxes = screen.getAllByRole('checkbox');
    // checkboxes[0] = select all, [1] = targets only, [2] = row 1, [3] = row 2
    // Actually, let's find the right one — the table checkboxes
    // The "Targets only" checkbox is also a checkbox. Let's click a row checkbox.
    // We need to find the checkbox inside the table body rows.
    fireEvent.click(checkboxes[2]); // third checkbox = first table row

    await waitFor(() => {
      expect(screen.getByText('1 selected')).toBeInTheDocument();
    });
    expect(screen.getByText('Extract Contacts')).toBeInTheDocument();
    expect(screen.getByText('Enrich Apollo')).toBeInTheDocument();
    expect(screen.getByText('Promote to CRM')).toBeInTheDocument();
    expect(screen.getByText('Reject')).toBeInTheDocument();
  });

  it('shows Apollo settings popover when clicking Enrich Apollo with selection', async () => {
    const user = userEvent.setup();
    renderPipeline();

    await waitFor(() => {
      expect(screen.getByText('example.com')).toBeInTheDocument();
    });

    // Select a company using fireEvent for reliability
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[2]);

    await waitFor(() => {
      expect(screen.getByText('Enrich Apollo')).toBeInTheDocument();
    });

    // Click Enrich Apollo button
    await user.click(screen.getByText('Enrich Apollo'));

    // Apollo Settings popover should appear
    expect(screen.getByText('Apollo Settings')).toBeInTheDocument();
    expect(screen.getByText('Role/Title Filters')).toBeInTheDocument();
    expect(screen.getByText('Run Enrichment')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('loads data with correct API calls', async () => {
    renderPipeline();
    await waitFor(() => {
      expect(mockListDiscoveredCompanies).toHaveBeenCalled();
      expect(mockGetStats).toHaveBeenCalled();
      expect(mockListProjects).toHaveBeenCalled();
    });
  });

  it('shows "no company" message when currentCompany is null', () => {
    mockCurrentCompany = null;

    render(
      <MemoryRouter>
        <PipelinePage />
      </MemoryRouter>,
    );

    expect(screen.getByText('Select a company to view the pipeline')).toBeInTheDocument();
  });

  it('shows total companies count', async () => {
    renderPipeline();
    await waitFor(() => {
      expect(screen.getByText('2 companies')).toBeInTheDocument();
    });
  });

  it('select all checkbox selects all companies', async () => {
    renderPipeline();

    await waitFor(() => {
      expect(screen.getByText('example.com')).toBeInTheDocument();
    });

    // checkboxes: [0]=targets-only, [1]=select-all, [2]=row1, [3]=row2
    const checkboxes = screen.getAllByRole('checkbox');
    fireEvent.click(checkboxes[1]);

    await waitFor(() => {
      expect(screen.getByText('2 selected')).toBeInTheDocument();
    });
  });
});
