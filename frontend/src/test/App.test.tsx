import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock all page components to simple stubs
vi.mock('../pages/DataSearchPage', () => ({
  DataSearchPage: () => <div data-testid="data-search-page">DataSearchPage</div>,
}));
vi.mock('../pages/HomePage', () => ({
  HomePage: () => <div data-testid="home-page">HomePage</div>,
}));
vi.mock('../pages/DatasetsPage', () => ({
  DatasetsPage: () => <div data-testid="datasets-page">DatasetsPage</div>,
}));
vi.mock('../pages/AllProspectsPage', () => ({
  AllProspectsPage: () => <div data-testid="prospects-page">AllProspectsPage</div>,
}));
vi.mock('../pages/KnowledgeBasePage', () => ({
  __esModule: true,
  default: () => <div data-testid="kb-page">KnowledgeBasePage</div>,
}));
vi.mock('../pages/RepliesPage', () => ({
  RepliesPage: () => <div data-testid="replies-page">RepliesPage</div>,
}));
vi.mock('../pages/ContactsPage', () => ({
  ContactsPage: () => <div data-testid="contacts-page">ContactsPage</div>,
}));
vi.mock('../pages/TemplatesPage', () => ({
  TemplatesPage: () => <div data-testid="templates-page">TemplatesPage</div>,
}));
vi.mock('../pages/SettingsPage', () => ({
  SettingsPage: () => <div data-testid="settings-page">SettingsPage</div>,
}));
vi.mock('../pages/DashboardPage', () => ({
  DashboardPage: () => <div data-testid="dashboard-page">DashboardPage</div>,
}));
vi.mock('../pages/PromptDebugPage', () => ({
  __esModule: true,
  default: () => <div data-testid="prompt-debug-page">PromptDebugPage</div>,
}));
vi.mock('../pages/TasksPage', () => ({
  TasksPage: () => <div data-testid="tasks-page">TasksPage</div>,
}));

// Mock Layout to just render children
vi.mock('../components/Layout', () => ({
  Layout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="layout">{children}</div>
  ),
}));

// Mock ErrorBoundary
vi.mock('../components/ErrorBoundary', () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Mock Toast
vi.mock('../components/Toast', () => ({
  ToastProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  useToast: () => ({
    toast: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
  setToastFunction: vi.fn(),
}));

// Mock store
vi.mock('../store/appStore', () => ({
  useAppStore: () => ({
    currentCompany: { id: 1, name: 'Test', color: '#000' },
    companies: [],
    setCurrentCompany: vi.fn(),
    setCompanies: vi.fn(),
    resetCompanyData: vi.fn(),
  }),
}));

vi.mock('../api', () => ({
  companiesApi: {
    listCompanies: vi.fn().mockResolvedValue([]),
    getCompany: vi.fn().mockResolvedValue({ id: 1, name: 'Test' }),
  },
}));

// Need to import App after all mocks
import App from '../App';

describe('App routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset window location
    window.history.pushState({}, '', '/');
  });

  it('renders DataSearchPage at root /', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('data-search-page')).toBeInTheDocument();
    });
  });

  it('renders DataSearchPage at /data-search', async () => {
    window.history.pushState({}, '', '/data-search');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('data-search-page')).toBeInTheDocument();
    });
  });

  it('renders HomePage at /companies', async () => {
    window.history.pushState({}, '', '/companies');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('home-page')).toBeInTheDocument();
    });
  });

  it('renders DashboardPage at /dashboard', async () => {
    window.history.pushState({}, '', '/dashboard');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });
  });

  it('renders RepliesPage at /replies inside Layout', async () => {
    window.history.pushState({}, '', '/replies');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('replies-page')).toBeInTheDocument();
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });

  it('renders ContactsPage at /contacts inside Layout', async () => {
    window.history.pushState({}, '', '/contacts');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('contacts-page')).toBeInTheDocument();
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });

  it('renders TemplatesPage at /templates inside Layout', async () => {
    window.history.pushState({}, '', '/templates');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('templates-page')).toBeInTheDocument();
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });

  it('renders SettingsPage at /settings inside Layout', async () => {
    window.history.pushState({}, '', '/settings');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('settings-page')).toBeInTheDocument();
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });

  it('renders TasksPage at /tasks inside Layout', async () => {
    window.history.pushState({}, '', '/tasks');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('tasks-page')).toBeInTheDocument();
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });

  it('renders PromptDebugPage at /prompt-debug inside Layout', async () => {
    window.history.pushState({}, '', '/prompt-debug');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('prompt-debug-page')).toBeInTheDocument();
      expect(screen.getByTestId('layout')).toBeInTheDocument();
    });
  });

  it('renders DatasetsPage at /company/:id/data', async () => {
    window.history.pushState({}, '', '/company/1/data');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('datasets-page')).toBeInTheDocument();
    });
  });

  it('renders AllProspectsPage at /company/:id/prospects', async () => {
    window.history.pushState({}, '', '/company/1/prospects');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('prospects-page')).toBeInTheDocument();
    });
  });

  it('renders ContactsPage at /company/:id/contacts', async () => {
    window.history.pushState({}, '', '/company/1/contacts');
    render(<App />);
    await waitFor(() => {
      expect(screen.getByTestId('contacts-page')).toBeInTheDocument();
    });
  });
});
