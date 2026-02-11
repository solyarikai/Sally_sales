import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ImportModal } from '../components/ImportModal';

// Mock the API
vi.mock('../api', () => ({
  datasetsApi: {
    uploadCsv: vi.fn(),
    importGoogleSheets: vi.fn(),
  },
}));

// Mock the store
vi.mock('../store/appStore', () => ({
  useAppStore: () => ({
    addDataset: vi.fn(),
    setCurrentDataset: vi.fn(),
  }),
}));

describe('ImportModal', () => {
  const defaultProps = {
    isOpen: true,
    onClose: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders nothing when isOpen is false', () => {
    const { container } = render(<ImportModal isOpen={false} onClose={vi.fn()} />);
    expect(container.innerHTML).toBe('');
  });

  it('renders modal title "Import Data"', () => {
    render(<ImportModal {...defaultProps} />);
    expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Import Data');
  });

  it('renders CSV and Google Sheets method buttons', () => {
    render(<ImportModal {...defaultProps} />);
    expect(screen.getByText('Upload CSV')).toBeInTheDocument();
    expect(screen.getByText('Google Sheets')).toBeInTheDocument();
  });

  it('renders dataset name input', () => {
    render(<ImportModal {...defaultProps} />);
    expect(screen.getByPlaceholderText('My Lead List')).toBeInTheDocument();
  });

  it('shows CSV upload area by default', () => {
    render(<ImportModal {...defaultProps} />);
    expect(screen.getByText('Click or drag to upload')).toBeInTheDocument();
    expect(screen.getByText('CSV files up to 50MB')).toBeInTheDocument();
  });

  it('switches to Google Sheets URL input when clicked', async () => {
    render(<ImportModal {...defaultProps} />);
    await userEvent.click(screen.getByText('Google Sheets'));
    expect(
      screen.getByPlaceholderText('https://docs.google.com/spreadsheets/d/...')
    ).toBeInTheDocument();
  });

  it('renders Cancel and Import buttons', () => {
    render(<ImportModal {...defaultProps} />);
    expect(screen.getByText('Cancel')).toBeInTheDocument();
    // "Import Data" appears as both h2 title and button text
    const importTexts = screen.getAllByText('Import Data');
    expect(importTexts.length).toBeGreaterThanOrEqual(2);
  });

  it('Import button is disabled when no file is selected (CSV mode)', () => {
    render(<ImportModal {...defaultProps} />);
    const importBtn = screen.getAllByText('Import Data').find(
      (el) => el.tagName === 'SPAN'
    );
    // The button parent should be disabled
    const btn = importBtn?.closest('button');
    expect(btn).toBeDisabled();
  });

  it('calls onClose when Cancel is clicked', async () => {
    const onClose = vi.fn();
    render(<ImportModal isOpen={true} onClose={onClose} />);
    await userEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when backdrop is clicked', async () => {
    const onClose = vi.fn();
    const { container } = render(<ImportModal isOpen={true} onClose={onClose} />);
    const backdrop = container.querySelector('.bg-black\\/30');
    expect(backdrop).toBeTruthy();
    await userEvent.click(backdrop!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('shows Google Sheets help text about public access', async () => {
    render(<ImportModal {...defaultProps} />);
    await userEvent.click(screen.getByText('Google Sheets'));
    expect(
      screen.getByText(/publicly accessible/)
    ).toBeInTheDocument();
  });
});
