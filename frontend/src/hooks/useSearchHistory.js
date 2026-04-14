import { useState, useEffect, useCallback } from "react";

const HISTORY_KEY = "searchHistory";
const SAVED_KEY = "savedProfiles";

export default function useSearchHistory() {
  const [history, setHistory] = useState(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });

  const [saved, setSaved] = useState(() => {
    try {
      const parsed = JSON.parse(localStorage.getItem(SAVED_KEY) ?? "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  });

  // Sync state with localStorage changes from other tabs/components
  useEffect(() => {
    const handleStorage = () => {
      try {
        setHistory(JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]"));
        setSaved(JSON.parse(localStorage.getItem(SAVED_KEY) ?? "[]"));
      } catch (e) {
        console.error("Failed to sync search history:", e);
      }
    };

    window.addEventListener("storage", handleStorage);
    // Custom event to handle same-window but inter-component updates
    window.addEventListener("search-history-update", handleStorage);

    return () => {
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("search-history-update", handleStorage);
    };
  }, []);

  const saveToHistory = useCallback((entry) => {
    // entry can be an object { gameName, tagLine, region }
    if (!entry || !entry.gameName || !entry.tagLine || !entry.region) return;
    
    const entryObj = {
      gameName: entry.gameName.trim(),
      tagLine: entry.tagLine.trim(),
      region: entry.region
    };

    setHistory((prev) => {
      // Filter out duplicates by comparing name#tag
      const filtered = prev.filter((h) => {
        const hName = typeof h === 'string' ? h.split('#')[0] : h.gameName;
        const hTag = typeof h === 'string' ? h.split('#')[1] : h.tagLine;
        return (
          hName.toLowerCase() !== entryObj.gameName.toLowerCase() ||
          hTag.toLowerCase() !== entryObj.tagLine.toLowerCase()
        );
      });
      
      const next = [entryObj, ...filtered].slice(0, 10);
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
      window.dispatchEvent(new Event("search-history-update"));
      return next;
    });
  }, []);

  const toggleSaved = useCallback((profile) => {
    setSaved((prev) => {
      const exists = prev.find((p) => p.puuid === profile.puuid);
      let next;
      if (exists) {
        next = prev.filter((p) => p.puuid !== profile.puuid);
      } else {
        next = [profile, ...prev].slice(0, 20);
      }
      localStorage.setItem(SAVED_KEY, JSON.stringify(next));
      window.dispatchEvent(new Event("search-history-update"));
      return next;
    });
  }, []);

  return { history, saved, saveToHistory, toggleSaved };
}
