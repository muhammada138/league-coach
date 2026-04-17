import { render, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { useContext } from 'react';
import { ThemeProvider } from './ThemeProvider';
import { ThemeContext } from './ThemeContext';

describe('ThemeProvider', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  const TestComponent = () => {
    const { dark, toggle } = useContext(ThemeContext);
    return (
      <div>
        <span data-testid="theme-status">{dark ? 'dark' : 'light'}</span>
        <button data-testid="toggle-btn" onClick={toggle}>Toggle</button>
      </div>
    );
  };

  it('should initialize with dark theme by default if localStorage is empty', () => {
    const { getByTestId } = render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    expect(getByTestId('theme-status').textContent).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem('theme')).toBe('dark');
  });

  it('should initialize with theme from localStorage', () => {
    localStorage.setItem('theme', 'light');

    const { getByTestId } = render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    expect(getByTestId('theme-status').textContent).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });

  it('should toggle theme when toggle function is called', () => {
    const { getByTestId } = render(
      <ThemeProvider>
        <TestComponent />
      </ThemeProvider>
    );

    expect(getByTestId('theme-status').textContent).toBe('dark');

    act(() => {
      getByTestId('toggle-btn').click();
    });

    expect(getByTestId('theme-status').textContent).toBe('light');
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(localStorage.getItem('theme')).toBe('light');

    act(() => {
      getByTestId('toggle-btn').click();
    });

    expect(getByTestId('theme-status').textContent).toBe('dark');
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(localStorage.getItem('theme')).toBe('dark');
  });
});
