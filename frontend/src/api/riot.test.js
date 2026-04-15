import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';

// Mock axios BEFORE importing the file that uses it
vi.mock('axios', () => {
  const mockApi = {
    get: vi.fn(),
    post: vi.fn(),
    interceptors: {
      response: {
        use: vi.fn(),
      },
    },
  };
  return {
    default: {
      create: vi.fn(() => mockApi),
    },
  };
});

import { getProfile } from './riot';

describe('riot API wrappers', () => {
  let mockApi;

  beforeEach(() => {
    vi.clearAllMocks();
    mockApi = axios.create();
  });

  describe('getProfile', () => {
    it('fetches profile data successfully', async () => {
      const mockData = { tier: 'GOLD', rank: 'I' };
      mockApi.get.mockResolvedValueOnce({ data: mockData });

      const result = await getProfile('test-puuid', 'euw1');

      expect(mockApi.get).toHaveBeenCalledWith('/profile/test-puuid', { params: { region: 'euw1' } });
      expect(result).toEqual(mockData);
    });

    it('uses default region na1 if not provided', async () => {
      const mockData = { tier: 'SILVER', rank: 'II' };
      mockApi.get.mockResolvedValueOnce({ data: mockData });

      const result = await getProfile('test-puuid');

      expect(mockApi.get).toHaveBeenCalledWith('/profile/test-puuid', { params: { region: 'na1' } });
      expect(result).toEqual(mockData);
    });

    it('throws an error if the API request fails', async () => {
      const mockError = new Error('Network Error');
      mockApi.get.mockRejectedValueOnce(mockError);

      await expect(getProfile('test-puuid')).rejects.toThrow('Network Error');
    });
  });
});
