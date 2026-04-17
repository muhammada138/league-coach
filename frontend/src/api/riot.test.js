import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getLiveEnrich, getSummoner, getProfile, askCoach } from './riot';

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

  describe('askCoach', () => {
    it('should call api.post with correct endpoint and parameters, and return data', async () => {
      const mockData = { answer: 'Buy control wards' };
      mockPost.mockResolvedValueOnce({ data: mockData });

      const question = 'How to win?';
      const context = 'Playing Jungle';
      const history = ['Hello', 'Hi'];

      const result = await askCoach(question, context, history);

      expect(mockPost).toHaveBeenCalledWith('/ask', {
        question,
        context,
        history,
      });
      expect(result).toEqual(mockData);
    });

    it('should handle API errors correctly', async () => {
      const mockError = new Error('API Timeout');
      mockPost.mockRejectedValueOnce(mockError);

      const question = 'How to win?';
      const context = 'Playing Jungle';
      const history = ['Hello', 'Hi'];

      await expect(askCoach(question, context, history)).rejects.toThrow('API Timeout');
    });
  });
});
