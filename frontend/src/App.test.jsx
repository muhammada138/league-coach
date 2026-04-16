import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock the SpeedInsights component since we don't need to test it here
vi.mock('@vercel/speed-insights/react', () => ({
  SpeedInsights: () => <div data-testid="speed-insights" />
}));

// Mock page components to verify routing
vi.mock('./pages/Home', () => ({
  default: () => <div data-testid="page-home">Home Page</div>
}));
vi.mock('./pages/Dashboard', () => ({
  default: () => <div data-testid="page-dashboard">Dashboard Page</div>
}));
vi.mock('./pages/IngestDashboard', () => ({
  default: () => <div data-testid="page-ingest">Ingest Page</div>
}));
vi.mock('./pages/TermsOfService', () => ({
  default: () => <div data-testid="page-terms">Terms Page</div>
}));
vi.mock('./pages/PrivacyPolicy', () => ({
  default: () => <div data-testid="page-privacy">Privacy Page</div>
}));

// Mock Navbar to isolate page routing
vi.mock('./components/Navbar', () => ({
  default: () => <nav data-testid="navbar">Navbar</nav>
}));

// Create a wrapper component to render App, mocking local storage for RegionSelector
describe('App Routing', () => {
  beforeEach(() => {
    // Reset window.history to root before each test
    window.history.pushState({}, 'Test page', '/');
    vi.clearAllMocks();
  });

  it('renders Navbar and SpeedInsights on all routes', () => {
    render(<App />);
    expect(screen.getByTestId('navbar')).toBeInTheDocument();
    expect(screen.getByTestId('speed-insights')).toBeInTheDocument();
  });

  it('renders Home component on root path "/"', () => {
    window.history.pushState({}, 'Test page', '/');
    render(<App />);
    expect(screen.getByTestId('page-home')).toBeInTheDocument();
  });

  it('renders Dashboard component on player path "/player/:region/:gameName/:tagLine"', () => {
    window.history.pushState({}, 'Test page', '/player/na1/Faker/KR1');
    render(<App />);
    expect(screen.getByTestId('page-dashboard')).toBeInTheDocument();
  });

  it('renders IngestDashboard component on admin path "/admin/ingest"', () => {
    window.history.pushState({}, 'Test page', '/admin/ingest');
    render(<App />);
    expect(screen.getByTestId('page-ingest')).toBeInTheDocument();
  });

  it('renders TermsOfService component on path "/terms"', () => {
    window.history.pushState({}, 'Test page', '/terms');
    render(<App />);
    expect(screen.getByTestId('page-terms')).toBeInTheDocument();
  });

  it('renders PrivacyPolicy component on path "/privacy"', () => {
    window.history.pushState({}, 'Test page', '/privacy');
    render(<App />);
    expect(screen.getByTestId('page-privacy')).toBeInTheDocument();
  });
});
