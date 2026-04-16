import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  getLiveEnrich, getSummoner, getProfile, analyzeSummoner,
  getHistory, getScoreboard, askCoach, getLiveGame, getWinPredict,
  getLpHistory, getTeammates, getIngestStatus, toggleIngest
} from './riot';

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
    it('should fetch summoner analysis with default parameters', async () => {
      const mockData = { analysis: 'good' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await analyzeSummoner('puuid1', 'GameName');

      expect(mockGet).toHaveBeenCalledWith('/analyze/puuid1', {
        params: { game_name: 'GameName', count: 10, region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should fetch summoner analysis with explicit parameters', async () => {
      const mockData = { analysis: 'better' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await analyzeSummoner('puuid2', 'GameName2', 20, 'euw1');

      expect(mockGet).toHaveBeenCalledWith('/analyze/puuid2', {
        params: { game_name: 'GameName2', count: 20, region: 'euw1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getHistory', () => {
    it('should fetch history with default parameters', async () => {
      const mockData = { matches: [] };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getHistory('puuid1', 0, 10);

      expect(mockGet).toHaveBeenCalledWith('/history/puuid1', {
        params: { start: 0, count: 10, queue: 420, region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should fetch history with explicit parameters', async () => {
      const mockData = { matches: ['match1'] };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getHistory('puuid2', 10, 5, 440, 'euw1');

      expect(mockGet).toHaveBeenCalledWith('/history/puuid2', {
        params: { start: 10, count: 5, queue: 440, region: 'euw1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getScoreboard', () => {
    it('should fetch scoreboard with default region', async () => {
      const mockData = { scoreboard: {} };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getScoreboard('match1');

      expect(mockGet).toHaveBeenCalledWith('/match/match1/scoreboard', {
        params: { region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should fetch scoreboard with explicit region', async () => {
      const mockData = { scoreboard: {} };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getScoreboard('match2', 'kr');

      expect(mockGet).toHaveBeenCalledWith('/match/match2/scoreboard', {
        params: { region: 'kr' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('askCoach', () => {
    it('should post question, context, and history', async () => {
      const mockData = { answer: 'yes' };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const result = await askCoach('q1', 'ctx1', 'hist1');

      expect(mockPost).toHaveBeenCalledWith('/ask', {
        question: 'q1',
        context: 'ctx1',
        history: 'hist1'
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getLiveGame', () => {
    it('should fetch live game with default region', async () => {
      const mockData = { gameId: 1 };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getLiveGame('puuid1');

      expect(mockGet).toHaveBeenCalledWith('/live/puuid1', {
        params: { region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should fetch live game with explicit region', async () => {
      const mockData = { gameId: 2 };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getLiveGame('puuid2', 'kr');

      expect(mockGet).toHaveBeenCalledWith('/live/puuid2', {
        params: { region: 'kr' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getWinPredict', () => {
    it('should post participants and live_stats', async () => {
      const mockData = { winProbability: 0.75 };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const result = await getWinPredict(['p1'], { stats: 1 });

      expect(mockPost).toHaveBeenCalledWith('/win-predict', {
        participants: ['p1'],
        live_stats: { stats: 1 }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getLpHistory', () => {
    it('should fetch lp history with default queue', async () => {
      const mockData = { history: [] };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getLpHistory('puuid1');

      expect(mockGet).toHaveBeenCalledWith('/lp-history/puuid1', {
        params: { queue: 'RANKED_SOLO_5x5' }
      });
      expect(result).toEqual(mockData);
    });

    it('should fetch lp history with explicit queue', async () => {
      const mockData = { history: [] };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getLpHistory('puuid2', 'RANKED_FLEX_SR');

      expect(mockGet).toHaveBeenCalledWith('/lp-history/puuid2', {
        params: { queue: 'RANKED_FLEX_SR' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getTeammates', () => {
    it('should fetch teammates', async () => {
      const mockData = { teammates: [] };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getTeammates('puuid1');

      expect(mockGet).toHaveBeenCalledWith('/teammates/puuid1');
      expect(result).toEqual(mockData);
    });
  });

  describe('getIngestStatus', () => {
    it('should fetch ingest status', async () => {
      const mockData = { status: 'running' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await getIngestStatus();

      expect(mockGet).toHaveBeenCalledWith('/ingest/status');
      expect(result).toEqual(mockData);
    });
  });

  describe('toggleIngest', () => {
    it('should post toggle ingest', async () => {
      const mockData = { success: true };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const result = await toggleIngest();

      expect(mockPost).toHaveBeenCalledWith('/ingest/toggle');
      expect(result).toEqual(mockData);
    });
  });
});
