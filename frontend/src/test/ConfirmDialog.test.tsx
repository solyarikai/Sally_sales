import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { ConfirmDialog } from '../components/ConfirmDialog';

describe('ConfirmDialog', () => {
  const defaultProps = {
    isOpen: true,
    title: 'Delete item?',
    message: 'This action cannot be undone.',
    onConfirm: vi.fn(),
    onCancel: vi.fn(),
  };

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <ConfirmDialog {...defaultProps} isOpen={false} />
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders title and message when open', () => {
    render(<ConfirmDialog {...defaultProps} />);
    expect(screen.getByText('Delete item?')).toBeInTheDocument();
    expect(screen.getByText('This action cannot be undone.')).toBeInTheDocument();
  });

  it('renders default button text (Confirm / Cancel)', () => {
    render(<ConfirmDialog {...defaultProps} />);
    expect(screen.getByText('Confirm')).toBeInTheDocument();
    expect(screen.getByText('Cancel')).toBeInTheDocument();
  });

  it('renders custom button text', () => {
    render(
      <ConfirmDialog
        {...defaultProps}
        confirmText="Yes, delete"
        cancelText="No, keep it"
      />
    );
    expect(screen.getByText('Yes, delete')).toBeInTheDocument();
    expect(screen.getByText('No, keep it')).toBeInTheDocument();
  });

  it('calls onConfirm when confirm button is clicked', async () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog {...defaultProps} onConfirm={onConfirm} />);
    await userEvent.click(screen.getByText('Confirm'));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when cancel button is clicked', async () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog {...defaultProps} onCancel={onCancel} />);
    await userEvent.click(screen.getByText('Cancel'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when backdrop is clicked', async () => {
    const onCancel = vi.fn();
    const { container } = render(
      <ConfirmDialog {...defaultProps} onCancel={onCancel} />
    );
    // Backdrop is the first child div with bg-black/30
    const backdrop = container.querySelector('.bg-black\\/30');
    expect(backdrop).toBeTruthy();
    await userEvent.click(backdrop!);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when X button is clicked', async () => {
    const onCancel = vi.fn();
    render(<ConfirmDialog {...defaultProps} onCancel={onCancel} />);
    // The X button is the btn-icon button
    const xButton = document.querySelector('.btn-icon');
    expect(xButton).toBeTruthy();
    await userEvent.click(xButton!);
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('shows danger icon for danger variant', () => {
    render(<ConfirmDialog {...defaultProps} variant="danger" />);
    // The danger variant adds a red alert triangle icon container
    const dangerIcon = document.querySelector('.bg-red-100');
    expect(dangerIcon).toBeInTheDocument();
  });

  it('applies danger styling to confirm button for danger variant', () => {
    render(<ConfirmDialog {...defaultProps} variant="danger" />);
    const confirmBtn = screen.getByText('Confirm');
    expect(confirmBtn.className).toContain('btn-danger');
  });

  it('applies primary styling to confirm button for default variant', () => {
    render(<ConfirmDialog {...defaultProps} />);
    const confirmBtn = screen.getByText('Confirm');
    expect(confirmBtn.className).toContain('btn-primary');
  });
});
