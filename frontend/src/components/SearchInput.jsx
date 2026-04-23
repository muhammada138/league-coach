import { useState, useRef, useMemo } from "react";
import RegionSelector from "./RegionSelector";
import useSearchHistory from "../hooks/useSearchHistory";
import SearchSuggestions from "./SearchSuggestions";

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
  const { history, saved, toggleSaved, removeFromHistory } = useSearchHistory();
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestionTab, setSuggestionTab] = useState("recent"); // "recent" | "saved"
  const [focusedIdx, setFocusedIdx] = useState(-1);
  const wrapperRef = useRef(null);
  const blurTimer = useRef(null);

  const queryParams = gameName.trim().toLowerCase();

  const suggestions = useMemo(() => {
    const list = queryParams ? (() => {
      const seen = new Set();
      const results = [];
      for (const p of saved) {
        if (!p.gameName) continue;
        const key = `${p.gameName}#${p.tagLine}`.toLowerCase();
        if (key.includes(queryParams)) {
          seen.add(key);
          results.push({ ...p, type: 'saved' });
        }
      }
      for (const h of history) {
        const hName = typeof h === 'string' ? h.split('#')[0] : h.gameName;
        const hTag = typeof h === 'string' ? h.split('#')[1] : h.tagLine;
        if (!hName) continue;
        const key = `${hName}#${hTag}`.toLowerCase();
        if (key.includes(queryParams) && !seen.has(key)) {
          results.push({ ...(typeof h === 'string' ? { gameName: hName, tagLine: hTag } : h), type: 'recent' });
        }
      }
      return results;
    })() : (suggestionTab === "saved" ? saved.map(p => ({ ...p, type: 'saved' })) : history.map(h => {
      const n = typeof h === 'string' ? h.split('#')[0] : h.gameName;
      const t = typeof h === 'string' ? h.split('#')[1] : h.tagLine;
      return { ...(typeof h === 'string' ? { gameName: n, tagLine: t } : h), type: 'recent' };
    }));

    return list.map(item => {
      const isSaved = saved.some(p =>
        p.gameName.toLowerCase() === item.gameName.toLowerCase() &&
        p.tagLine.toLowerCase() === item.tagLine.toLowerCase()
      );
      return { ...item, isSaved };
    }).slice(0, 10);
  }, [queryParams, suggestionTab, saved, history]);

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
    <div className={`relative w-full ${navbar ? "max-w-md" : "max-w-2xl"}`} ref={wrapperRef}>
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
          onChange={(newRegion) => {
            setRegion(newRegion);
            localStorage.setItem("lastRegion", newRegion);
          }}
          pill
          compact={navbar}
        />

        <div className="flex-1 flex items-center min-w-0">
          <input
            type="text"
            placeholder={placeholder.split('#')[0]}
            value={gameName}
            onChange={(e) => {
              const val = e.target.value;
              if (val.includes('#')) {
                const [name, ...rest] = val.split('#');
                setGameName(name);
                setTagLine(rest.join('#'));
                setShowSuggestions(true);
              } else {
                setGameName(val);
                setShowSuggestions(true);
              }
            }}
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
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" />
            </svg>
          )}
        </button>
      </form>

      {/* Suggestions Dropdown */}
      {showSuggestions && (suggestions.length > 0 || history.length > 0 || saved.length > 0 || error) && (
        <SearchSuggestions
          error={error}
          queryParams={queryParams}
          suggestionTab={suggestionTab}
          setSuggestionTab={setSuggestionTab}
          suggestions={suggestions}
          applySuggestion={applySuggestion}
          focusedIdx={focusedIdx}
          toggleSaved={toggleSaved}
          removeFromHistory={removeFromHistory}
        />
      )}
    </div>
  );
}
