import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { JobProgressCard } from '../components/JobProgressCard';
import type { EnrichmentJob } from '../types';

// Mock the useJobProgress hook
vi.mock('../hooks/useJobProgress', () => ({
  useJobProgress: () => ({ progress: null }),
}));

const baseJob: EnrichmentJob = {
  id: 1,
  dataset_id: 1,
  output_column: 'email_verified',
  custom_prompt: 'verify email',
  model: 'gpt-4o-mini',
  status: 'completed',
  total_rows: 100,
  processed_rows: 100,
  failed_rows: 0,
  error_message: null,
  created_at: '2024-01-01',
  updated_at: '2024-01-01',
};

describe('JobProgressCard', () => {
  it('renders column name', () => {
    render(<JobProgressCard job={baseJob} />);
    expect(screen.getByText('email_verified')).toBeInTheDocument();
  });

  it('shows completed state with row count', () => {
    render(<JobProgressCard job={baseJob} />);
    expect(screen.getByText(/100 rows/)).toBeInTheDocument();
  });

  it('shows failed rows count when present', () => {
    render(
      <JobProgressCard
        job={{ ...baseJob, failed_rows: 5 }}
      />
    );
    expect(screen.getByText(/5 failed/)).toBeInTheDocument();
  });

  it('shows progress bar when processing', () => {
    const processingJob = {
      ...baseJob,
      status: 'processing' as const,
      processed_rows: 50,
    };
    const { container } = render(<JobProgressCard job={processingJob} />);
    // Shows progress text
    expect(screen.getByText('50/100')).toBeInTheDocument();
    expect(screen.getByText('50%')).toBeInTheDocument();
    // Has progress bar
    const bar = container.querySelector('.bg-blue-600');
    expect(bar).toBeTruthy();
  });

  it('shows stop button when running', () => {
    const processingJob = {
      ...baseJob,
      status: 'processing' as const,
      processed_rows: 30,
    };
    const onStop = vi.fn();
    const { container } = render(
      <JobProgressCard job={processingJob} onStop={onStop} />
    );
    // Stop button has the Square icon
    const stopBtn = container.querySelector('.hover\\:bg-red-100');
    expect(stopBtn).toBeTruthy();
  });

  it('calls onStop when stop button is clicked', async () => {
    const processingJob = {
      ...baseJob,
      status: 'processing' as const,
      processed_rows: 30,
    };
    const onStop = vi.fn();
    const { container } = render(
      <JobProgressCard job={processingJob} onStop={onStop} />
    );
    const stopBtn = container.querySelector('.hover\\:bg-red-100') as HTMLElement;
    await userEvent.click(stopBtn);
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it('shows error message for failed jobs', () => {
    const failedJob = {
      ...baseJob,
      status: 'failed' as const,
      error_message: 'API rate limit exceeded',
    };
    render(<JobProgressCard job={failedJob} />);
    expect(screen.getByText('API rate limit exceeded')).toBeInTheDocument();
  });

  it('shows cancelled state with row counts', () => {
    const cancelledJob = {
      ...baseJob,
      status: 'cancelled' as const,
      processed_rows: 42,
    };
    render(<JobProgressCard job={cancelledJob} />);
    expect(screen.getByText('42/100 rows')).toBeInTheDocument();
  });

  it('shows edit button for completed jobs when onEdit provided', () => {
    const onEdit = vi.fn();
    const { container } = render(
      <JobProgressCard job={baseJob} onEdit={onEdit} />
    );
    const editBtn = container.querySelector('[title="Edit & run again"]');
    expect(editBtn).toBeTruthy();
  });

  it('shows rerun button for completed jobs when onRerun provided', () => {
    const onRerun = vi.fn();
    const { container } = render(
      <JobProgressCard job={baseJob} onRerun={onRerun} />
    );
    const rerunBtn = container.querySelector('[title="Run again"]');
    expect(rerunBtn).toBeTruthy();
  });

  it('calls onEdit with job when edit button clicked', async () => {
    const onEdit = vi.fn();
    const { container } = render(
      <JobProgressCard job={baseJob} onEdit={onEdit} />
    );
    const editBtn = container.querySelector('[title="Edit & run again"]') as HTMLElement;
    await userEvent.click(editBtn);
    expect(onEdit).toHaveBeenCalledWith(baseJob);
  });

  it('calls onRerun with job when rerun button clicked', async () => {
    const onRerun = vi.fn();
    const { container } = render(
      <JobProgressCard job={baseJob} onRerun={onRerun} />
    );
    const rerunBtn = container.querySelector('[title="Run again"]') as HTMLElement;
    await userEvent.click(rerunBtn);
    expect(onRerun).toHaveBeenCalledWith(baseJob);
  });

  it('applies correct border color for each status', () => {
    const statuses = [
      { status: 'processing', borderClass: 'border-blue-200' },
      { status: 'completed', borderClass: 'border-emerald-100' },
      { status: 'failed', borderClass: 'border-red-100' },
      { status: 'cancelled', borderClass: 'border-neutral-200' },
    ];

    for (const { status, borderClass } of statuses) {
      const { container, unmount } = render(
        <JobProgressCard
          job={{ ...baseJob, status: status as any, processed_rows: 50 }}
        />
      );
      expect(container.firstChild).toHaveClass(borderClass);
      unmount();
    }
  });
});
