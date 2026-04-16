import { describe, it, expect, vi, beforeEach } from 'vitest';

// Use vi.hoisted to ensure these variables are initialized before vi.mock
const { mockGet, mockPost, interceptors } = vi.hoisted(() => {
  const get = vi.fn();
  const post = vi.fn();
  const callbacks = {};
  return {
    mockGet: get,
    mockPost: post,
    interceptors: callbacks
  };
});

vi.mock('axios', () => {
  return {
    default: {
      create: vi.fn(() => ({
        get: mockGet,
        post: mockPost,
        interceptors: {
          response: {
            use: vi.fn((successCb, errorCb) => {
              interceptors.success = successCb;
              interceptors.error = errorCb;
            })
          }
        }
      }))
    }
  };
});

import * as riot from './riot';

describe('Riot API Wrappers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('interceptors', () => {
    it('should return response on success', () => {
      const mockResponse = { data: 'test' };
      expect(interceptors.success(mockResponse)).toBe(mockResponse);
    });

    it('should log error on 429 status', async () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const mockError = { response: { status: 429 } };

      await expect(interceptors.error(mockError)).rejects.toEqual(mockError);
      expect(errorSpy).toHaveBeenCalledWith("Riot API rate limit exceeded. Please try again in a few seconds.");
      errorSpy.mockRestore();
    });

    it('should log error on ECONNABORTED code', async () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const mockError = { code: 'ECONNABORTED' };

      await expect(interceptors.error(mockError)).rejects.toEqual(mockError);
      expect(errorSpy).toHaveBeenCalledWith("The request timed out. The backend or Riot API is slow.");
      errorSpy.mockRestore();
    });

    it('should reject other errors without logging', async () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      const mockError = { response: { status: 500 } };

      await expect(interceptors.error(mockError)).rejects.toEqual(mockError);
      expect(errorSpy).not.toHaveBeenCalled();
      errorSpy.mockRestore();
    });
  });

  describe('getLiveEnrich', () => {
    it('should call api.post with correct parameters (default values) and return data', async () => {
      const mockData = { enrichData: 'test' };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const puuids = ['puuid1', 'puuid2'];
      const result = await riot.getLiveEnrich(puuids);

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
      const result = await riot.getLiveEnrich(puuids, 440, 'euw1');

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

      const result = await riot.getSummoner('Hide on bush', 'KR1');

      expect(mockGet).toHaveBeenCalledWith(
        '/summoner/Hide%20on%20bush/KR1',
        { params: { region: 'na1' } }
      );
      expect(result).toEqual(mockData);
    });

    it('fetches summoner data with explicit region', async () => {
      const mockData = { id: '123', name: 'Faker' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getSummoner('Hide on bush', 'KR1', 'kr');

      expect(mockGet).toHaveBeenCalledWith(
        '/summoner/Hide%20on%20bush/KR1',
        { params: { region: 'kr' } }
      );
      expect(result).toEqual(mockData);
    });

    it('properly URI encodes gameName and tagLine', async () => {
      const mockData = { id: '123', name: 'Faker' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getSummoner('Test / Name', 'Tag # Line');

      expect(mockGet).toHaveBeenCalledWith(
        '/summoner/Test%20%2F%20Name/Tag%20%23%20Line',
        { params: { region: 'na1' } }
      );
      expect(result).toEqual(mockData);
    });

    it('throws an error if the API call fails', async () => {
      const mockError = new Error('API Error');
      mockGet.mockRejectedValueOnce(mockError);

      await expect(riot.getSummoner('Hide on bush', 'KR1')).rejects.toThrow('API Error');
    });
  });

  describe('getProfile', () => {
    it('should fetch profile with default region (na1)', async () => {
      const mockData = { name: 'Player', level: 100 };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getProfile('test-puuid');

      expect(mockGet).toHaveBeenCalledWith('/profile/test-puuid', {
        params: { region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should fetch profile with a custom region', async () => {
      const mockData = { name: 'PlayerEU', level: 200 };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getProfile('test-puuid-eu', 'euw1');

      expect(mockGet).toHaveBeenCalledWith('/profile/test-puuid-eu', {
        params: { region: 'euw1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should handle API errors appropriately', async () => {
      const mockError = new Error('API Error');
      mockGet.mockRejectedValueOnce(mockError);

      await expect(riot.getProfile('error-puuid')).rejects.toThrow('API Error');
    });
  });
});

  describe('analyzeSummoner', () => {
    it('should call api.get with default count and region', async () => {
      const mockData = { analysis: 'test' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.analyzeSummoner('test-puuid', 'gameName');

      expect(mockGet).toHaveBeenCalledWith('/analyze/test-puuid', {
        params: { game_name: 'gameName', count: 10, region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should call api.get with explicit count and region', async () => {
      const mockData = { analysis: 'test2' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.analyzeSummoner('test-puuid', 'gameName', 20, 'euw1');

      expect(mockGet).toHaveBeenCalledWith('/analyze/test-puuid', {
        params: { game_name: 'gameName', count: 20, region: 'euw1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getHistory', () => {
    it('should call api.get with default queue and region', async () => {
      const mockData = { history: 'test' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getHistory('test-puuid', 0, 10);

      expect(mockGet).toHaveBeenCalledWith('/history/test-puuid', {
        params: { start: 0, count: 10, queue: 420, region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should call api.get with explicit queue and region', async () => {
      const mockData = { history: 'test2' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getHistory('test-puuid', 10, 20, 440, 'euw1');

      expect(mockGet).toHaveBeenCalledWith('/history/test-puuid', {
        params: { start: 10, count: 20, queue: 440, region: 'euw1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getScoreboard', () => {
    it('should call api.get with default region', async () => {
      const mockData = { scoreboard: 'test' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getScoreboard('test-match-id');

      expect(mockGet).toHaveBeenCalledWith('/match/test-match-id/scoreboard', {
        params: { region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should call api.get with explicit region', async () => {
      const mockData = { scoreboard: 'test2' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getScoreboard('test-match-id', 'euw1');

      expect(mockGet).toHaveBeenCalledWith('/match/test-match-id/scoreboard', {
        params: { region: 'euw1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('askCoach', () => {
    it('should call api.post with question, context, and history', async () => {
      const mockData = { answer: 'test' };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const result = await riot.askCoach('How to win?', 'game data', ['past game']);

      expect(mockPost).toHaveBeenCalledWith('/ask', {
        question: 'How to win?',
        context: 'game data',
        history: ['past game']
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getLiveGame', () => {
    it('should call api.get with default region', async () => {
      const mockData = { live: 'test' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getLiveGame('test-puuid');

      expect(mockGet).toHaveBeenCalledWith('/live/test-puuid', {
        params: { region: 'na1' }
      });
      expect(result).toEqual(mockData);
    });

    it('should call api.get with explicit region', async () => {
      const mockData = { live: 'test2' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getLiveGame('test-puuid', 'euw1');

      expect(mockGet).toHaveBeenCalledWith('/live/test-puuid', {
        params: { region: 'euw1' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getWinPredict', () => {
    it('should call api.post with participants and live_stats', async () => {
      const mockData = { win: true };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getWinPredict(['p1', 'p2'], { gold: 1000 });

      expect(mockPost).toHaveBeenCalledWith('/win-predict', {
        participants: ['p1', 'p2'],
        live_stats: { gold: 1000 }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getLpHistory', () => {
    it('should call api.get with default queue', async () => {
      const mockData = { lp: 'test' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getLpHistory('test-puuid');

      expect(mockGet).toHaveBeenCalledWith('/lp-history/test-puuid', {
        params: { queue: 'RANKED_SOLO_5x5' }
      });
      expect(result).toEqual(mockData);
    });

    it('should call api.get with explicit queue', async () => {
      const mockData = { lp: 'test2' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getLpHistory('test-puuid', 'RANKED_FLEX_SR');

      expect(mockGet).toHaveBeenCalledWith('/lp-history/test-puuid', {
        params: { queue: 'RANKED_FLEX_SR' }
      });
      expect(result).toEqual(mockData);
    });
  });

  describe('getTeammates', () => {
    it('should call api.get with puuid', async () => {
      const mockData = { teammates: 'test' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getTeammates('test-puuid');

      expect(mockGet).toHaveBeenCalledWith('/teammates/test-puuid');
      expect(result).toEqual(mockData);
    });
  });

  describe('getIngestStatus', () => {
    it('should call api.get without parameters', async () => {
      const mockData = { status: 'running' };
      mockGet.mockResolvedValueOnce({ data: mockData });

      const result = await riot.getIngestStatus();

      expect(mockGet).toHaveBeenCalledWith('/ingest/status');
      expect(result).toEqual(mockData);
    });
  });

  describe('toggleIngest', () => {
    it('should call api.post without parameters', async () => {
      const mockData = { toggled: true };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const result = await riot.toggleIngest();

      expect(mockPost).toHaveBeenCalledWith('/ingest/toggle');
      expect(result).toEqual(mockData);
    });
  });
