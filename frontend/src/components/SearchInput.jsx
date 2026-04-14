import { useState, useRef, useEffect } from "react";
import RegionSelector from "./RegionSelector";
import useSearchHistory from "../hooks/useSearchHistory";

export default function SearchInput({ 
  region, setRegion, 
  gameName, setGameName, 
  tagLine, setTagLine, 
  onSubmit, 
  loading = false,
  error = "",
  placeholder = "Name#TAG",
  navbar = false 
}) {
  const { history, saved } = useSearchHistory();
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionTab, setSuggestionTab] = useState("recent"); // "recent" | "saved"
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const blurTimer = useRef(null);
  const containerRef = useRef(null);

  const queryParams = gameName.trim().toLowerCase();
  
  // Combine saved and history for suggestions
  const suggestions = (() => {
    // If user is typing, show all matches from both
    if (queryParams) {
      const seen = new Set();
      const results = [];
      
      // 1. Check Saved
      for (const p of saved) {
        if (!p.gameName) continue;
        const key = `${p.gameName}#${p.tagLine}`.toLowerCase();
        if (key.includes(queryParams)) {
          seen.add(key);
          results.push({ ...p, type: 'saved' });
        }
      }
      
      // 2. Check Recent
      for (const h of history) {
        const hName = typeof h === 'string' ? h.split('#')[0] : h.gameName;
        const hTag = typeof h === 'string' ? h.split('#')[1] : h.tagLine;
        if (!hName) continue;
        const key = `${hName}#${hTag}`.toLowerCase();
        if (key.includes(queryParams) && !seen.has(key)) {
          results.push({ ...(typeof h === 'string' ? { gameName: hName, tagLine: hTag } : h), type: 'recent' });
        }
      }
      return results.slice(0, 8);
    }

    // If NOT typing, show selected tab
    if (suggestionTab === "saved") {
      return saved.map(p => ({ ...p, type: 'saved' })).slice(0, 10);
    } else {
      return history
        .map(h => {
          const n = typeof h === 'string' ? h.split('#')[0] : h.gameName;
          const t = typeof h === 'string' ? h.split('#')[1] : h.tagLine;
          if (!n) return null;
          // Mark as saved if it exists in saved list to show star correctly
          const isSaved = saved.some(p => 
            p.gameName.toLowerCase() === n.toLowerCase() && 
            p.tagLine.toLowerCase() === t.toLowerCase()
          );
          return { 
            ...(typeof h === 'string' ? { gameName: n, tagLine: t } : h), 
            type: isSaved ? 'saved' : 'recent' 
          };
        })
        .filter(Boolean)
        .slice(0, 10);
    }
  })();

  const applySuggestion = (s) => {
    setGameName(s.gameName);
    setTagLine(s.tagLine || "");
    if (s.region) {
      setRegion(s.region);
      localStorage.setItem("lastRegion", s.region);
    }
    setShowSuggestions(false);
    
    if (typeof onSubmit === 'function') {
      onSubmit(s);
    }
  };

  const handleKeyDown = (e) => {
    if (!showSuggestions || suggestions.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setFocusedIdx((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setFocusedIdx((i) => Math.max(i - 1, -1));
    } else if (e.key === "Enter" && focusedIdx >= 0) {
      e.preventDefault();
      applySuggestion(suggestions[focusedIdx]);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <div className={`relative w-full ${navbar ? "max-w-md" : "max-w-2xl"}`} ref={containerRef}>
      <form 
        onSubmit={handleFormSubmit}
        className={`group flex items-stretch transition-all duration-300 relative z-10
          ${navbar ? "h-9" : "h-14"}
          bg-white dark:bg-[#0d111a]/80 backdrop-blur-md
          border ${error ? "border-red-500/50" : "border-slate-200 dark:border-white/[0.08]"}
          focus-within:border-[#c89b3c]/60 dark:focus-within:border-[#c89b3c]/40
          rounded-xl shadow-lg shadow-black/5 dark:shadow-black/40
          ${navbar ? "ring-0" : "focus-within:ring-4 focus-within:ring-[#c89b3c]/5"}`}
      >
        <RegionSelector 
          value={region} 
          onChange={setRegion} 
          pill 
          compact={navbar} 
        />

        <div className="flex-1 flex items-center min-w-0">
          <input
            type="text"
            placeholder={placeholder.split('#')[0]}
            value={gameName}
            onChange={(e) => { setGameName(e.target.value); setShowSuggestions(true); }}
            onFocus={() => { clearTimeout(blurTimer.current); setShowSuggestions(true); }}
            onBlur={() => { blurTimer.current = setTimeout(() => setShowSuggestions(false), 200); }}
            onKeyDown={handleKeyDown}
            className={`w-full bg-transparent px-3 outline-none 
              text-slate-900 dark:text-white/90
              placeholder-slate-400 dark:placeholder-white/20
              ${navbar ? "text-xs" : "text-base font-medium"}`}
          />
          <span className="text-slate-300 dark:text-white/10 font-bold px-1 select-none">#</span>
          <input
            type="text"
            placeholder={placeholder.split('#')[1] || "TAG"}
            value={tagLine}
            onChange={(e) => setTagLine(e.target.value.toUpperCase())}
            onFocus={() => { clearTimeout(blurTimer.current); setShowSuggestions(true); }}
            onBlur={() => { blurTimer.current = setTimeout(() => setShowSuggestions(false), 200); }}
            className={`w-16 sm:w-20 bg-transparent px-2 outline-none
              text-[#c89b3c] font-black
              placeholder-slate-400 dark:placeholder-white/20
              ${navbar ? "text-xs" : "text-sm"}`}
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className={`flex items-center justify-center transition-all
            ${navbar ? "w-10 text-slate-400 hover:text-[#c89b3c]" : "px-6 text-[#c89b3c] hover:bg-[#c89b3c]/5"}
            disabled:opacity-50`}
        >
          {loading ? (
            <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
          ) : (
            <svg className={navbar ? "w-4 h-4" : "w-5 h-5"} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
            </svg>
          )}
        </button>
      </form>

      {/* Suggestions Dropdown */}
      {showSuggestions && (suggestions.length > 0 || history.length > 0 || saved.length > 0 || error) && (
        <div className="absolute top-full left-0 right-0 mt-2 z-50
          bg-white dark:bg-[#0d111a]
          border border-slate-200 dark:border-white/[0.08]
          rounded-2xl shadow-2xl shadow-black/60
          overflow-hidden animate-fadeIn backdrop-blur-xl"
        >
          {error && (
            <div className="px-4 py-3 bg-red-500/5 border-b border-red-500/10 text-red-500 text-xs font-semibold flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
              {error}
            </div>
          )}
          
          {/* Tabs UI */}
          {!queryParams && (
            <div className="flex border-b border-slate-100 dark:border-white/[0.04]">
              {["recent", "saved"].map((t) => (
                <button
                  key={t}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => setSuggestionTab(t)}
                  className={`flex-1 py-2.5 text-[10px] font-black uppercase tracking-[0.15em] transition-colors
                    ${suggestionTab === t 
                      ? "text-[#c89b3c] bg-[#c89b3c]/5 border-b border-[#c89b3c]" 
                      : "text-slate-400 dark:text-white/20 hover:text-slate-600 dark:hover:text-white/40"}`}
                >
                  {t === "recent" ? "Recent" : "Favorites"}
                </button>
              ))}
            </div>
          )}

          {queryParams && (
            <div className="px-4 py-2 border-b border-slate-100 dark:border-white/[0.04]">
              <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/20">
                Matches
              </span>
            </div>
          )}

          <div className="max-h-[300px] overflow-y-auto no-scrollbar">
            {suggestions.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <p className="text-xs text-slate-400 dark:text-white/10 italic">
                  No {suggestionTab === "recent" ? "recent searches" : "favorite profiles"} found
                </p>
              </div>
            ) : (
              suggestions.map((s, i) => (
                <button
                  key={`${s.gameName}#${s.tagLine}-${i}`}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => applySuggestion(s)}
                  className={`w-full text-left px-4 py-3 flex items-center gap-3 transition-colors
                    ${i === focusedIdx 
                      ? "bg-[#c89b3c]/10 text-[#c89b3c]" 
                      : "hover:bg-slate-50 dark:hover:bg-white/[0.04] text-slate-700 dark:text-white/70"}`}
                >
                  {s.type === 'saved' ? (
                    <svg className="w-3.5 h-3.5 text-[#c89b3c]" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M8 1.5l1.75 3.55 3.92.57-2.84 2.77.67 3.9L8 10.35l-3.5 1.84.67-3.9L2.33 5.62l3.92-.57L8 1.5z" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5 text-slate-300 dark:text-white/10" viewBox="0 0 12 12" fill="none">
                      <path d="M6 1v5l3 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/><circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.3"/>
                    </svg>
                  )}
                  <div className="flex flex-col min-w-0">
                    <span className="text-sm font-semibold truncate leading-tight">
                      {s.gameName}
                      <span className="text-slate-400 dark:text-white/20 font-medium">#{s.tagLine}</span>
                    </span>
                    {s.region && (
                      <span className="text-[9px] font-bold uppercase tracking-tighter text-[#c89b3c]/50">
                        {s.region}
                      </span>
                    )}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
