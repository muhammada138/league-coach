import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getSummoner } from './riot';

const { mockGet } = vi.hoisted(() => ({
  mockGet: vi.fn()
}));

vi.mock('axios', () => {
  return {
    default: {
      create: vi.fn(() => ({
        get: mockGet,
        post: vi.fn(),
        interceptors: {
          response: { use: vi.fn() }
        }
      }))
    }
  };
});

describe('getSummoner', () => {
  beforeEach(() => {
    mockGet.mockClear();
  });

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
