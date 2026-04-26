import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ThemeToggle from './ThemeToggle';
import * as useThemeHook from '../hooks/useTheme';

describe('ThemeToggle', () => {
  it('renders correctly with dark theme', () => {
    vi.spyOn(useThemeHook, 'useTheme').mockReturnValue({ dark: true, toggle: vi.fn() });

    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: /Switch to light mode/i });
    expect(button).toBeInTheDocument();
  });

  it('renders correctly with light theme', () => {
    vi.spyOn(useThemeHook, 'useTheme').mockReturnValue({ dark: false, toggle: vi.fn() });

    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: /Switch to dark mode/i });
    expect(button).toBeInTheDocument();
  });

  it('calls toggle function when clicked', () => {
    const mockToggle = vi.fn();
    vi.spyOn(useThemeHook, 'useTheme').mockReturnValue({ dark: false, toggle: mockToggle });

    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: /Switch to dark mode/i });
    fireEvent.click(button);

    expect(mockToggle).toHaveBeenCalledTimes(1);
  });
});
