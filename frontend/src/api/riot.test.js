import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getLiveEnrich, getSummoner, getProfile, analyzeSummoner, getHistory, getScoreboard, askCoach, getLiveGame, getWinPredict, getLpHistory, getTeammates, getIngestStatus, toggleIngest } from './riot';

const { mockGet, mockPost } = vi.hoisted(() => ({
  mockGet: vi.fn(),
  mockPost: vi.fn(),
}));

vi.mock('axios', () => {
  return {
    default: {
      create: vi.fn(() => ({
        get: mockGet,
        post: mockPost,
        interceptors: {
          response: { use: vi.fn() }
        }
      }))
    }
  };
});

describe('Riot API Wrappers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getLiveEnrich', () => {
    it('handles API errors gracefully', async () => {
      const mockError = new Error('Live Enrich API Error');
      mockPost.mockRejectedValueOnce(mockError);
      await expect(getLiveEnrich(['puuid1'])).rejects.toThrow('Live Enrich API Error');
    });
    it('should call api.post with correct parameters (default values) and return data', async () => {
      const mockData = { enrichData: 'test' };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const puuids = ['puuid1', 'puuid2'];
      const result = await getLiveEnrich(puuids);

      expect(mockPost).toHaveBeenCalledWith('/live-enrich', {
        puuids,
        queue_id: 420,
        region: 'na1',
      });
      expect(result).toEqual(mockData);
    });

    it('should call api.post with explicitly provided parameters', async () => {
      const mockData = { enrichData: 'test2' };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const puuids = ['puuid3'];
      const result = await getLiveEnrich(puuids, 440, 'euw1');

      expect(mockPost).toHaveBeenCalledWith('/live-enrich', {
        puuids,
        queue_id: 440,
        region: 'euw1',
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getSummoner', () => {
    it('fetches summoner data with default region', async () => {
      const mockData = { id: '123', name: 'Faker' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getSummoner('Hide on bush', 'KR1');

      expect(mockGet).toHaveBeenCalledWith(
        '/summoner/Hide%20on%20bush/KR1',
        { params: { region: 'na1' } }
      );
      expect(result).toEqual(mockData);
    });

    it('fetches summoner data with explicit region', async () => {
      const mockData = { id: '123', name: 'Faker' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getSummoner('Hide on bush', 'KR1', 'kr');

      expect(mockGet).toHaveBeenCalledWith(
        '/summoner/Hide%20on%20bush/KR1',
        { params: { region: 'kr' } }
      );
      expect(result).toEqual(mockData);
    });

    it('properly URI encodes gameName and tagLine', async () => {
      const mockData = { id: '123', name: 'Faker' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getSummoner('Test / Name', 'Tag # Line');

      expect(mockGet).toHaveBeenCalledWith(
        '/summoner/Test%20%2F%20Name/Tag%20%23%20Line',
        { params: { region: 'na1' } }
      );
      expect(result).toEqual(mockData);
    });

    it('throws an error if the API call fails', async () => {
      const mockError = new Error('API Error');
      mockGet.mockRejectedValueOnce(mockError);

      await expect(getSummoner('Hide on bush', 'KR1')).rejects.toThrow('API Error');
    });
  });

  describe('getProfile', () => {
    it('should fetch profile with default region (na1)', async () => {
      const mockData = { name: 'Player', level: 100 };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getProfile('test-puuid');

      expect(mockGet).toHaveBeenCalledWith('/profile/test-puuid', {
        params: { region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should fetch profile with a custom region', async () => {
      const mockData = { name: 'PlayerEU', level: 200 };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getProfile('test-puuid-eu', 'euw1');

      expect(mockGet).toHaveBeenCalledWith('/profile/test-puuid-eu', {
        params: { region: 'euw1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should handle API errors appropriately', async () => {
      const mockError = new Error('API Error');
      mockGet.mockRejectedValueOnce(mockError);

      await expect(getProfile('error-puuid')).rejects.toThrow('API Error');
    });
  });

  describe('analyzeSummoner', () => {
    it('fetches analyzed summoner data with correct default parameters', async () => {
      const mockData = { analyzed: true };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await analyzeSummoner('puuid1', 'GameName');

      expect(mockGet).toHaveBeenCalledWith('/analyze/puuid1', {
        params: { game_name: 'GameName', count: 10, region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getHistory', () => {
    it('fetches match history correctly', async () => {
      const mockData = { matches: [] };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getHistory('puuid2', 0, 20);

      expect(mockGet).toHaveBeenCalledWith('/history/puuid2', {
        params: { start: 0, count: 20, queue: 420, region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getScoreboard', () => {
    it('fetches match scoreboard correctly', async () => {
      const mockData = { scoreboard: [] };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getScoreboard('match_123');

      expect(mockGet).toHaveBeenCalledWith('/match/match_123/scoreboard', {
        params: { region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('askCoach', () => {
    it('calls POST /ask correctly', async () => {
      const mockData = { answer: 'Yes' };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const result = await askCoach('question?', 'context', 'history');

      expect(mockPost).toHaveBeenCalledWith('/ask', {
        question: 'question?',
        context: 'context',
        history: 'history'
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getLiveGame', () => {
    it('fetches live game data correctly', async () => {
      const mockData = { gameId: 1 };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getLiveGame('puuid3');

      expect(mockGet).toHaveBeenCalledWith('/live/puuid3', {
        params: { region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getWinPredict', () => {
    it('calls POST /win-predict correctly', async () => {
      const mockData = { prediction: 0.8 };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const result = await getWinPredict([{ id: 1 }], { stats: 1 });

      expect(mockPost).toHaveBeenCalledWith('/win-predict', {
        participants: [{ id: 1 }],
        live_stats: { stats: 1 }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getLpHistory', () => {
    it('fetches lp history correctly', async () => {
      const mockData = { lp: [] };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getLpHistory('puuid4');

      expect(mockGet).toHaveBeenCalledWith('/lp-history/puuid4', {
        params: { queue: 'RANKED_SOLO_5x5' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getTeammates', () => {
    it('fetches teammates correctly', async () => {
      const mockData = { teammates: [] };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getTeammates('puuid5');

      expect(mockGet).toHaveBeenCalledWith('/teammates/puuid5');
      expect(result).toEqual(mockData);
    });
  });

  describe('getIngestStatus', () => {
    it('fetches ingest status correctly', async () => {
      const mockData = { status: 'ok' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getIngestStatus();

      expect(mockGet).toHaveBeenCalledWith('/ingest/status');
      expect(result).toEqual(mockData);
    });
  });

  describe('toggleIngest', () => {
    it('toggles ingest status correctly', async () => {
      const mockData = { toggled: true };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const result = await toggleIngest();

      expect(mockPost).toHaveBeenCalledWith('/ingest/toggle');
      expect(result).toEqual(mockData);
    });
  });
});
