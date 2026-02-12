import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { DataTable } from '../components/DataTable';
import type { DataRow } from '../types';

// Mock useVirtualizer - return all items as virtual
vi.mock('@tanstack/react-virtual', () => ({
  useVirtualizer: ({ count }: { count: number }) => ({
    getVirtualItems: () =>
      Array.from({ length: count }, (_, i) => ({
        index: i,
        start: i * 36,
        end: (i + 1) * 36,
        size: 36,
      })),
    getTotalSize: () => count * 36,
  }),
}));

const makeRow = (index: number, data: Record<string, string>, enriched: Record<string, string> = {}): DataRow => ({
  id: index + 1,
  dataset_id: 1,
  row_index: index,
  data,
  enriched_data: enriched,
  enrichment_status: 'completed',
  created_at: '2024-01-01',
  updated_at: null,
});

const sampleRows: DataRow[] = [
  makeRow(0, { name: 'Alice', email: 'alice@test.com' }),
  makeRow(1, { name: 'Bob', email: 'bob@test.com' }),
  makeRow(2, { name: 'Charlie', email: 'charlie@test.com' }),
];

describe('DataTable', () => {
  it('renders "No data" when data is empty', () => {
    render(<DataTable data={[]} columns={['name']} />);
    expect(screen.getByText('No data')).toBeInTheDocument();
  });

  it('renders column headers', () => {
    render(<DataTable data={sampleRows} columns={['name', 'email']} />);
    expect(screen.getByText('name')).toBeInTheDocument();
    expect(screen.getByText('email')).toBeInTheDocument();
  });

  it('renders row index numbers', () => {
    render(<DataTable data={sampleRows} columns={['name']} />);
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('renders cell values', () => {
    render(<DataTable data={sampleRows} columns={['name', 'email']} />);
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('bob@test.com')).toBeInTheDocument();
  });

  it('renders enriched columns with sparkle icon', () => {
    const rows = [
      makeRow(0, { name: 'Alice' }, { summary: 'Great lead' }),
    ];
    render(<DataTable data={rows} columns={['name']} />);
    expect(screen.getByText('summary')).toBeInTheDocument();
    expect(screen.getByText('Great lead')).toBeInTheDocument();
  });

  it('shows cell expansion popup on click', async () => {
    render(<DataTable data={sampleRows} columns={['name']} />);
    // Click a cell value
    await userEvent.click(screen.getByText('Alice'));
    // Should show expanded popup with cell content
    const popups = document.querySelectorAll('.whitespace-pre-wrap');
    const hasAlice = Array.from(popups).some((el) => el.textContent === 'Alice');
    expect(hasAlice).toBe(true);
  });

  it('closes popup when clicking overlay', async () => {
    render(<DataTable data={sampleRows} columns={['name']} />);
    await userEvent.click(screen.getByText('Alice'));
    // Click the overlay to dismiss
    const overlay = document.querySelector('.fixed.inset-0.z-40');
    expect(overlay).toBeTruthy();
    await userEvent.click(overlay!);
    // Popup should be gone
    const popups = document.querySelectorAll('.whitespace-pre-wrap');
    expect(popups.length).toBe(0);
  });

  it('renders # header for index column', () => {
    render(<DataTable data={sampleRows} columns={['name']} />);
    expect(screen.getByText('#')).toBeInTheDocument();
  });

  it('truncates long cell text', () => {
    const longText = 'A'.repeat(100);
    const rows = [makeRow(0, { desc: longText })];
    render(<DataTable data={rows} columns={['desc']} />);
    // truncate(text, 40) means 40 chars + "..."
    const truncated = screen.getByText(longText.slice(0, 40) + '...');
    expect(truncated).toBeInTheDocument();
  });
});
