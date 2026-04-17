import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ThemeToggle from './ThemeToggle';
import * as useThemeHook from '../hooks/useTheme';

describe('ThemeToggle', () => {
  it('renders correctly with dark theme', () => {
    vi.spyOn(useThemeHook, 'useTheme').mockReturnValue({ dark: true, toggle: vi.fn() });

    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: /toggle theme/i });
    expect(button).toBeInTheDocument();

    // Check elements are present
    expect(screen.getByText('Light')).toBeInTheDocument();
    expect(screen.getByText('Dark')).toBeInTheDocument();

    // With dark=true, the toggle circle should be on the right (left-[calc(50%-1px)])
    const toggleCircle = button.querySelector('span:first-child');
    expect(toggleCircle.className).toContain('left-[calc(50%-1px)]');
  });

  it('renders correctly with light theme', () => {
    vi.spyOn(useThemeHook, 'useTheme').mockReturnValue({ dark: false, toggle: vi.fn() });

    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: /toggle theme/i });
    expect(button).toBeInTheDocument();

    // With dark=false, the toggle circle should be on the left (left-0.5)
    const toggleCircle = button.querySelector('span:first-child');
    expect(toggleCircle.className).toContain('left-0.5');
  });

  it('calls toggle function when clicked', () => {
    const mockToggle = vi.fn();
    vi.spyOn(useThemeHook, 'useTheme').mockReturnValue({ dark: false, toggle: mockToggle });

    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: /toggle theme/i });
    fireEvent.click(button);

    expect(mockToggle).toHaveBeenCalledTimes(1);
  });
});
