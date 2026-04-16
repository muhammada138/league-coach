import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock the SpeedInsights component
vi.mock('@vercel/speed-insights/react', () => ({
  SpeedInsights: () => <div data-testid="speed-insights" />
}));

// Mock the page components to easily identify them
vi.mock('./pages/Home', () => ({ default: () => <div data-testid="home-page" /> }));
vi.mock('./pages/Dashboard', () => ({ default: () => <div data-testid="dashboard-page" /> }));
vi.mock('./pages/IngestDashboard', () => ({ default: () => <div data-testid="ingest-dashboard-page" /> }));
vi.mock('./pages/TermsOfService', () => ({ default: () => <div data-testid="terms-page" /> }));
vi.mock('./pages/PrivacyPolicy', () => ({ default: () => <div data-testid="privacy-page" /> }));
vi.mock('./components/Navbar', () => ({ default: () => <nav data-testid="navbar" /> }));

describe('App', () => {
  beforeEach(() => {
    // Reset URL to root before each test
    window.history.pushState({}, '', '/');
  });

  it('renders without crashing and shows Home on default route', () => {
    render(<App />);

    expect(screen.getByTestId('navbar')).toBeInTheDocument();
    expect(screen.getByTestId('home-page')).toBeInTheDocument();
    expect(screen.getByTestId('speed-insights')).toBeInTheDocument();
  });

  it('renders Dashboard component for /player/:region/:gameName/:tagLine route', () => {
    window.history.pushState({}, '', '/player/na/Riot/123');
    render(<App />);
    expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
  });

  it('renders IngestDashboard component for /admin/ingest route', () => {
    window.history.pushState({}, '', '/admin/ingest');
    render(<App />);
    expect(screen.getByTestId('ingest-dashboard-page')).toBeInTheDocument();
  });

  it('renders TermsOfService component for /terms route', () => {
    window.history.pushState({}, '', '/terms');
    render(<App />);
    expect(screen.getByTestId('terms-page')).toBeInTheDocument();
  });

  it('renders PrivacyPolicy component for /privacy route', () => {
    window.history.pushState({}, '', '/privacy');
    render(<App />);
    expect(screen.getByTestId('privacy-page')).toBeInTheDocument();
  });

  it('applies dark mode transition classes to the main container', () => {
    const { container } = render(<App />);
    const mainDiv = container.querySelector('.min-h-screen');

    expect(mainDiv).toBeInTheDocument();
    expect(mainDiv).toHaveClass('bg-slate-50');
    expect(mainDiv).toHaveClass('dark:bg-[#05080f]');
    expect(mainDiv).toHaveClass('transition-colors');
    expect(mainDiv).toHaveClass('duration-300');
  });
});
