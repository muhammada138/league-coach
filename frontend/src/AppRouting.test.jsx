import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import App from './App';
import * as riotApi from './api/riot';

vi.mock('@vercel/speed-insights/react', () => ({
  SpeedInsights: () => <div data-testid="speed-insights" />
}));

// Mock the riot api so dashboard rendering works
vi.mock('./api/riot', () => ({
  getLpHistory: vi.fn(),
  getProfile: vi.fn(),
  analyzeSummoner: vi.fn(),
  getSummoner: vi.fn(),
  getRunesMap: vi.fn(),
  getIngestStatus: vi.fn(),
}));

// Hide console.error during tests to suppress React act() warnings that occur due to components with complex side effects.
const originalError = console.error;
beforeEach(() => {
    console.error = vi.fn();
});

afterEach(() => {
    console.error = originalError;
});

// Mock global fetch since some components use it
globalThis.fetch = vi.fn().mockResolvedValue({
    json: () => Promise.resolve({}),
});

window.scrollTo = vi.fn();

describe('App Routing', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/');
    vi.clearAllMocks();
  });

  it('renders Home component on /', async () => {
    render(<App />);
    await waitFor(() => {
        expect(screen.getByText(/Stop guessing\./i)).toBeInTheDocument();
    });
  });

  it('renders Dashboard on /player/:region/:gameName/:tagLine', async () => {
    window.history.pushState({}, '', '/player/na1/Faker/NA1');

    riotApi.getSummoner.mockResolvedValue({ puuid: 'test' });
    riotApi.getProfile.mockResolvedValue({ tier: 'GOLD', division: 'I', wins: 0, losses: 0, lp: 0 });
    riotApi.analyzeSummoner.mockResolvedValue({
      games: [],
      coaching: '',
      playerAverages: { kda: 0, cspm: 0, visionScore: 0, winRate: 0 },
      lobbyAverages: { kda: 0, cspm: 0, visionScore: 0, winRate: 0 },
      deltas: {},
    });
    riotApi.getLpHistory.mockResolvedValue([]);

    render(<App />);
    await waitFor(() => {
        expect(screen.getByText(/AI Coaching/i)).toBeInTheDocument();
    });
  });

  it('renders TermsOfService on /terms', async () => {
    window.history.pushState({}, '', '/terms');
    render(<App />);
    await waitFor(() => {
        expect(screen.getByRole('heading', { name: /Terms of Service/i })).toBeInTheDocument();
    });
  });

  it('renders PrivacyPolicy on /privacy', async () => {
    window.history.pushState({}, '', '/privacy');
    render(<App />);
    await waitFor(() => {
        expect(screen.getByRole('heading', { name: /Privacy Policy/i })).toBeInTheDocument();
    });
  });

  it('renders IngestDashboard on /admin/ingest', async () => {
    window.history.pushState({}, '', '/admin/ingest');
    riotApi.getIngestStatus.mockResolvedValue({ is_paused: true, total_matches: 0 });
    render(<App />);
    await waitFor(() => {
        expect(screen.getByText(/ML Training Ingestion/i)).toBeInTheDocument();
    });
  });
});
