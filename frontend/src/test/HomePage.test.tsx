import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { HomePage } from '../pages/HomePage';

// Mock APIs
const mockListCompanies = vi.fn();
const mockListEnvironments = vi.fn();

vi.mock('../api', () => ({
  companiesApi: {
    listCompanies: (...args: unknown[]) => mockListCompanies(...args),
    deleteCompany: vi.fn(),
    createCompany: vi.fn(),
    updateCompany: vi.fn(),
  },
  environmentsApi: {
    listEnvironments: (...args: unknown[]) => mockListEnvironments(...args),
    createEnvironment: vi.fn(),
    updateEnvironment: vi.fn(),
    deleteEnvironment: vi.fn(),
  },
}));

// Mock store with all fields HomePage uses
vi.mock('../store/appStore', () => ({
  useAppStore: () => ({
    currentCompany: null,
    currentEnvironment: null,
    companies: [
      {
        id: 1,
        name: 'Acme Corp',
        color: '#3B82F6',
        prospects_count: 500,
        datasets_count: 3,
        documents_count: 2,
        user_id: 1,
        environment_id: null,
        description: null,
        website: null,
        logo_url: null,
        is_active: true,
        created_at: '2024-01-01',
        updated_at: null,
      },
    ],
    environments: [],
    setCurrentCompany: vi.fn(),
    setCompanies: vi.fn(),
    setCurrentEnvironment: vi.fn(),
    setEnvironments: vi.fn(),
    addCompany: vi.fn(),
    updateCompany: vi.fn(),
    removeCompany: vi.fn(),
    addEnvironment: vi.fn(),
    updateEnvironment: vi.fn(),
    removeEnvironment: vi.fn(),
    resetCompanyData: vi.fn(),
  }),
}));

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListCompanies.mockResolvedValue([]);
    mockListEnvironments.mockResolvedValue([]);
  });

  it('renders the Companies heading', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Companies')).toBeInTheDocument();
    });
  });

  it('calls list APIs on mount', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(mockListCompanies).toHaveBeenCalled();
      expect(mockListEnvironments).toHaveBeenCalled();
    });
  });

  it('renders company name from store', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Acme Corp')).toBeInTheDocument();
    });
  });

  it('shows environment section after loading', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );
    await waitFor(() => {
      // With empty environments, shows "No environments yet"
      expect(screen.getByText(/no environments/i)).toBeInTheDocument();
    });
  });
});
