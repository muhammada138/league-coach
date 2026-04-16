import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

vi.mock('@vercel/speed-insights/react', () => ({
  SpeedInsights: () => <div data-testid="speed-insights" />
}));

vi.mock('./context/ThemeProvider', () => ({
  ThemeProvider: ({ children }) => <div data-testid="theme-provider">{children}</div>
}));

vi.mock('./components/Navbar', () => ({
  default: () => <nav data-testid="navbar" />
}));

vi.mock('./pages/Home', () => ({
  default: () => <div data-testid="home-page" />
}));

vi.mock('./pages/Dashboard', () => ({
  default: () => <div data-testid="dashboard-page" />
}));

vi.mock('./pages/IngestDashboard', () => ({
  default: () => <div data-testid="ingest-page" />
}));

vi.mock('./pages/TermsOfService', () => ({
  default: () => <div data-testid="terms-page" />
}));

vi.mock('./pages/PrivacyPolicy', () => ({
  default: () => <div data-testid="privacy-page" />
}));

describe('App Component', () => {
  beforeEach(() => {
    // Reset URL to base before each test
    window.history.pushState({}, '', '/');
  });

  it('renders correctly with required context and components', () => {
    render(<App />);

    // Verify ThemeProvider wraps everything
    expect(screen.getByTestId('theme-provider')).toBeInTheDocument();

    // Verify main components render
    expect(screen.getByTestId('navbar')).toBeInTheDocument();
    expect(screen.getByTestId('home-page')).toBeInTheDocument();
    expect(screen.getByTestId('speed-insights')).toBeInTheDocument();

    // Verify the container has the expected classes
    const container = screen.getByTestId('theme-provider').firstChild;
    expect(container).toHaveClass('min-h-screen');
    expect(container).toHaveClass('bg-slate-50');
    expect(container).toHaveClass('dark:bg-[#05080f]');
  });

  describe('Routing', () => {
    it('renders Home component on root path /', () => {
      render(<App />);
      expect(screen.getByTestId('home-page')).toBeInTheDocument();
    });

    it('renders Dashboard component on /player/:region/:gameName/:tagLine', () => {
      window.history.pushState({}, '', '/player/na1/Faker/HIDE');
      render(<App />);
      expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
    });

    it('renders IngestDashboard component on /admin/ingest', () => {
      window.history.pushState({}, '', '/admin/ingest');
      render(<App />);
      expect(screen.getByTestId('ingest-page')).toBeInTheDocument();
    });

    it('renders TermsOfService component on /terms', () => {
      window.history.pushState({}, '', '/terms');
      render(<App />);
      expect(screen.getByTestId('terms-page')).toBeInTheDocument();
    });

    it('renders PrivacyPolicy component on /privacy', () => {
      window.history.pushState({}, '', '/privacy');
      render(<App />);
      expect(screen.getByTestId('privacy-page')).toBeInTheDocument();
    });

    it('handles unknown routes gracefully (does not render other pages)', () => {
      window.history.pushState({}, '', '/unknown/route/123');
      render(<App />);

      expect(screen.queryByTestId('home-page')).not.toBeInTheDocument();
      expect(screen.queryByTestId('dashboard-page')).not.toBeInTheDocument();
      expect(screen.queryByTestId('ingest-page')).not.toBeInTheDocument();
      expect(screen.queryByTestId('terms-page')).not.toBeInTheDocument();
      expect(screen.queryByTestId('privacy-page')).not.toBeInTheDocument();

      // Navbar and SpeedInsights should still render
      expect(screen.getByTestId('navbar')).toBeInTheDocument();
      expect(screen.getByTestId('speed-insights')).toBeInTheDocument();
    });
  });
});
