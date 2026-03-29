import { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import ThemeToggle from "./ThemeToggle";
import { getSummoner } from "../api/riot";

// ── localStorage helpers ─────────────────────────────────────────────────────
export const SAVED_KEY = "savedProfiles";

export function readSaved() {
  try {
    return JSON.parse(localStorage.getItem(SAVED_KEY) ?? "[]");
  } catch {
    return [];
  }
}

export function writeSaved(profiles) {
  localStorage.setItem(SAVED_KEY, JSON.stringify(profiles));
}

const HISTORY_KEY = "searchHistory";

function readSearchHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) ?? "[]");
  } catch {
    return [];
  }
}

function saveSearchHistory(entry) {
  const history = readSearchHistory().filter(
    (h) => h.toLowerCase() !== entry.toLowerCase()
  );
  localStorage.setItem(HISTORY_KEY, JSON.stringify([entry, ...history].slice(0, 8)));
}

// "Faker #KR1", "Faker#KR1" → { gameName, tagLine } or null
function parseRiotId(raw) {
  const match = raw.trim().match(/^(.+?)\s*#\s*(.+)$/);
  if (!match) return null;
  const gameName = match[1].trim();
  const tagLine = match[2].trim();
  return gameName && tagLine ? { gameName, tagLine } : null;
}

// ── Profile avatar (icon image or letter fallback) ───────────────────────────
function ProfileAvatar({ profile }) {
  const [failed, setFailed] = useState(false);
  if (!profile.profileIconId || failed) {
    return (
      <span className="w-6 h-6 rounded-md bg-[#c89b3c]/10 border border-[#c89b3c]/20 text-[#c89b3c] text-[10px] font-black flex items-center justify-center flex-shrink-0">
        {profile.gameName.charAt(0).toUpperCase()}
      </span>
    );
  }
  return (
    <img
      src={`https://ddragon.leagueoflegends.com/cdn/14.24.1/img/profileicon/${profile.profileIconId}.png`}
      alt=""
      className="w-6 h-6 rounded-md object-cover flex-shrink-0"
      onError={() => setFailed(true)}
    />
  );
}

// ── Navbar search bar ────────────────────────────────────────────────────────
function NavSearch() {
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [history, setHistory] = useState([]);
  const inputRef = useRef(null);
  const blurTimer = useRef(null);
  const navigate = useNavigate();

  const expanded = focused || query.length > 0;
  const showHistory = focused && !error;
  const filteredHistory = query.length === 0
    ? history
    : history.filter((h) => h.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    if (focused) setHistory(readSearchHistory());
  }, [focused]);

  const handleSubmit = async (e, prefill) => {
    e?.preventDefault();
    const raw = prefill ?? query;
    const parsed = parseRiotId(raw);
    if (!parsed) {
      setError("Format: Name#TAG");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const data = await getSummoner(parsed.gameName, parsed.tagLine);
      saveSearchHistory(raw);
      setQuery("");
      inputRef.current?.blur();
      navigate(
        `/player/${encodeURIComponent(data.gameName)}/${encodeURIComponent(parsed.tagLine)}`,
        { state: { puuid: data.puuid } }
      );
    } catch (err) {
      setError(err.response?.status === 404 ? "Summoner not found" : "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  const handleHistoryClick = (item) => {
    setQuery(item);
    handleSubmit(null, item);
  };

  const handleBlur = () => {
    blurTimer.current = setTimeout(() => setFocused(false), 150);
  };
  const handleFocus = () => {
    clearTimeout(blurTimer.current);
    setFocused(true);
  };

  useEffect(() => () => clearTimeout(blurTimer.current), []);

  return (
    <form onSubmit={handleSubmit} className="relative">
      <div
        className={`flex items-center h-8 rounded-lg border overflow-hidden transition-all duration-200
          ${error
            ? "border-red-400 dark:border-red-500/60"
            : expanded
            ? "border-[#c89b3c]/60 dark:border-[#c89b3c]/50"
            : "border-slate-200 dark:border-white/10"
          }
          bg-slate-50 dark:bg-white/[0.04]
          ${expanded ? "w-44 sm:w-52" : "w-8 sm:w-40"}`}
      >
        <button
          type="submit"
          tabIndex={-1}
          disabled={loading}
          onClick={(e) => { if (!expanded) { e.preventDefault(); inputRef.current?.focus(); } }}
          className="flex-shrink-0 w-8 h-8 flex items-center justify-center
            text-slate-400 dark:text-white/30 hover:text-[#c89b3c] transition-colors"
        >
          {loading ? (
            <span className="w-3.5 h-3.5 rounded-full border-[1.5px] border-slate-300 dark:border-white/20 border-t-[#c89b3c] animate-spin block" />
          ) : (
            <svg className="w-3.5 h-3.5" viewBox="0 0 16 16" fill="none">
              <circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" strokeWidth="1.5" />
              <path d="M10.5 10.5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          )}
        </button>

        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setError(""); }}
          onFocus={handleFocus}
          onBlur={handleBlur}
          onKeyDown={(e) => e.key === "Escape" && inputRef.current?.blur()}
          placeholder="Name#TAG"
          className={`py-1.5 pr-2.5 bg-transparent text-xs
            text-slate-800 dark:text-white
            placeholder-slate-400 dark:placeholder-white/25
            focus:outline-none transition-all duration-200
            ${expanded ? "flex-1" : "w-0 sm:flex-1"}`}
        />
      </div>

      {/* Search history dropdown */}
      {showHistory && filteredHistory.length > 0 && (
        <div className="absolute top-full left-0 mt-1.5 w-52 z-50
          bg-white dark:bg-[#0b0f1a]
          border border-slate-200 dark:border-white/[0.08]
          rounded-xl shadow-xl dark:shadow-black/60
          overflow-hidden animate-fadeIn">
          <div className="px-3 py-2 border-b border-slate-100 dark:border-white/[0.06]">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">
              {query.length === 0 ? "Recent" : "Suggestions"}
            </span>
          </div>
          <div className="py-1">
            {filteredHistory.map((item) => {
              const hashIdx = item.indexOf("#");
              const name = hashIdx > -1 ? item.slice(0, hashIdx) : item;
              const tag = hashIdx > -1 ? item.slice(hashIdx + 1) : "";
              return (
                <button
                  key={item}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => handleHistoryClick(item)}
                  className="w-full text-left px-3 py-2 text-xs
                    hover:bg-slate-50 dark:hover:bg-white/[0.04]
                    text-slate-700 dark:text-white/70 transition-colors flex items-center gap-1.5"
                >
                  <svg className="w-3 h-3 text-slate-300 dark:text-white/20 flex-shrink-0" viewBox="0 0 12 12" fill="none">
                    <path d="M6 1v5l3 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                    <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.3"/>
                  </svg>
                  <span className="truncate">
                    {name}
                    {tag && <span className="text-slate-400 dark:text-white/30">#{tag}</span>}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Error tooltip */}
      {error && (
        <div className="absolute top-full mt-1.5 left-0 z-50
          bg-white dark:bg-[#0d1117]
          border border-red-200 dark:border-red-500/30
          rounded-lg px-3 py-1.5 shadow-lg
          text-xs text-red-500 dark:text-red-400 whitespace-nowrap">
          {error}
        </div>
      )}
    </form>
  );
}

// ── Saved profiles dropdown ──────────────────────────────────────────────────
function SavedDropdown() {
  const [open, setOpen] = useState(false);
  const [profiles, setProfiles] = useState([]);
  const [loadingId, setLoadingId] = useState(null);
  const wrapperRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (open) setProfiles(readSaved());
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (e) => {
      if (!wrapperRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  const handleNavigate = async (p) => {
    setLoadingId(p.puuid);
    try {
      const data = await getSummoner(p.gameName, p.tagLine);
      setOpen(false);
      navigate(
        `/player/${encodeURIComponent(data.gameName)}/${encodeURIComponent(p.tagLine)}`,
        { state: { puuid: data.puuid } }
      );
    } catch {
      setOpen(false);
      navigate(
        `/player/${encodeURIComponent(p.gameName)}/${encodeURIComponent(p.tagLine)}`,
        { state: { puuid: p.puuid } }
      );
    } finally {
      setLoadingId(null);
    }
  };

  const handleRemove = (e, puuid) => {
    e.stopPropagation();
    const updated = profiles.filter((p) => p.puuid !== puuid);
    writeSaved(updated);
    setProfiles(updated);
  };

  return (
    <div ref={wrapperRef} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 h-8 px-2.5 rounded-lg border text-xs font-semibold transition-colors duration-150
          ${open
            ? "bg-[#c89b3c]/10 border-[#c89b3c]/40 text-[#c89b3c]"
            : "bg-slate-50 dark:bg-white/[0.04] border-slate-200 dark:border-white/10 text-slate-500 dark:text-white/40 hover:text-[#c89b3c] hover:border-[#c89b3c]/30"
          }`}
      >
        <svg className="w-3.5 h-3.5 flex-shrink-0" viewBox="0 0 16 16" fill="currentColor">
          <path d="M8 1.5l1.75 3.55 3.92.57-2.84 2.77.67 3.9L8 10.35l-3.5 1.84.67-3.9L2.33 5.62l3.92-.57L8 1.5z" />
        </svg>
        <span className="hidden sm:inline">Saved</span>
      </button>

      {open && (
        <div className="absolute top-full right-0 mt-2 w-60 z-50
          bg-white dark:bg-[#0b0f1a]
          border border-slate-200 dark:border-white/[0.08]
          rounded-xl shadow-xl dark:shadow-black/60
          overflow-hidden animate-fadeIn">

          <div className="px-4 py-2.5 border-b border-slate-100 dark:border-white/[0.06]">
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400 dark:text-white/25">
              Saved Profiles
            </span>
          </div>

          {profiles.length === 0 ? (
            <p className="px-4 py-5 text-xs text-slate-400 dark:text-white/25 text-center">
              No saved profiles yet
            </p>
          ) : (
            <div className="py-1 max-h-64 overflow-y-auto">
              {profiles.map((p) => (
                <div
                  key={p.puuid}
                  onClick={() => handleNavigate(p)}
                  className="group flex items-center gap-2.5 px-3.5 py-2.5 cursor-pointer
                    hover:bg-slate-50 dark:hover:bg-white/[0.04] transition-colors"
                >
                  {loadingId === p.puuid ? (
                    <span className="w-6 h-6 flex-shrink-0 flex items-center justify-center">
                      <span className="w-3.5 h-3.5 rounded-full border-[1.5px] border-slate-300 dark:border-white/20 border-t-[#c89b3c] animate-spin block" />
                    </span>
                  ) : (
                    <ProfileAvatar profile={p} />
                  )}

                  <span className="flex-1 min-w-0 text-xs font-semibold text-slate-700 dark:text-white/70 truncate">
                    {p.gameName}
                    <span className="text-slate-400 dark:text-white/30 font-normal">#{p.tagLine}</span>
                  </span>

                  <button
                    onClick={(e) => handleRemove(e, p.puuid)}
                    className="flex-shrink-0 w-5 h-5 rounded flex items-center justify-center
                      text-slate-300 dark:text-white/20
                      hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10
                      opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                      <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                    </svg>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Navbar ───────────────────────────────────────────────────────────────────
export default function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50
      bg-slate-50/80 dark:bg-[#05080f]/80
      backdrop-blur-md
      border-b border-slate-200/80 dark:border-white/5
      transition-colors duration-300">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between gap-3">
        <Link
          to="/"
          className="text-sm font-bold tracking-widest uppercase text-[#c89b3c] hover:text-[#d4a94a] transition-colors duration-200 flex-shrink-0"
        >
          Rift IQ
        </Link>

        <div className="flex items-center gap-2 ml-auto">
          <NavSearch />
          <SavedDropdown />
          <ThemeToggle />
        </div>
      </div>
    </nav>
  );
}
