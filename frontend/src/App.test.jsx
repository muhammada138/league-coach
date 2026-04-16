import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

// Mock the components that fetch data or might be complex
vi.mock('@vercel/speed-insights/react', () => ({
  SpeedInsights: () => <div data-testid="speed-insights" />
}));

// Provide basic stubs for components so we can identify them
vi.mock('./pages/Home', () => ({ default: () => <div data-testid="home-page">Home Page</div> }));
vi.mock('./pages/Dashboard', () => ({ default: () => <div data-testid="dashboard-page">Dashboard Page</div> }));
vi.mock('./pages/IngestDashboard', () => ({ default: () => <div data-testid="ingest-dashboard-page">Ingest Dashboard Page</div> }));
vi.mock('./pages/TermsOfService', () => ({ default: () => <div data-testid="terms-page">Terms of Service</div> }));
vi.mock('./pages/PrivacyPolicy', () => ({ default: () => <div data-testid="privacy-page">Privacy Policy</div> }));

describe('App Routing', () => {
  beforeEach(() => {
    // Reset the history before each test to ensure a clean state
    window.history.pushState({}, '', '/');
  });

  it('renders without crashing and shows Home page on default route', () => {
    render(<App />);

    // Check if the Navbar is present
    const navbars = document.querySelectorAll('nav');
    expect(navbars.length).toBeGreaterThan(0);

    // Check if the SpeedInsights component is rendered
    expect(screen.getByTestId('speed-insights')).toBeInTheDocument();

    // Verify default route (Home)
    expect(screen.getByTestId('home-page')).toBeInTheDocument();
  });

  it('navigates to Terms of Service page', () => {
    window.history.pushState({}, '', '/terms');
    render(<App />);
    expect(screen.getByTestId('terms-page')).toBeInTheDocument();
  });

  it('navigates to Privacy Policy page', () => {
    window.history.pushState({}, '', '/privacy');
    render(<App />);
    expect(screen.getByTestId('privacy-page')).toBeInTheDocument();
  });

  it('navigates to Ingest Dashboard page', () => {
    window.history.pushState({}, '', '/admin/ingest');
    render(<App />);
    expect(screen.getByTestId('ingest-dashboard-page')).toBeInTheDocument();
  });

  it('navigates to Dashboard page for a player', () => {
    window.history.pushState({}, '', '/player/na1/Riot/123');
    render(<App />);
    expect(screen.getByTestId('dashboard-page')).toBeInTheDocument();
  });
});
