import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import {
  LoadingSpinner,
  LoadingOverlay,
  LoadingPlaceholder,
  ButtonSpinner,
} from '../components/LoadingSpinner';

describe('LoadingSpinner', () => {
  it('renders without text by default', () => {
    const { container } = render(<LoadingSpinner />);
    // Should have the spinner icon (animate-spin)
    const spinner = container.querySelector('.animate-spin');
    expect(spinner).toBeTruthy();
    // No text element
    expect(container.querySelector('span')).toBeNull();
  });

  it('renders text when provided', () => {
    render(<LoadingSpinner text="Loading data..." />);
    expect(screen.getByText('Loading data...')).toBeInTheDocument();
  });

  it('applies sm size class', () => {
    const { container } = render(<LoadingSpinner size="sm" />);
    const spinner = container.querySelector('.animate-spin');
    expect(spinner?.className).toContain('w-4');
    expect(spinner?.className).toContain('h-4');
  });

  it('applies md size class (default)', () => {
    const { container } = render(<LoadingSpinner />);
    const spinner = container.querySelector('.animate-spin');
    expect(spinner?.className).toContain('w-6');
    expect(spinner?.className).toContain('h-6');
  });

  it('applies lg size class', () => {
    const { container } = render(<LoadingSpinner size="lg" />);
    const spinner = container.querySelector('.animate-spin');
    expect(spinner?.className).toContain('w-8');
    expect(spinner?.className).toContain('h-8');
  });

  it('applies custom className', () => {
    const { container } = render(
      <LoadingSpinner className="custom-class" />
    );
    expect(container.firstChild).toHaveClass('custom-class');
  });
});

describe('LoadingOverlay', () => {
  it('renders with default "Loading..." text', () => {
    render(<LoadingOverlay />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('renders with custom text', () => {
    render(<LoadingOverlay text="Processing..." />);
    expect(screen.getByText('Processing...')).toBeInTheDocument();
  });

  it('renders a full-screen overlay', () => {
    const { container } = render(<LoadingOverlay />);
    const overlay = container.firstChild as HTMLElement;
    expect(overlay.className).toContain('fixed');
    expect(overlay.className).toContain('inset-0');
  });
});

describe('LoadingPlaceholder', () => {
  it('renders with default "Loading..." text', () => {
    render(<LoadingPlaceholder />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });

  it('renders with custom text', () => {
    render(<LoadingPlaceholder text="Fetching records..." />);
    expect(screen.getByText('Fetching records...')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(
      <LoadingPlaceholder className="my-class" />
    );
    expect(container.firstChild).toHaveClass('my-class');
  });
});

describe('ButtonSpinner', () => {
  it('renders a small spinning icon', () => {
    const { container } = render(<ButtonSpinner />);
    const icon = container.firstChild as HTMLElement;
    expect(icon.className).toContain('animate-spin');
    expect(icon.className).toContain('w-4');
    expect(icon.className).toContain('h-4');
  });

  it('applies custom className', () => {
    const { container } = render(<ButtonSpinner className="text-white" />);
    const icon = container.firstChild as HTMLElement;
    expect(icon.className).toContain('text-white');
  });
});
