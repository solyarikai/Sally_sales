import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Layout } from '../components/Layout';

// Mock the API
vi.mock('../api', () => ({
  companiesApi: {
    listCompanies: vi.fn().mockResolvedValue([
      {
        id: 1,
        name: 'Acme Corp',
        color: '#3B82F6',
        prospects_count: 500,
        datasets_count: 3,
        documents_count: 2,
        user_id: 1,
        environment_id: 1,
        description: null,
        website: null,
        logo_url: null,
        is_active: true,
        created_at: '2024-01-01',
        updated_at: null,
      },
    ]),
    getCompany: vi.fn().mockResolvedValue({
      id: 1,
      name: 'Acme Corp',
      color: '#3B82F6',
      prospects_count: 500,
      datasets_count: 3,
      documents_count: 2,
      user_id: 1,
      environment_id: 1,
    }),
  },
}));

// Mock contacts API (Layout calls contactsApi.listProjects on mount)
vi.mock('../api/contacts', () => ({
  contactsApi: {
    listProjects: vi.fn().mockResolvedValue([
      { id: 1, name: 'Test Project', description: 'desc', target_segments: 'tech', contact_count: 10, created_at: '2024-01-01', updated_at: '2024-01-01' },
    ]),
  },
}));

// Mock store — vi.mock is hoisted, so define the mock object inline
vi.mock('../store/appStore', () => {
  const store = {
    currentCompany: {
      id: 1,
      name: 'Acme Corp',
      color: '#3B82F6',
      prospects_count: 500,
      datasets_count: 3,
      documents_count: 2,
      user_id: 1,
      environment_id: 1,
    },
    companies: [
      {
        id: 1,
        name: 'Acme Corp',
        color: '#3B82F6',
        prospects_count: 500,
        datasets_count: 3,
        documents_count: 2,
        user_id: 1,
        environment_id: 1,
      },
    ],
    currentProject: { id: 1, name: 'Test Project', description: 'desc', target_segments: 'tech', contact_count: 10, created_at: '2024-01-01', updated_at: '2024-01-01' },
    projects: [
      { id: 1, name: 'Test Project', description: 'desc', target_segments: 'tech', contact_count: 10, created_at: '2024-01-01', updated_at: '2024-01-01' },
    ],
    setCurrentCompany: vi.fn(),
    setCompanies: vi.fn(),
    setCurrentProject: vi.fn(),
    setProjects: vi.fn(),
    resetCompanyData: vi.fn(),
  };

  const useAppStore = () => store;
  useAppStore.getState = () => store;

  return { useAppStore };
});

function renderWithRouter(children: React.ReactNode, initialPath = '/company/1/data') {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/company/:companyId/*" element={<Layout>{children}</Layout>} />
        <Route path="/*" element={<Layout>{children}</Layout>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders children content', () => {
    renderWithRouter(<div>Page content</div>);
    expect(screen.getByText('Page content')).toBeInTheDocument();
  });

  it('renders the LeadGen logo text', () => {
    renderWithRouter(<div>Test</div>);
    expect(screen.getByText('LeadGen')).toBeInTheDocument();
  });

  it('renders navigation items', () => {
    renderWithRouter(<div>Test</div>);
    expect(screen.getByText('Data Search')).toBeInTheDocument();
    expect(screen.getByText('Data')).toBeInTheDocument();
    expect(screen.getByText('Prospects')).toBeInTheDocument();
    expect(screen.getByText('CRM')).toBeInTheDocument();
    expect(screen.getByText('Knowledge')).toBeInTheDocument();
    expect(screen.getByText('Replies')).toBeInTheDocument();
    expect(screen.getByText('Search Results')).toBeInTheDocument();
    expect(screen.getByText('Pipeline')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('renders the project selector with current project name', () => {
    renderWithRouter(<div>Test</div>);
    expect(screen.getByText('Test Project')).toBeInTheDocument();
  });

  it('toggles project dropdown on click', async () => {
    renderWithRouter(<div>Test</div>);
    const projectButton = screen.getByText('Test Project');
    await userEvent.click(projectButton);
    expect(screen.getByText('Switch Project')).toBeInTheDocument();
  });

  it('renders S logo icon', () => {
    renderWithRouter(<div>Test</div>);
    expect(screen.getByText('S')).toBeInTheDocument();
  });
});
