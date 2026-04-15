import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';

// Mock the SpeedInsights component since we don't need to test it here
vi.mock('@vercel/speed-insights/react', () => ({
  SpeedInsights: () => <div data-testid="speed-insights" />
}));

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);

    // We should be on the home page by default
    // Let's verify we see the Home text (assuming Home component has some recognizable text like "League Coach" or similar from the Navbar)
    // Actually, we can just test if the Navbar is present as it's rendered on all routes
    const navbars = document.querySelectorAll('nav');
    expect(navbars.length).toBeGreaterThan(0);

    // Check if the SpeedInsights component is rendered
    expect(screen.getByTestId('speed-insights')).toBeInTheDocument();
  });
});
