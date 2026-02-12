import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ContactsPage } from '../pages/ContactsPage';

// Mock AG Grid (it doesn't render well in happy-dom)
vi.mock('ag-grid-react', () => ({
  AgGridReact: vi.fn(() => <div data-testid="ag-grid-mock">AG Grid</div>),
}));

vi.mock('ag-grid-community', () => ({
  ModuleRegistry: { registerModules: vi.fn() },
  AllCommunityModule: {},
}));

// Mock contacts API
const mockList = vi.fn();
const mockGetStats = vi.fn();
const mockGetFilterOptions = vi.fn();
const mockListProjects = vi.fn();
const mockExportCsv = vi.fn();
const mockDeleteMany = vi.fn();
const mockCreate = vi.fn();

vi.mock('../api', () => ({
  contactsApi: {
    list: (...args: unknown[]) => mockList(...args),
    getStats: (...args: unknown[]) => mockGetStats(...args),
    getFilterOptions: (...args: unknown[]) => mockGetFilterOptions(...args),
    listProjects: (...args: unknown[]) => mockListProjects(...args),
    exportCsv: (...args: unknown[]) => mockExportCsv(...args),
    deleteMany: (...args: unknown[]) => mockDeleteMany(...args),
    create: (...args: unknown[]) => mockCreate(...args),
    createProject: vi.fn(),
    updateProject: vi.fn(),
    deleteProject: vi.fn(),
    getProjectAISDR: vi.fn(),
    generateTAM: vi.fn(),
    generateGTM: vi.fn(),
    generatePitches: vi.fn(),
    generateAllAISDR: vi.fn(),
    getImportTemplate: vi.fn(),
    importCsv: vi.fn(),
    listTasks: vi.fn().mockResolvedValue({ tasks: [] }),
    updateTask: vi.fn(),
  },
}));

// Mock Toast
vi.mock('../components/Toast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  }),
}));

// Mock ConfirmDialog
vi.mock('../components/ConfirmDialog', () => ({
  ConfirmDialog: () => null,
}));

// Mock ContactDetailModal
vi.mock('../components/ContactDetailModal', () => ({
  ContactDetailModal: () => null,
}));

// Mock ErrorBoundary
vi.mock('../components/ErrorBoundary', () => ({
  SectionErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock filters — provide the context and components
vi.mock('../components/filters', () => ({
  ContactsFilterContext: {
    Provider: ({ children, value }: { children: React.ReactNode; value: any }) => <>{children}</>,
  },
  CampaignColumnFilter: vi.fn(),
  StatusColumnFilter: vi.fn(),
}));

const mockContacts = [
  {
    id: 1,
    email: 'john@example.com',
    first_name: 'John',
    last_name: 'Doe',
    company_name: 'Acme',
    job_title: 'CEO',
    status: 'touched',
    source: 'smartlead',
    has_replied: false,
    campaigns: [{ name: 'Campaign 1', source: 'smartlead' }],
    created_at: '2024-01-01',
  },
  {
    id: 2,
    email: 'jane@test.io',
    first_name: 'Jane',
    last_name: 'Smith',
    company_name: 'TestCo',
    job_title: 'CTO',
    status: 'warm',
    source: 'getsales',
    has_replied: true,
    campaigns: [],
    created_at: '2024-01-02',
  },
];

const mockStatsData = {
  total: 150,
  by_status: {
    touched: 50,
    warm: 30,
    qualified: 10,
    replied: 20,
  },
  by_source: {
    smartlead: 100,
    getsales: 50,
  },
};

function renderContacts() {
  return render(
    <MemoryRouter>
      <ContactsPage />
    </MemoryRouter>,
  );
}

describe('ContactsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({
      contacts: mockContacts,
      total: 2,
    });
    mockGetStats.mockResolvedValue(mockStatsData);
    mockGetFilterOptions.mockResolvedValue({
      segments: ['Enterprise', 'SMB'],
      sources: ['smartlead', 'getsales'],
    });
    mockListProjects.mockResolvedValue([
      { id: 1, name: 'Project Alpha', contact_count: 50, campaign_filters: [] },
    ]);
    // Mock the campaigns endpoint (called via fetch, not contactsApi)
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        campaigns: [
          { name: 'Campaign 1', source: 'smartlead' },
          { name: 'LinkedIn Campaign', source: 'getsales' },
        ],
      }),
    }) as any;
  });

  it('renders the page title', async () => {
    renderContacts();
    await waitFor(() => {
      expect(screen.getByText('CRM Contacts')).toBeInTheDocument();
    });
  });

  it('calls API on mount to load contacts, stats, filter options, projects', async () => {
    renderContacts();
    await waitFor(() => {
      expect(mockList).toHaveBeenCalled();
      expect(mockGetStats).toHaveBeenCalled();
      expect(mockGetFilterOptions).toHaveBeenCalled();
      expect(mockListProjects).toHaveBeenCalled();
    });
  });

  it('renders search input', async () => {
    renderContacts();
    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search contacts...')).toBeInTheDocument();
    });
  });

  it('renders filter buttons (Replied, Follow-up, Campaigns)', async () => {
    renderContacts();
    await waitFor(() => {
      expect(screen.getByText('Replied')).toBeInTheDocument();
    });
    expect(screen.getByText('Follow-up')).toBeInTheDocument();
    expect(screen.getByText('Campaigns')).toBeInTheDocument();
  });

  it('renders Projects button', async () => {
    renderContacts();
    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument();
    });
  });

  it('renders Reset button', async () => {
    renderContacts();
    await waitFor(() => {
      expect(screen.getByText('Reset')).toBeInTheDocument();
    });
  });

  it('renders pagination controls', async () => {
    renderContacts();
    await waitFor(() => {
      expect(screen.getByText('First')).toBeInTheDocument();
    });
    expect(screen.getByText('Prev')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
    expect(screen.getByText('Last')).toBeInTheDocument();
  });

  it('shows total count', async () => {
    renderContacts();
    await waitFor(() => {
      expect(screen.getByText('2')).toBeInTheDocument();
    });
  });

  it('renders AG Grid mock', async () => {
    renderContacts();
    await waitFor(() => {
      expect(screen.getByTestId('ag-grid-mock')).toBeInTheDocument();
    });
  });

  it('shows project dropdown when clicking Projects button', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Projects')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Projects'));

    expect(screen.getByText('Project Alpha')).toBeInTheDocument();
  });

  it('shows replied count badge when stats have replies', async () => {
    renderContacts();
    await waitFor(() => {
      expect(screen.getByText('20')).toBeInTheDocument();
    });
  });
});
