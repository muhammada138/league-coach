import { describe, it, expect, vi, beforeEach } from 'vitest';
import axios from 'axios';
import { getLiveEnrich } from './riot';

// Hoist the mocks to avoid ReferenceError
vi.mock('axios', () => {
  const mockPost = vi.fn();
  const mockGet = vi.fn();
  const mockApi = {
    post: mockPost,
    get: mockGet,
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
    // export them so we can test them
    mockPost,
    mockGet,
  };
});

describe('getLiveEnrich', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should call api.post with correct parameters (default values) and return data', async () => {
    const mockData = { enrichData: 'test' };
    const { mockPost } = await import('axios');
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
    const { mockPost } = await import('axios');
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
