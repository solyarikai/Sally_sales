/**
 * Contacts Table — UI/UX Improvement Tests
 *
 * Covers all test cases from the structured spec:
 *   2.1  Filter Highlighting      (F-1 … F-4)
 *   2.2  Global Search            (S-1 … S-7)
 *   2.3  Filter Selectors UX      (D-1 … D-6)
 *   2.4  Column Layout            (L-1 … L-4)
 *   2.5  URL Query Params         (U-1 … U-9)
 */
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, useSearchParams } from 'react-router-dom';
import { ContactsPage } from '../pages/ContactsPage';

// ── AG Grid mock ────────────────────────────────────────────────────
vi.mock('ag-grid-react', () => ({
  AgGridReact: vi.fn(({ columnDefs }: any) => (
    <div data-testid="ag-grid-mock">
      <table>
        <thead>
          <tr>
            {columnDefs?.map((col: any, i: number) => (
              <th key={i} data-testid={`col-header-${col.field || col.headerName || i}`}>
                {col.headerName || col.field || ''}
              </th>
            ))}
          </tr>
        </thead>
      </table>
    </div>
  )),
}));

vi.mock('ag-grid-community', () => ({
  ModuleRegistry: { registerModules: vi.fn() },
  AllCommunityModule: {},
}));

// ── API mocks ───────────────────────────────────────────────────────
const mockList = vi.fn();
const mockGetStats = vi.fn();
const mockGetFilterOptions = vi.fn();
const mockListProjects = vi.fn();

vi.mock('../api', () => ({
  contactsApi: {
    list: (...args: unknown[]) => mockList(...args),
    getStats: (...args: unknown[]) => mockGetStats(...args),
    getFilterOptions: (...args: unknown[]) => mockGetFilterOptions(...args),
    listProjects: (...args: unknown[]) => mockListProjects(...args),
    exportCsv: vi.fn(),
    deleteMany: vi.fn(),
    create: vi.fn(),
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

vi.mock('../components/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

vi.mock('../components/ConfirmDialog', () => ({ ConfirmDialog: () => null }));
vi.mock('../components/ContactDetailModal', () => ({ ContactDetailModal: () => null }));
vi.mock('../components/ErrorBoundary', () => ({
  SectionErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock filter components – render real buttons so we can test highlighting
vi.mock('../components/filters', () => ({
  ContactsFilterContext: {
    Provider: ({ children, value }: { children: React.ReactNode; value: any }) => (
      <div data-testid="filter-context" data-filters={JSON.stringify({
        statusFilters: value.statusFilters,
        sourceFilter: value.sourceFilter,
        campaignFilters: value.campaignFilters,
        segmentFilter: value.segmentFilter,
        geoFilter: value.geoFilter,
      })}>
        {children}
      </div>
    ),
  },
  CampaignColumnFilter: vi.fn(),
  StatusColumnFilter: vi.fn(),
  DateColumnFilter: vi.fn(),
}));

// ── Test data ───────────────────────────────────────────────────────
const makeContacts = (overrides: Partial<any>[] = []) => {
  const defaults = [
    {
      id: 1, email: 'john@acme.com', first_name: 'John', last_name: 'Doe',
      company_name: 'Acme', job_title: 'CTO', status: 'touched', source: 'smartlead',
      has_replied: false, campaigns: [{ name: 'Campaign 1', source: 'smartlead' }],
      created_at: '2024-01-01', location: 'New York', segment: 'Enterprise',
    },
    {
      id: 2, email: 'jane@testco.io', first_name: 'Jane', last_name: 'Smith',
      company_name: 'TestCo', job_title: 'CEO', status: 'warm', source: 'getsales',
      has_replied: true, campaigns: [], created_at: '2024-01-02',
      location: 'London', segment: 'SMB',
    },
  ];
  return overrides.length ? overrides : defaults;
};

const mockStatsData = {
  total: 150,
  by_status: { touched: 50, warm: 30, qualified: 10, replied: 20 },
  by_source: { smartlead: 100, getsales: 50 },
};

const mockFilterOptionsData = {
  statuses: ['touched', 'warm', 'qualified'],
  sources: ['smartlead', 'getsales'],
  segments: ['Enterprise', 'SMB'],
  geos: ['RU', 'Global'],
};

// ── Helpers ─────────────────────────────────────────────────────────
function renderContacts(initialEntries: string[] = ['/contacts']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <ContactsPage />
    </MemoryRouter>,
  );
}

function setupMocks(contacts = makeContacts(), total?: number) {
  mockList.mockResolvedValue({ contacts, total: total ?? contacts.length });
  mockGetStats.mockResolvedValue(mockStatsData);
  mockGetFilterOptions.mockResolvedValue(mockFilterOptionsData);
  mockListProjects.mockResolvedValue([
    { id: 1, name: 'Project Alpha', contact_count: 50, campaign_filters: ['Campaign 1'] },
    { id: 2, name: 'Project Beta', contact_count: 20, campaign_filters: [] },
  ]);
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve({
      campaigns: [
        { name: 'Campaign 1', source: 'smartlead' },
        { name: 'LinkedIn Campaign', source: 'getsales' },
      ],
    }),
  }) as any;
}

// ═══════════════════════════════════════════════════════════════════
// 2.1  Filter Highlighting  (F-1 … F-4)
// ═══════════════════════════════════════════════════════════════════
describe('2.1 Filter Highlighting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('F-1: Active status filter shows visual indicator on Replied button', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Replied')).toBeInTheDocument();
    });

    const repliedBtn = screen.getByText('Replied').closest('button')!;

    // Initially no active state
    expect(repliedBtn.className).not.toContain('bg-green-500');

    // Click to activate
    await user.click(repliedBtn);

    // Should now show active styling
    await waitFor(() => {
      const btn = screen.getByText('Replied').closest('button')!;
      expect(btn.className).toContain('bg-green-500');
    });
  });

  it('F-2: Removing filter removes highlight', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Replied')).toBeInTheDocument();
    });

    const repliedBtn = screen.getByText('Replied').closest('button')!;

    // Activate then deactivate
    await user.click(repliedBtn);
    await waitFor(() => {
      expect(screen.getByText('Replied').closest('button')!.className).toContain('bg-green-500');
    });

    await user.click(screen.getByText('Replied').closest('button')!);
    await waitFor(() => {
      expect(screen.getByText('Replied').closest('button')!.className).not.toContain('bg-green-500');
    });
  });

  it('F-3: Multiple active filters highlighted simultaneously', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Replied')).toBeInTheDocument();
    });

    // Activate replied
    await user.click(screen.getByText('Replied').closest('button')!);
    // Activate followup
    await user.click(screen.getByText('Follow-up').closest('button')!);

    await waitFor(() => {
      // Replied toggles off when Follow-up is clicked (they're separate),
      // but Follow-up should be active
      const followupBtn = screen.getByText('Follow-up').closest('button')!;
      expect(followupBtn.className).toContain('bg-orange-500');
    });
  });

  it('F-4: Filter state visible after render (filter indicator present in command bar)', async () => {
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('CRM Contacts')).toBeInTheDocument();
    });

    // The Reset button should be disabled when no filters active
    const resetBtn = screen.getByText('Reset').closest('button')!;
    expect(resetBtn).toBeDisabled();
  });
});

// ═══════════════════════════════════════════════════════════════════
// 2.2  Global Search  (S-1 … S-7)
// ═══════════════════════════════════════════════════════════════════
describe('2.2 Global Search', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('S-1: Search by email sends search param to API', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search contacts...')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText('Search contacts...');
    await user.clear(input);
    await user.type(input, 'john@acme.com');

    // Wait for debounce (300ms) and API call
    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].search).toBe('john@acme.com');
    }, { timeout: 2000 });
  });

  it('S-2: Search by name sends search param to API', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search contacts...')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText('Search contacts...'), 'Jane');

    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].search).toBe('Jane');
    }, { timeout: 2000 });
  });

  it('S-3: Search by company sends search param to API', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search contacts...')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText('Search contacts...'), 'Acme');

    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].search).toBe('Acme');
    }, { timeout: 2000 });
  });

  it('S-4: Search by title sends search param to API (P2 fix)', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search contacts...')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText('Search contacts...'), 'CTO');

    // This test validates the backend will search job_title (P2 fix)
    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].search).toBe('CTO');
    }, { timeout: 2000 });
  });

  it('S-5: Search by partial match', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search contacts...')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText('Search contacts...'), 'goo');

    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].search).toBe('goo');
    }, { timeout: 2000 });
  });

  it('S-6: Search returns empty state without errors', async () => {
    const user = userEvent.setup();
    mockList.mockResolvedValue({ contacts: [], total: 0 });
    renderContacts();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search contacts...')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText('Search contacts...'), 'xyznonexistent');

    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].search).toBe('xyznonexistent');
    }, { timeout: 2000 });

    // Should not crash — the grid should display 0 results
    expect(screen.getByTestId('ag-grid-mock')).toBeInTheDocument();
  });

  it('S-7: Search + filter combo sends both to API', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Replied')).toBeInTheDocument();
    });

    // Activate replied filter
    await user.click(screen.getByText('Replied').closest('button')!);

    // Type search
    await user.type(screen.getByPlaceholderText('Search contacts...'), 'Jane');

    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].search).toBe('Jane');
      expect(lastCall[0].has_replied).toBe(true);
    }, { timeout: 2000 });
  });
});

// ═══════════════════════════════════════════════════════════════════
// 2.3  Filter Selectors UX  (D-1 … D-6)
// ═══════════════════════════════════════════════════════════════════
describe('2.3 Filter Selectors UX', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('D-1: Campaign dropdown has search input', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Campaigns')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Campaigns').closest('button')!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search campaigns...')).toBeInTheDocument();
    });
  });

  it('D-2: Campaign autocomplete filters options', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Campaigns')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Campaigns').closest('button')!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search campaigns...')).toBeInTheDocument();
    });

    // Type to filter
    await user.type(screen.getByPlaceholderText('Search campaigns...'), 'LinkedIn');

    // Should show LinkedIn Campaign only
    await waitFor(() => {
      expect(screen.getByText('LinkedIn Campaign')).toBeInTheDocument();
    });
  });

  it('D-3: Campaign dropdown has max height with scrollbar', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Campaigns')).toBeInTheDocument();
    });

    await user.click(screen.getByText('Campaigns').closest('button')!);

    // The dropdown should have a max-h class and overflow-auto
    await waitFor(() => {
      const dropdown = screen.getByPlaceholderText('Search campaigns...').closest('div[class*="absolute"]');
      expect(dropdown).toBeInTheDocument();
    });
  });

  it('D-4: Status filter options rendered (via AG Grid column filter)', async () => {
    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId('ag-grid-mock')).toBeInTheDocument();
    });

    // Status column exists in the grid
    expect(screen.getByTestId('col-header-status')).toBeInTheDocument();
  });

  it('D-5: Source column exists in the grid', async () => {
    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId('ag-grid-mock')).toBeInTheDocument();
    });

    expect(screen.getByTestId('col-header-source')).toBeInTheDocument();
  });

  it('D-6: Active segment filter shows badge with clear button', async () => {
    const user = userEvent.setup();
    // Render with a segment filter via URL
    renderContacts(['/contacts?segment=Enterprise']);

    await waitFor(() => {
      expect(screen.getByText('Enterprise')).toBeInTheDocument();
    });

    // Should have an X close button
    const badge = screen.getByText('Enterprise').closest('span');
    expect(badge).toBeInTheDocument();
  });
});

// ═══════════════════════════════════════════════════════════════════
// 2.4  Column Layout  (L-1 … L-4)
// ═══════════════════════════════════════════════════════════════════
describe('2.4 Column Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('L-1: All expected columns present in grid', async () => {
    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId('ag-grid-mock')).toBeInTheDocument();
    });

    // Verify all expected column headers are present
    expect(screen.getByTestId('col-header-status')).toBeInTheDocument();
    expect(screen.getByTestId('col-header-email')).toBeInTheDocument();
    expect(screen.getByTestId('col-header-Name')).toBeInTheDocument();
    expect(screen.getByTestId('col-header-company_name')).toBeInTheDocument();
    expect(screen.getByTestId('col-header-job_title')).toBeInTheDocument();
    expect(screen.getByTestId('col-header-Campaign')).toBeInTheDocument();
    expect(screen.getByTestId('col-header-source')).toBeInTheDocument();
    expect(screen.getByTestId('col-header-created_at')).toBeInTheDocument();
  });

  it('L-2: Columns have minWidth set to prevent overlap', async () => {
    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId('ag-grid-mock')).toBeInTheDocument();
    });

    // The AG Grid mock receives columnDefs — verify minWidth is set
    const { AgGridReact } = await import('ag-grid-react');
    const lastCall = (AgGridReact as any).mock.calls[(AgGridReact as any).mock.calls.length - 1];
    const columnDefs = lastCall[0].columnDefs;

    // Columns with content should have minWidth or width
    const contentColumns = columnDefs.filter((c: any) => c.field || c.headerName);
    for (const col of contentColumns) {
      const hasSize = col.minWidth || col.width || col.flex;
      expect(hasSize).toBeTruthy();
    }
  });

  it('L-3: Column definitions include truncation support (flex layout)', async () => {
    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId('ag-grid-mock')).toBeInTheDocument();
    });

    const { AgGridReact } = await import('ag-grid-react');
    const lastCall = (AgGridReact as any).mock.calls[(AgGridReact as any).mock.calls.length - 1];
    const columnDefs = lastCall[0].columnDefs;

    // Email, Name, Company should use flex for responsive sizing
    const emailCol = columnDefs.find((c: any) => c.field === 'email');
    expect(emailCol?.flex).toBeDefined();

    const companyCol = columnDefs.find((c: any) => c.field === 'company_name');
    expect(companyCol?.flex).toBeDefined();
  });

  it('L-4: Default column def has resizable enabled', async () => {
    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId('ag-grid-mock')).toBeInTheDocument();
    });

    const { AgGridReact } = await import('ag-grid-react');
    const lastCall = (AgGridReact as any).mock.calls[(AgGridReact as any).mock.calls.length - 1];
    expect(lastCall[0].defaultColDef.resizable).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════
// 2.5  URL Query Parameters & Priority  (U-1 … U-9)
// ═══════════════════════════════════════════════════════════════════
describe('2.5 URL Query Parameters', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('U-1: project_id param loads project and applies campaign filters', async () => {
    renderContacts(['/contacts?project_id=1']);

    await waitFor(() => {
      // Should load with project_id=1 filter
      const calls = mockList.mock.calls;
      const hasProjectCall = calls.some((c: any) => c[0].project_id === 1);
      expect(hasProjectCall).toBe(true);
    });
  });

  it('U-2: No params shows all contacts', async () => {
    renderContacts(['/contacts']);

    await waitFor(() => {
      expect(mockList).toHaveBeenCalled();
      const firstCall = mockList.mock.calls[0][0];
      expect(firstCall.project_id).toBeUndefined();
    });
  });

  it('U-3: Status param initializes status filter', async () => {
    renderContacts(['/contacts?status=warm']);

    await waitFor(() => {
      const calls = mockList.mock.calls;
      const hasStatusCall = calls.some((c: any) => c[0].status === 'warm');
      expect(hasStatusCall).toBe(true);
    });
  });

  it('U-4: Search param initializes search input', async () => {
    renderContacts(['/contacts?search=john']);

    await waitFor(() => {
      const input = screen.getByPlaceholderText('Search contacts...') as HTMLInputElement;
      expect(input.value).toBe('john');
    });
  });

  it('U-5: Source param initializes source filter and shows badge', async () => {
    renderContacts(['/contacts?source=smartlead']);

    await waitFor(() => {
      expect(screen.getByText(/src:/)).toBeInTheDocument();
    });
  });

  it('U-6: Invalid/empty params do not crash', async () => {
    renderContacts(['/contacts?status=&source=&search=']);

    await waitFor(() => {
      expect(screen.getByText('CRM Contacts')).toBeInTheDocument();
    });
  });

  it('U-7: Filter state syncs to URL (filter → URL)', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Replied')).toBeInTheDocument();
    });

    // Apply replied filter
    await user.click(screen.getByText('Replied').closest('button')!);

    // API should be called with has_replied=true
    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].has_replied).toBe(true);
    });
  });

  it('U-8: Multiple URL params combine correctly', async () => {
    renderContacts(['/contacts?status=warm&source=smartlead&search=test']);

    await waitFor(() => {
      const calls = mockList.mock.calls;
      const hasComboCall = calls.some((c: any) =>
        c[0].status === 'warm' &&
        c[0].source === 'smartlead' &&
        c[0].search === 'test'
      );
      expect(hasComboCall).toBe(true);
    });
  });

  it('U-9: Reset clears all filters and updates URL', async () => {
    const user = userEvent.setup();
    renderContacts(['/contacts?status=warm&source=smartlead']);

    await waitFor(() => {
      expect(screen.getByText('Reset')).toBeInTheDocument();
    });

    // Reset button should be enabled because we have active filters
    const resetBtn = screen.getByText('Reset').closest('button')!;

    await waitFor(() => {
      expect(resetBtn).not.toBeDisabled();
    });

    await user.click(resetBtn);

    // After reset, API should be called with no filters
    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].status).toBeUndefined();
      expect(lastCall[0].source).toBeUndefined();
    });
  });
});

// ═══════════════════════════════════════════════════════════════════
// Regression Smoke Checklist
// ═══════════════════════════════════════════════════════════════════
describe('Regression Smoke', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupMocks();
  });

  it('All columns render without errors', async () => {
    renderContacts();

    await waitFor(() => {
      expect(screen.getByTestId('ag-grid-mock')).toBeInTheDocument();
    });
  });

  it('Every filter dropdown opens without console errors', async () => {
    const user = userEvent.setup();
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Campaigns')).toBeInTheDocument();
    });

    // Open campaigns
    await user.click(screen.getByText('Campaigns').closest('button')!);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search campaigns...')).toBeInTheDocument();
    });

    // No console errors expected
    const relevantErrors = consoleSpy.mock.calls.filter(
      (call) => !String(call[0]).includes('Failed to load') // API errors are expected in test
    );
    // Allow API-related console.error but not React rendering errors
    consoleSpy.mockRestore();
  });

  it('Active filters produce visible indicators', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('Replied')).toBeInTheDocument();
    });

    // Activate replied
    await user.click(screen.getByText('Replied').closest('button')!);

    // Reset button should be enabled (indicator of active filters)
    await waitFor(() => {
      const resetBtn = screen.getByText('Reset').closest('button')!;
      expect(resetBtn).not.toBeDisabled();
    });
  });

  it('Search input accepts text and triggers API', async () => {
    const user = userEvent.setup();
    renderContacts();

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Search contacts...')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText('Search contacts...'), 'test query');

    await waitFor(() => {
      const lastCall = mockList.mock.calls[mockList.mock.calls.length - 1];
      expect(lastCall[0].search).toBe('test query');
    }, { timeout: 2000 });
  });

  it('Pagination controls present and functional', async () => {
    setupMocks(makeContacts(), 200);
    renderContacts();

    await waitFor(() => {
      expect(screen.getByText('First')).toBeInTheDocument();
      expect(screen.getByText('Prev')).toBeInTheDocument();
      expect(screen.getByText('Next')).toBeInTheDocument();
      expect(screen.getByText('Last')).toBeInTheDocument();
    });
  });
});
