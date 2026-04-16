import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock the components since we only want to test routing
vi.mock('@vercel/speed-insights/react', () => ({
  SpeedInsights: () => <div data-testid="speed-insights" />
}));

vi.mock('./pages/Home', () => ({ default: () => <div data-testid="home-page" /> }));
vi.mock('./pages/Dashboard', () => ({ default: () => <div data-testid="dashboard-page" /> }));
vi.mock('./pages/IngestDashboard', () => ({ default: () => <div data-testid="ingest-page" /> }));
vi.mock('./pages/TermsOfService', () => ({ default: () => <div data-testid="terms-page" /> }));
vi.mock('./pages/PrivacyPolicy', () => ({ default: () => <div data-testid="privacy-page" /> }));

// Mock Navbar to reduce noise in snapshot or rendering
vi.mock('./components/Navbar', () => ({ default: () => <nav data-testid="navbar" /> }));

// To avoid issues with ResizeObserver that might be used by charts or components, mock it
global.ResizeObserver = vi.fn().mockImplementation(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}));

describe('App Routing', () => {
  beforeEach(() => {
    // Reset the route before each test
    window.history.pushState({}, 'Test page', '/');
  });

  it('renders without crashing and shows common elements', () => {
    render(<App />);

    expect(screen.getByTestId('navbar')).toBeInTheDocument();
    expect(screen.getByTestId('speed-insights')).toBeInTheDocument();
  });

  it('renders Home component on root path "/"', () => {
    window.history.pushState({}, 'Home page', '/');
    render(<App />);
    expect(screen.getByTestId('home-page')).toBeInTheDocument();
  });

  it('renders Dashboard component on "/player/:region/:gameName/:tagLine"', () => {
    window.history.pushState({}, 'Dashboard page', '/player/na1/Faker/hide');
    render(<App />);
    expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
  });

  it('renders IngestDashboard component on "/admin/ingest"', () => {
    window.history.pushState({}, 'Ingest page', '/admin/ingest');
    render(<App />);
    expect(screen.getByTestId('ingest-page')).toBeInTheDocument();
  });

  it('renders TermsOfService component on "/terms"', () => {
    window.history.pushState({}, 'Terms page', '/terms');
    render(<App />);
    expect(screen.getByTestId('terms-page')).toBeInTheDocument();
  });

  it('renders PrivacyPolicy component on "/privacy"', () => {
    window.history.pushState({}, 'Privacy page', '/privacy');
    render(<App />);
    expect(screen.getByTestId('privacy-page')).toBeInTheDocument();
  });

  it('does not render known pages on an unknown route', () => {
    window.history.pushState({}, 'Unknown page', '/unknown-route-123');
    render(<App />);

    // The navbar and speed insights should still render
    expect(screen.getByTestId('navbar')).toBeInTheDocument();
    expect(screen.getByTestId('speed-insights')).toBeInTheDocument();

    // None of the main pages should render
    expect(screen.queryByTestId('home-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('dashboard-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('ingest-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('terms-page')).not.toBeInTheDocument();
    expect(screen.queryByTestId('privacy-page')).not.toBeInTheDocument();
  });
});
