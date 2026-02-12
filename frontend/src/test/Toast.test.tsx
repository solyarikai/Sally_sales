import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ToastProvider, useToast } from '../components/Toast';

// Helper to trigger toasts from within provider
function ToastTrigger() {
  const { success, error, warning, info, toasts } = useToast();
  return (
    <div>
      <button onClick={() => success('Success title', 'Success desc')}>
        trigger-success
      </button>
      <button onClick={() => error('Error title', 'Error desc')}>
        trigger-error
      </button>
      <button onClick={() => warning('Warning title')}>trigger-warning</button>
      <button onClick={() => info('Info title')}>trigger-info</button>
      <span data-testid="toast-count">{toasts.length}</span>
    </div>
  );
}

describe('ToastProvider', () => {
  it('renders children', () => {
    render(
      <ToastProvider>
        <div>Child content</div>
      </ToastProvider>
    );
    expect(screen.getByText('Child content')).toBeInTheDocument();
  });

  it('success() adds a toast with title and description', async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );

    await act(async () => {
      screen.getByText('trigger-success').click();
    });

    expect(screen.getByText('Success title')).toBeInTheDocument();
    expect(screen.getByText('Success desc')).toBeInTheDocument();
  });

  it('error() adds a toast with title and description', async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );

    await act(async () => {
      screen.getByText('trigger-error').click();
    });

    expect(screen.getByText('Error title')).toBeInTheDocument();
    expect(screen.getByText('Error desc')).toBeInTheDocument();
  });

  it('warning() adds a toast', async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );

    await act(async () => {
      screen.getByText('trigger-warning').click();
    });

    expect(screen.getByText('Warning title')).toBeInTheDocument();
  });

  it('info() adds a toast', async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );

    await act(async () => {
      screen.getByText('trigger-info').click();
    });

    expect(screen.getByText('Info title')).toBeInTheDocument();
  });

  it('increments toast count after each trigger', async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );

    expect(screen.getByTestId('toast-count').textContent).toBe('0');

    await act(async () => {
      screen.getByText('trigger-success').click();
    });
    expect(screen.getByTestId('toast-count').textContent).toBe('1');

    await act(async () => {
      screen.getByText('trigger-error').click();
    });
    expect(screen.getByTestId('toast-count').textContent).toBe('2');
  });
});

describe('useToast outside provider', () => {
  it('throws when used without ToastProvider', () => {
    // Suppress console.error for this test
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});

    function BadComponent() {
      useToast();
      return null;
    }

    expect(() => render(<BadComponent />)).toThrow(
      'useToast must be used within a ToastProvider'
    );

    spy.mockRestore();
  });
});
