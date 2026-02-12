import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { TemplatesPage } from '../pages/TemplatesPage';

// Mock API
const mockTemplatesList = vi.fn();
vi.mock('../api', () => ({
  templatesApi: {
    list: (...args: unknown[]) => mockTemplatesList(...args),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

// Mock store
vi.mock('../store/appStore', () => ({
  useAppStore: () => ({
    templates: [
      {
        id: 1,
        name: 'Company Research',
        prompt_template: 'Research {{company}}',
        output_column: 'research',
        tags: ['research'],
        is_system: false,
        user_id: 1,
        created_at: '2024-01-01',
        updated_at: null,
      },
      {
        id: 2,
        name: 'System Template',
        prompt_template: 'System prompt',
        output_column: 'sys',
        tags: ['system'],
        is_system: true,
        user_id: 1,
        created_at: '2024-01-01',
        updated_at: null,
      },
    ],
    setTemplates: vi.fn(),
    addTemplate: vi.fn(),
  }),
}));

describe('TemplatesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTemplatesList.mockResolvedValue([]);
  });

  it('renders the Prompt Templates heading', async () => {
    render(
      <MemoryRouter>
        <TemplatesPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Prompt Templates')).toBeInTheDocument();
    });
  });

  it('renders template names from store', () => {
    render(
      <MemoryRouter>
        <TemplatesPage />
      </MemoryRouter>
    );
    expect(screen.getByText('Company Research')).toBeInTheDocument();
    expect(screen.getByText('System Template')).toBeInTheDocument();
  });

  it('renders New Template button', () => {
    render(
      <MemoryRouter>
        <TemplatesPage />
      </MemoryRouter>
    );
    expect(screen.getByText('New Template')).toBeInTheDocument();
  });

  it('shows tag filter pills', () => {
    render(
      <MemoryRouter>
        <TemplatesPage />
      </MemoryRouter>
    );
    // Tags appear both in filter pills and on cards — check at least one each
    expect(screen.getAllByText('research').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('system').length).toBeGreaterThanOrEqual(1);
  });

  it('opens create form when New Template clicked', async () => {
    render(
      <MemoryRouter>
        <TemplatesPage />
      </MemoryRouter>
    );
    await userEvent.click(screen.getByText('New Template'));
    expect(screen.getByPlaceholderText(/template name/i)).toBeInTheDocument();
  });

  it('calls list API on mount', () => {
    render(
      <MemoryRouter>
        <TemplatesPage />
      </MemoryRouter>
    );
    expect(mockTemplatesList).toHaveBeenCalled();
  });
});
