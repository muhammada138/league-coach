const TIER_COLORS = {
  IRON: "text-slate-400",
  BRONZE: "text-orange-700",
  SILVER: "text-slate-300",
  GOLD: "text-yellow-500",
  PLATINUM: "text-emerald-400",
  EMERALD: "text-emerald-500",
  DIAMOND: "text-blue-400",
  MASTER: "text-purple-400",
  GRANDMASTER: "text-red-400",
  CHALLENGER: "text-sky-300",
  UNRANKED: "text-slate-400",
};

export default function SearchSuggestions({
  error,
  queryParams,
  suggestionTab,
  setSuggestionTab,
  suggestions,
  applySuggestion,
  focusedIdx,
  toggleSaved,
  removeFromHistory,
}) {
  return (
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
            <div
              key={`${s.gameName}#${s.tagLine}-${i}`}
              onClick={() => applySuggestion(s)}
              className={`group w-full text-left px-4 py-3 flex items-center gap-3 transition-colors cursor-pointer
                ${i === focusedIdx
                  ? "bg-[#c89b3c]/10 text-[#c89b3c]"
                  : "hover:bg-slate-50 dark:hover:bg-white/[0.04] text-slate-700 dark:text-white/70"}`}
            >
              <div className="flex-shrink-0">
                {s.type === 'saved' ? (
                  <svg className="w-3.5 h-3.5 text-[#c89b3c]" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 1.5l1.75 3.55 3.92.57-2.84 2.77.67 3.9L8 10.35l-3.5 1.84.67-3.9L2.33 5.62l3.92-.57L8 1.5z" />
                  </svg>
                ) : (
                  <svg className="w-3.5 h-3.5 text-slate-300 dark:text-white/10" viewBox="0 0 12 12" fill="none">
                    <path d="M6 1v5l3 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" /><circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.3" />
                  </svg>
                )}
              </div>
              <div className="flex-1 min-w-0 flex flex-col">
                <span className="text-sm font-semibold truncate leading-tight">
                  {s.gameName}
                  <span className="text-slate-400 dark:text-white/20 font-medium">#{s.tagLine}</span>
                </span>
                <div className="flex items-center gap-1.5 mt-0.5">
                  {s.region && (
                    <span className="text-[9px] font-bold uppercase tracking-tighter text-[#c89b3c]/50">
                      {s.region}
                    </span>
                  )}
                  {s.tier && s.tier !== "UNRANKED" && (
                    <>
                      <span className="w-0.5 h-0.5 rounded-full bg-slate-300 dark:bg-white/20" />
                      <span className={`text-[9px] font-bold uppercase tracking-wide ${TIER_COLORS[s.tier] || "text-slate-400"}`}>
                        {["MASTER", "GRANDMASTER", "CHALLENGER"].includes(s.tier)
                          ? `${s.tier} ${s.lp ?? 0} LP`
                          : `${s.tier} ${s.division ?? ""}`}
                      </span>
                    </>
                  )}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all duration-200">
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggleSaved(s);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      e.stopPropagation();
                      toggleSaved(s);
                    }
                  }}
                  className={`w-7 h-7 rounded-lg flex items-center justify-center transition-all focus:outline-none focus:ring-1 focus:ring-[#c89b3c]/50
                    ${s.isSaved
                      ? "bg-[#c89b3c]/10 text-[#c89b3c] shadow-sm shadow-[#c89b3c]/5"
                      : "text-slate-400 dark:text-white/20 hover:text-[#c89b3c] hover:bg-[#c89b3c]/10"}`}
                  title={s.isSaved ? "Remove Favorite" : "Favorite Profile"}
                >
                  <svg className={`w-3.5 h-3.5 ${s.isSaved ? "fill-current" : ""}`} viewBox="0 0 16 16" fill="currentColor">
                    <path d="M8 1.5l1.75 3.55 3.92.57-2.84 2.77.67 3.9L8 10.35l-3.5 1.84.67-3.9L2.33 5.62l3.92-.57L8 1.5z" />
                  </svg>
                </button>
                <button
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (s.type === 'saved') toggleSaved(s);
                    else removeFromHistory(s);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      e.stopPropagation();
                      if (s.type === 'saved') toggleSaved(s);
                      else removeFromHistory(s);
                    }
                  }}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-red-500/30 hover:text-red-500 hover:bg-red-500/10 transition-all focus:outline-none focus:ring-1 focus:ring-red-500/50"
                  title={s.type === 'saved' ? "Remove Favorite" : "Remove from Recent"}
                >
                  <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.8">
                    <path d="M9 3l-6 6M3 3l6 6" strokeLinecap="round" />
                  </svg>
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
