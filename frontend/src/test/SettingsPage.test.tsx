import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { SettingsPage } from '../pages/SettingsPage';

// Mock APIs
vi.mock('../api', () => ({
  settingsApi: {
    getOpenAI: vi.fn().mockResolvedValue({
      has_api_key: true,
      api_key_masked: 'sk-***',
      default_model: 'gpt-4o-mini',
    }),
    testOpenAI: vi.fn(),
    updateOpenAI: vi.fn(),
  },
  integrationsApi: {
    getAll: vi.fn().mockResolvedValue({
      integrations: [
        { name: 'instantly', connected: false },
        { name: 'smartlead', connected: false },
        { name: 'findymail', connected: false },
        { name: 'millionverifier', connected: false },
      ],
    }),
    getInstantly: vi.fn().mockResolvedValue({ connected: false }),
    getSmartlead: vi.fn().mockResolvedValue({ connected: false }),
    getFindymail: vi.fn().mockResolvedValue({ connected: false }),
    getMillionverifier: vi.fn().mockResolvedValue({ connected: false }),
    connectInstantly: vi.fn(),
    disconnectInstantly: vi.fn(),
    connectSmartlead: vi.fn(),
    disconnectSmartlead: vi.fn(),
    connectFindymail: vi.fn(),
    disconnectFindymail: vi.fn(),
    connectMillionverifier: vi.fn(),
    disconnectMillionverifier: vi.fn(),
  },
}));

// Mock store
vi.mock('../store/appStore', () => ({
  useAppStore: () => ({
    openaiSettings: { has_api_key: true, api_key_masked: 'sk-***', model: 'gpt-4o-mini' },
    setOpenAISettings: vi.fn(),
  }),
}));

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the Settings heading', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });
  });

  it('renders OpenAI and Integrations tabs', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('OpenAI')).toBeInTheDocument();
      expect(screen.getByText('Integrations')).toBeInTheDocument();
    });
  });

  it('shows API key input on OpenAI tab', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      // With has_api_key=true, placeholder is dots; otherwise 'sk-proj-...'
      const input = screen.getByPlaceholderText(/•+|sk-/);
      expect(input).toBeInTheDocument();
    });
  });

  it('shows Save Settings button on OpenAI tab', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Save Settings')).toBeInTheDocument();
    });
  });

  it('shows Test Connection button on OpenAI tab', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('Test Connection')).toBeInTheDocument();
    });
  });

  it('switches to Integrations tab', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );
    await userEvent.click(screen.getByText('Integrations'));
    await waitFor(() => {
      expect(screen.getByText('Instantly.ai')).toBeInTheDocument();
      expect(screen.getByText('Smartlead')).toBeInTheDocument();
      expect(screen.getByText('Findymail')).toBeInTheDocument();
      expect(screen.getByText('MillionVerifier')).toBeInTheDocument();
    });
  });

  it('shows model selection cards', async () => {
    render(
      <MemoryRouter>
        <SettingsPage />
      </MemoryRouter>
    );
    await waitFor(() => {
      expect(screen.getByText('GPT-4o Mini')).toBeInTheDocument();
    });
  });
});
