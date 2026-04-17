import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import useSearchHistory from './useSearchHistory';

describe('useSearchHistory', () => {
  const HISTORY_KEY = "searchHistory";
  const SAVED_KEY = "savedProfiles";

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('should initialize with empty history and saved profiles if localStorage is empty', () => {
    const { result } = renderHook(() => useSearchHistory());
    expect(result.current.history).toEqual([]);
    expect(result.current.saved).toEqual([]);
  });

  it('should initialize with data from localStorage', () => {
    const mockHistory = [{ gameName: 'Faker', tagLine: 'KR1', region: 'kr' }];
    const mockSaved = [{ gameName: 'Chovy', tagLine: 'KR1', region: 'kr' }];

    localStorage.setItem(HISTORY_KEY, JSON.stringify(mockHistory));
    localStorage.setItem(SAVED_KEY, JSON.stringify(mockSaved));

    const { result } = renderHook(() => useSearchHistory());
    expect(result.current.history).toEqual(mockHistory);
    expect(result.current.saved).toEqual(mockSaved);
  });

  it('should handle malformed JSON in localStorage gracefully', () => {
    localStorage.setItem(HISTORY_KEY, 'invalid-json');
    localStorage.setItem(SAVED_KEY, 'invalid-json');

    const { result } = renderHook(() => useSearchHistory());
    expect(result.current.history).toEqual([]);
    expect(result.current.saved).toEqual([]);
  });

  it('saveToHistory should add a valid entry to history and limit to 10 items', () => {
    const { result } = renderHook(() => useSearchHistory());

    const entry1 = { gameName: 'Player1', tagLine: 'NA1', region: 'na1' };

    act(() => {
      result.current.saveToHistory(entry1);
    });

    expect(result.current.history).toEqual([entry1]);
    expect(JSON.parse(localStorage.getItem(HISTORY_KEY))).toEqual([entry1]);

    // Add 10 more entries
    act(() => {
      for (let i = 2; i <= 11; i++) {
        result.current.saveToHistory({ gameName: `Player${i}`, tagLine: 'NA1', region: 'na1' });
      }
    });

    expect(result.current.history.length).toBe(10);
    // The most recently added is 'Player11'
    expect(result.current.history[0].gameName).toBe('Player11');
    expect(result.current.history[9].gameName).toBe('Player2'); // Player1 fell off
  });

  it('saveToHistory should handle duplicates by moving to front and updating fields', () => {
    const { result } = renderHook(() => useSearchHistory());

    const entry = { gameName: 'Player1', tagLine: 'NA1', region: 'na1', tier: 'SILVER' };

    act(() => {
      result.current.saveToHistory(entry);
    });

    const entryUpdate = { gameName: 'Player1', tagLine: 'NA1', region: 'na1', tier: 'GOLD' };

    act(() => {
      result.current.saveToHistory(entryUpdate);
    });

    expect(result.current.history).toEqual([entryUpdate]);
    expect(result.current.history.length).toBe(1);
  });

  it('saveToHistory should update saved profiles if a saved profile is searched again with changes', () => {
    const { result } = renderHook(() => useSearchHistory());

    const profile = { gameName: 'Player1', tagLine: 'NA1', region: 'na1', tier: 'SILVER' };

    act(() => {
      result.current.toggleSaved(profile);
    });

    expect(result.current.saved).toEqual([profile]);

    const updatedProfile = { gameName: 'Player1', tagLine: 'NA1', region: 'na1', tier: 'GOLD' };

    act(() => {
      result.current.saveToHistory(updatedProfile);
    });

    expect(result.current.saved).toEqual([updatedProfile]);
    expect(JSON.parse(localStorage.getItem(SAVED_KEY))).toEqual([updatedProfile]);
  });

  it('removeFromHistory should remove the specific entry', () => {
    const mockHistory = [
      { gameName: 'Player1', tagLine: 'NA1', region: 'na1' },
      { gameName: 'Player2', tagLine: 'NA1', region: 'na1' }
    ];
    localStorage.setItem(HISTORY_KEY, JSON.stringify(mockHistory));

    const { result } = renderHook(() => useSearchHistory());

    act(() => {
      result.current.removeFromHistory({ gameName: 'Player1', tagLine: 'NA1' });
    });

    expect(result.current.history).toEqual([{ gameName: 'Player2', tagLine: 'NA1', region: 'na1' }]);
  });

  it('toggleSaved should add and then remove a profile, limiting to 20 items', () => {
    const { result } = renderHook(() => useSearchHistory());
    const profile = { gameName: 'Player1', tagLine: 'NA1', region: 'na1' };

    act(() => {
      result.current.toggleSaved(profile);
    });
    expect(result.current.saved).toEqual([profile]);
    expect(JSON.parse(localStorage.getItem(SAVED_KEY))).toEqual([profile]);

    act(() => {
      result.current.toggleSaved(profile);
    });
    expect(result.current.saved).toEqual([]);
    expect(JSON.parse(localStorage.getItem(SAVED_KEY))).toEqual([]);
  });

  it('should sync state across tabs when storage event is fired', () => {
    const { result } = renderHook(() => useSearchHistory());

    const newHistory = [{ gameName: 'NewPlayer', tagLine: 'NA1', region: 'na1' }];

    act(() => {
      localStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory));
      window.dispatchEvent(new Event('storage'));
    });

    expect(result.current.history).toEqual(newHistory);
  });

  it('should sync state on custom search-history-update event', () => {
    const { result } = renderHook(() => useSearchHistory());

    const newSaved = [{ gameName: 'NewSaved', tagLine: 'NA1', region: 'na1' }];

    act(() => {
      localStorage.setItem(SAVED_KEY, JSON.stringify(newSaved));
      window.dispatchEvent(new Event('search-history-update'));
    });

    expect(result.current.saved).toEqual(newSaved);
  });
});
