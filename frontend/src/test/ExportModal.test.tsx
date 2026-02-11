import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ExportModal } from '../components/ExportModal';
import type { Dataset } from '../types';

// Mock APIs
vi.mock('../api/export', () => ({
  exportApi: {
    downloadCsv: vi.fn(),
    exportToGoogleSheets: vi.fn(),
  },
}));

vi.mock('../api/integrations', () => ({
  integrationsApi: {
    getInstantly: vi.fn().mockResolvedValue({ connected: false, campaigns: [] }),
    getSmartlead: vi.fn().mockResolvedValue({ connected: false, campaigns: [] }),
    getInstantlyCampaigns: vi.fn().mockResolvedValue([]),
    sendLeadsToInstantly: vi.fn(),
    sendLeadsToSmartlead: vi.fn(),
  },
}));

vi.mock('../api/datasets', () => ({
  datasetsApi: {
    markRowsExported: vi.fn(),
  },
}));

vi.mock('../components/FieldMappingModal', () => ({
  FieldMappingModal: () => null,
}));

const mockDataset: Dataset = {
  id: 1,
  name: 'Test Dataset',
  user_id: 1,
  company_id: 1,
  row_count: 100,
  columns: ['email', 'first_name', 'company'],
  status: 'ready',
  created_at: '2024-01-01',
  updated_at: null,
  source_type: 'csv',
  source_url: null,
  is_deleted: false,
  folder_id: null,
};

describe('ExportModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
    dataset: mockDataset,
    selectedRowIds: new Set<number>(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <ExportModal {...defaultProps} isOpen={false} />
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders modal title "Export Data"', () => {
    render(<ExportModal {...defaultProps} />);
    expect(screen.getByText('Export Data')).toBeInTheDocument();
  });

  it('shows dataset name and row count', () => {
    render(<ExportModal {...defaultProps} />);
    expect(screen.getByText(/100 rows from Test Dataset/)).toBeInTheDocument();
  });

  it('renders 4 format buttons', () => {
    render(<ExportModal {...defaultProps} />);
    expect(screen.getByText('CSV')).toBeInTheDocument();
    expect(screen.getByText('Instantly')).toBeInTheDocument();
    expect(screen.getByText('Smartlead')).toBeInTheDocument();
    expect(screen.getByText('Clipboard')).toBeInTheDocument();
  });

  it('renders Cancel and Download buttons for CSV', () => {
    render(<ExportModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeInTheDocument();
    expect(screen.getByText('Download')).toBeInTheDocument();
  });

  it('changes button text when Clipboard selected', async () => {
    render(<ExportModal {...defaultProps} />);
    await userEvent.click(screen.getByText('Clipboard'));
    expect(screen.getByText('Copy to Clipboard')).toBeInTheDocument();
  });

  it('does not show "Export selected only" when no rows selected', () => {
    render(<ExportModal {...defaultProps} />);
    expect(screen.queryByText(/Export selected only/)).not.toBeInTheDocument();
  });

  it('shows "Export selected only" when rows are selected', () => {
    render(
      <ExportModal {...defaultProps} selectedRowIds={new Set([1, 2, 3])} />
    );
    expect(screen.getByText(/Export selected only \(3 rows\)/)).toBeInTheDocument();
  });

  it('calls onClose when Cancel is clicked', async () => {
    const onClose = vi.fn();
    render(<ExportModal {...defaultProps} onClose={onClose} />);
    await userEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when backdrop is clicked', async () => {
    const onClose = vi.fn();
    const { container } = render(
      <ExportModal {...defaultProps} onClose={onClose} />
    );
    const backdrop = container.querySelector('.bg-black\\/30');
    await userEvent.click(backdrop!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
