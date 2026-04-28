import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ThemeToggle from './ThemeToggle';
import * as useThemeHook from '../hooks/useTheme';

describe('ThemeToggle', () => {
  it('renders correctly with dark theme', () => {
    vi.spyOn(useThemeHook, 'useTheme').mockReturnValue({ dark: true, toggle: vi.fn() });

    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: /Switch to (light|dark) mode/i });
    expect(button).toBeInTheDocument();

    const svgs = button.querySelectorAll('svg');
    expect(svgs[0].className.baseVal || svgs[0].className).toContain('opacity-100');
    expect(svgs[1].className.baseVal || svgs[1].className).toContain('opacity-0');
  });

  it('renders correctly with light theme', () => {
    vi.spyOn(useThemeHook, 'useTheme').mockReturnValue({ dark: false, toggle: vi.fn() });

    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: /Switch to (light|dark) mode/i });
    expect(button).toBeInTheDocument();

    const svgs = button.querySelectorAll('svg');
    expect(svgs[0].className.baseVal || svgs[0].className).toContain('opacity-0');
    expect(svgs[1].className.baseVal || svgs[1].className).toContain('opacity-100');
  });

  it('calls toggle function when clicked', () => {
    const mockToggle = vi.fn();
    vi.spyOn(useThemeHook, 'useTheme').mockReturnValue({ dark: false, toggle: mockToggle });

    render(<ThemeToggle />);

    const button = screen.getByRole('button', { name: /Switch to (light|dark) mode/i });
    fireEvent.click(button);

    expect(mockToggle).toHaveBeenCalledTimes(1);
  });
});
