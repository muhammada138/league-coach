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
    // entry can be an object { gameName, tagLine, region, tier, profileIconId, puuid }
    if (!entry || !entry.gameName || !entry.tagLine || !entry.region) return;

    const entryObj = {
      gameName: entry.gameName.trim(),
      tagLine: entry.tagLine.trim(),
      region: entry.region,
      tier: entry.tier,
      profileIconId: entry.profileIconId,
      puuid: entry.puuid
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

  const removeFromHistory = useCallback((profile) => {
    if (!profile) return;
    setHistory((prev) => {
      const next = prev.filter((h) => {
        const hName = typeof h === 'string' ? h.split('#')[0] : h.gameName;
        const hTag = typeof h === 'string' ? h.split('#')[1] : h.tagLine;
        return (
          hName.toLowerCase() !== profile.gameName.toLowerCase() ||
          hTag.toLowerCase() !== profile.tagLine.toLowerCase()
        );
      });
      localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
      window.dispatchEvent(new Event("search-history-update"));
      return next;
    });
  }, []);

  const toggleSaved = useCallback((profile) => {
    setSaved((prev) => {
      // Find by gameName + tagLine since puuid might be missing in history entries
      const exists = prev.find((p) =>
        p.gameName.toLowerCase() === profile.gameName.toLowerCase() &&
        p.tagLine.toLowerCase() === profile.tagLine.toLowerCase()
      );

      let next;
      if (exists) {
        next = prev.filter((p) =>
          p.gameName.toLowerCase() !== profile.gameName.toLowerCase() ||
          p.tagLine.toLowerCase() !== profile.tagLine.toLowerCase()
        );
      } else {
        // Ensure we preserve the region when saving
        const toSave = {
          ...profile,
          region: profile.region || localStorage.getItem("lastRegion") || "na1"
        };
        next = [toSave, ...prev].slice(0, 20);
      }
      localStorage.setItem(SAVED_KEY, JSON.stringify(next));
      window.dispatchEvent(new Event("search-history-update"));
      return next;
    });
  }, []);

  return { history, saved, saveToHistory, toggleSaved, removeFromHistory };
}
