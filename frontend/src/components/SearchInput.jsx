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
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const blurTimer = useRef(null);
  const containerRef = useRef(null);

  const queryParams = gameName.trim().toLowerCase();
  
  // Combine saved and history for suggestions
  const suggestions = (() => {
    const seen = new Set();
    const results = [];
    
    // 1. Saved Profiles
    for (const p of saved) {
      if (!p.gameName) continue;
      const key = `${p.gameName}#${p.tagLine}`.toLowerCase();
      if (!queryParams || key.includes(queryParams)) {
        seen.add(key);
        results.push({ ...p, type: 'saved' });
      }
    }
    
    // 2. Recent History
    for (const h of history) {
      if (typeof h !== 'string' || !h.includes('#')) continue;
      const key = h.toLowerCase();
      if ((!queryParams || key.includes(queryParams)) && !seen.has(key)) {
        const [n, t] = h.split('#');
        results.push({ gameName: n, tagLine: t, type: 'recent' });
      }
    }
    
    return results.slice(0, 8);
  })();

  const applySuggestion = (s) => {
    setGameName(s.gameName);
    setTagLine(s.tagLine || "");
    if (s.region) setRegion(s.region);
    setShowSuggestions(false);
    
    // If it's a direct selection, maybe auto-submit? 
    // For now, let's just fill the form as per DeepLol.
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

  const clearAndSubmit = (e) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <div className={`relative w-full ${navbar ? "max-w-md" : "max-w-2xl"}`} ref={containerRef}>
      <form 
        onSubmit={clearAndSubmit}
        className={`group flex items-stretch transition-all duration-300 relative z-10
          ${navbar ? "h-9" : "h-14"}
          bg-white dark:bg-[#0d111a]/80 backdrop-blur-md
          border ${error ? "border-red-500/50" : "border-slate-200 dark:border-white/[0.08]"}
          focus-within:border-[#c89b3c]/60 dark:focus-within:border-[#c89b3c]/40
          rounded-xl shadow-lg shadow-black/5 dark:shadow-black/40
          ${navbar ? "ring-0" : "focus-within:ring-4 focus-within:ring-[#c89b3c]/5"}`}
      >
        {/* Region Pill */}
        <RegionSelector 
          value={region} 
          onChange={setRegion} 
          pill 
          compact={navbar} 
        />

        {/* Name Input */}
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

        {/* Search Icon / Button */}
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
      {showSuggestions && (suggestions.length > 0 || error) && (
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
          
          <div className="px-4 py-2 border-b border-slate-100 dark:border-white/[0.04]">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/20">
              {queryParams ? "Matching Summoners" : "Recent Searches"}
            </span>
          </div>

          <div className="max-h-[300px] overflow-y-auto no-scrollbar">
            {suggestions.map((s, i) => (
              <button
                key={`${s.gameName}#${s.tagLine}-${i}`}
                type="button"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => applySuggestion(s)}
                className={`w-full text-left px-4 py-3.5 flex items-center gap-3 transition-colors
                  ${i === focusedIdx 
                    ? "bg-[#c89b3c]/10 text-[#c89b3c]" 
                    : "hover:bg-slate-50 dark:hover:bg-white/[0.04] text-slate-700 dark:text-white/70"}`}
              >
                {s.type === 'saved' ? (
                  <svg className="w-4 h-4 text-[#c89b3c]/60" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 1.5l1.75 3.55 3.92.57-2.84 2.77.67 3.9L8 10.35l-3.5 1.84.67-3.9L2.33 5.62l3.92-.57L8 1.5z" />
                  </svg>
                ) : (
                  <svg className="w-4 h-4 text-slate-300 dark:text-white/10" viewBox="0 0 12 12" fill="none">
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
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
