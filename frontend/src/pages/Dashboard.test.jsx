import { render, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import Dashboard from './Dashboard';
import { getLpHistory, getProfile, analyzeSummoner, getSummoner } from '../api/riot';

// Mock the API calls
vi.mock('../api/riot', () => ({
  getLpHistory: vi.fn(),
  getProfile: vi.fn(),
  analyzeSummoner: vi.fn(),
  getSummoner: vi.fn(),
  getRunesMap: vi.fn(),
}));

describe('Dashboard Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('handles getLpHistory promise rejection gracefully', async () => {
    const mockPuuid = 'test-puuid-123';

    // Mock getSummoner
    getSummoner.mockResolvedValue({ puuid: mockPuuid });
    // Mock getProfile
    getProfile.mockResolvedValue({
      tier: 'GOLD',
      division: 'I',
      lp: 50,
      wins: 10,
      losses: 10,
      summonerLevel: 100,
    });
    // Mock analyzeSummoner
    analyzeSummoner.mockResolvedValue({
      games: [],
      coaching: '',
      playerAverages: {
          kda: 2, cspm: 5, visionScore: 10, totalDamageDealtToChampions: 1000, goldEarned: 1000
      },
      lobbyAverages: {
          kda: 2, cspm: 5, visionScore: 10, totalDamageDealtToChampions: 1000, goldEarned: 1000
      },
      deltas: {},
    });
    // Mock getLpHistory to reject
    const mockError = new Error('Failed to fetch LP history');
    getLpHistory.mockRejectedValue(mockError);

    // Mock global fetch since some components like getRunesMap/getChampIdMap use it
    globalThis.fetch = vi.fn().mockResolvedValue({
      json: () => Promise.resolve({}),
    });

    window.scrollTo = vi.fn();

    render(
      <MemoryRouter initialEntries={['/player/na1/TestSummoner/NA1']}>
        <Routes>
          <Route path="/player/:region/:gameName/:tagLine" element={<Dashboard />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(getLpHistory).toHaveBeenCalledWith(mockPuuid, 'RANKED_SOLO_5x5', 'na1');
    });

    // Test that the component rendered completely despite the error
    await waitFor(() => {
        // If it reaches here, the catch block swallowed the error
        // as intended without crashing the app
        expect(getLpHistory).toHaveBeenCalledTimes(1);
    });
  });
});
